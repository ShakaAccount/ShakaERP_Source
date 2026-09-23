import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from .category_view import (
    CATEGORY_VIEW, CATEGORY_MEMBER_VIEW, refresh_writable_view,
)

_logger = logging.getLogger(__name__)


class RaesMdCategory(models.Model):
    _name = 'raes.md.category'
    _table = 'raes_md_category'
    _auto = False
    _log_access = False
    _rec_name = 'title'
    _description = 'MD Category (md.category)'

    code = fields.Char(size=10)
    title = fields.Char(required=True)
    english_title = fields.Char()

    parent_id = fields.Many2one('raes.md.category', 'Parent Category',
                                ondelete='restrict')
    root_id = fields.Many2one('raes.md.category', 'Root Category',
                              ondelete='restrict')

    reserved_attibute1 = fields.Char()
    reserved_attibute2 = fields.Char()
    reserved_attibute3 = fields.Char()

    creator_user_id = fields.Integer(default=lambda self: self.env.uid,
                                     required=True)
    creation_date = fields.Datetime(default=fields.Datetime.now,
                                    required=True)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()

    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company,
                                 required=True)
    entity_id = fields.Many2one('raes.md.entity', 'Entity', required=True,
                                ondelete='cascade')

    is_node_only = fields.Boolean()
    is_user_defined = fields.Boolean()

    member_ids = fields.One2many('raes.md.category.member', 'category_id',
                                 string='Members')

    def init(self):
        try:
            refresh_writable_view(self.env, *CATEGORY_VIEW)
        except Exception:
            _logger.exception("Could not (re)build view raes_md_category")
            raise

    @api.constrains('parent_id', 'entity_id')
    def _check_same_entity_as_root(self):
        """A node must share its tree root's entity.

        The legacy ``md.category_same_entity`` trigger already enforces
        this with a recursive ancestor walk, but it raises a raw
        PostgreSQL error. Checking here turns that into a proper
        ValidationError the UI can display.
        """
        for rec in self:
            root = rec._get_tree_root()
            if root and root.entity_id and rec.entity_id != root.entity_id:
                raise ValidationError(_(
                    'Category "%(title)s" belongs to entity "%(root)s" '
                    '(tree root "%(root_title)s"). A sub-category must use '
                    'the same entity as its tree root.',
                    title=rec.title,
                    root=root.entity_id.display_name,
                    root_title=root.title,
                ))

    def _get_tree_root(self):
        """Return the root record of this node's branch.

        Follows ``parent_id`` upward (falling back to ``root_id`` when it
        is already correct) and tolerates a broken/cyclic chain by
        returning an empty recordset.
        """
        self.ensure_one()
        seen = set()
        node = self
        while node and node.id not in seen:
            seen.add(node.id)
            if not node.parent_id:
                return node
            node = node.parent_id
        return self.browse()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Row-level security: the category's company is whatever the
            # user has active in Odoo, unless a parent dictates otherwise.
            vals.setdefault('company_id', self.env.company.id)
            vals.setdefault('creator_user_id', self.env.uid)
            vals.setdefault('creation_date', fields.Datetime.now())
            vals.setdefault('is_user_defined', True)

            parent_id = vals.get('parent_id')
            if not vals.get('root_id') and parent_id:
                parent = self.browse(parent_id)
                # A child must share its tree root's company AND entity.
                if parent.company_id:
                    vals['company_id'] = parent.company_id.id
                if not vals.get('entity_id') and parent.entity_id:
                    vals['entity_id'] = parent.entity_id.id
                vals['root_id'] = parent.root_id.id or parent.id

            # Pre-validate entity consistency BEFORE the DB trigger
            # fires. The legacy md.category_same_entity() trigger raises
            # a raw Postgres error that leaves the ORM cache broken
            # (MissingError on read-back). Catching it here yields a
            # proper ValidationError the UI can render.
            entity_id = vals.get('entity_id')
            if parent_id and entity_id:
                parent = self.browse(parent_id)
                if parent.exists():
                    root = parent._get_tree_root() or parent
                    if root.entity_id and root.entity_id.id != entity_id:
                        raise ValidationError(_(
                            'A sub-category must belong to the same entity '
                            'as its tree root "%(root)s" (entity %(ent)s).',
                            root=root.title,
                            ent=root.entity_id.display_name,
                        ))

        records = super().create(vals_list)
        # A brand-new root has no root_id yet: it is its own root.
        for rec in records.filtered(lambda r: not r.root_id):
            rec.sudo().write({'root_id': rec.id})
        return records

    def write(self, vals):
        vals = dict(vals)
        # Re-parenting must keep root_id in sync and must not create a
        # cycle (a node cannot become its own ancestor).
        if 'parent_id' in vals:
            new_parent = (self.browse(vals['parent_id']) if vals['parent_id']
                          else self.browse())
            for rec in self:
                if new_parent:
                    # Reject a cycle: the new parent must not sit below
                    # this record in the tree.
                    node, seen = new_parent, set()
                    while node and node.id not in seen:
                        if node.id == rec.id:
                            raise ValidationError(_(
                                'Cannot move "%(title)s" under its own '
                                'descendant "%(parent)s".',
                                title=rec.title,
                                parent=new_parent.title,
                            ))
                        seen.add(node.id)
                        node = node.parent_id

                    # Pre-validate entity match on re-parent.
                    root = new_parent._get_tree_root() or new_parent
                    if (root.entity_id and rec.entity_id
                            and rec.entity_id.id != root.entity_id.id):
                        raise ValidationError(_(
                            'Cannot move "%(t)s": a sub-category must share '
                            "its tree root's entity (\"%(r)s\").",
                            t=rec.title, r=root.title,
                        ))

                    vals.setdefault(
                        'root_id', new_parent.root_id.id or new_parent.id)
                else:
                    vals.setdefault('root_id', rec.id)

        vals.setdefault('editor_user_id', self.env.uid)
        vals.setdefault('modification_date', fields.Datetime.now())
        result = super().write(vals)
        # A node that became a root must point at itself.
        if 'parent_id' in vals and not vals['parent_id']:
            for rec in self.filtered(lambda r: r.root_id.id != r.id):
                rec.sudo().write({'root_id': rec.id})
        return result

    def unlink(self):
        """Delete this category, every descendant, and all member links.

        The legacy ``md.category.parent_id`` FK is ON DELETE RESTRICT, so
        children must go before their parents. ``md.category_member`` has
        no ON DELETE CASCADE toward ``md.category``, so its rows are
        removed explicitly for every node in the subtree.
        """
        # 1. Collect every layer of the subtree, top-down (BFS).
        layers = [self]
        seen = set(self.ids)
        layer = self
        while layer:
            children = self.search([('parent_id', 'in', layer.ids)])
            children = children.filtered(lambda c: c.id not in seen)
            if not children:
                break
            seen.update(children.ids)
            layers.append(children)
            layer = children

        # 2. Delete member rows for every node in the subtree.
        all_ids = [i for lyr in layers for i in lyr.ids]
        self.env['raes.md.category.member'].sudo().search(
            [('category_id', 'in', all_ids)]).unlink()

        # 3. Delete categories deepest-first so the RESTRICT on
        #    parent_id never blocks a parent that still has children.
        for lyr in reversed(layers):
            super(RaesMdCategory, lyr).unlink()

        return True


