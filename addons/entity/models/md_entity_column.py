import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import ddl_builder
from .md_view import MD_ENTITY_COLUMN_VIEW, refresh_md_view

_logger = logging.getLogger(__name__)

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

    # Editable now — user picks them explicitly.
    is_primary_key = fields.Boolean(string='Primary Key')
    is_identity = fields.Boolean(string='Identity')

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
    # Ordinal position rules — 1..N, no gaps, no duplicates.
    #
    # The constraint is deferred when an ordinal change is part of a
    # batch (see md_entity.write/create): the parent sets
    # ``skip_ordinal_check`` in context so intermediate states during
    # a swap are not rejected. The parent then runs the full validation
    # once after all child writes complete.
    # ------------------------------------------------------------------
    @api.constrains('ordinal_position', 'entity_id')
    def _check_ordinal_position(self):
        if self.env.context.get('skip_ordinal_check'):
            return
        # Delegate to the entity so the same error text and logic is
        # used whether the column was written directly or via a batch.
        for entity in self.mapped('entity_id'):
            entity._validate_column_ordinals()

    # ------------------------------------------------------------------
    # One PK and one identity per entity
    # ------------------------------------------------------------------
    @api.constrains('is_primary_key', 'entity_id')
    def _check_single_primary_key(self):
        if self.env.context.get('skip_single_pk_check'):
            return
        for rec in self:
            if not rec.is_primary_key or not rec.entity_id:
                continue
            others = self.search([
                ('entity_id', '=', rec.entity_id.id),
                ('is_primary_key', '=', True),
                ('id', '!=', rec.id),
            ], limit=1)
            if others:
                raise ValidationError(_(
                    "Entity '%(e)s' already has a primary-key column "
                    "('%(c)s'). Only one column can be the primary key.",
                    e=rec.entity_id.display_name,
                    c=others.name))

    @api.constrains('is_identity', 'entity_id')
    def _check_single_identity(self):
        if self.env.context.get('skip_single_identity_check'):
            return
        for rec in self:
            if not rec.is_identity or not rec.entity_id:
                continue
            others = self.search([
                ('entity_id', '=', rec.entity_id.id),
                ('is_identity', '=', True),
                ('id', '!=', rec.id),
            ], limit=1)
            if others:
                raise ValidationError(_(
                    "Entity '%(e)s' already has an identity column "
                    "('%(c)s'). Only one column can be identity.",
                    e=rec.entity_id.display_name,
                    c=others.name))

    # ------------------------------------------------------------------
    # Size / reference handling
    # ------------------------------------------------------------------
    @api.onchange('data_type')
    def _onchange_data_type_clear_size(self):
        if self.data_type and self.data_type not in SIZE_REQUIRED_TYPES:
            self.size = False

    @api.onchange('reference_entity_id')
    def _onchange_reference_entity_set_bigint(self):
        if self.reference_entity_id:
            self.data_type = 'bigint'
            self.size = False

    @api.constrains('reference_entity_id', 'data_type')
    def _check_reference_entity_forces_bigint(self):
        for rec in self:
            if rec.reference_entity_id and rec.data_type != 'bigint':
                raise ValidationError(_(
                    "Column '%(c)s' references entity '%(e)s', so its "
                    "Data Type must be BigInt.",
                    c=rec.name, e=rec.reference_entity_id.display_name))

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
        for vals in vals_list:
            vals['is_user_defined'] = 1
            if vals.get('reference_entity_id'):
                vals['data_type'] = 'bigint'
                vals['size'] = False
            dt = vals.get('data_type')
            if dt and dt not in SIZE_REQUIRED_TYPES:
                vals['size'] = False

        res = super().create(vals_list)

        if not self.env.context.get('skip_dw_sync'):
            for entity in res.mapped('entity_id'):
                # Let UserError propagate so the user sees the reason
                # the FK could not be created.
                entity._sync_dw_table()
        return res

    def write(self, vals):
        # Capture old names to rename the DB column
        old_names = {}
        if 'name' in vals:
            for rec in self:
                old_names[rec.id] = rec.name

        vals.pop('is_user_defined', None)

        if 'reference_entity_id' in vals:
            if vals['reference_entity_id']:
                vals['data_type'] = 'bigint'
                vals['size'] = False

        new_type = vals.get('data_type')
        if new_type is not None and new_type not in SIZE_REQUIRED_TYPES:
            vals['size'] = False

        if 'modification_date' not in vals:
            vals['modification_date'] = fields.Datetime.now()
        if 'editor_user_id' not in vals:
            vals['editor_user_id'] = self.env.uid

        # Rename the DB column on MSSQL before touching metadata
        if 'name' in vals:
            for rec in self:
                old_name = old_names.get(rec.id, rec.name)
                new_name = vals['name']
                if (old_name != new_name
                        and rec.entity_id.schema_name):
                    conn = rec.entity_id._get_dw_connection()
                    if conn:
                        ddl_builder.rename_column(
                            conn,
                            rec.entity_id.schema_name,
                            rec.entity_id.name,
                            old_name, new_name)

        res = super().write(vals)

        if not self.env.context.get('skip_dw_sync'):
            for entity in self.mapped('entity_id'):
                entity._sync_dw_table()
        return res

    def action_clear_reference_entity(self):
        """Clear the reference and re-enable the Data Type field."""
        self.ensure_one()
        self.reference_entity_id = False

    def unlink(self):
        entities = self.mapped('entity_id')

        res = super().unlink()

        # Close ordinal gaps: renumber remaining columns 1, 2, 3, ...
        Column = self.with_context(skip_ordinal_check=True)
        for entity in entities:
            cols = Column.search([
                ('entity_id', '=', entity.id),
            ], order='ordinal_position')
            for i, col in enumerate(cols, start=1):
                if col.ordinal_position != i:
                    col.write({'ordinal_position': i})
        return res