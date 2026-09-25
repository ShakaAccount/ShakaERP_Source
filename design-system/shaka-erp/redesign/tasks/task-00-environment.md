# Task 0: Environment (you run this; ~15 min)

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

Odoo runs **locally from the repo** with the `.venv` Python (3.12, which has the Odoo dependencies). `odoo.conf` is already valid: it points at the database on the dev server, so there's nothing to configure.

**The database server is live and shared with the team.** Everything below goes into a **new** `shaka_design` database. Never pass `-u`/`-i` against the team's working database from these tasks.

1. Optional: if `odoo.conf` doesn't already set `dev_mode = xml`, add `--dev=xml` to the run command in step 5, so new SCSS files and XML edits load without a restart.

2. Branch (local `dev` already equals `origin/dev`):
   
   ```bash
   git switch -c feature/shaka-apple-redesign
   ```

3. QA database with demo data, Persian and the core surfaces:
   
   ```bash
   .venv/bin/python ./odoo-bin -c odoo.conf -d shaka_design --with-demo --load-language=fa_IR -i mail,contacts,crm,sale_management,project,account_accountant,hr,stock,calendar,shaka_theme --stop-after-init
   ```
   
   Always go through `.venv/bin/python`. Running bare `./odoo-bin` picks up system Python 3.14, which lacks `babel` and the other Odoo dependencies (see `CLAUDE.md`).

4. Custom screens. `-i` is all-or-nothing, so install **one module per command** and skip any that fail on the DW chain (`raes_dw_connector` → `entity`): `budget_planning`, `category`, `win_access`, `powerbi_portal`, `daily_sales_performance`, `sales_analysis`, `jalali_date`, `my_debrand`. Note skipped ones in `../PLAN.md`.
   
   ```bash
   .venv/bin/python ./odoo-bin -c odoo.conf -d shaka_design -i budget_planning --stop-after-init
   ```

5. Start the dev server (leave it running in its own terminal):
   
   ```bash
   .venv/bin/python ./odoo-bin -c odoo.conf -d shaka_design
   ```
   
   **You** log in once in the in-app browser at `http://localhost:8069/web/login?db=shaka_design`.
- **Restart:** Ctrl+C, then run the same command again. A manifest edit needs a restart. Python/XML model changes need the same command with `-u shaka_theme` (or the module you changed).
- **Port taken:** check `pgrep -af odoo-bin` and kill the old process.

Done when `http://localhost:8069/shaka` loads with no console or websocket errors, Shaka Theme is installed, and switching to فارسی flips the UI to RTL.
