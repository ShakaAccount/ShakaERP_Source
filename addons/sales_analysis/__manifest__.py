{
    'name': 'Sales Analysis',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Manual allocation of receipts to sales invoices',
    'description': """
Sales Analysis
==============
Manually allocate customer receipts to the sales invoices they settle,
with numbered allocation documents for reconciliation analysis.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/sales_analysis/static/description/icon.png',
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
