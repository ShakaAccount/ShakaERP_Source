"""Materialise entity metadata as real MSSQL tables.

Executes DDL against the MSSQL server behind ``raes.dw.connection`` using
pymssql, over the same connection machinery the DW connector already uses.

Idempotent: re-running with unchanged metadata is a no-op. Additive only
— it creates missing tables/columns and refreshes FKs. It does NOT drop
columns or change existing column types, to protect DW data.
"""
import logging

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


MSSQL_TYPE_MAP = {
    'bigint':   'BIGINT',
    'int':      'INT',
    'tinyint':  'TINYINT',
    'bit':      'BIT',
    'decimal':  'DECIMAL',
    'float':    'FLOAT',
    'date':     'DATE',
    'datetime': 'DATETIME',
    'time':     'TIME',
    'varchar':  'VARCHAR',
    'nvarchar': 'NVARCHAR',
    'char':     'CHAR',
    'nchar':    'NCHAR',
}

SIZED_TYPES = {'varchar', 'nvarchar', 'char', 'nchar'}
PRECISION_TYPES = {'decimal'}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _q(name):
    """Quote a T-SQL identifier."""
    return '[' + (name or '').replace(']', ']]') + ']'


def _esc_str(value):
    return str(value or '').replace("'", "''")


def _tsql_type(data_type, size):
    key = (data_type or '').lower()
    base = MSSQL_TYPE_MAP.get(key)
    if not base:
        raise UserError(_("Unsupported data type: %s", data_type))

    if key in SIZED_TYPES and size:
        raw = str(size).strip()
        if raw.lower() == 'max' and key in ('varchar', 'nvarchar'):
            return f'{base}(MAX)'
        try:
            return f'{base}({int(raw)})'
        except (ValueError, TypeError):
            raise UserError(_(
                "Invalid size '%(s)s' for %(t)s.", s=size, t=data_type))

    if key in PRECISION_TYPES:
        raw = str(size or '').strip()
        if not raw:
            return 'DECIMAL(18,2)'
        parts = [p.strip() for p in raw.replace(',', ' ').split() if p.strip()]
        try:
            if len(parts) == 1:
                return f'DECIMAL({int(parts[0])},0)'
            if len(parts) == 2:
                return f'DECIMAL({int(parts[0])},{int(parts[1])})'
        except (ValueError, TypeError):
            pass
        raise UserError(_(
            "Invalid decimal size '%s'. Use 'precision,scale'.", size))

    return base


def _get_connection(entity):
    """Return the raes.dw.connection linked to an entity, or empty."""
    config = entity.env['raes.md.entity.config'].sudo().search(
        [('entity_id', '=', entity.id)], limit=1)
    return config.connection_id if config else entity.env['raes.dw.connection']


def _open(connection):
    """Open a pymssql connection through the DW connector's own helper."""
    catalog = connection.env['raes.dw.catalog']
    return catalog._mssql_connect(connection)


def _schema_exists(cur, schema):
    cur.execute("SELECT 1 FROM sys.schemas WHERE name = %s", (schema,))
    return cur.fetchone() is not None


def _table_exists(cur, schema, table):
    cur.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (schema, table))
    return cur.fetchone() is not None


def _existing_columns(cur, schema, table):
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (schema, table))
    return {r[0].lower() for r in cur.fetchall()}


# ----------------------------------------------------------------------
# DDL steps
# ----------------------------------------------------------------------
def _create_schema(cur, schema):
    cur.execute(f'CREATE SCHEMA {_q(schema)}')


def _create_table(cur, schema, table, columns):
    if not columns:
        raise UserError(_(
            "Entity '%s' has no columns; cannot create the table.") % table)

    pk = columns.filtered(lambda c: c.is_primary_key)[:1]
    pieces = []
    for col in columns.sorted('ordinal_position'):
        piece = f'{_q(col.name)} {_tsql_type(col.data_type, col.size)}'
        if col.is_primary_key and col.is_identity:
            piece += ' IDENTITY(1,1)'
        if col.is_primary_key:
            piece += ' NOT NULL'
        pieces.append(piece)
    if pk:
        pieces.append(f'PRIMARY KEY ({_q(pk.name)})')

    sql = (f'CREATE TABLE {_q(schema)}.{_q(table)} (\n  '
           + ',\n  '.join(pieces) + '\n)')
    _logger.info("DW DDL (MSSQL): %s", sql)
    cur.execute(sql)


