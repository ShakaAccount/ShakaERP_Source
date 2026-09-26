{
    'name': 'Shaka UI Kit',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'Reusable OWL UI building blocks shared across Shaka ERP addons.',
    'description': """
Shaka UI Kit
============
Shared OWL components styled with the ``shaka_theme`` tokens, starting with
the tree component used by ``category`` and ``win_access``.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/shaka_ui_kit/static/description/icon.svg',
    'depends': ['web', 'shaka_theme'],
    'assets': {
        'web.assets_backend': [
            'shaka_ui_kit/static/src/js/tree_node.js',
            'shaka_ui_kit/static/src/xml/tree_node.xml',
            'shaka_ui_kit/static/src/scss/tree.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
