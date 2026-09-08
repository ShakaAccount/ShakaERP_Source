# Connecting MySQL to PostgreSQL via Foreign Data Wrapper — and Using It in Odoo 19

This guide covers setting up `mysql_fdw` (the PostgreSQL Foreign Data Wrapper for MySQL) on four platforms — **Windows (native)**, **Arch Linux (native)**, **Debian (native)**, and **Docker** — and then wiring the resulting foreign table into an **Odoo 19** read-only model.

The pattern mirrors the SQL Server (`tds_fdw`) setup, but uses `mysql_fdw` instead, since that's the maintained FDW for MySQL/MariaDB sources.

---

## 1. Concepts (read this first)

- **`mysql_fdw`** is a PostgreSQL extension that lets Postgres query a remote MySQL/MariaDB table as if it were a local table.
- It requires **MySQL's client library** (`libmysqlclient` or MariaDB's equivalent `libmariadb`) to be present at build time, since `mysql_fdw` links against it.
- The general flow is always the same regardless of OS:
  1. Install PostgreSQL dev headers + MySQL client dev headers.
  2. Build and install the `mysql_fdw` extension.
  3. In Postgres: `CREATE EXTENSION`, `CREATE SERVER`, `CREATE USER MAPPING`, `CREATE FOREIGN TABLE`.
  4. Grant privileges to whatever role Odoo connects as.
  5. Build a plain Postgres view on top (optional but recommended — insulates Odoo from FDW-specific quirks).
  6. Create an `_auto = False` Odoo model backed by that view.

Read-only note: like `tds_fdw`, `mysql_fdw` has limited/fragile write support. Treat this pipeline as **read-only** unless you've specifically tested write-back for your Postgres/mysql_fdw version.

---

## 2. Windows (native)

Native Windows builds of PostgreSQL extensions are the most friction-prone path, because compiling C extensions on Windows requires Visual Studio Build Tools matched to the exact PostgreSQL build.

### 2.1 Prerequisites

