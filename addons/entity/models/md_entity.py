import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import ddl_builder
from .md_view import MD_ENTITY_VIEW, refresh_md_view

_logger = logging.getLogger(__name__)

ENTITY_TYPE_LOOKUP_CATEGORY = '1001'
ENTITY_SYSTEM_LOOKUP_CATEGORY = '1004'

# ----------------------------------------------------------------------
# Arabic → Persian normalisation
#
# Persian text frequently contains Arabic codepoints that look identical
# to the Persian ones but don't compare equal:
#     ي (U+064A Arabic Yeh)  ≠ ی (U+06CC Persian Yeh)
#     ك (U+0643 Arabic Kaf)  ≠ ک (U+06A9 Persian Kef)
#     ة (U+0629 Teh Marbuta) ≠ ه (U+0647 Heh)
# A search for "ی" therefore misses every row that stored "ي", and vice
# versa. The map below normalises both the incoming search term and the
# database value to a canonical Persian form before the LIKE runs.
#
# Diacritics (Harakat) are mapped to the empty string — they are
# invisible in most Persian text, so stripping them makes search more
# forgiving. Arabic-Indic digits (٠-٩) and extended Arabic-Indic digits
# (۰-۹) are mapped to their ASCII forms so a search for "123" matches
# "۱۲۳" and vice versa.
# ----------------------------------------------------------------------
_PERSIAN_NORMALIZE_MAP = {
    # Letters
    '\u064A': '\u06CC',  # ي Arabic Yeh       → ی Persian Yeh
    '\u0649': '\u06CC',  # ى Alef Maksura     → ی
    '\u0643': '\u06A9',  # ك Arabic Kaf       → ک Persian Kef
    '\u0629': '\u0647',  # ة Teh Marbuta      → ه Heh
    '\u06C0': '\u0647',  # ۀ Heh + Yeh        → ه
    # Diacritics — removed
    '\u064B': '', '\u064C': '', '\u064D': '',
    '\u064E': '', '\u064F': '', '\u0650': '',
    '\u0651': '', '\u0652': '',
    '\u0653': '', '\u0654': '', '\u0655': '',
    '\u0670': '',
    # Add to the map:
    '\u200C': '',  # ZWNJ
    '\u200D': '',  # ZWJ
    '\u200E': '', '\u200F': '',
    # Arabic-Indic digits → ASCII
    '\u0660': '0', '\u0661': '1', '\u0662': '2', '\u0663': '3',
    '\u0664': '4', '\u0665': '5', '\u0666': '6', '\u0667': '7',
    '\u0668': '8', '\u0669': '9',
    # Extended Arabic-Indic (Persian) digits → ASCII
    '\u06F0': '0', '\u06F1': '1', '\u06F2': '2', '\u06F3': '3',
    '\u06F4': '4', '\u06F5': '5', '\u06F6': '6', '\u06F7': '7',
    '\u06F8': '8', '\u06F9': '9',

    # Decimal / thousands separators
    '\u066B': '.', '\u066C': ',',
}


def _persian_normalize(text):
    """Return *text* with Arabic codepoints mapped to Persian ones."""
    if not text:
        return text
    for src, dst in _PERSIAN_NORMALIZE_MAP.items():
        if src in text:
            text = text.replace(src, dst)
    return text


def _sql_persian_normalize(column_expr, term=None, dialect='mssql'):
    """Return a SQL expression that maps Arabic codepoints in
    *column_expr* to their Persian equivalents.

    When ``term`` (already normalised) is given, only the mappings
    whose *target* character appears in the term are emitted — the DB
    value for the other characters can't change whether ``term`` is a
    substring of the normalised value. This keeps the REPLACE chain
    short for typical searches.

    ``dialect`` selects the string-literal prefix: ``N'…'`` for MSSQL
    (Unicode), bare ``'…'`` for PostgreSQL (which is already UTF-8).
    """
    prefix = "N" if dialect == 'mssql' else ""
    expr = column_expr
    for src, dst in _PERSIAN_NORMALIZE_MAP.items():
        if term is not None and dst and dst not in term:
            continue
        src_esc = src.replace("'", "''")
        dst_esc = dst.replace("'", "''")
        expr = f"REPLACE({expr}, {prefix}'{src_esc}', {prefix}'{dst_esc}')"
    return expr


