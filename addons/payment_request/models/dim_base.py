"""Shared plumbing for the read-only DW dimension models.

The public odoo_raes_dim_* views are (re)created on module install/upgrade and
after every DW bootstrap. Two rules keep name_search from ever 500-ing:

* a missing source relation must not break the model — fall back to an empty
  view with the same shape (0 rows instead of UndefinedTable)
* columns the source does not have are exposed as typed NULLs, so every ORM
  field always resolves (0 rows instead of UndefinedColumn)
"""


def _resolve_source(env, candidates, remote_table):
    """First existing relation among the DW mapping lines + candidates."""
    cr = env.cr
    names = list(candidates)
    if remote_table:
        # plain existence check: init() runs mid module-load, so the mapping
        # table may not exist yet and any rollback here would discard the
        # tables the load transaction just created
        cr.execute("SELECT to_regclass('public.raes_dw_table_map') IS NOT NULL")
        if cr.fetchone()[0]:
            cr.execute(
                "SELECT local_view_name FROM raes_dw_table_map "
                "WHERE lower(remote_table) = lower(%s)", [remote_table])
            names = [r[0] for r in cr.fetchall()] + names
    cr.execute(
        "SELECT c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = ANY(%s) "
        "AND c.relkind IN ('v', 'r', 'f', 'm', 'p')", [names])
    found = {r[0] for r in cr.fetchall()}
    for name in names:
        if name in found and name not in (
                'odoo_raes_dim_company', 'odoo_raes_dim_party',
                'odoo_raes_dim_cost_center'):
            return name
    return None


def _source_columns(env, rel):
    cr = env.cr
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s", [rel])
    return {r[0].lower() for r in cr.fetchall()}


def refresh_dim_view(env, view, id_col, columns, candidates, remote_table):
    """(Re)create public.<view>: id alias + every model column, NULL-filled
    when the DW source lacks it (or is missing entirely)."""
    cr = env.cr
    src = _resolve_source(env, candidates, remote_table)
    src_cols = _source_columns(env, src) if src else set()

    def _ref(col, sqltype):
        return (f'{src}.{col}' if (src and col in src_cols)
                else f'NULL::{sqltype}')

    select = [f'{_ref(col, t)} AS {col}' for col, t in columns.items()]
    # id alias comes first; the id column stays readable under its own name
    body = ', '.join([f'{_ref(id_col, columns[id_col])} AS id'] + select)

    cr.execute(
        "SELECT c.relkind FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = %s", [view])
    row = cr.fetchone()
    if row:
        kind = 'TABLE' if row[0] in ('r', 'p') else 'VIEW'
        cr.execute(f'DROP {kind} IF EXISTS public.{view} CASCADE')

    if src:
        cr.execute(f'CREATE VIEW public.{view} AS '
                   f'SELECT {body} FROM public.{src}')
    else:
        cr.execute(f'CREATE VIEW public.{view} AS SELECT {body} WHERE false')
    return src
