{
    'name': "category",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','web','entity'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/category_views.xml',
        # 'views/actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'category/static/src/js/split_view.js',
            'category/static/src/xml/split_view.xml',
            'category/static/src/js/category_manager.js',
            'category/static/src/xml/category_manager.xml',
            # 'my_module/static/src/scss/split_view.scss',  # Optional for custom styling
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
}

