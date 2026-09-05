import logging

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Catalog.Type codes that are NOT reports (folders, resources, data sources,
# shared datasets, models...). We deliberately EXCLUDE these rather than
# match an exact "this is a report" code, since the exact numeric code for
# Power BI (.pbix) reports specifically can vary by PBIRS version and isn't
# something we could verify with confidence. Verify with the diagnostic
# query in the module's help text if discovery finds nothing / finds junk.
_NON_REPORT_TYPES = (1, 3, 5, 6)  # Folder, Resource, DataSource, Model (typical SSRS/PBIRS codes)


class PbirsDiscoveryConfig(models.Model):
    _name = "pbirs.discovery.config"
    _description = "PBIRS Discovery - SQL Connection Settings"

    name = fields.Char(default="PBIRS Discovery", required=True)
    sql_server = fields.Char(required=True, help="SQL Server host\\instance, e.g. pbirs-sql01 or pbirs-sql01\\SQLEXPRESS")
    sql_database = fields.Char(required=True, default="ReportServer")
    auth_mode = fields.Selection(
        [("windows", "Windows Trusted Connection"), ("sql", "SQL Server Login")],
        default="windows", required=True,
        help="Recommended: 'Windows Trusted Connection' if the Odoo "
             "service runs as your dedicated AD service account (see "
             "module description) - reuses that identity automatically, "
             "no SQL credentials stored in Odoo. Grant that account just "
             "db_datareader on this database - avoid using 'sa' or any "
             "sysadmin login here, this connection is read-only anyway.",
    )
    sql_username = fields.Char(string="SQL Login")
    sql_password = fields.Char(string="SQL Password")
    odbc_driver = fields.Char(
        string="ODBC Driver",
        required=True,
        default="ODBC Driver 17 for SQL Server",
        help="Must match EXACTLY the name of an ODBC driver actually "
             "installed on this machine - varies by machine, do not assume "
             "'ODBC Driver 17/18 for SQL Server' is present. Check with, in "
             "PowerShell: Get-OdbcDriver | Where-Object {$_.Name -like "
             "\"*SQL Server*\"} - and set this field to match whatever that "
             "returns exactly (e.g. just 'SQL Server' on machines with only "
             "the legacy driver installed).",
    )
    trust_server_certificate = fields.Boolean(
        string="Trust Server Certificate",
        default=False,
        help="Enable if SQL Server uses a self-signed/untrusted TLS "
             "certificate (common on internal/test servers) and you get a "
             "certificate trust error connecting. Equivalent to "
             "'TrustServerCertificate=true' in a SQL connection string.",
    )
    portal_base_url = fields.Char(
        required=True,
        help="Base URL of the PBIRS web portal, e.g. "
             "https://pbirs.company.local/reports/powerbi "
             "(catalog paths get appended to this to build each report's URL).",
    )
    active = fields.Boolean(default=True)
    last_run_date = fields.Datetime(readonly=True)
    last_run_summary = fields.Text(readonly=True)

    soap_url = fields.Char(
        string="PBIRS SOAP Endpoint",
        help="URL of the ReportService2010 SOAP endpoint, used to PUSH "
             "access changes made in Odoo back to PBIRS (separate from the "
             "SQL settings above, which are read-only discovery). Usually "
             "https://pbirs.company.local/ReportServer/ReportService2010.asmx "
             "- note this is normally the /ReportServer/ virtual directory, "
             "not the /reports/ portal path used in Portal Base URL above.",
    )
    soap_auth_mode = fields.Selection(
        [
            ("windows_current", "Windows Integrated (run as the Odoo service account)"),
            ("windows_explicit", "Windows - explicit domain credentials"),
        ],
        default="windows_current",
        string="SOAP Auth Mode",
        help="'Windows Integrated' uses whatever Windows account the Odoo "
             "service itself runs as (requires the 'requests-negotiate-sspi' "
             "package, Windows only). Use 'explicit credentials' if Odoo "
             "doesn't run as an account with PBIRS access, or if it isn't "
             "running on Windows at all (requires 'requests-ntlm' instead).",
    )
    soap_domain = fields.Char(string="Domain", help="e.g. shaka")
    soap_username = fields.Char(string="SOAP Username")
    soap_password = fields.Char(string="SOAP Password")

    def _get_soap_client(self):
        self.ensure_one()
        from .pbirs_soap_client import PbirsSoapClient

        if not self.soap_url:
            raise UserError(
                "No PBIRS SOAP Endpoint configured on this connection record "
                "- set it under PBIRS Discovery > Connection Settings > "
                "PBIRS SOAP Endpoint before pushing access changes."
            )

        try:
            import requests
        except ImportError:
            raise UserError("The 'requests' package is required. Install it with: pip install requests")

        session = requests.Session()
        if self.soap_auth_mode == "windows_current":
            try:
                from requests_negotiate_sspi import HttpNegotiateAuth
            except ImportError:
                raise UserError(
                    "Windows Integrated SOAP auth needs the "
                    "'requests-negotiate-sspi' package (Windows only). "
                    "Install it with:\n"
                    '"<odoo>\\python\\python.exe" -m pip install requests-negotiate-sspi\n'
                    "or switch SOAP Auth Mode to explicit domain credentials."
                )
            session.auth = HttpNegotiateAuth()
        else:
            try:
                from requests_ntlm import HttpNtlmAuth
            except ImportError:
                raise UserError(
                    "Explicit-credential SOAP auth needs the "
                    "'requests-ntlm' package. Install it with:\n"
                    '"<odoo>\\python\\python.exe" -m pip install requests-ntlm'
                )
            if not (self.soap_domain and self.soap_username):
                raise UserError(
                    "Domain and SOAP Username are required for explicit "
                    "Windows credentials SOAP auth."
                )
            session.auth = HttpNtlmAuth(
                "%s\\%s" % (self.soap_domain, self.soap_username), self.soap_password or ""
            )

        return PbirsSoapClient(self.soap_url, session)

    def action_test_soap_connection(self):
        self.ensure_one()
        client = self._get_soap_client()
        try:
            client.get_policies("/")
        except Exception as e:
            raise UserError("SOAP connection test failed: %s" % e)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": "Connected to the PBIRS SOAP endpoint successfully.",
                "type": "success",
                "sticky": False,
            },
        }

    def _get_connection(self):
        try:
            import pyodbc
        except ImportError:
            raise UserError(
                "The 'pyodbc' package is required. Install it with: "
                "pip install pyodbc\n"
                "You also need a 'ODBC Driver for SQL Server' installed on "
                "this machine (Microsoft's ODBC Driver 17 or 18 for SQL Server)."
            )
        self.ensure_one()
        trust_cert_part = "TrustServerCertificate=yes;" if self.trust_server_certificate else ""
        driver_part = "DRIVER={%s};" % self.odbc_driver
        if self.auth_mode == "windows":
            conn_str = (
                "%sSERVER=%s;DATABASE=%s;Trusted_Connection=yes;%s"
            ) % (driver_part, self.sql_server, self.sql_database, trust_cert_part)
        else:
            conn_str = (
                "%sSERVER=%s;DATABASE=%s;UID=%s;PWD=%s;%s"
            ) % (driver_part, self.sql_server, self.sql_database, self.sql_username, self.sql_password or "", trust_cert_part)
        try:
            return pyodbc.connect(conn_str, timeout=10)
        except pyodbc.Error as e:
            raise UserError(
                "Could not connect to the PBIRS SQL Server database: %s\n\n"
                "This usually means the 'ODBC Driver' field (%s) doesn't "
                "match a driver actually installed on this machine. Check "
                "with 'Get-OdbcDriver | Where-Object {$_.Name -like \"*SQL "
                "Server*\"}' in PowerShell and set the field to match "
                "exactly what that returns." % (e, self.odbc_driver)
            )

    def action_test_connection(self):
        self.ensure_one()
        conn = self._get_connection()
        conn.close()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": "Connected to the PBIRS SQL Server database successfully.",
                "type": "success",
                "sticky": False,
            },
        }

    _POLICY_QUERY = """
        SELECT
            c.Path AS ItemPath,
            c.Name AS ItemName,
            u.UserName AS PrincipalName
        FROM Catalog c
        JOIN Policies p ON c.PolicyID = p.PolicyID
        JOIN PolicyUserRole pur ON p.PolicyID = pur.PolicyID
        JOIN Users u ON pur.UserID = u.UserID
        WHERE c.Type NOT IN ({exclude_types})
        ORDER BY c.Path
    """

    def action_discover_now(self):
        self._run_discovery()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "PBIRS Discovery",
                "message": "Discovery finished. See the connection records log for details.",
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _cron_discover_all(self):
        for config in self.search([("active", "=", True)]):
            config._run_discovery()

    def _run_discovery(self):
        self.ensure_one()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = self._POLICY_QUERY.format(
                exclude_types=",".join(str(t) for t in _NON_REPORT_TYPES)
            )
            cursor.execute(query)
            rows = cursor.fetchall()
        except Exception as e:
            self.write({
                "last_run_date": fields.Datetime.now(),
                "last_run_summary": "ERROR querying PBIRS database: %s" % e,
            })
            _logger.error("PBIRS Discovery: SQL query failed: %s", e)
            return
        finally:
            conn.close()

        # Group principal names by report path/name.
        reports_seen = {}  # path -> {"name":..., "principals": set()}
        for row in rows:
            path, name, principal = row.ItemPath, row.ItemName, row.PrincipalName
            reports_seen.setdefault(path, {"name": name, "principals": set()})
            reports_seen[path]["principals"].add(principal)

        if not reports_seen:
            self.write({
                "last_run_date": fields.Datetime.now(),
                "last_run_summary": "Query returned 0 rows. Check the SQL "
                                     "connection and the _NON_REPORT_TYPES "
                                     "filter matches your PBIRS schema "
                                     "(run the diagnostic query in the "
                                     "module notes to check Catalog.Type "
                                     "values).",
            })
            return

        ad_config = self.env["ad.group.sync.config"].search([("active", "=", True)], limit=1)
        if not ad_config:
            raise UserError(
                "No active AD connection configured (needed to tell which "
                "PBIRS principals are AD groups vs individual users). Set "
                "one up under AD Group Sync > Connection Settings first."
            )

        Report = self.env["powerbi.report"]
        Mapping = self.env["ad.group.mapping"]
        Group = self.env["res.groups"]
        Users = self.env["res.users"]

        summary_lines = []
        ad_conn = ad_config._get_connection()
        try:
            for path, info in reports_seen.items():
                group_records = self.env["res.groups"]
                user_records = self.env["res.users"]
                unresolved = []          # not found in AD at all (built-in/local Windows principals)
                users_not_in_odoo = []   # real AD users, but no matching Odoo user yet (haven't logged in)

                for principal in info["principals"]:
                    resolved = ad_config._resolve_principal(principal, conn=ad_conn)

                    if not resolved:
                        unresolved.append(principal)
                        continue

                    if resolved["is_group"]:
                        mapping = Mapping.search([("ad_group_dn", "=", resolved["dn"])], limit=1)
                        if mapping:
                            odoo_group = mapping.odoo_group_id
                        else:
                            odoo_group = Group.create({
                                "name": "PowerBI - %s" % resolved["sam"],
                            })
                            Mapping.create({
                                "ad_group_dn": resolved["dn"],
                                "odoo_group_id": odoo_group.id,
                            })
                            summary_lines.append(
                                "Created new Odoo group + mapping for AD group %s" % resolved["sam"]
                            )
                        group_records |= odoo_group
                    else:
                        # Individual AD user - only wireable if they already
                        # have an Odoo user record (e.g. from a prior LDAP
                        # login via auth_ldap). We never auto-create Odoo
                        # user accounts here.
                        odoo_user = Users.search(
                            [("login", "=ilike", resolved["sam"])], limit=1
                        )
                        if odoo_user:
                            user_records |= odoo_user
                        else:
                            users_not_in_odoo.append(resolved["sam"])

                report = Report.search([("catalog_path", "=", path)], limit=1)
                url = "%s%s?rs:embed=true" % (self.portal_base_url.rstrip("/"), path)
                vals = {
                    "name": info["name"],
                    "url": url,
                    "catalog_path": path,
                    "managed_by_discovery": True,
                    "allowed_group_ids": [(6, 0, group_records.ids)],
                    "allowed_user_ids": [(6, 0, user_records.ids)],
                }
                if report:
                    if report.managed_by_discovery:
                        report.with_context(skip_auto_push=True).write(vals)
                    else:
                        summary_lines.append(
                            "Skipped '%s' - a manually-created report already "
                            "exists at this catalog path, not overwriting it." % info["name"]
                        )
                        continue
                else:
                    report = Report.create(vals)
                    summary_lines.append("Created report entry: %s" % info["name"])

                if users_not_in_odoo:
                    summary_lines.append(
                        "Note: %s grants access to AD user(s) %s who haven't "
                        "logged into Odoo yet - they'll gain visibility "
                        "automatically the next time this sync runs after "
                        "their first login." % (info["name"], ", ".join(users_not_in_odoo))
                    )
                if unresolved:
                    summary_lines.append(
                        "Note: %s has principals not found in AD at all "
                        "(likely Windows built-in/local accounts, e.g. "
                        "BUILTIN\\Administrators - these can't be mapped to "
                        "Odoo and are ignored): %s"
                        % (info["name"], ", ".join(unresolved))
                    )
        finally:
            ad_conn.unbind()

        summary = "\n".join(summary_lines) if summary_lines else "No changes - everything already in sync."
        self.write({
            "last_run_date": fields.Datetime.now(),
            "last_run_summary": summary,
        })
        _logger.info("PBIRS Discovery: %s", summary)
