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
    _auto = False              # Odoo must NOT create the table
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

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company,
                                 required=True)
    entity_id = fields.Many2one('raes.md.entity', 'Entity', required=True,
                                ondelete='cascade')

    is_node_only = fields.Boolean()
    is_user_defined = fields.Boolean()

    member_ids = fields.One2many('raes.md.category.member', 'category_id',
                                 string='Members')

    def init(self):
        # init() runs on install AND on every upgrade. Rebuild the writable
        # view so a DW reload that CASCADEd it away does not break the ORM.
        try:
            refresh_writable_view(self.env, *CATEGORY_VIEW)
        except Exception:
            _logger.exception("Could not (re)build view raes_md_category")
            raise

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('company_id', self.env.company.id)
            vals.setdefault('creator_user_id', self.env.uid)
            vals.setdefault('creation_date', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        vals.setdefault('editor_user_id', self.env.uid)
        vals.setdefault('modification_date', fields.Datetime.now())
        return super().write(vals)


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

    # NOTE: this model is _auto = False and backed by a view, so a
    # _sql_constraints entry can never be materialised in the database
    # (verified: no matching row in pg_constraint). Uniqueness is
    # enforced in Python instead.
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