from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


def _ident(name):
    # trust boundary: identifier comes from admin input -> quote strictly
    return '"' + (name or '').replace('"', '""') + '"'


class RaesDwConnection(models.Model):
    _name = 'raes.dw.connection'
    _description = 'Shaka_DW Foreign Data Connection (tds_fdw)'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    host = fields.Char(required=True, default='127.0.0.1')
    port = fields.Integer(required=True, default=1433)
    database = fields.Char(string='MSSQL Database', required=True)
    mssql_user = fields.Char(string='MSSQL User', required=True)
    mssql_password = fields.Char(string='MSSQL Password', password=True)
    remote_schema = fields.Char(default='BI', required=True,
                                help='MSSQL schema holding the Dim tables.')
    tables_to_import = fields.Text(
        string='Remote Tables',
        default='DimCompany, DimParty, DimCostCenter',
        help='Comma-separated MSSQL table names imported as foreign tables.')
    line_ids = fields.One2many('raes.dw.table_map', 'connection_id',
                               string='Odoo View Mapping',
                               help='Maps each imported foreign table to the '
                                    'public view the dim models read from.')
    active = fields.Boolean(default=True)
    last_test = fields.Datetime(readonly=True)
    last_test_result = fields.Text(readonly=True)
    last_bootstrap = fields.Datetime(readonly=True)

    # ------------------------------------------------------------------
    def _server_name(self):
        return f"raes_dw_{self.id}"

    def _server_options(self):
        esc = lambda v: str(v).replace("'", "''")
        return ("servername '%s', port '%s', database '%s'"
                % (esc(self.host), esc(self.port), esc(self.database)))

    def _ensure_server_and_mapping(self, server_name):
        cr = self.env.cr
        esc = lambda v: str(v).replace("'", "''")
        cr.execute("SELECT 1 FROM pg_foreign_server WHERE srvname = %s",
                   [server_name])
        exists = cr.fetchone()
        if exists:
            cr.execute(f"ALTER SERVER {_ident(server_name)} "
                       f"OPTIONS (SET servername '{esc(self.host)}', "
                       f"SET port '{esc(self.port)}', "
                       f"SET database '{esc(self.database)}')")
        else:
            cr.execute(f"CREATE SERVER {_ident(server_name)} "
                       f"FOREIGN DATA WRAPPER tds_fdw "
                       f"OPTIONS ({self._server_options()})")
        db_user = cr._cnx.info.user  # role the odoo process connects as
        cr.execute("SELECT 1 FROM pg_user_mappings WHERE srvname = %s "
                   "AND usename = %s", [server_name, db_user])
        if cr.fetchone():
            cr.execute(f"DROP USER MAPPING FOR {_ident(db_user)} "
                       f"SERVER {_ident(server_name)}")
        cr.execute(f"CREATE USER MAPPING FOR {_ident(db_user)} "
                   f"SERVER {_ident(server_name)} OPTIONS "
                   f"(username '{esc(self.mssql_user)}', "
                   f"password '{esc(self.mssql_password or '')}')")

    def _remote_tables(self):
        tables = [t.strip() for t in (self.tables_to_import or '').split(',')
                  if t.strip()]
        return tables or ['sysdiagrams']

    # ---------------- table explorer ----------------

    def _scratch_schema(self):
        return f"fdw_raes"

    def action_browse_tables(self):
        """IMPORT FOREIGN SCHEMA (full) into a throwaway schema, list every
        remote table as a selectable tree row, drop the throwaway schema."""
        for rec in self:
            cr = rec.env.cr
            server = rec._server_name()
            probe = f"_fdw_browse_{rec.id}"
            rec._ensure_server_and_mapping(server)
            cr.execute(f"DROP SCHEMA IF EXISTS {_ident(probe)} CASCADE")
            cr.execute(f"CREATE SCHEMA {_ident(probe)}")
            cr.execute(
                f"IMPORT FOREIGN SCHEMA {_ident(rec.remote_schema)} "
                f"FROM SERVER {_ident(server)} INTO {_ident(probe)}")
            cr.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s ORDER BY table_name", [probe])
            tables = [r[0] for r in cr.fetchall()]
            cr.execute(f"DROP SCHEMA {_ident(probe)} CASCADE")
            # already-mapped names preselected
            mapped = {l.remote_table.lower() for l in rec.line_ids}
            cr.execute("DELETE FROM raes_dw_remote_table "
                       "WHERE connection_id = %s", [rec.id])
            for t in tables:
                cr.execute(
                    "INSERT INTO raes_dw_remote_table "
                    "(connection_id, remote_schema, remote_table, selected) "
                    "VALUES (%s, %s, %s, %s)",
                    [rec.id, rec.remote_schema, t, t.lower() in mapped])
            cr.commit()
            return {
                'type': 'ir.actions.act_window',
                'name': _('جداول %(db)s', db=rec.database),
                'res_model': 'raes.dw.remote_table',
                'view_mode': 'list,form',
                'domain': [('connection_id', '=', rec.id)],
                'target': 'current',
            }

    def action_import_selected(self, row_ids=None):
        """For selected explorer rows (or all mapped lines): import the
        foreign table if missing and create its public alias view."""
        rows = self.env['raes.dw.remote_table'].browse(row_ids or [])
        for row in rows:
            conn = row.connection_id
            cr = conn.env.cr
            server = conn._server_name()
            schema = conn._scratch_schema()
            table = row.remote_table
            conn._ensure_server_and_mapping(server)
            cr.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(schema)}")
            cr.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = %s AND lower(table_name) = %s",
                [schema, table.lower()])
            if cr.fetchone()[0] == 0:
                cr.execute(
                    f"IMPORT FOREIGN SCHEMA {_ident(row.remote_schema)} "
                    f"LIMIT TO ({_ident(table)}) FROM SERVER "
                    f"{_ident(server)} INTO {_ident(schema)}")
            local = 'raes_' + ''.join(
                c for c in table.lower() if c.isalnum() or c == '_')
            src = f"{_ident(schema)}.{_ident(table)}"
            cr.execute(
                f"DROP VIEW IF EXISTS public.{_ident(local)}")
            cr.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position", [schema, table])
            cols = [r[0] for r in cr.fetchall()]
            sel = ", ".join(f"{_ident(c)} AS {c.lower().replace(' ', '_')}"
                            for c in cols)
            cr.execute(
                f"CREATE VIEW public.{_ident(local)} AS SELECT {sel} FROM {src}")
            if not conn.line_ids.filtered(
                    lambda l: l.remote_table.lower() == table.lower()):
                conn.write({'line_ids': [(0, 0, {
                    'remote_table': table,
                    'local_view_name': local,
                })]})
            row_count = 0
            try:
                cr.execute(f"SELECT count(*) FROM {src}")
                row_count = cr.fetchone()[0]
            except Exception:
                cr.rollback()
            row.write({'selected': False, 'row_count': row_count})
        self.env.cr.commit()
        return True

    def action_test_connection(self):
        for rec in self:
            server = f"_fdw_test_{rec.id}"
            schema = "_fdw_test"
            cr = rec.env.cr
            try:
                rec._ensure_server_and_mapping(server)
                cr.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(schema)}")
                table = rec._remote_tables()[0]
                cr.execute(
                    f"IMPORT FOREIGN SCHEMA {_ident(rec.remote_schema)} "
                    f"LIMIT TO ({_ident(table)}) FROM SERVER "
                    f"{_ident(server)} INTO {_ident(schema)}")
                cr.execute(f"SELECT count(*) FROM "
                           f"{_ident(schema)}.{_ident(table)}")
                n = cr.fetchone()[0]
                cr.commit()
                rec.write({
                    'last_test': fields.Datetime.now(),
                    'last_test_result':
                        _("OK — '%s' reachable, %s rows", table, n),
                })
            except Exception as e:
                rec.env.cr.rollback()
                rec.write({
                    'last_test': fields.Datetime.now(),
                    'last_test_result': _("FAIL — %s", str(e)[:500]),
                })
                raise UserError(_('اتصال برقرار نشد:\n%s', str(e)[:500]))
            finally:
                try:
                    cr.execute(f"DROP SCHEMA IF EXISTS {_ident(schema)} CASCADE")
                    cr.execute(f"DROP SERVER IF EXISTS {_ident(server)} CASCADE")
                    cr.commit()
                except Exception:
                    rec.env.cr.rollback()

    def action_bootstrap(self):
        """Create/refresh server + user mapping + foreign tables + the public
        alias views the dim models read (raes_dim_*_view). No shell needed."""
        for rec in self:
            cr = rec.env.cr
            server = rec._server_name()
            schema = 'fdw_raes'
            ok, skipped = [], []
            rec._ensure_server_and_mapping(server)
            cr.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(schema)}")
            for table in rec._remote_tables():
                try:
                    # tds_fdw matches LIMIT TO names case-sensitively; quote
                    # them so remote casing (DimCompany) is preserved
                    cr.execute(
                        f"IMPORT FOREIGN SCHEMA {_ident(rec.remote_schema)} "
                        f"LIMIT TO ({', '.join(_ident(t) for t in [table])}) "
                        f"FROM SERVER {_ident(server)} INTO {_ident(schema)}")
                    cr.execute(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = %s AND lower(table_name) = %s",
                        [schema, table.lower()])
                    if cr.fetchone()[0] == 0:
                        raise Exception(f"remote table {table} not found")
                    ok.append(table)
                except Exception as e:
                    cr.rollback()
                    cr.execute("SELECT 1 FROM information_schema.tables "
                               "WHERE table_schema=%s AND lower(table_name)=%s",
                               [schema, table.lower()])
                    if cr.fetchone():
                        skipped.append(table)
                    else:
                        raise UserError(_(
                            "جدول %(t)s در اسکیمای %(s)s پیدا نشد: %(e)s",
                            t=table, s=rec.remote_schema, e=str(e)[:200]))
            for table in ok + skipped:
                # one public alias view per imported table (lowercased cols);
                # the mapping line is registered on the fly so the dim models
                # find the view without a second manual step
                line = rec.line_ids.filtered(
                    lambda l: l.remote_table.lower() == table.lower())[:1]
                local = line.local_view_name if line else 'raes_' + ''.join(
                    c for c in table.lower() if c.isalnum() or c == '_')
                src = f"{_ident(schema)}.{_ident(table)}"
                cr.execute(
                    f"DROP VIEW IF EXISTS public.{_ident(local)}")
                # foreign columns keep MSSQL casing; dim models expect
                # lowercase -> alias every column to lower()
                cr.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s "
                    "ORDER BY ordinal_position",
                    [schema, table])
                cols = [r[0] for r in cr.fetchall()]
                sel = ", ".join(
                    f"{_ident(c)} AS {c.lower().replace(' ', '_')}"
                    for c in cols)
                cr.execute(
                    f"CREATE VIEW public.{_ident(local)} AS "
                    f"SELECT {sel} FROM {src}")
                if not line:
                    rec.write({'line_ids': [(0, 0, {
                        'remote_table': table,
                        'local_view_name': local})]})
            cr.commit()
            # point the dim models at the freshly built alias views
            for model in ('odoo.raes.dim.company', 'odoo.raes.dim.party',
                          'odoo.raes.dim.cost_center'):
                self.env[model].init()
            cr.commit()
            rec.write({'last_bootstrap': fields.Datetime.now()})
            rec.message_post(body=_(
                "Bootstrap done. Imported: %(ok)s. Already existed: "
                "%(skip)s. Views refreshed: %(views)s",
                ok=', '.join(ok) or '-',
                skip=', '.join(skipped) or '-',
                views=', '.join(rec.line_ids.mapped('local_view_name')) or '-'))


