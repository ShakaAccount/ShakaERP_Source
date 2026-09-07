{
    'name': 'Generic Lookup Tables',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Generic key-value lookup types and values for use across custom modules',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/lookup_type_views.xml',
        'views/lookup_value_views.xml',
    ],
    'installable': True,
    'application': False,
}
