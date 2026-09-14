from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

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

    # Companion-table backed relation (raes.md.entity.config).
    # NOTE: store=False + compute means the value lives in the companion
    # table, not in raes_md_entity. The inverse writes it there.
    connection_id = fields.Many2one(
        'raes.dw.connection', string='DW Connection',
        compute='_compute_connection_id',
        inverse='_inverse_connection_id',
        store=False,
        help='Foreign Data Wrapper connection this entity belongs to. '
             'Stored in raes.md.entity.config, not in the DW.')

    database_name = fields.Char(
        string='Database Name', readonly=True,
        help='Filled automatically from the linked DW connection.')

    # Raw value that ends up in the DW column md.entity.schema_name
    schema_name = fields.Char(string='Schema')

    # UI picker — dropdown backed by raes.dw.schema, filtered by connection
    schema_id = fields.Many2one(
        'raes.dw.schema', string='Schema',
        compute='_compute_schema_id',
        inverse='_inverse_schema_id',
        store=False,
    )

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

    # ------------------------------------------------------------------
    # connection_id — companion table compute / inverse
    # ------------------------------------------------------------------
    def _compute_connection_id(self):
        Config = self.env['raes.md.entity.config'].sudo()
        configs = Config.search([('entity_id', 'in', self.ids)])
        by_entity = {c.entity_id.id: c.connection_id for c in configs}
        for rec in self:
            rec.connection_id = by_entity.get(rec.id, False)

    def _inverse_connection_id(self):
        Config = self.env['raes.md.entity.config'].sudo()
        for rec in self:
            config = Config.search([('entity_id', '=', rec.id)], limit=1)
            if rec.connection_id:
                if config:
                    if config.connection_id != rec.connection_id:
                        config.connection_id = rec.connection_id.id
                else:
                    Config.create({
                        'entity_id': rec.id,
                        'connection_id': rec.connection_id.id,
                    })
            elif config:
                config.connection_id = False

    # ------------------------------------------------------------------
    # schema_id — picker compute / inverse
    # ------------------------------------------------------------------
    @api.depends('schema_name')
    def _compute_schema_id(self):
        Schema = self.env['raes.dw.schema'].sudo()
        for rec in self:
            conn = rec.connection_id
            if rec.schema_name and conn:
                rec.schema_id = Schema.search([
                    ('connection_id', '=', conn.id),
                    ('name', '=', rec.schema_name),
                ], limit=1)
            else:
                rec.schema_id = False

    def _inverse_schema_id(self):
        for rec in self:
            rec.schema_name = rec.schema_id.name if rec.schema_id else False

    # ------------------------------------------------------------------
    # Onchange — keep DB name + schema in sync with connection
    # ------------------------------------------------------------------
    @api.onchange('connection_id')
    def _onchange_connection_id(self):
        if self.connection_id:
            self.database_name = self.connection_id.database
            # If the picked schema doesn't belong to the new connection,
            # drop it and clear the raw value.
            if self.schema_id and self.schema_id.connection_id != self.connection_id:
                self.schema_id = False
                self.schema_name = False
        else:
            self.database_name = False
            self.schema_id = False
            self.schema_name = False

    # ------------------------------------------------------------------
    # PK column helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_column_name(entity_name, entity_type_lu):
        """Dim (entity_type_lu == '1')  ->  ``{entity_name}ID``
        Anything else (Fact, ...)    ->  ``id``
        """
        if str(entity_type_lu) == '1':
            return f'{entity_name}ID'
        return 'id'

    def _ensure_pk_column(self):
        """Create or synchronise the auto PK column."""
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

    def action_open_connection(self):
        self.ensure_one()
        if not self.connection_id:
            raise UserError(_('No DW connection linked to this entity.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('DW Connection'),
            'res_model': 'raes.dw.connection',
            'res_id': self.connection_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_rebuild_catalog(self):
        self.ensure_one()
        if not self.connection_id:
            raise UserError(_('No DW connection linked to this entity.'))
        # sync_connection is decorated with @api.model in the DW connector
        # addon, so call it on the catalog model itself.
        self.env['raes.dw.catalog'].sync_connection(self.connection_id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Catalog rebuilt'),
                'message': _('Schemas of %s refreshed.',
                             self.connection_id.display_name),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            conn_id = vals.get('connection_id')
            if conn_id and not vals.get('database_name'):
                conn = self.env['raes.dw.connection'].browse(conn_id)
                vals['database_name'] = conn.database
        entities = super().create(vals_list)
        entities._ensure_pk_column()
        return entities

    def write(self, vals):
        if 'modification_date' not in vals:
            vals['modification_date'] = fields.Datetime.now()
        if 'editor_user_id' not in vals:
            vals['editor_user_id'] = self.env.uid

        if 'connection_id' in vals:
            conn_id = vals['connection_id']
            if conn_id:
                conn = self.env['raes.dw.connection'].browse(conn_id)
                vals.setdefault('database_name', conn.database)
            else:
                vals.setdefault('database_name', False)

        res = super().write(vals)

        if 'name' in vals or 'entity_type_lu' in vals:
            self._ensure_pk_column()

        return res