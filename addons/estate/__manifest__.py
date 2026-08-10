{
    'name': "Real Estate",
    'summary': "Real Estate module for the Odoo tutorial",
    'description': """
Real Estate advertisement management.
    """,
    'author': "Amirhosin",
    'category': 'Real Estate',
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/estate_property_views.xml',
        'views/estate_menus.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
