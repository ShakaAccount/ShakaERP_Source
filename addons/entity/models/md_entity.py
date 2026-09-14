from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .md_view import MD_ENTITY_VIEW, refresh_md_view

ENTITY_TYPE_LOOKUP_CATEGORY = '1001'
ENTITY_SYSTEM_LOOKUP_CATEGORY = '1004'


class StrSelection(fields.Selection):
    """Selection that exposes the DB value as a string on read."""

    def convert_to_read(self, value, record, use_display_name=True):
        if value is None or value is False:
            return value
        return str(value)

    def convert_to_record(self, value, record):
        if value is None or value is False:
            return value
        return str(value)


class RaesMdEntity(models.Model):
    _name = 'raes.md.entity'
    _table = 'raes_md_entity'
    _auto = False
    _log_access = False
    _rec_name = 'name'
    _order = 'schema_name, name'
    _description = 'MD Entity (md.entity)'

    # ------------------------------------------------------------------
    # Selections
    # ------------------------------------------------------------------
    @api.model
    def _selection_entity_type_lu(self):
        fallback = [('1', 'Dim'), ('2', 'Fact')]
        Lookup = self.env.get('raes.gnr.lookup')
        if Lookup is None:
            return fallback
        try:
            lookups = Lookup.search(
                [('category_code', '=', ENTITY_TYPE_LOOKUP_CATEGORY)],
                order='code',
            )
        except Exception:
            return fallback
        if not lookups:
            return fallback
        return [(str(lk.code), lk.value or str(lk.code)) for lk in lookups]

    @api.model
    def _selection_entity_system_lu(self):
        Lookup = self.env.get('raes.gnr.lookup')
        if Lookup is None:
            return []
        try:
            lookups = Lookup.search(
                [('category_code', '=', ENTITY_SYSTEM_LOOKUP_CATEGORY)],
                order='code',
            )
        except Exception:
            return []
        return [(str(lk.code), lk.value or str(lk.code)) for lk in lookups]

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    entity_type_lu = StrSelection(
        selection='_selection_entity_type_lu',
        string='Entity Type',
        required=True,
        default='1',
    )

    system_lu = StrSelection(
        selection='_selection_entity_system_lu',
        string='Entity System',
    )

    schema_name = fields.Char(index=True)
    name = fields.Char(required=True, index=True)
    title = fields.Char(string='Persian Name')

    module_id = fields.Many2one(
        'raes.gnr.module', string='Module',
        required=True, ondelete='restrict', index=True)

    is_category_based = fields.Boolean()
    is_user_defined = fields.Boolean()
    is_company_based = fields.Boolean()
    is_active = fields.Boolean(default=True)
    priority = fields.Integer()

    master_entity_id = fields.Many2one(
        'raes.md.entity', string='Master Entity', index=True)
    child_ids = fields.One2many(
        'raes.md.entity', 'master_entity_id', string='Child Entities')
    column_ids = fields.One2many(
        'raes.md.entity_column', 'entity_id', string='Columns')
    column_count = fields.Integer(
        compute='_compute_column_count', string='Columns')

    entity_full_name = fields.Char(
        string='Entity Full Name',
        related='name', store=False, readonly=True,
    )

    creator_user_id = fields.Integer(
        required=True, default=lambda self: self.env.uid)
    creation_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()
    database_name = fields.Char()

    # ------------------------------------------------------------------
    # PK column helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_column_name(entity_name, entity_type_lu):
        """Return the name of the auto-generated PK column for an entity.

        Dim (entity_type_lu == '1')  ->  ``{entity_name}ID`` (DimSalesID)
        Anything else (Fact, ...)    ->  ``id``
        """
        if str(entity_type_lu) == '1':
            return f'{entity_name}ID'
        return 'id'

    def _ensure_pk_column(self):
        """Create or synchronise the auto PK column.

        Keeps the name (Dim vs Fact rule) and ``is_identity`` in sync with
        the entity's current ``name`` and ``entity_type_lu``.
        """
        Column = self.env['raes.md.entity_column'].with_context(
            skip_ordinal_check=True,
            skip_is_user_defined_force=True,
        )
        for entity in self:
            expected_name = self._pk_column_name(
                entity.name, entity.entity_type_lu)
            expected_identity = str(entity.entity_type_lu) == '2'

            existing = entity.column_ids.filtered(
                lambda c: c.ordinal_position == 1)

            if existing:
                updates = {}
                if existing.name != expected_name:
                    updates['name'] = expected_name
                if existing.is_identity != expected_identity:
                    updates['is_identity'] = expected_identity
                if updates:
                    existing.with_context(
                        skip_ordinal_check=True,
                    ).write(updates)
                continue

            Column.create({
                'entity_id': entity.id,
                'name': expected_name,
                'title': 'کلید اصلی',
                'data_type': 'int',
                'ordinal_position': 1,
                'is_primary_key': True,
                'is_identity': expected_identity,
                'is_user_defined': 0,
            })

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('name', 'schema_name')
    def _check_name_unique(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('id', '!=', rec.id),
            ]
            if rec.schema_name:
                domain.append(('schema_name', '=', rec.schema_name))
            else:
                domain.append(('schema_name', '=', False))
            if self.search_count(domain):
                raise ValidationError(_(
                    "An entity named '%(n)s' already exists in schema "
                    "'%(s)s'.",
                    n=rec.name, s=rec.schema_name or '—'))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def init(self):
        refresh_md_view(self.env, *MD_ENTITY_VIEW)

    @api.depends('column_ids')
    def _compute_column_count(self):
        for rec in self:
            rec.column_count = len(rec.column_ids)

    def action_open_columns(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Columns of %s', self.name),
            'res_model': 'raes.md.entity_column',
            'view_mode': 'list,form',
            'domain': [('entity_id', '=', self.id)],
            'context': {'default_entity_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        entities = super().create(vals_list)
        entities._ensure_pk_column()
        return entities

    def write(self, vals):
        if 'modification_date' not in vals:
            vals['modification_date'] = fields.Datetime.now()
        if 'editor_user_id' not in vals:
            vals['editor_user_id'] = self.env.uid
        res = super().write(vals)

        # Any change to `name` or `entity_type_lu` may affect the PK
        # column's name and/or is_identity — resync it.
        if 'name' in vals or 'entity_type_lu' in vals:
            self._ensure_pk_column()

        return res