- PostgreSQL installed via EDB's Windows installer (this guide assumes the standard `C:\Program Files\PostgreSQL\16` layout).
- **Visual Studio Build Tools** (2019 or 2022, matching what your PostgreSQL binaries were compiled with — EDB installers are typically built with VS 2019).
- **MySQL Connector/C** (or MySQL Server's `include`/`lib` folders) — download "MySQL Connector/C 6.1" or use the `include`/`lib` from a MySQL Server install.
- Git for Windows.

### 2.2 Get mysql_fdw source

```powershell
git clone https://github.com/EnterpriseDB/mysql_fdw.git
cd mysql_fdw
```

### 2.3 Build using the provided Windows makefile

`mysql_fdw` ships a `Makefile` intended for `nmake` on Windows via the `win32` build path used by other PostgreSQL contrib modules. Open **"x64 Native Tools Command Prompt for VS 2019"** (Start Menu, under Visual Studio) — this sets up the compiler environment — then:

```cmd
set PGROOT=C:\Program Files\PostgreSQL\16
set MYSQL_ROOT=C:\Program Files\MySQL\MySQL Connector C 6.1

cd mysql_fdw
nmake /f Makefile.win MYSQL_HOME="%MYSQL_ROOT%" PGROOT="%PGROOT%"
```

If `Makefile.win` isn't present in the cloned repo version (naming varies by release), fall back to the general contrib win32 build instructions in `README.md` of the repo — the exact nmake invocation has changed across `mysql_fdw` releases, so check the version you cloned.

### 2.4 Install the built artifacts

Copy the resulting `.dll` and `.control`/`.sql` files into your PostgreSQL install:

```cmd
copy mysql_fdw.dll "C:\Program Files\PostgreSQL\16\lib\"
copy mysql_fdw.control "C:\Program Files\PostgreSQL\16\share\extension\"
copy mysql_fdw--*.sql "C:\Program Files\PostgreSQL\16\share\extension\"
```

Also ensure `libmysql.dll` (from MySQL Connector/C) is reachable — either copy it into PostgreSQL's `bin` folder or add its folder to `PATH`, since Windows resolves DLL dependencies at load time.

### 2.5 Practical alternative for Windows

Compiling on native Windows is genuinely painful and version-sensitive. Two more reliable alternatives if you're on Windows:

- **Run PostgreSQL inside WSL2** (Debian/Ubuntu userspace) and follow the Debian instructions below — avoids MSVC entirely.
- **Use Docker Desktop for Windows** and follow the Docker instructions below — this is the most reproducible option and what's recommended for production use on a Windows host.

### 2.6 Create the extension (same on every platform from here)

Once the `.dll`/`.control`/`.sql` files are in place, restart the PostgreSQL service (Services app → PostgreSQL → Restart), then in `psql` or pgAdmin:

```sql
CREATE EXTENSION mysql_fdw;
```

Continue at **Section 6 (Common Postgres Setup)** below.

---

## 3. Arch Linux (native)

### 3.1 Install prerequisites

```bash
sudo pacman -S postgresql base-devel git mariadb-libs
```

`mariadb-libs` provides the client library/headers `mysql_fdw` links against (MariaDB's client library is ABI-compatible with MySQL's for this purpose). Confirm headers exist:

```bash
pkg-config --cflags --libs mariadb
```

If `pkg-config` can't find it, locate manually:

```bash
find /usr -iname "mysql.h" 2>/dev/null
```

### 3.2 Build and install

```bash
git clone https://github.com/EnterpriseDB/mysql_fdw.git
cd mysql_fdw
```

`mysql_fdw`'s `Makefile` looks for MySQL headers via `mysql_config` or `mariadb_config` on the `PATH`. Point it explicitly if needed:

```bash
export PATH="/usr/bin:$PATH"   # ensure mariadb_config is discoverable
which mariadb_config

make USE_PGXS=1
sudo make USE_PGXS=1 install
```

If `make` complains it can't find `mysql_config`, set it explicitly:

```bash
make USE_PGXS=1 MYSQL_CONFIG=/usr/bin/mariadb_config
sudo make USE_PGXS=1 install
```

As with `tds_fdw` on Arch, you may see a trailing `llvm-lto` bitcode error at the very end of `install` — that's cosmetic (JIT bitcode only) and can be ignored; the `.so`, `.control`, and `.sql` files install successfully before that step runs.

### 3.3 Verify

```bash
ls /usr/share/postgresql/extension/mysql_fdw*
ls /usr/lib/postgresql/mysql_fdw.so
```

Continue at **Section 6**.

---

## 4. Debian (native)

Debian is the most straightforward native path, since the standard `postgresql-server-dev-<version>` package plus `libmysqlclient-dev` cover everything needed.

### 4.1 Install prerequisites

```bash
sudo apt-get update
sudo apt-get install -y postgresql-server-dev-16 libmysqlclient-dev build-essential git
```

If `libmysqlclient-dev` isn't available in your Debian release's repos (some releases ship only MariaDB packages), use the MariaDB equivalent:

```bash
sudo apt-get install -y libmariadb-dev libmariadb-dev-compat
```

### 4.2 Build and install

```bash
git clone https://github.com/EnterpriseDB/mysql_fdw.git
cd mysql_fdw
make USE_PGXS=1
sudo make USE_PGXS=1 install
```

### 4.3 Verify

```bash
ls /usr/share/postgresql/16/extension/mysql_fdw*
ls /usr/lib/postgresql/16/lib/mysql_fdw.so
```

(Debian's PGXS paths are versioned under `/usr/lib/postgresql/<version>/` unlike Arch's unversioned `/usr/lib/postgresql/`.)

Continue at **Section 6**.

---

## 5. Docker

This is the most portable option and matches the pattern from your SHAKA ERP Docker Compose setup.

### 5.1 Custom Postgres Dockerfile

```dockerfile
FROM postgres:16

RUN apt-get update && apt-get install -y \
    libmariadb-dev \
    libmariadb-dev-compat \
    build-essential \
    postgresql-server-dev-16 \
    git \
    && git clone https://github.com/EnterpriseDB/mysql_fdw.git /tmp/mysql_fdw \
    && cd /tmp/mysql_fdw \
    && make USE_PGXS=1 \
    && make USE_PGXS=1 install \
    && cd / && rm -rf /tmp/mysql_fdw \
    && apt-get remove -y build-essential git postgresql-server-dev-16 \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
```

### 5.2 docker-compose.yml

```yaml
services:
  postgres:
    build:
      context: ./postgres
      dockerfile: Dockerfile
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: your_password
      POSTGRES_DB: postgres
    restart: unless-stopped

volumes:
  pgdata:
```

```bash
docker compose build postgres
docker compose up -d postgres
```

### 5.3 Verify inside the container

```bash
docker compose exec postgres psql -U odoo -d your_db -c "CREATE EXTENSION IF NOT EXISTS mysql_fdw;"
```

Continue at **Section 6**.

---

## 6. Common Postgres Setup (all platforms, from here identical)

Once `mysql_fdw` is installed on your platform of choice, everything from this point runs inside `psql` and is identical everywhere.

### 6.1 Create the extension

```sql
CREATE EXTENSION IF NOT EXISTS mysql_fdw;
```

### 6.2 Create the foreign server

```sql
CREATE SERVER mysql_server
  FOREIGN DATA WRAPPER mysql_fdw
  OPTIONS (host '192.168.1.20', port '3306');
```

Note `mysql_fdw` takes `host`/`port` at the server level — the target **database** is specified per-table (`dbname` option), not at the server level, unlike `tds_fdw`.

### 6.3 Create the user mapping

```sql
CREATE USER MAPPING FOR odoo
  SERVER mysql_server
  OPTIONS (username 'mysql_user', password 'mysql_password');
```

Replace `odoo` with whatever Postgres role your Odoo instance actually connects as.

### 6.4 Create the foreign table

Example assuming a MySQL table `shop_db.products`:

```sql
CREATE FOREIGN TABLE fdw_products (
    id            integer,
    sku           varchar(64),
    name          varchar(255),
    price         numeric(12,2),
    stock_qty     integer
)
SERVER mysql_server
OPTIONS (dbname 'shop_db', table_name 'products');
```

### 6.5 Test the connection

```sql
SELECT * FROM fdw_products LIMIT 5;
```

If you get `permission denied for foreign table`, you likely ran this as a different role than the one with the mapping — see Section 6.7.

### 6.6 Create a Postgres view on top (recommended)

```sql
CREATE VIEW public.products_view AS
SELECT id, sku, name, price, stock_qty
FROM fdw_products;
```

Insulating Odoo behind a plain view means if you ever swap the underlying FDW, rename columns, or add transformation logic, Odoo's model definition doesn't need to change — only the view does.

### 6.7 Grants (this trips people up every time)

Objects created as `postgres` are owned by `postgres`; your Odoo role (`odoo`) needs explicit grants on **every layer**:

```sql
GRANT USAGE ON FOREIGN SERVER mysql_server TO odoo;
GRANT SELECT ON fdw_products TO odoo;
GRANT SELECT ON products_view TO odoo;
```

Verify as the actual Odoo role:

```sql
SET ROLE odoo;
SELECT * FROM products_view LIMIT 5;
RESET ROLE;
```

Optional: auto-grant future objects to `odoo` so you don't repeat this for every new table:

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT ON TABLES TO odoo;
```

---

## 7. Using It in Odoo 19

### 7.1 Scaffold the addon

```bash
mkdir -p mysql_products_dashboard/{models,views,security}
```

`mysql_products_dashboard/__manifest__.py`:

```python
{
    'name': 'MySQL Products (Read-Only)',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Read-only view of products from external MySQL database',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/mysql_product_views.xml',
    ],
    'installable': True,
    'application': False,
}
```

`mysql_products_dashboard/__init__.py`:

```python
from . import models
```

`mysql_products_dashboard/models/__init__.py`:

```python
from . import mysql_product
```

`mysql_products_dashboard/models/mysql_product.py`:

```python
from odoo import models, fields

