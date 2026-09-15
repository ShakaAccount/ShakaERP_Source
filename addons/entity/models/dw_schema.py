from odoo import api, fields, models


class RaesDwSchema(models.Model):
    """Read-only mirror of the distinct schemas in every DW connection.

    Backed by a PostgreSQL view over ``raes_dw_catalog`` so it always
    reflects the current catalog without any explicit sync step.
    """
    _name = 'raes.dw.schema'
    _description = 'DW Schema'
    _auto = False
    _log_access = False
    _order = 'connection_id, name'
    _rec_name = 'name'

    name = fields.Char(index=True)
    connection_id = fields.Many2one(
        'raes.dw.connection', string='Connection',
        index=True)

    def init(self):
        cr = self.env.cr

        # The earlier version of this model created a real TABLE. Drop
        # whatever is currently in the way — table OR view — before we
        # recreate it as a view. PostgreSQL has no single "DROP ANY", so
        # check pg_class.relkind first.
        cr.execute("""
            SELECT relkind
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = current_schema()
               AND c.relname = 'raes_dw_schema'
        """)
        row = cr.fetchone()
        if row:
            kind = row[0]
            if kind == 'v':
                cr.execute("DROP VIEW raes_dw_schema CASCADE")
            elif kind == 'm':
                cr.execute("DROP MATERIALIZED VIEW raes_dw_schema CASCADE")
            elif kind == 'r':
                cr.execute("DROP TABLE raes_dw_schema CASCADE")

        cr.execute("""
            CREATE VIEW raes_dw_schema AS
            SELECT row_number() OVER (
                       ORDER BY connection_id, schema_name) AS id,
                   schema_name  AS name,
                   connection_id
              FROM (SELECT DISTINCT connection_id, schema_name
                      FROM raes_dw_catalog
                     WHERE active = TRUE
                       AND schema_name IS NOT NULL) t
        """)