{
    'name': 'Generic Lookup Tables',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'Generic key-value lookup types and values for use across custom modules',
    'description': """
Generic Lookup Tables
=====================
Lookup types and their values (key/value pairs) that other Shaka modules
use for configurable selection lists instead of hard-coded selections.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/generic_lookup/static/description/icon.svg',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/lookup_type_views.xml',
        'views/lookup_value_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
