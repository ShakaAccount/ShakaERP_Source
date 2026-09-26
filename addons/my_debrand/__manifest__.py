{
    'name': 'My Debrand',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'Strip Odoo branding from the login page and shell',
    'description': """
Debrand
=======
Removes Odoo branding (logos, "Powered by" footer, links) from the login
page and the backend web client shell.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/my_debrand/static/description/icon.svg',
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
}