class MysqlProduct(models.Model):
    _name = 'mysql.product'
    _description = 'Product (Read-Only, from external MySQL)'
    _auto = False
    _log_access = False

    sku = fields.Char(string='SKU', readonly=True)
    name = fields.Char(string='Name', readonly=True)
    price = fields.Float(string='Price', readonly=True)
    stock_qty = fields.Integer(string='Stock Qty', readonly=True)

    def init(self):
        self._cr.execute("""
            DROP VIEW IF EXISTS mysql_product CASCADE;
            CREATE VIEW mysql_product AS (
                SELECT
                    id AS id,
                    sku,
                    name,
                    price,
                    stock_qty
                FROM products_view
            )
        """)
```

`mysql_products_dashboard/security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_mysql_product_user,mysql.product.user,model_mysql_product,base.group_user,1,0,0,0
```

`mysql_products_dashboard/views/mysql_product_views.xml`:

```xml
<odoo>
    <record id="view_mysql_product_list" model="ir.ui.view">
        <field name="name">mysql.product.list</field>
        <field name="model">mysql.product</field>
        <field name="arch" type="xml">
            <list create="false" edit="false" delete="false" duplicate="false">
                <field name="sku"/>
                <field name="name"/>
                <field name="price"/>
                <field name="stock_qty"/>
            </list>
        </field>
    </record>

    <record id="view_mysql_product_form" model="ir.ui.view">
        <field name="name">mysql.product.form</field>
        <field name="model">mysql.product</field>
        <field name="arch" type="xml">
            <form create="false" edit="false" delete="false" duplicate="false">
                <sheet>
                    <group>
                        <field name="sku"/>
                        <field name="name"/>
                        <field name="price"/>
                        <field name="stock_qty"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_mysql_product" model="ir.actions.act_window">
        <field name="name">MySQL Products</field>
        <field name="res_model">mysql.product</field>
        <field name="view_mode">list,form</field>
    </record>

    <menuitem id="menu_mysql_product_root" name="External Data" sequence="150"/>
    <menuitem id="menu_mysql_product"
              name="MySQL Products"
              action="action_mysql_product"
              parent="menu_mysql_product_root"/>