class RaesMdCategoryMember(models.Model):
    _name = 'raes.md.category.member'
    _table = 'raes_md_category_member'
    _auto = False
    _log_access = False
    _description = 'MD Category Member (md.category_member)'

    category_id = fields.Many2one('raes.md.category', required=True,
                                  ondelete='cascade')
    member_id = fields.Integer('DW Member ID', required=True, index=True)

    creator_user_id = fields.Integer(default=lambda self: self.env.uid,
                                     required=True)
    creation_date = fields.Datetime(default=fields.Datetime.now,
                                    required=True)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()

    entity_id = fields.Many2one('raes.md.entity', required=True,
                                ondelete='cascade')

    @api.constrains('category_id', 'member_id', 'entity_id')
    def _check_unique_member(self):
        for rec in self:
            domain = [
                ('category_id', '=', rec.category_id.id),
                ('member_id', '=', rec.member_id),
                ('entity_id', '=', rec.entity_id.id),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    _('This member is already in the category!'))

            parent = rec.category_id.parent_id
            if parent and self.search_count([
                ('category_id.parent_id', '=', parent.id),
                ('category_id', '!=', rec.category_id.id),
                ('member_id', '=', rec.member_id),
                ('entity_id', '=', rec.entity_id.id),
                ('id', '!=', rec.id),
            ]):
                raise ValidationError(_(
                    'This member already belongs to sibling category '
                    '"%(parent)s" and cannot be added to another '
                    'sub-category of the same parent.',
                    parent=parent.title,
                ))

    def init(self):
        try:
            refresh_writable_view(self.env, *CATEGORY_MEMBER_VIEW)
        except Exception:
            _logger.exception("Could not (re)build view raes_md_category_member")
            raise

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('creator_user_id', self.env.uid)
            vals.setdefault('creation_date', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        vals.setdefault('editor_user_id', self.env.uid)
        vals.setdefault('modification_date', fields.Datetime.now())
        return super().write(vals)
