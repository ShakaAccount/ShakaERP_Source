{
    'name': 'Payment Request',
    'summary': 'Payment requests against DW dimensions and generic lookups',
    'category': 'Uncategorized',
    'version': '19.0.1.0.0',
    'depends': ['base', 'mail', 'generic_lookup', 'raes_dw_connector'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/lookup_data.xml',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
}
