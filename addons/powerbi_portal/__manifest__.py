{
    "name": "Power BI Portal",
    "version": "19.0.1.0.0",
    "summary": "Power BI reports sidebar + AD-driven access, with two-way sync to PBIRS",
    "description": """Power BI Portal
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

FastAPI mode (recommended - replaces direct SQL + SOAP):
Turn on 'Use FastAPI' in PBIRS Discovery > Connection Settings and provide
the Windows Access Management API Base URL + API Key. The API runs on the BI
host with the correct Windows/AD service identity, so Odoo no longer needs
Kerberos/SSPI/NTLM libraries or an ODBC driver to reach PBIRS - it also
unlocks SSAS, AD and local-group provisioning from the same endpoint. Both
Discovery (pull) and Access Push (write) then route through the API, fixing
the Windows-Integrated auth problem entirely (the old 401/SSPI errors).

Cross-platform notes:

- Windows Integrated SOAP auth uses 'requests-kerberos' (cross-platform
  Kerberos/GSSAPI) with fallback to 'requests-negotiate-sspi' (Windows
  SSPI). On Linux, the Odoo service must have a valid Kerberos TGT. In
  FastAPI mode none of this is needed.
- ODBC driver name must match exactly what's installed on the machine:
  check with 'Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}'
  in PowerShell on Windows, or 'odbcinst -q -d | grep -i sql' on Linux.
""",
    "category": 'Shaka ERP',
    "author": "ShakaERP",
    "maintainer": "ShakaERP",
    "website": "https://shakasystem.com",
    "license": "LGPL-3",
    "icon": "/powerbi_portal/static/description/icon.png",
    "depends": ["base", "web", "shaka_ui_kit"],
    "external_dependencies": {
        # ldap3: AD Group Sync LDAP bind (pure Python, no C extension - avoids
        #   the python-ldap/OpenLDAP-headers compile problem on Windows).
        # pyodbc: PBIRS Discovery SQL connection (only in legacy non-FastAPI mode).
        # requests: PBIRS Access Push calls - used by the FastAPI client
        #   (recommended). In legacy SOAP mode it also needs EITHER
        #   requests-kerberos (cross-platform Kerberos/GSSAPI - recommended,
        #   works on both Windows and Linux) OR requests-negotiate-sspi
        #   (Windows-only SSPI) OR requests-ntlm (explicit domain credentials).
        #   Not listed here since which one is needed depends on the auth mode;
        #   the module gives an install hint naming the right one if missing.
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
    "auto_install": False,
}
