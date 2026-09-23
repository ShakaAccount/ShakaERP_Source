# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Odoo 19 (Enterprise) monorepo. Odoo core itself is vendored under `odoo/`
(installed editable — see `odoo.egg-info`, `setup.py`). All custom business
logic lives under `addons/`, each subdirectory a standard Odoo module
(`__manifest__.py` + `models/`, `views/`, `static/`, etc.). `README.md` and
top-level `LICENSE`/`setup.py` are stock Odoo boilerplate, not
project-specific — ignore them for anything but licensing.

## Running the server

```bash
.venv/bin/python odoo-bin -c odoo.conf -u <module_name>
```

**Always invoke via `.venv/bin/python`, never bare `./odoo-bin`.** The
shebang resolves to system Python (currently 3.14 on this box), which does
not have `babel` or any other Odoo dependency installed — only `.venv`
(Python 3.12) does. Running `./odoo-bin` directly fails with
`ModuleNotFoundError: No module named 'babel'`.

- `-u <module>`: upgrade an already-installed module (re-reads models/views,
  updates the registry). Use this after changing any custom addon's Python
  or XML.
- `-i <module>`: install a module for the first time.
- Only one server instance can bind port 8069 at a time. If a previous run
  is still alive (`pgrep -af odoo-bin`), `kill <pid>` it before starting a
  new one — a second instance fails fast with "Address already in use".
- A model missing from the registry (`RPC_ERROR 404`, `KeyError: 'x.y.z'` in
  `registry.py`) almost always means the owning module needs `-u`/`-i` and a
  restart — a running process never picks up new/changed models on its own.

## Tests

Two different mechanisms exist side by side:

- **Odoo test framework** (`odoo.tests.BaseCase`/`TransactionCase`, tagged
  `post_install`/`-at_install`) — e.g. `addons/win_access/tests/`. Run via
  the standard Odoo test flags: `--test-enable --test-tags /<module>
  --stop-after-init -u <module>`.
- **Standalone scripts**, not wired into the Odoo test runner — e.g.
  `addons/shaka_theme/tests/scss_compile_check.py` compiles the theme through
  libsass in the same order Odoo builds the light and dark bundles and asserts
  the variables resolve to the Shaka palette. Run these directly:
  `.venv/bin/python addons/shaka_theme/tests/scss_compile_check.py`.

## Module icons — a specific gotcha

Odoo's `get_module_icon()` (`odoo/modules/module.py`) only auto-discovers
`static/description/icon.png` by default. It never falls back to
`icon.svg` unless the manifest explicitly sets an `'icon'` key pointing at
it (`'icon': '/module_name/static/description/icon.svg'`). Without that
key, an SVG-only icon is silently ignored and the module shows Odoo's
generic default icon instead — no error anywhere.

Also, `ir.module.module.icon` is a **stored** field, set at module
install/update time — so even after fixing the manifest, an
already-installed module's icon won't refresh until you upgrade it
(`-u <module>`, or Apps > Update Apps List > Upgrade in the UI).

## Architecture: the DW integration layer

The core cross-cutting architecture is a bridge from Odoo into an external
SQL Server data warehouse ("Shaka DW" / `Shaka_DW`), built in layers:

1. **`raes_dw_connector`** — owns the MSSQL connection
   (`raes.dw.connection`) and a foreign-table catalog (`raes.dw.catalog`)
   over `tds_fdw`. This is the only module that speaks MSSQL connection
   details directly.
2. **`entity`** (depends on `raes_dw_connector`) — exposes DW metadata
   tables (`md.entity`, `md.entity_column`, `gnr.module`, `gnr.lookup`) as
   Odoo models, and provides `ddl_builder.py` (DDL generation against the
   remote MSSQL side) plus the DW query helpers other addons reuse directly
   — e.g. `_persian_normalize`/`_sql_persian_normalize` from
   `md_entity.py`, imported by `win_access/models/bi_user_access.py`.
3. **`category`** and **`win_access`** (both depend on `entity`) build
   user-facing features on top: `category` is a 3-pane manager for
   `md.category`/`md.category_member` (which DW item belongs to which
   category); `win_access` manages AD/local-Windows/SSAS/PBIRS group
   membership through an external HTTP API (see
   `addons/win_access/docs/BI_ACCESS.md` for the row-level-security design —
   SSAS access is driven entirely by rows in `MD.UserAccess`, never by
   per-user SSAS roles or DAX).
4. `dim_company_dashboard`, `payment_request`, `sales_analysis` also depend
   directly on `raes_dw_connector`/`entity` for read access to DW dimension
   tables.

### Writable mirror-view pattern

Because Odoo can only query tables in its own `search_path`, several models
that logically live in the DW (`md`/`gnr` Postgres schemas, same database)
are backed by a **writable SQL VIEW in `public`**, not a real table:
`_auto = False`, and an `init()` method that calls
`refresh_writable_view(...)` (defined in `entity/models/md_view.py`,
re-exported by `category/models/category_view.py`). This view is rebuilt on
every install/upgrade *and* from a `post_init_hook`, because a DW reload
(`pgloader` DROP + recreate) CASCADE-drops these views and nothing else
recreates them. A missing source table degrades to an empty view rather
than an error, so databases that were never wired to the DW still load the
module. `raes.md.category`/`raes.md.category.member`
(`addons/category/models/category.py`) and the entity/gnr models in
`addons/entity/models/md_view.py` both follow this pattern — when adding a
new model over a DW table, follow it too rather than inventing a new
mechanism.

### Security layer

`shaka_security` provides `shaka.access.mixin`, an `AbstractModel` other
models inherit to get form-level (not just group-level) access control,
keyed by `shaka.access.form` + per-user `shaka.user.form.access` records,
with an additional workflow-stage access check
(`_shaka_check_workflow_access`). Superusers and `base.group_system` always
bypass it.

### UI theme layer

`shaka_theme` themes Odoo by overriding its SCSS variables
(`web._assets_primary_variables`, plus `web.dark_mode_variables` for dark), so
Odoo Enterprise's own dark mode is the only dark mode. Addon SCSS uses the
`var(--shaka-*)` tokens it exports (or Odoo's `$o-*` vars), never
dark-mode selectors — a page-specific dark tweak goes in
`@if $o-webclient-color-scheme == dark { … }`, since each bundle is compiled
once per scheme. The design source of truth is
`design-system/shaka-erp/MASTER.md`. `shaka_ui_makeover` is deprecated
(`installable: False`, see its `DEPRECATED.md`).

## Deployment / disaster recovery

Production runs via `docker-compose.yml` (Postgres + pgBackRest continuous
WAL archiving, Odoo web, nginx). Full procedures — initial deploy, backup
verification, point-in-time restore, filestore recovery, full host
rebuild — are documented in `DEPLOYMENT_GUIDE.md` and
`DISASTER_RECOVERY.md`; read those before touching backup/restore scripts
or `pgbackrest.conf`/`docker-compose.yml` rather than guessing at the
retention/archiving setup.
