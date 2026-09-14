from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .md_view import MD_ENTITY_COLUMN_VIEW, refresh_md_view

# GNR.LookUp category used for the column-type dropdown
COLUMN_TYPE_LOOKUP_CATEGORY = '1005'


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

    # Always 1 for user-created columns; never exposed to the UI.
    is_user_defined = fields.Integer(
        string='User Defined',
        default=1,
        readonly=True,
        help='The DDL declares this as int4, not bool — kept as Integer. '
             'Always forced to 1 for columns created through Odoo.')

    @api.model
    def _selection_column_type_lu(self):
        """Populate the Column Type dropdown from GNR.LookUp
        (category_code = 1005).  Shows `value`, stores `code`."""
        Lookup = self.env.get('raes.gnr.lookup')
        if Lookup is None:
            return []
        try:
            lookups = Lookup.search(
                [('category_code', '=', COLUMN_TYPE_LOOKUP_CATEGORY)],
                order='code',
            )
        except Exception:
            return []
        return [
            (str(lk.code), lk.value or str(lk.code))
            for lk in lookups
        ]

    column_type_lu = fields.Selection(
        selection='_selection_column_type_lu',
        string='Column Type',
    )

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Force the flag regardless of what the caller passed
            vals['is_user_defined'] = 1
        return super().create(vals_list)

    def write(self, vals):
        # Never let the flag be overwritten
        vals.pop('is_user_defined', None)
        if 'modification_date' not in vals:
            vals['modification_date'] = fields.Datetime.now()
        if 'editor_user_id' not in vals:
            vals['editor_user_id'] = self.env.uid
        return super().write(vals)