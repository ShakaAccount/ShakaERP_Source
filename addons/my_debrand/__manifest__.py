{
    'name': 'My Debrand',
    'version': '1.0',
    'category': 'Customizations',
    'summary': 'Strip Odoo branding from the login page and shell',
    'depends': ['web'],
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'my_debrand/static/src/scss/login.scss',
        ],
        'web.assets_backend': [
            'my_debrand/static/src/scss/debrand.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
