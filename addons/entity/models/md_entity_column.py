from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .md_view import MD_ENTITY_COLUMN_VIEW, refresh_md_view


class RaesMdEntityColumn(models.Model):
    """Direct mapping of the existing md.entity_column table."""
    _name = 'raes.md.entity_column'
    _table = 'raes_md_entity_column'
    _auto = False
    _log_access = False
    _rec_name = 'name'
    _order = 'entity_id, ordinal_position, name'
    _description = 'MD Entity Column (md.entity_column)'

    entity_id = fields.Many2one(
        'raes.md.entity', string='Entity',
        required=True, ondelete='cascade', index=True)

    name = fields.Char(index=True)
    # Persian name / display label
    title = fields.Char(string='Persian Name')
    data_type = fields.Char()
    size = fields.Char()
    ordinal_position = fields.Integer()

    # Auto-managed – never edited by the user directly.
    is_primary_key = fields.Boolean(readonly=True)
    is_identity = fields.Boolean(readonly=True)

    reference_entity_id = fields.Many2one(
        'raes.md.entity', string='Reference Entity',
        ondelete='set null', index=True)

    is_user_defined = fields.Integer(
        help='The DDL declares this as int4, not bool — kept as Integer.')
    column_type_lu = fields.Integer()

    creator_user_id = fields.Integer(
        required=True, default=lambda self: self.env.uid)
    creation_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()

    # Mirror of `name`
    original_name = fields.Char(
        string='Original Name',
        related='name',
        store=False,
        readonly=True,
    )

    def init(self):
        refresh_md_view(self.env, *MD_ENTITY_COLUMN_VIEW)

    @api.constrains('name', 'entity_id')
    def _check_name_unique(self):
        for rec in self:
            if not rec.name or not rec.entity_id:
                continue
            if self.search_count([
                ('entity_id', '=', rec.entity_id.id),
                ('name', '=', rec.name),
                ('id', '!=', rec.id),
            ]):
                raise ValidationError(_(
                    "Column '%(c)s' already exists on entity "
                    "'%(e)s'.",
                    c=rec.name, e=rec.entity_id.display_name))

    def write(self, vals):
        if 'modification_date' not in vals:
            vals['modification_date'] = fields.Datetime.now()
        if 'editor_user_id' not in vals:
            vals['editor_user_id'] = self.env.uid
        return super().write(vals)