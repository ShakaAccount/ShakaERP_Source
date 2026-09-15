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

# In entity_addon/models/md_view.py  (append at the end)

def refresh_writable_view(env, view, schema, table, columns):
    """
    (Re)create public.<view> over <schema>.<table> with INSTEAD OF triggers
    so Odoo can INSERT / UPDATE / DELETE through the view.

    `columns` is an OrderedDict-like mapping {column_name: sql_type}.
    Uses `bigint` / `text` / `timestamptz` so it matches the DW DDL
    (int8, varchar, timestamp) without casting surprises.
    """
    cr = env.cr

    # 1. Does the source relation exist?
    cr.execute(
        "SELECT c.relkind FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = %s AND c.relname = %s",
        [schema, table],
    )
    row = cr.fetchone()
    src = f'{schema}.{table}' if row and row[0] in ('r', 'v', 'f', 'm', 'p') else None

    # 2. Which columns really exist on the source?
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        [schema, table],
    )
    src_cols = {r[0] for r in cr.fetchall()} if src else set()

    # 3. Build the SELECT list
    def ref(col):
        return f'{src}.{col}' if (src and col in src_cols) else f'NULL'

    select = ', '.join(f'{ref(c)} AS {c}' for c in columns)

    # 4. (Re)create the view
    cr.execute(f'DROP VIEW IF EXISTS public.{view} CASCADE')
    tail = f' FROM {src}' if src else ' WHERE false'
    cr.execute(f'CREATE VIEW public.{view} AS SELECT {select}{tail}')

    if not src:
        return  # source missing → read-only empty view, nothing more to do

    # 5. Build INSTEAD OF triggers so the view is writable
    #
    # `id` is a ``GENERATED BY DEFAULT AS IDENTITY`` column on the legacy
    # table. Emitting ``NEW.id`` unconditionally would push an explicit
    # NULL for callers (Odoo) that omit the PK, raising
    # ``null value in column "id" violates not-null constraint``. So the
    # identity column is only listed when the caller supplied a value,
    # and the generated key is returned via RETURNING so the ORM sees it.
    col_list = list(columns.keys())
    has_identity = 'id' in col_list
    non_id = [c for c in col_list if c != 'id']
    non_id_cols = ", ".join(non_id)
    non_id_vals = ", ".join(f"NEW.{c}" for c in non_id)
    identity_cols = "id, " + non_id_cols if non_id_cols else "id"
    identity_vals = "NEW.id, " + non_id_vals if non_id_vals else "NEW.id"
    update_sets = ", ".join(f"{c} = NEW.{c}" for c in non_id)

    if has_identity:
        ins_body = (
            f"IF NEW.id IS NULL THEN\n"
            f"                INSERT INTO {src} ({non_id_cols}) "
            f"VALUES ({non_id_vals}) RETURNING id INTO NEW.id;\n"
            f"            ELSE\n"
            f"                INSERT INTO {src} ({identity_cols}) "
            f"VALUES ({identity_vals});\n"
            f"            END IF;"
        )
    else:
        ins_body = (f"INSERT INTO {src} ({non_id_cols}) "
                    f"VALUES ({non_id_vals});")

    cr.execute(f"""
        CREATE OR REPLACE FUNCTION public.{view}_ins() RETURNS trigger AS $body$
        BEGIN
            {ins_body}
            RETURN NEW;
        END;
        $body$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_{view}_ins ON public.{view};
        CREATE TRIGGER trg_{view}_ins INSTEAD OF INSERT ON public.{view}
        FOR EACH ROW EXECUTE FUNCTION public.{view}_ins();
    """)

    cr.execute(f"""
        CREATE OR REPLACE FUNCTION public.{view}_upd() RETURNS trigger AS $body$
        BEGIN
            UPDATE {src} SET {update_sets} WHERE id = OLD.id;
            RETURN NEW;
        END;
        $body$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_{view}_upd ON public.{view};
        CREATE TRIGGER trg_{view}_upd INSTEAD OF UPDATE ON public.{view}
        FOR EACH ROW EXECUTE FUNCTION public.{view}_upd();
    """)

    cr.execute(f"""
        CREATE OR REPLACE FUNCTION public.{view}_del() RETURNS trigger AS $body$
        BEGIN
            DELETE FROM {src} WHERE id = OLD.id;
            RETURN OLD;
        END;
        $body$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_{view}_del ON public.{view};
        CREATE TRIGGER trg_{view}_del INSTEAD OF DELETE ON public.{view}
        FOR EACH ROW EXECUTE FUNCTION public.{view}_del();
    """)