class RaesDwTableMap(models.Model):
    _name = 'raes.dw.table_map'
    _description = 'DW Foreign Table -> Odoo Public View Mapping'

    connection_id = fields.Many2one(
        'raes.dw.connection', required=True, ondelete='cascade')
    remote_table = fields.Char(required=True)
    local_view_name = fields.Char(string='Local View', required=True)


class RaesDwRemoteTable(models.Model):
    """Browse result of IMPORT FOREIGN SCHEMA: every remote table as a tree
    row; ticking rows and running the action creates the alias views."""
    _name = 'raes.dw.remote_table'
    _description = 'Remote DW Table (explorer row)'
    _order = 'remote_schema, remote_table'

    connection_id = fields.Many2one(
        'raes.dw.connection', required=True, ondelete='cascade')
    remote_schema = fields.Char(string='Schema', required=True)
    remote_table = fields.Char(string='Table', required=True)
    selected = fields.Boolean(string='انتخاب', default=False)
    row_count = fields.Integer(string='Rows', readonly=True)
    mapped_view = fields.Char(compute='_compute_mapped_view')

    def _compute_mapped_view(self):
        for rec in self:
            rec.mapped_view = rec.connection_id.line_ids.filtered(
                lambda l: l.remote_table.lower() == rec.remote_table.lower()
            ).mapped('local_view_name')[:1] or ''

    _remote_table_uniq = models.Constraint(
        'UNIQUE (connection_id, remote_schema, remote_table)',
        'Table listed once per connection')

    def action_make_views(self):
        """Create public alias views (lowercase cols) for selected rows and
        register them as mapping lines. Foreign tables are imported into the
        fdw_raes scratch schema of the parent connection first."""
        for rec in self:
            conn = rec.connection_id
            conn.action_import_selected(rec.ids)
        return True
