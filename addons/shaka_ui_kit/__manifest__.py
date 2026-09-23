{
    'name': 'Shaka UI Kit',
    'summary': 'Reusable OWL UI building blocks shared across Shaka ERP addons.',
    'author': 'RAES',
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'shaka_ui_kit/static/src/js/tree_node.js',
            'shaka_ui_kit/static/src/xml/tree_node.xml',
            'shaka_ui_kit/static/src/scss/tree.scss',
        ],
    },
    'installable': True,
    'application': False,
}