def _quote_ident(name):
    """Quote a PostgreSQL identifier (local, trusted-by-origin names)."""
    return '"' + str(name).replace('"', '""') + '"'


def _split_relation(relation):
    """``schema.table`` -> (schema, table); bare names -> (public, name)."""
    if '.' in relation:
        schema, table = relation.split('.', 1)
        return schema.strip('"'), table.strip('"')
    return 'public', relation.strip('"')


def _localize_name(name, available):
    """Map a catalog (MSSQL PascalCase) column name onto one that
    really exists locally, matched case-insensitively. The bootstrap
    alias views lowercase every column, hence the fallback."""
    if not name:
        return None
    low = str(name).lower()
    if low in available:
        return low
    compact = low.replace('_', '').replace(' ', '')
    for cand in available:
        if cand.replace('_', '').replace(' ', '') == compact:
            return cand
    return None


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
                order='code')
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
                order='code')
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

    schema_name = fields.Char(string='Schema')

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
        required=True, default=lambda self: fields.Datetime.now())
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
            if self.schema_id and self.schema_id.connection_id != self.connection_id:
                self.schema_id = False
                self.schema_name = False
        else:
            self.database_name = False
            self.schema_id = False
            self.schema_name = False

    # ------------------------------------------------------------------
    # DW connection lookup + table sync
    # ------------------------------------------------------------------
    def _get_dw_connection(self):
        self.ensure_one()
        config = self.env['raes.md.entity.config'].sudo().search(
            [('entity_id', '=', self.id)], limit=1)
        return config.connection_id if config else False

    def _sync_dw_table(self):
        for rec in self:
            if not rec.schema_name or not rec.name:
                continue
            connection = rec._get_dw_connection()
            if not connection:
                continue
            try:
                ddl_builder.sync_table(connection, rec)
            except Exception as e:
                _logger.exception(
                    "DW table sync failed for %s", rec.display_name)
                raise UserError(_(
                    "Could not create or update the DW table for "
                    "'%(e)s':\n%(msg)s",
                    e=rec.display_name, msg=str(e)[:500]))

    # ------------------------------------------------------------------
    # Ordinal position validation (shared with md.entity.column)
    # ------------------------------------------------------------------
    def _validate_column_ordinals(self):
        """Ensure each entity's columns form a gap-free 1..N sequence."""
        for entity in self:
            cols = entity.column_ids.filtered(
                lambda c: c.ordinal_position and c.ordinal_position > 0
            ).sorted('ordinal_position')
            if not cols:
                continue

            positions = [c.ordinal_position for c in cols]

            if len(positions) != len(set(positions)):
                dupes = sorted({p for p in positions
                                if positions.count(p) > 1})
                raise ValidationError(_(
                    "Entity '%(e)s' has more than one column sharing "
                    "ordinal position %(p)s. Each column must have a "
                    "unique position starting from 1.",
                    e=entity.display_name,
                    p=', '.join(str(d) for d in dupes),
                ))

            expected = list(range(1, len(positions) + 1))
            if positions != expected:
                raise ValidationError(_(
                    "Ordinal positions of entity '%(e)s' must form a "
                    "gap-free sequence 1..%(n)s. Current positions: "
                    "%(got)s. Renumber your columns so they read "
                    "1, 2, 3, ... with no gaps.",
                    e=entity.display_name,
                    n=len(positions),
                    got=', '.join(str(p) for p in positions),
                ))

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

    def action_sync_dw_table(self):
        self.ensure_one()
        if not self.schema_name or not self.name:
            raise UserError(_(
                'Set a Schema and a Name before syncing the DW table.'))
        if not self._get_dw_connection():
            raise UserError(_(
                'Link a DW Connection before syncing the DW table.'))
        self._sync_dw_table()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('DW table synced'),
                'message': _('Table %(s)s.%(t)s is up to date.',
                             s=self.schema_name, t=self.name),
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

        has_columns = any(v.get('column_ids') for v in vals_list)
        if has_columns:
            self_ctx = self.with_context(skip_ordinal_check=True)
        else:
            self_ctx = self

        entities = super(RaesMdEntity, self_ctx).create(vals_list)

        if has_columns:
            entities._validate_column_ordinals()

        entities._sync_dw_table()
        return entities

    def write(self, vals):
        old_meta = {}
        if 'name' in vals or 'schema_name' in vals:
            for rec in self:
                old_meta[rec.id] = (rec.name, rec.schema_name)

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

        batch_ordinals = 'column_ids' in vals
        if batch_ordinals:
            self_ctx = self.with_context(skip_ordinal_check=True)
        else:
            self_ctx = self

        res = super(RaesMdEntity, self_ctx).write(vals)

        for rec in self:
            old = old_meta.get(rec.id)
            if not old:
                continue
            old_name, old_schema = old
            if old_name != rec.name or old_schema != rec.schema_name:
                conn = rec._get_dw_connection()
                if conn:
                    ddl_builder.rename_table(
                        conn,
                        old_schema, old_name,
                        rec.schema_name, rec.name)

        if batch_ordinals:
            self._validate_column_ordinals()

        self._sync_dw_table()

        return res

    @api.model
    def get_dw_records(self, entity_id, offset=0, limit=10, search_term=''):
        """Fetch records dynamically from the DW table linked to this entity.

        Returns ``{'records': [...], 'total': n, 'reason': str|None}``.
        Each record carries a normalized ``id`` (the resolved DW primary
        key) and a display ``label`` in addition to the raw DW columns —
        the raw PK column is a lowercased MSSQL name (``partyid``,
        ``detailedledgerid``, ...), so callers must not assume
        ``record.id`` exists unless it is normalized here.
        """
        empty = {'records': [], 'total': 0, 'reason': None}
        entity = self.browse(entity_id)
        if not entity.exists():
            return dict(empty, reason='no-entity')

        conn, relation, source = self._dw_resolve_relation(entity)
        if not relation:
            _logger.info(
                'DW relation unresolved for entity %s (%s.%s): %s',
                entity.id, entity.schema_name, entity.name, source)
            return dict(empty, reason=source or 'unresolved')

        pk = self._dw_pk_column(entity, relation)
        if not pk:
            _logger.warning(
                'No PK column resolvable for entity %s on %s',
                entity.id, relation)
            return dict(empty, reason='no-pk')

        clause, params = self._build_dw_where(
            search_term, self._dw_search_columns(entity, relation))
        where = 'WHERE ' + clause if clause else ''

        self.env.cr.execute(
            'SELECT COUNT(*) FROM %s t %s' % (relation, where), params)
        total = self.env.cr.fetchone()[0]

        offset = max(int(offset or 0), 0)
        limit = max(int(limit or 10), 1)
        self.env.cr.execute(
            'SELECT t.* FROM %s t %s ORDER BY t.%s LIMIT %%s OFFSET %%s'
            % (relation, where, pk), params + [limit, offset])
        cols = [c[0] for c in self.env.cr.description]
        raw = [dict(zip(cols, r)) for r in self.env.cr.fetchall()]
        records = [self._dw_normalize_record(r, pk) for r in raw]
        return {'records': records, 'total': total, 'reason': None}

    def unlink(self):
        """Drop the DW table on the linked MSSQL server, then delete the
        metadata.

        A refusal from ``ddl_builder.drop_table`` (non-empty table or
        incoming foreign keys) aborts the whole unlink *before* any
        metadata is removed, so the entity is left untouched.
        """
        for entity in self:
            if not entity.schema_name or not entity.name:
                continue
            conn = entity._get_dw_connection()
            if not conn:
                continue
            ddl_builder.drop_table(conn, entity.schema_name, entity.name)

        self.env['raes.md.entity.config'].sudo().search(
            [('entity_id', 'in', self.ids)]).unlink()

        return super().unlink()

    # ------------------------------------------------------------------
    # Category Manager helpers
    # ------------------------------------------------------------------
    @api.model
    def get_category_tree(self):
        """Return the categories the current user can see, as a flat list.

        Scoped to every company the user has currently selected in the
        Odoo company switcher (``env.companies``), not just the active
        one — so checking two companies shows both companies' trees.
        Orphans (parent in an unselected company) are promoted to roots.
        """
        allowed_ids = self.env.companies.ids
        if not allowed_ids:
            return []

        cats = self.env['raes.md.category'].search_read(
            [('company_id', 'in', allowed_ids)],
            ['id', 'title', 'parent_id', 'entity_id', 'code', 'company_id'],
            order='title',
        )
        if not cats:
            return []

        visible_ids = {c['id'] for c in cats}
        for c in cats:
            if c['parent_id'] and c['parent_id'][0] not in visible_ids:
                c['parent_id'] = False
                c['_orphan'] = True
        return cats

    # ------------------------------------------------------------------
    # DW relation resolution (pluggable seam)
    # ------------------------------------------------------------------
    _DW_SEARCH_COLUMN_WHITELIST = (
        'title', 'englishtitle', 'english_title', 'name', 'code',
        'companytitle', 'partytitle',
    )

    def _dw_resolve_relation(self, entity):
        """Return ``(connection, local_relation, source)`` for `entity`."""
        if not entity.name:
            return None, None, 'no-table-name'

        conn = entity._get_dw_connection()
        if not conn:
            return None, None, 'no-connection'

        wanted = entity.name.lower()

        line = conn.line_ids.filtered(
            lambda l: l.remote_table.lower() == wanted)[:1]
        if line and line.local_view_name:
            return conn, line.local_view_name, 'table_map'

        cr = self.env.cr
        schemas = ['fdw_raes']
        if conn.remote_schema and conn.remote_schema not in schemas:
            schemas.append(conn.remote_schema)
        for schema in schemas:
            cr.execute(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = %s AND lower(c.relname) = %s "
                "AND c.relkind IN ('r', 'v', 'f', 'm', 'p') "
                "ORDER BY (c.relkind = 'f') DESC, c.relname LIMIT 1",
                [schema, wanted])
            row = cr.fetchone()
            if row:
                return conn, f'{schema}.{_quote_ident(row[0])}', \
                    f'catalog:{schema}'

        return conn, None, 'not-imported'

    def _dw_column_names(self, relation):
        """Real column names present on `relation`, lowercased."""
        if not relation:
            return set()
        schema, table = _split_relation(relation)
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND lower(table_name) = %s",
            [schema, table.lower()])
        return {r[0].lower() for r in self.env.cr.fetchall()}

    def _dw_pk_column(self, entity, relation):
        """Local (lowercased) PK column of the DW relation."""
        available = self._dw_column_names(relation)
        if not available:
            return None

        catalog = self.env['raes.md.entity_column'].search(
            [('entity_id', '=', entity.id),
             ('is_primary_key', '=', True)], limit=1)
        if catalog and catalog.name:
            cand = _localize_name(catalog.name, available)
            if cand:
                return cand

        ids = sorted(c for c in available if c.endswith('id'))
        return ids[0] if ids else None

    def _dw_search_columns(self, entity, relation):
        """Whitelisted columns that actually exist on `relation`."""
        available = self._dw_column_names(relation)
        if not available:
            return []
        cols = [c for c in self._DW_SEARCH_COLUMN_WHITELIST
                if c in available]
        if cols:
            return cols
        for col in self.env['raes.md.entity_column'].search(
                [('entity_id', '=', entity.id)]):
            if not col.name:
                continue
            cand = _localize_name(col.name, available)
            if cand and cand not in cols:
                cols.append(cand)
        return cols

    def _build_dw_where(self, search_term, columns=None):
        """Return ``(clause, params)`` for a free-text search.

        Both the search term and the underlying column values are passed
        through Persian/Arabic normalization so a search for ``ی``
        matches a stored ``ي`` and vice versa.
        """
        cols = list(columns if columns is not None
                    else self._DW_SEARCH_COLUMN_WHITELIST)
        if not search_term or not cols:
            return '', []
        normalized = _persian_normalize(search_term)
        clauses = []
        for c in cols:
            col_expr = _sql_persian_normalize(
                f'CAST(t.{c} AS TEXT)',
                term=normalized, dialect='postgresql')
            clauses.append(f'{col_expr} ILIKE %s')
        return '(' + ' OR '.join(clauses) + ')', [f'%{normalized}%'] * len(cols)

    def _dw_pane(self, entity_id, category_id, offset, limit, search_term,
                 in_category):
        """Shared implementation of the two category item panes.

        Legacy Postgres path. The active category manager uses
        ``_dw_category_pane`` (MSSQL) instead.
        """
        empty = {'records': [], 'total': 0, 'reason': None}
        entity = self.browse(entity_id)
        if not entity.exists():
            return dict(empty, reason='no-entity')

        conn, relation, source = self._dw_resolve_relation(entity)
        if not relation:
            _logger.info(
                "DW relation unresolved for entity %s (%s.%s): %s",
                entity.id, entity.schema_name, entity.name, source)
            return dict(empty, reason=source or 'unresolved')

        pk = self._dw_pk_column(entity, relation)
        if not pk:
            _logger.warning(
                "No PK column resolvable for entity %s on %s",
                entity.id, relation)
            return dict(empty, reason='no-pk')

        clause, params = self._build_dw_where(
            search_term, self._dw_search_columns(entity, relation))
        op = 'IN' if in_category else 'NOT IN'
        sub = (
            f'SELECT member_id FROM md.category_member '
            f'WHERE category_id = %s AND entity_id = %s'
        )
        where = (f'WHERE {clause} AND t.{pk} {op} ({sub})' if clause
                 else f'WHERE t.{pk} {op} ({sub})')
        params = list(params) + [category_id, entity_id]

        self.env.cr.execute(
            f'SELECT COUNT(*) FROM {relation} t {where}', params)
        total = self.env.cr.fetchone()[0]

        offset = max(int(offset or 0), 0)
        limit = max(int(limit or 20), 1)
        self.env.cr.execute(
            f'SELECT t.* FROM {relation} t {where} '
            f'ORDER BY t.{pk} LIMIT %s OFFSET %s', params + [limit, offset])
        cols = [c[0] for c in self.env.cr.description]
        raw = [dict(zip(cols, r)) for r in self.env.cr.fetchall()]

        records = [self._dw_normalize_record(r, pk) for r in raw]
        return {'records': records, 'total': total, 'reason': None}

    _DW_LABEL_CANDIDATES = (
        'title', 'name', 'englishtitle', 'english_title', 'codetitle',
        'companytitle', 'partytitle', 'valuetitle', 'value',
    )

    def _dw_normalize_record(self, record, pk):
        rec = {k.lower(): v for k, v in record.items()}
        pk_val = rec.get(pk.lower())
        rec['id'] = '' if pk_val is None else str(pk_val)
        rec['_pk'] = pk.lower()
        rec[rec['_pk']] = str(rec[rec['_pk']])

        label = None
        for cand in self._DW_LABEL_CANDIDATES:
            val = rec.get(cand)
            if val not in (None, False, ''):
                label = str(val).strip()
                break
        rec['label'] = label or (f'#{rec["id"]}' if rec['id'] else '—')
        return rec

    @api.model
    def get_dw_pane_diagnostics(self, entity_id):
        """Explain why a pane may be empty for `entity_id`."""
        entity = self.browse(entity_id)
        if not entity.exists():
            return {'error': 'Entity %s does not exist.' % entity_id}
        conn, relation, source = self._dw_resolve_relation(entity)
        return {
            'entity': entity.display_name,
            'schema': entity.schema_name or '',
            'table': entity.name or '',
            'connection_id': conn.id if conn else None,
            'relation': relation,
            'source': source,
            'pk': self._dw_pk_column(entity, relation) if relation else None,
            'search_columns': (self._dw_search_columns(entity, relation)
                               if relation else []),
        }

    # ------------------------------------------------------------------
    # Category pane fetch — LOCAL membership, REMOTE (MSSQL) row data
    # ------------------------------------------------------------------
    @api.model
    def get_items_not_in_category(self, entity_id, category_id,
                                  offset=0, limit=20, search_term='',
                                  search_column=None):
        return self._dw_category_pane(
            entity_id, category_id, offset, limit, search_term,
            in_category=False, search_column=search_column)

    @api.model
    def get_items_in_category(self, entity_id, category_id,
                              offset=0, limit=20, search_term='',
                              search_column=None):
        return self._dw_category_pane(
            entity_id, category_id, offset, limit, search_term,
            in_category=True, search_column=search_column)

    def _dw_connection_for(self, entity):
        """Return the raes.dw.connection for this entity, or empty recordset."""
        config = self.env['raes.md.entity.config'].sudo().search(
            [('entity_id', '=', entity.id)], limit=1)
        return config.connection_id if config else self.env['raes.dw.connection']

    def _dw_mssql_open(self, connection):
        """Open the pymssql connection shared with the DDL builder."""
        return self.env['raes.dw.catalog']._mssql_connect(connection)

    def _dw_remote_pk(self, cur, entity):
        """PK column name on the MSSQL side."""
        meta_pk = entity.column_ids.filtered(lambda c: c.is_primary_key)[:1]
        if meta_pk and meta_pk.name:
            return meta_pk.name
        cur.execute("""
                    SELECT kcu.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                             JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                                  ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                                      AND kcu.TABLE_SCHEMA = tc.TABLE_SCHEMA
                                      AND kcu.TABLE_NAME = tc.TABLE_NAME
                    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                      AND tc.TABLE_SCHEMA = %s
                      AND tc.TABLE_NAME = %s
                    ORDER BY kcu.ORDINAL_POSITION
                    """, (entity.schema_name, entity.name))
        row = cur.fetchone()
        return row[0] if row else None

    def _dw_remote_search_columns(self, entity):
        """Text-like, non-PK columns that are safe to ILIKE-search."""
        text_types = {'varchar', 'nvarchar', 'char', 'nchar'}
        return [
            c.name for c in entity.column_ids
            if c.name
               and (c.data_type or '').lower() in text_types
               and not c.is_primary_key
        ]

    def _dw_category_pane(self, entity_id, category_id, offset, limit,
                          search_term, in_category, search_column=None):
        """Fetch one page for one side of the Category Manager.

        ``search_column`` — when set, the free-text filter is applied to
        only that DW column; when empty, it applies to the default
        whitelist of text columns. Both the search term and the stored
        value are passed through Persian/Arabic normalization so ``ی``
        matches ``ي``.
        """
        empty = {'records': [], 'total': 0, 'reason': None}

        entity = self.browse(entity_id)
        if not entity.exists():
            return dict(empty, reason='no-entity')

        category = self.env['raes.md.category'].browse(category_id)
        if not category.exists():
            return dict(empty, reason='no-entity')

        connection = self._dw_connection_for(entity)
        if not connection:
            return dict(empty, reason='no-connection')
        if not entity.schema_name or not entity.name:
            return dict(empty, reason='no-table')

        # --- Company scope -------------------------------------------
        allowed = set(self.env.companies.ids)
        if category.company_id and category.company_id.id in allowed:
            company_id = category.company_id.id
        elif category.company_id:
            _logger.info(
                "Category %s belongs to company %s which is not in %s",
                category_id, category.company_id.id, allowed)
            return dict(empty, reason='company-mismatch')
        else:
            company_id = self.env.company.id

        # 1. Members from the LOCAL postgres side -------------------------
        self.env.cr.execute(
            "SELECT member_id FROM md.category_member "
            "WHERE category_id = %s AND entity_id = %s",
            (category_id, entity_id))
        member_ids = [r[0] for r in self.env.cr.fetchall()]

        if in_category and not member_ids:
            return empty

        # 2. Open the MSSQL session and resolve identifiers ---------------
        ms = None
        try:
            ms = self._dw_mssql_open(connection)
            cur = ms.cursor()

            pk = self._dw_remote_pk(cur, entity)
            if not pk:
                return dict(empty, reason='no-pk')

            if search_column:
                wanted = search_column.lower()
                real = next(
                    (c.name for c in entity.column_ids
                     if c.name and c.name.lower() == wanted),
                    None,
                ) or search_column
                search_cols = [real]
            else:
                search_cols = self._dw_remote_search_columns(entity)

            table = ddl_builder._qfull(connection.database,
                                       entity.schema_name, entity.name)
            pk_q = ddl_builder._q(pk)

            company_col = next(
                (c.name for c in entity.column_ids
                 if c.name and c.name.lower() in ('companyid', 'company_id')),
                None,
            ) or 'CompanyID'
            company_q = ddl_builder._q(company_col)

            # 3. Build the WHERE clause (pymssql: %s placeholders) --------
            where_parts = []
            params = []

            where_parts.append(f'CAST({company_q} AS INT) = %s')
            params.append(company_id)

            if search_term and search_cols:
                normalized_term = _persian_normalize(search_term)
                likes = []
                for col in search_cols:
                    col_expr = _sql_persian_normalize(
                        f'CAST({ddl_builder._q(col)} AS NVARCHAR(MAX))',
                        term=normalized_term, dialect='mssql')
                    likes.append(f'{col_expr} LIKE %s')
                    params.append(f'%{normalized_term}%')
                where_parts.append('(' + ' OR '.join(likes) + ')')

            if member_ids:
                placeholders = ','.join(['%s'] * len(member_ids))
                op = 'IN' if in_category else 'NOT IN'
                where_parts.append(f'{pk_q} {op} ({placeholders})')
                params.extend(member_ids)

            where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts \
                else ''

            # 4. Count ---------------------------------------------------
            cur.execute(
                f'SELECT COUNT_BIG(*) FROM {table} {where_sql}',
                tuple(params))
            row = cur.fetchone()
            total = int(row[0] or 0) if row else 0

            if total == 0:
                return empty

            # 5. Page ----------------------------------------------------
            cur.execute(
                f'SELECT * FROM {table} {where_sql} '
                f'ORDER BY {pk_q} '
                f'OFFSET %s ROWS FETCH NEXT %s ROWS ONLY',
                tuple(params + [offset, limit]))
            cols = [d[0] for d in cur.description]
            raw = [dict(zip((c.lower() for c in cols), r))
                   for r in cur.fetchall()]

            records = [self._dw_normalize_record(r, pk.lower()) for r in raw]
            return {'records': records, 'total': total, 'reason': None}

        except Exception:
            _logger.exception(
                "MSSQL DW pane fetch failed for entity %s (%s.%s)",
                entity_id, entity.schema_name, entity.name)
            return dict(empty, reason='connection-error')
        finally:
            if ms is not None:
                try:
                    ms.close()
                except Exception:
                    pass
