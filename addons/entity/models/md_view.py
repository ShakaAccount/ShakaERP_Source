"""Public mirror views over the Shaka DW tables living in the `md` / `gnr`
schemas of the SAME database.

Odoo can only address tables in its search_path, so each DW table gets a thin
read/write view in `public`. Two facts drive the design:

* `post_init_hook` runs ONCE — a DW reload (pgloader DROP TABLE + recreate)
  CASCADE-drops these views and nothing brings them back, leaving the models
  pointing at a relation that no longer exists
  (`UndefinedTable: relation "raes_md_entity_column" does not exist`);
* a missing source schema/table must not break the ORM — DBs that never had
  the DW wired must still load the module.

So the views are (re)created from every model's `init()` (each install and
upgrade) and from `post_init_hook`, and a missing source degrades to an empty
view instead of an error.
"""

# kind -> SQL type, mirrored from the DW DDL
_ENTITY_COLUMNS = {
    'id': 'integer', 'entity_type_lu': 'integer', 'schema_name': 'varchar',
    'name': 'varchar', 'title': 'varchar', 'module_id': 'integer',
    'is_category_based': 'boolean', 'is_user_defined': 'boolean',
    'is_company_based': 'boolean', 'is_active': 'boolean',
    'priority': 'integer', 'master_entity_id': 'integer',
    'entity_full_name': 'varchar', 'creator_user_id': 'integer',
    'creation_date': 'timestamp', 'editor_user_id': 'integer',
    'modification_date': 'timestamp', 'system_lu': 'integer',
    'database_name': 'varchar',
}

_ENTITY_COLUMN_COLUMNS = {
    'id': 'integer', 'entity_id': 'integer', 'name': 'varchar',
    'title': 'varchar', 'data_type': 'varchar', 'size': 'varchar',
    'ordinal_position': 'integer', 'is_primary_key': 'boolean',
    'is_identity': 'boolean', 'reference_entity_id': 'integer',
    'is_user_defined': 'integer', 'column_type_lu': 'integer',
    'creator_user_id': 'integer', 'creation_date': 'timestamp',
    'editor_user_id': 'integer', 'modification_date': 'timestamp',
    'original_name': 'varchar',
}

_GNR_MODULE_COLUMNS = {
    'id': 'integer', 'title': 'varchar', 'creator_user_id': 'integer',
    'creation_date': 'timestamp', 'editor_user_id': 'integer',
    'modification_date': 'timestamp', 'is_user_defined': 'boolean',
    'priority': 'integer',
}

# GNR.LookUp — SQL Server DDL:
#   Id int IDENTITY, CategoryCode varchar(200), CategoryTitleEn varchar(200),
#   CategoryTitle varchar(200), Code int, Value varchar(200),
#   CreatorUserId int, CreationDate datetime, EditorUserId int,
#   ModificationDate datetime, PK (Id)
_GNR_LOOKUP_COLUMNS = {
    'id': 'integer',
    'category_code': 'varchar',
    'category_title_en': 'varchar',
    'category_title': 'varchar',
    'code': 'integer',
    'value': 'varchar',
    'creator_user_id': 'integer',
    'creation_date': 'timestamp',
    'editor_user_id': 'integer',
    'modification_date': 'timestamp',
}

# (public view, source schema, source table, columns)
VIEW_SPECS = [
    ('raes_md_entity', 'md', 'entity', _ENTITY_COLUMNS),
    ('raes_md_entity_column', 'md', 'entity_column', _ENTITY_COLUMN_COLUMNS),
    ('raes_gnr_module', 'gnr', 'module', _GNR_MODULE_COLUMNS),
    ('raes_gnr_lookup', 'gnr', 'look_up', _GNR_LOOKUP_COLUMNS),
]


MD_ENTITY_VIEW = VIEW_SPECS[0]
MD_ENTITY_COLUMN_VIEW = VIEW_SPECS[1]
GNR_MODULE_VIEW = VIEW_SPECS[2]
GNR_LOOKUP_VIEW = VIEW_SPECS[3]


def refresh_md_view(env, view, schema, table, columns):
    """(Re)create public.<view> over <schema>.<table>; empty view when the
    source is absent. Returns the source name or None."""
    cr = env.cr
    cr.execute(
        "SELECT c.relkind FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = %s AND c.relname = %s", [schema, table])
    row = cr.fetchone()
    src = f'{schema}.{table}' if row and row[0] in (
        'r', 'v', 'f', 'm', 'p') else None

    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s", [schema, table])
    src_cols = {r[0] for r in cr.fetchall()} if src else set()

    def ref(col, sqltype):
        return (f'{src}.{col}' if (src and col in src_cols)
                else f'NULL::{sqltype}')

    select = ', '.join(f'{ref(c, t)} AS {c}' for c, t in columns.items())
    cr.execute(f'DROP VIEW IF EXISTS public.{view} CASCADE')
    tail = f' FROM {src}' if src else ' WHERE false'
    cr.execute(f'CREATE VIEW public.{view} AS SELECT {select}{tail}')
    return src


def refresh_all(env):
    """Rebuild every mirror view; used by post_init_hook."""
    for spec in VIEW_SPECS:
        refresh_md_view(env, *spec)