# Copyright 2011 Daniel Reis
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
"""SQL Server + generic ODBC adapters for base_external_dbsource.

pyodbc is the only driver: MS ODBC Driver 18 for SQL Server handles MSSQL
(and any other DB with an ODBC driver), so no pymssql/mysql-connector needed.
"""

import logging

import pyodbc

from odoo import fields, models

_logger = logging.getLogger(__name__)


class BaseExternalDbsource(models.Model):
    """Inherits base.external.dbsource, adds MSSQL and ODBC connectors."""

    _inherit = "base.external.dbsource"

    connector = fields.Selection(
        selection_add=[
            ("mssql", "Microsoft SQL Server (ODBC)"),
            ("odbc", "ODBC"),
        ],
        ondelete={"mssql": "cascade", "odbc": "cascade"},
    )
    # pyodbc uses the same PWD=%s; placeholder as the base class.
    PWD_STRING = "PWD=%s;"

    @staticmethod
    def _normalize_odbc_conn(conn):
        # Textarea artifacts break ODBC parsing: the driver does NOT treat
        # newlines as separators, so "TSC=yes\nPWD=x" makes TSC's value
        # "yes\nPWD=x" -> 08001. Treat newlines as ';', trim every token.
        parts = (conn.replace("\r", "").replace("\n", ";")).split(";")
        return ";".join(p.strip() for p in parts if p.strip())

    # --- MSSQL (via ODBC Driver 18) ---

    def connection_close_mssql(self, connection):
        return connection.close()

    def connection_open_mssql(self):
        # normalize(): textarea newlines break attribute parsing (08001)
        return pyodbc.connect(self._normalize_odbc_conn(self.conn_string_full), timeout=15)

    def execute_mssql(self, query, params, metadata):
        return self._execute_odbc(query, params, metadata)

    # --- Generic ODBC ---

    def connection_close_odbc(self, connection):
        return connection.close()

    def connection_open_odbc(self):
        # normalize(): textarea newlines break attribute parsing (08001)
        return pyodbc.connect(self._normalize_odbc_conn(self.conn_string_full), timeout=15)

    def execute_odbc(self, query, params, metadata):
        return self._execute_odbc(query, params, metadata)

    def _execute_odbc(self, query, params, metadata):
        with self.connection_open() as connection:
            cur = connection.cursor()
            # psycopg2 %(name)s style -> pyodbc ? style
            py_params = list(params.values()) if isinstance(params, dict) else params
            cur.execute(query, py_params or ())
            cols = []
            if metadata and cur.description:
                cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return rows, cols