def _add_missing_columns(cur, schema, table, columns):
    existing = _existing_columns(cur, schema, table)
    for col in columns.sorted('ordinal_position'):
        if col.name.lower() in existing:
            continue
        # Note: T-SQL forbids adding an IDENTITY column to an existing
        # table. If a new column is marked is_identity, we add it as a
        # plain column; adjust manually if you truly need IDENTITY.
        piece = f'{_q(col.name)} {_tsql_type(col.data_type, col.size)}'
        sql = f'ALTER TABLE {_q(schema)}.{_q(table)} ADD {piece}'
        _logger.info("DW DDL (MSSQL): %s", sql)
        cur.execute(sql)


def _sync_fks(cur, schema, table, columns):
    # Drop every FK we manage for this table (prefix fk_<table>_)
    prefix = f'fk_{table}_'
    cur.execute("""
        SELECT fk.name
          FROM sys.foreign_keys fk
          JOIN sys.tables t  ON t.object_id = fk.parent_object_id
          JOIN sys.schemas s ON s.schema_id = t.schema_id
         WHERE s.name = %s AND t.name = %s
           AND fk.name LIKE %s
    """, (schema, table, prefix + '%'))
    for (fk_name,) in cur.fetchall():
        cur.execute(
            f'ALTER TABLE {_q(schema)}.{_q(table)} '
            f'DROP CONSTRAINT {_q(fk_name)}')

    for col in columns:
        ref = col.reference_entity_id
        if not ref or not ref.schema_name or not ref.name:
            continue
        ref_pk = ref.column_ids.filtered(lambda c: c.is_primary_key)[:1]
        if not ref_pk:
            continue
        fk_name = (f'fk_{table}_{col.name}')[:128]      # MSSQL limit
        sql = (
            f'ALTER TABLE {_q(schema)}.{_q(table)} '
            f'ADD CONSTRAINT {_q(fk_name)} '
            f'FOREIGN KEY ({_q(col.name)}) '
            f'REFERENCES {_q(ref.schema_name)}.{_q(ref.name)} '
            f'({_q(ref_pk.name)})')
        _logger.info("DW DDL (MSSQL): %s", sql)
        cur.execute(sql)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def sync_table(connection, entity):
    """Create or update the MSSQL table for ``entity`` on ``connection``."""
    if not connection:
        return
    if not entity.schema_name or not entity.name:
        return

    ms = _open(connection)
    try:
        cur = ms.cursor()
        if not _schema_exists(cur, entity.schema_name):
            _create_schema(cur, entity.schema_name)

        columns = entity.column_ids
        if not _table_exists(cur, entity.schema_name, entity.name):
            _create_table(cur, entity.schema_name, entity.name, columns)
        else:
            _add_missing_columns(cur, entity.schema_name, entity.name, columns)

        _sync_fks(cur, entity.schema_name, entity.name, columns)
        ms.commit()
    except Exception:
        try:
            ms.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            ms.close()
        except Exception:
            pass


def rename_table(connection, old_schema, old_table, new_schema, new_table):
    """Rename and/or move a table. No-op when the source doesn't exist."""
    if not connection or not old_schema or not old_table:
        return

    ms = _open(connection)
    try:
        cur = ms.cursor()
        if not _table_exists(cur, old_schema, old_table):
            return

        cur_schema = old_schema
        if old_schema != new_schema:
            if not _schema_exists(cur, new_schema):
                _create_schema(cur, new_schema)
            cur.execute(
                f'ALTER SCHEMA {_q(new_schema)} TRANSFER '
                f'{_q(old_schema)}.{_q(old_table)}')
            cur_schema = new_schema

        if old_table != new_table:
            cur.execute(
                f"EXEC sp_rename "
                f"'{_esc_str(cur_schema)}.{_esc_str(old_table)}', "
                f"'{_esc_str(new_table)}'")

        ms.commit()
    except Exception:
        try:
            ms.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            ms.close()
        except Exception:
            pass


def rename_column(connection, schema, table, old_col, new_col):
    if (not connection or not schema or not table
            or not old_col or not new_col or old_col == new_col):
        return

    ms = _open(connection)
    try:
        cur = ms.cursor()
        if not _table_exists(cur, schema, table):
            return
        existing = _existing_columns(cur, schema, table)
        if old_col.lower() not in existing or new_col.lower() in existing:
            return
        cur.execute(
            f"EXEC sp_rename "
            f"'{_esc_str(schema)}.{_esc_str(table)}.{_esc_str(old_col)}', "
            f"'{_esc_str(new_col)}', 'COLUMN'")
        ms.commit()
    except Exception:
        try:
            ms.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            ms.close()
        except Exception:
            pass