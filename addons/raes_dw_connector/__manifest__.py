{
    'name': 'RAES DW Connector',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'MSSQL data-warehouse foreign tables exposed as Odoo views',
    'description': """
RAES DW Connector
=================
Owns the connection to the Shaka DW SQL Server (``raes.dw.connection``) and
a catalogue of its tables mapped into PostgreSQL through ``tds_fdw`` foreign
tables (``raes.dw.catalog``). The only module that handles MSSQL connection
details directly; every other DW-backed addon builds on it.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/raes_dw_connector/static/description/icon.svg',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/dw_connection_views.xml',
        'views/dw_remote_table_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
