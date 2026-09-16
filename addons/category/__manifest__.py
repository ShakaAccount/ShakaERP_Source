{
    'name': 'Category',
    'summary': 'Standalone 3-pane Category Manager over md.category / '
               'md.category_member (Shaka DW).',
    'description': """
Category Manager
================
A standalone OWL client action that links rows of a dynamic data-warehouse
table to the legacy ``md.category`` hierarchy through
``md.category_member``.

The legacy tables live in the ``md`` schema and cannot be modified, so Odoo
addresses them through writable public mirror views
(``public.raes_md_category`` / ``public.raes_md_category_member``) rebuilt by
``refresh_writable_view`` on every install and upgrade.
""",
    'author': 'RAES',
    'website': 'https://www.yourcompany.com',
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'web', 'entity'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/category_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'category/static/src/js/category_manager.js',
            'category/static/src/xml/category_manager.xml',
            'category/static/src/scss/category_manager.scss',
        ],
    },
    'installable': True,
    'application': True,
}
