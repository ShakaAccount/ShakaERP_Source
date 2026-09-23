{
    'name': 'Payment Request',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Payment requests against DW dimensions and generic lookups',
    'description': """
Payment Request
===============
Payment requests coded against read-only Shaka DW dimensions (company,
cost center, ...) and generic lookups, with an activity-driven approval
workflow.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/payment_request/static/description/icon.png',
    'depends': ['base', 'mail', 'generic_lookup', 'raes_dw_connector'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/lookup_data.xml',
        'data/activity_data.xml',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
