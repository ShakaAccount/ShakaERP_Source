from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .md_view import MD_ENTITY_COLUMN_VIEW, refresh_md_view

COLUMN_TYPE_LOOKUP_CATEGORY = '1005'

DATA_TYPE_SELECTION = [
    ('bigint', 'BigInt'),
    ('int', 'Int'),
    ('tinyint', 'TinyInt'),
    ('bit', 'Bit'),
    ('decimal', 'Decimal'),
    ('float', 'Float'),
    ('date', 'Date'),
    ('datetime', 'DateTime'),
    ('time', 'Time'),
    ('varchar', 'VarChar'),
    ('nvarchar', 'NVarChar'),
    ('char', 'Char'),
    ('nchar', 'NChar'),
]

SIZE_REQUIRED_TYPES = {'decimal', 'nvarchar', 'varchar', 'char', 'nchar'}


class StrSelection(fields.Selection):
    def convert_to_read(self, value, record, use_display_name=True):
        if value is None or value is False:
            return value
        return str(value)

    def convert_to_record(self, value, record):
        if value is None or value is False:
            return value
        return str(value)


class NormalizedDataType(fields.Selection):
    """Selection whose value is the lowercase-normalised DB string."""

    def convert_to_read(self, value, record, use_display_name=True):
        if value is None or value is False:
            return value
        return str(value).lower()

    def convert_to_record(self, value, record):
        if value is None or value is False:
            return value
        return str(value).lower()


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
    title = fields.Char(string='Persian Name')

    data_type = NormalizedDataType(
        selection=DATA_TYPE_SELECTION,
        string='Data Type',
    )

    # Only meaningful for decimal / nvarchar / varchar / char / nchar
    size = fields.Char(string='Size')

    ordinal_position = fields.Integer(string='Ordinal Position')

    is_primary_key = fields.Boolean(readonly=True)
    is_identity = fields.Boolean(readonly=True)

    reference_entity_id = fields.Many2one(
        'raes.md.entity', string='Reference Entity',
        ondelete='set null', index=True)

    is_user_defined = fields.Integer(
        string='User Defined',
        default=1,
        readonly=True,
        help='Always forced to 1 for columns created through Odoo.')

    @api.model
    def _selection_column_type_lu(self):
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
        return [(str(lk.code), lk.value or str(lk.code)) for lk in lookups]

    column_type_lu = StrSelection(
        selection='_selection_column_type_lu',
        string='Column Type',
    )

    creator_user_id = fields.Integer(
        required=True, default=lambda self: self.env.uid)
    creation_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()

    original_name = fields.Char(
        string='Original Name',
        related='name', store=False, readonly=True,
    )

    # ------------------------------------------------------------------
    # Ordinal position rules
    #   - position 1 is reserved for the auto PK column
    #   - the sequence 1..N must be continuous (no gaps, no duplicates)
    #   - user-created columns therefore start at 2
    # ------------------------------------------------------------------
    @api.constrains('ordinal_position', 'entity_id')
    def _check_ordinal_position(self):
        if self.env.context.get('skip_ordinal_check'):
            return
        for rec in self:
            if not rec.entity_id:
                continue
            cols = self.search([
                ('entity_id', '=', rec.entity_id.id),
                ('ordinal_position', '!=', False),
            ])
            positions = sorted(c.ordinal_position for c in cols)

            # Duplicate check
            if len(positions) != len(set(positions)):
                raise ValidationError(_(
                    "Two columns of entity '%(e)s' cannot share the same "
                    "ordinal position. Used positions: %(p)s.",
                    e=rec.entity_id.display_name, p=positions,
                ))

            # Continuity check
            expected = list(range(1, len(positions) + 1))
            if positions != expected:
                raise ValidationError(_(
                    "Ordinal positions of entity '%(e)s' must be "
                    "continuous, starting from 1 with no gaps. "
                    "Expected %(exp)s, got %(got)s.",
                    e=rec.entity_id.display_name,
                    exp=expected, got=positions,
                ))

    # ------------------------------------------------------------------
    # Size handling
    # ------------------------------------------------------------------
    @api.onchange('data_type')
    def _onchange_data_type_clear_size(self):
        if self.data_type and self.data_type not in SIZE_REQUIRED_TYPES:
            self.size = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
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
        if not self.env.context.get('skip_is_user_defined_force'):
            for vals in vals_list:
                vals['is_user_defined'] = 1
        for vals in vals_list:
            # Reference entity forces bigint
            if vals.get('reference_entity_id'):
                vals['data_type'] = 'bigint'
                vals['size'] = False
            # Otherwise drop size for types that don't use it
            dt = vals.get('data_type')
            if dt and dt not in SIZE_REQUIRED_TYPES:
                vals['size'] = False
        return super().create(vals_list)

    def write(self, vals):
        vals.pop('is_user_defined', None)

        if 'reference_entity_id' in vals:
            if vals['reference_entity_id']:
                # Setting a reference → force BigInt
                vals['data_type'] = 'bigint'
                vals['size'] = False
            # else: clearing the reference — no forced data_type, user keeps
            # whatever they pick next

        new_type = vals.get('data_type')
        if new_type is not None and new_type not in SIZE_REQUIRED_TYPES:
            vals['size'] = False

        if 'modification_date' not in vals:
            vals['modification_date'] = fields.Datetime.now()
        if 'editor_user_id' not in vals:
            vals['editor_user_id'] = self.env.uid
        return super().write(vals)

    def action_clear_reference_entity(self):
        """Clear the reference and re-enable the Data Type field."""
        self.ensure_one()
        self.reference_entity_id = False
        # Do NOT touch data_type here — the user picks the new one.

    def unlink(self):
        # Capture affected entities before delete
        entities = self.mapped('entity_id')

        # Do not allow removing the auto PK column via the UI
        pk_cols = self.filtered(lambda c: c.ordinal_position == 1)
        if pk_cols:
            raise ValidationError(_(
                "The primary-key column cannot be deleted."
            ))

        res = super().unlink()

        # Close ordinal gaps: renumber remaining user columns 2, 3, 4, ...
        Column = self.with_context(skip_ordinal_check=True)
        for entity in entities:
            cols = Column.search([
                ('entity_id', '=', entity.id),
                ('ordinal_position', '>', 1),
            ], order='ordinal_position')
            for i, col in enumerate(cols, start=2):
                if col.ordinal_position != i:
                    col.write({'ordinal_position': i})
        return res

    @api.onchange('reference_entity_id')
    def _onchange_reference_entity_set_bigint(self):
        if self.reference_entity_id:
            self.data_type = 'bigint'
            self.size = False