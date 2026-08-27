{
    'name': 'Shaka Skeuomorphic UI',
    'version': '1.0',
    'category': 'Customizations',
    'summary': 'Skeuomorphic UI theme for ShakaERP - realistic textures, depth, and tactile interfaces',
    'depends': ['web'],
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        # Odoo concatenates assets in list order (no local @import allowed), so
        # tokens -> mixins -> themed files must appear in that order.
        'web.assets_frontend': [
            'shaka_skeuomorphic_ui/static/src/scss/design_tokens.scss',
            'shaka_skeuomorphic_ui/static/src/scss/shaka_mixins.scss',
            'shaka_skeuomorphic_ui/static/src/scss/login.scss',
        ],
        'web.assets_backend': [
            'shaka_skeuomorphic_ui/static/src/scss/design_tokens.scss',
            'shaka_skeuomorphic_ui/static/src/scss/shaka_mixins.scss',
            'shaka_skeuomorphic_ui/static/src/scss/backend.scss',
            'shaka_skeuomorphic_ui/static/src/scss/chrome.scss',
            'shaka_skeuomorphic_ui/static/src/scss/views.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}