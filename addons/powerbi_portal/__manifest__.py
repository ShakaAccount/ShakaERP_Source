{
    "name": "Power BI Portal",
    "version": "19.0.1.0.0",
    "summary": "Power BI reports sidebar + AD-driven access, with two-way sync to PBIRS",
    "description": """
Power BI Portal
================
Shows a side navigation list of Power BI Report Server reports the current
user is allowed to see, filtered by Odoo security groups. Clicking a report
loads it in an iframe next to the sidebar, without a full page reload.
Authentication into the report itself is handled entirely by the browser's
own Windows/Kerberos session with the Report Server - Odoo never sees or
stores report-server credentials.

Includes (formerly the separate 'AD Group Sync' module, now merged in):
- AD Group Sync: keeps chosen Odoo security groups in sync with Active
  Directory group membership (pull, AD -> Odoo, on a schedule).
- PBIRS Discovery: reads the Report Server's own SQL Server database
  directly to find which AD groups already have access to which reports,
  and mirrors that into Odoo automatically (pull, PBIRS -> Odoo).
- PBIRS Access Push: automatically pushes a report's allowed groups/users
  back to PBIRS whenever the record is saved (manual save or autosave) -
  and auto-creates a matching AD group, seeded with the right members, if
  one doesn't already exist - the reverse direction, Odoo -> AD/PBIRS.

Recommended setup - one service account for everything:
Rather than separate credentials per integration, create a single
dedicated AD service account (e.g. DOMAIN\\svc-odoo-pbi) and:
  1. Run the Odoo Windows service AS this account (Services > Odoo > Log
     On tab). This alone covers Windows-Integrated auth for both the
     PBIRS Discovery SQL connection and the PBIRS SOAP access-push calls,
     with no extra passwords stored in Odoo for either.
  2. Use the SAME account's DN + password for the AD Group Sync LDAP bind
     below (LDAP needs an explicit bind, it can't reuse the Windows
     process identity the way the SQL/SOAP calls can).
  3. Grant this one account: db_datareader on the PBIRS ReportServer SQL
     database; Content Manager (or a narrower custom role) on the PBIRS
     folders reports live in; and Create Group objects delegated on a
     dedicated AD OU (for the access-push auto-create feature) - not
     domain admin, not sa, not System Administrator in PBIRS.
""",
    "category": "Extra Tools",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "external_dependencies": {
        # ldap3: AD Group Sync LDAP bind (pure Python, no C extension - avoids
        #   the python-ldap/OpenLDAP-headers compile problem on Windows).
        # pyodbc: PBIRS Discovery SQL connection.
        # requests: PBIRS Access Push SOAP calls. Also needs EITHER
        #   requests-negotiate-sspi (Windows Integrated, recommended - see
        #   single-account setup above) OR requests-ntlm (explicit domain
        #   credentials) depending on SOAP Auth Mode - not listed here since
        #   only one of the two is needed; the module gives an install hint
        #   naming the right one if it's missing.
        "python": ["ldap3", "pyodbc", "requests"]
    },
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/powerbi_report_views.xml",
        "views/ad_group_sync_views.xml",
        "views/pbirs_discovery_views.xml",
        "data/ir_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "powerbi_portal/static/src/js/powerbi_portal.js",
            "powerbi_portal/static/src/xml/powerbi_portal.xml",
            "powerbi_portal/static/src/scss/powerbi_portal.scss",
        ],
    },
    "installable": True,
    "application": True,
}
