{
    'name': 'Payment Request',
    'summary': 'Payment requests against DW dimensions and generic lookups',
    'category': 'Uncategorized',
    'version': '19.0.1.0.0',
    'depends': ['base', 'mail', 'generic_lookup'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/lookup_data.xml',
        'views/views.xml',
        'views/dw_connection_views.xml',
        'views/dw_remote_table_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'payment_request/static/src/pr_stage_radio.js',
            'payment_request/static/src/pr_stage_radio.xml',
            'payment_request/static/src/pr_stage_radio.scss',
        ],
    },
    'installable': True,
    'application': False,
}
