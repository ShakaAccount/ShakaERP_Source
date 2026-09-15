"""Materialise entity metadata as real MSSQL tables.

Executes DDL against the MSSQL server behind ``raes.dw.connection`` using
pymssql, over the same connection machinery the DW connector already uses.

Every DDL statement uses three-part naming ``[database].[schema].[table]``
so it works regardless of the connection's default database.

Idempotent: re-running with unchanged metadata is a no-op. Additive only
— it creates missing tables/columns and refreshes FKs. It does NOT drop
columns or change existing column types, to protect DW data.

Physical column order
---------------------
MSSQL has no way to reorder columns on an existing table — new columns
always append to the end. To keep the physical order aligned with the
metadata's ``ordinal_position``, ``_upsert_table`` rebuilds the table
whenever the physical order diverges. It only does so when the table is
empty and has no incoming foreign keys; otherwise it raises a
``UserError`` explaining the conflict.

Two-pass over the entity's reference dependency tree:

    1. Create/alter every table in the tree (no FKs yet).
    2. Add FK constraints for every column whose reference is set.
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
    return '[' + (name or '').replace(']', ']]') + ']'


def _qfull(database, schema, table):
    """Return ``[database].[schema].[table]`` when database is given,
    otherwise ``[schema].[table]``."""
    if database:
        return f'{_q(database)}.{_q(schema)}.{_q(table)}'
    return f'{_q(schema)}.{_q(table)}'


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
    config = entity.env['raes.md.entity.config'].sudo().search(
        [('entity_id', '=', entity.id)], limit=1)
    return config.connection_id if config else entity.env['raes.dw.connection']


def _open(connection):
    catalog = connection.env['raes.dw.catalog']
    return catalog._mssql_connect(connection)


def _schema_exists(cur, schema):
    cur.execute("SELECT 1 FROM sys.schemas WHERE name = %s", (schema,))
    return cur.fetchone() is not None


def _table_exists(cur, database, schema, table):
    cur.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_CATALOG = %s "
        "  AND TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (database, schema, table))
    return cur.fetchone() is not None


def _existing_columns(cur, database, schema, table):
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_CATALOG = %s "
        "  AND TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (database, schema, table))
    return {r[0].lower() for r in cur.fetchall()}


def _physical_column_order(cur, database, schema, table):
    """Column names in the order MSSQL physically stores them."""
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_CATALOG = %s "
        "  AND TABLE_SCHEMA = %s AND TABLE_NAME = %s "
        "ORDER BY ORDINAL_POSITION",
        (database, schema, table))
    return [r[0] for r in cur.fetchall()]


def _expected_column_order(entity):
    """Column names in the order the metadata says they should be."""
    return [
        c.name for c in entity.column_ids
        .filtered(lambda c: c.name)
        .sorted('ordinal_position')
    ]


def _existing_pk_columns(cur, database, schema, table):
    cur.execute("""
        SELECT c.name
          FROM sys.key_constraints kc
          JOIN sys.tables t  ON t.object_id = kc.parent_object_id
          JOIN sys.schemas s ON s.schema_id = t.schema_id
          JOIN sys.index_columns ic
               ON ic.object_id = kc.parent_object_id
              AND ic.index_id  = kc.unique_index_id
          JOIN sys.columns c
               ON c.object_id = ic.object_id
              AND c.column_id = ic.column_id
         WHERE s.name = %s AND t.name = %s AND kc.type = 'PK'
         ORDER BY ic.key_ordinal
    """, (schema, table))
    return [r[0] for r in cur.fetchall()]


def _drop_pk_constraint(cur, database, schema, table):
    cur.execute("""
        SELECT kc.name
          FROM sys.key_constraints kc
          JOIN sys.tables t  ON t.object_id = kc.parent_object_id
          JOIN sys.schemas s ON s.schema_id = t.schema_id
         WHERE s.name = %s AND t.name = %s AND kc.type = 'PK'
    """, (schema, table))
    for (pk_name,) in cur.fetchall():
        cur.execute(
            f'ALTER TABLE {_qfull(database, schema, table)} '
            f'DROP CONSTRAINT {_q(pk_name)}')


def _entity_tree(root):
    order, seen = [], set()

    def visit(entity):
        if entity.id in seen:
            return
        if not entity.schema_name or not entity.name:
            return
        seen.add(entity.id)
        for col in entity.column_ids:
            ref = col.reference_entity_id
            if ref:
                visit(ref)
        order.append(entity)

    visit(root)
    return order


# ----------------------------------------------------------------------
# DDL steps
# ----------------------------------------------------------------------
def _create_schema(cur, schema):
    cur.execute(f'CREATE SCHEMA {_q(schema)}')


def _create_table(cur, database, schema, table, columns):
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

    sql = (f'CREATE TABLE {_qfull(database, schema, table)} (\n  '
           + ',\n  '.join(pieces) + '\n)')
    _logger.info("DW DDL (MSSQL): %s", sql)
    cur.execute(sql)


def _add_missing_columns(cur, database, schema, table, columns):
    existing = _existing_columns(cur, database, schema, table)
    for col in columns.sorted('ordinal_position'):
        if col.name.lower() in existing:
            continue
        piece = f'{_q(col.name)} {_tsql_type(col.data_type, col.size)}'
        sql = (f'ALTER TABLE {_qfull(database, schema, table)} '
               f'ADD {piece}')
        _logger.info("DW DDL (MSSQL): %s", sql)
        cur.execute(sql)


def _ensure_pk_constraint(cur, database, entity):
    schema, table = entity.schema_name, entity.name
    meta_pk = entity.column_ids.filtered(lambda c: c.is_primary_key)[:1]
    if not meta_pk:
        return

    existing_pk = _existing_pk_columns(cur, database, schema, table)
    if existing_pk == [meta_pk.name]:
        return

    if existing_pk:
        _drop_pk_constraint(cur, database, schema, table)

    pk_name = (f'pk_{table}')[:128]
    sql = (
        f'ALTER TABLE {_qfull(database, schema, table)} '
        f'ADD CONSTRAINT {_q(pk_name)} '
        f'PRIMARY KEY ({_q(meta_pk.name)})')
    _logger.info("DW DDL (MSSQL): %s", sql)
    cur.execute(sql)


def _rebuild_table_if_empty(cur, database, schema, table, columns):
    """Drop and recreate the table to enforce the physical column order.

    Refuses when the table contains rows or is referenced by an FK from
    another table.
    """
    cur.execute(
        f'SELECT COUNT_BIG(*) FROM {_qfull(database, schema, table)}')
    row = cur.fetchone()
    row_count = int(row[0] or 0) if row else 0
    if row_count > 0:
        raise UserError(_(
            "Cannot reorder the columns of %(d)s.%(s)s.%(t)s on the DW "
            "server: the table contains %(n)s row(s). MSSQL cannot "
            "reorder columns in place. Empty the table first, then "
            "sync again — or delete the entity so the table can be "
            "rebuilt cleanly.",
            d=database, s=schema, t=table, n=row_count))

    cur.execute("""
        SELECT sch.name, tab.name, fk.name
          FROM sys.foreign_keys fk
          JOIN sys.tables tab ON tab.object_id = fk.parent_object_id
          JOIN sys.schemas sch ON sch.schema_id = tab.schema_id
         WHERE fk.referenced_object_id = OBJECT_ID(%s)
    """, (f'{schema}.{table}',))
    refs = cur.fetchall() or []
    if refs:
        details = '\n  - '.join(f'{r[0]}.{r[1]}  ({r[2]})' for r in refs)
        raise UserError(_(
            "Cannot reorder the columns of %(d)s.%(s)s.%(t)s on the DW "
            "server: other tables reference it via foreign keys:\n  - "
            "%(det)s\n\nRemove those references first, or empty the "
            "referring tables.",
            d=database, s=schema, t=table, det=details))

    _logger.info(
        "DW DDL (MSSQL): rebuilding %s.%s.%s to enforce column order",
        database, schema, table)
    cur.execute(f'DROP TABLE {_qfull(database, schema, table)}')
    _create_table(cur, database, schema, table, columns)


def _upsert_table(cur, database, entity):
    schema, table = entity.schema_name, entity.name
    if not _schema_exists(cur, schema):
        _create_schema(cur, schema)

    columns = entity.column_ids

    # Case 1 — table doesn't exist: create it in the right order.
    if not _table_exists(cur, database, schema, table):
        _create_table(cur, database, schema, table, columns)
        return

    # Case 2 — table exists: append any missing columns first.
    _add_missing_columns(cur, database, schema, table, columns)

    # Then check whether the physical order matches the metadata order.
    # ADD COLUMN always appends to the end, so any column that was
    # supposed to slot into the middle (or a reorder of existing ones)
    # shows up here as a mismatch.
    expected = _expected_column_order(entity)
    physical = _physical_column_order(cur, database, schema, table)

    if physical != expected:
        _rebuild_table_if_empty(
            cur, database, schema, table, columns)
        return

    # Order matches — just make sure the PK constraint is correct.
    _ensure_pk_constraint(cur, database, entity)


def _resolve_pk(ref):
    return ref.column_ids.filtered(lambda c: c.is_primary_key)[:1]


def _sync_fks(cur, database, entity):
    schema, table = entity.schema_name, entity.name
    if not _table_exists(cur, database, schema, table):
        return

    # ------------------------------------------------------------------
    # 1. Drop every FK we manage for this table.
    #    Deterministic names → DROP CONSTRAINT IF EXISTS, no catalog
    #    lookup needed (sys.foreign_keys is DB-scoped and can miss the
    #    target when the session's current DB differs).
    # ------------------------------------------------------------------
    managed_names = set()
    for col in entity.column_ids:
        if col.reference_entity_id:
            managed_names.add((f'fk_{table}_{col.name}')[:128])

    # Also catch stale FKs from columns removed in a previous edit
    cur.execute("""
        SELECT fk.name
          FROM sys.foreign_keys fk
          JOIN sys.tables t  ON t.object_id = fk.parent_object_id
          JOIN sys.schemas s ON s.schema_id = t.schema_id
         WHERE s.name = %s AND t.name = %s
           AND fk.name LIKE %s
    """, (schema, table, f'fk_{table}_%'))
    for (stale,) in cur.fetchall():
        managed_names.add(stale)

    for fk_name in managed_names:
        sql = (f'ALTER TABLE {_qfull(database, schema, table)} '
               f'DROP CONSTRAINT IF EXISTS {_q(fk_name)}')
        _logger.info("DW DDL (MSSQL): %s", sql)
        cur.execute(sql)

    # ------------------------------------------------------------------
    # 2. Add the current FKs back.
    # ------------------------------------------------------------------
    for col in entity.column_ids:
        ref = col.reference_entity_id
        if not ref:
            continue

        if not ref.schema_name or not ref.name:
            raise UserError(_(
                "Column '%(c)s' of entity '%(e)s' references entity "
                "'%(r)s', but that entity has no Schema or Name set. "
                "Fill them in before saving this column.",
                c=col.name, e=entity.display_name,
                r=ref.display_name))

        ref_pk = _resolve_pk(ref)
        if not ref_pk:
            raise UserError(_(
                "Column '%(c)s' of entity '%(e)s' references entity "
                "'%(r)s', but that entity has no column marked as "
                "Primary Key. Mark exactly one column of '%(r)s' as "
                "Primary Key, then save again.",
                c=col.name, e=entity.display_name,
                r=ref.display_name))

        ref_db = database
        if ref._get_dw_connection():
            ref_db = ref._get_dw_connection().database or database

        if not _table_exists(cur, ref_db, ref.schema_name, ref.name):
            raise UserError(_(
                "Column '%(c)s' of entity '%(e)s' references entity "
                "'%(r)s', but its table %(d)s.%(s)s.%(t)s does not "
                "exist on the DW server. Open '%(r)s' and click "
                "'Sync DW Table' first.",
                c=col.name, e=entity.display_name, r=ref.display_name,
                d=ref_db, s=ref.schema_name, t=ref.name))

        if ref_pk.name not in _existing_pk_columns(
                cur, ref_db, ref.schema_name, ref.name):
            raise UserError(_(
                "Column '%(c)s' of entity '%(e)s' references entity "
                "'%(r)s', but its table %(d)s.%(s)s.%(t)s has no "
                "PRIMARY KEY constraint matching column '%(p)s'. Open "
                "'%(r)s' and click 'Sync DW Table' to rebuild the "
                "constraint, then save this column again.",
                c=col.name, e=entity.display_name, r=ref.display_name,
                d=ref_db, s=ref.schema_name, t=ref.name, p=ref_pk.name))

        fk_name = (f'fk_{table}_{col.name}')[:128]
        sql = (
            f'ALTER TABLE {_qfull(database, schema, table)} '
            f'ADD CONSTRAINT {_q(fk_name)} '
            f'FOREIGN KEY ({_q(col.name)}) '
            f'REFERENCES {_qfull(ref_db, ref.schema_name, ref.name)} '
            f'({_q(ref_pk.name)})')
        _logger.info("DW DDL (MSSQL): %s", sql)
        cur.execute(sql)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def sync_table(connection, entity):
    if not connection:
        return
    if not entity.schema_name or not entity.name:
        return

    database = connection.database
    if not database:
        raise UserError(_(
            "The DW connection '%s' has no MSSQL database set.",
            connection.display_name))

    tree = _entity_tree(entity)

    ms = _open(connection)
    try:
        cur = ms.cursor()
        for node in tree:
            _upsert_table(cur, database, node)
        for node in tree:
            _sync_fks(cur, database, node)
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
    if not connection or not old_schema or not old_table:
        return
    database = connection.database
    ms = _open(connection)
    try:
        cur = ms.cursor()
        if not _table_exists(cur, database, old_schema, old_table):
            return

        cur_schema = old_schema
        if old_schema != new_schema:
            if not _schema_exists(cur, new_schema):
                _create_schema(cur, new_schema)
            cur.execute(
                f'ALTER SCHEMA {_q(new_schema)} TRANSFER '
                f'{_qfull(database, old_schema, old_table)}')
            cur_schema = new_schema

        if old_table != new_table:
            cur.execute(
                f"EXEC sp_rename "
                f"'{_esc_str(database)}.{_esc_str(cur_schema)}."
                f"{_esc_str(old_table)}', "
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
    database = connection.database
    ms = _open(connection)
    try:
        cur = ms.cursor()
        if not _table_exists(cur, database, schema, table):
            return
        existing = _existing_columns(cur, database, schema, table)
        if old_col.lower() not in existing or new_col.lower() in existing:
            return
        cur.execute(
            f"EXEC sp_rename "
            f"'{_esc_str(database)}.{_esc_str(schema)}."
            f"{_esc_str(table)}.{_esc_str(old_col)}', "
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


def drop_table(connection, schema, table):
    if not connection or not schema or not table:
        return
    database = connection.database
    ms = _open(connection)
    try:
        cur = ms.cursor()
        if not _table_exists(cur, database, schema, table):
            return

        cur.execute(
            f'SELECT COUNT_BIG(*) FROM '
            f'{_qfull(database, schema, table)}')
        row = cur.fetchone()
        row_count = int(row[0] or 0) if row else 0
        if row_count > 0:
            raise UserError(_(
                "Cannot drop table %(d)s.%(s)s.%(t)s on the DW server: "
                "it contains %(n)s row(s). Empty the table before "
                "deleting the entity, or detach the entity from its "
                "connection first.",
                d=database, s=schema, t=table, n=row_count))

        cur.execute("""
            SELECT sch.name AS ref_schema,
                   tab.name AS ref_table,
                   fk.name  AS fk_name
              FROM sys.foreign_keys fk
              JOIN sys.tables tab  ON tab.object_id = fk.parent_object_id
              JOIN sys.schemas sch ON sch.schema_id = tab.schema_id
             WHERE fk.referenced_object_id = OBJECT_ID(%s)
        """, (f'{schema}.{table}',))
        refs = cur.fetchall() or []
        if refs:
            details = '\n  - '.join(
                f'{r[0]}.{r[1]}  ({r[2]})' for r in refs)
            raise UserError(_(
                "Cannot drop table %(d)s.%(s)s.%(t)s on the DW server: "
                "it is referenced by foreign keys from other tables:"
                "\n  - %(det)s\n\nDelete or change those columns / "
                "entities first.",
                d=database, s=schema, t=table, det=details))

        sql = f'DROP TABLE {_qfull(database, schema, table)}'
        _logger.info("DW DDL (MSSQL): %s", sql)
        cur.execute(sql)
        ms.commit()
    except UserError:
        try:
            ms.rollback()
        except Exception:
            pass
        raise
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