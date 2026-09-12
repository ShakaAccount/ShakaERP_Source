{
    'name': 'RAES DW Connector',
    'summary': 'MSSQL data-warehouse foreign tables exposed as Odoo views',
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/dw_connection_views.xml',
        'views/dw_remote_table_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
