{
    'name': 'Sales Analysis',
    'version': '19.0.1.0.0',
    'summary': 'Manual allocation of receipts to sales invoices',
    'category': 'Accounting',
    'author': 'ShakaERP',
    'license': 'LGPL-3',
    'icon': '/sales_analysis/static/description/icons8-receipt-100 (1).png',
    'depends': ['base', 'mail', 'raes_dw_connector', 'shaka_security'],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/sales_analysis_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sales_analysis/static/src/scss/sales_analysis_theme.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