</odoo>
```

### 7.2 Install

Native (venv):

```bash
source /path/to/your/odoo-venv/bin/activate
python odoo-bin -i mysql_products_dashboard -d your_odoo_db --stop-after-init -c /path/to/odoo.conf
```

Docker:

```bash
docker compose exec odoo odoo -i mysql_products_dashboard -d your_odoo_db --stop-after-init
docker compose restart odoo
```

Use `-i` for a brand-new module, `-u` when updating an existing one after changing `init()` SQL or view fields.

---

## 8. Troubleshooting Checklist

| Symptom | Likely Cause |
|---|---|
| `ERROR: extension "mysql_fdw" is not available` | `.control` file not in Postgres's extension directory, or wrong Postgres version's directory |
| `permission denied for foreign table` | Querying as a role with no `USER MAPPING`, or missing `GRANT` |
| `could not connect to server` / timeout | Network/firewall between Postgres host and MySQL host — test with `mysql -h <host> -u <user> -p` first |
| `undefined symbol` on `CREATE EXTENSION` | `mysql_fdw` built against a different MySQL client library version than what's installed at runtime |
| Odoo shows `AccessError` on the new model | Missing/incorrect `ir.model.access.csv` row |
| Data appears once then never updates | You built a Postgres **table**, not a **view** — foreign tables/views are live; only a materialized view or a copied table would go stale |

---

## 9. Summary of the Pipeline

```
MySQL table
   │
   ▼ (mysql_fdw)
Foreign table in Postgres  (fdw_products)
   │
   ▼ (plain SQL view)
Postgres view              (products_view)
   │
   ▼ (Odoo _auto=False model + init())
Odoo-managed view          (mysql_product)
   │
   ▼ (ir.ui.view, form/list, create="false" edit="false")
Read-only Odoo screen
```

Every arrow above is a separate Postgres object with its own owner and ACLs — the most common failure at every stage is a missing `GRANT` for the role Odoo actually connects as, not a broken pipeline step.
