{
    'name': 'برنامه و بودجه',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'مدیریت برنامه‌ریزی، بودجه و زنجیره اجرای اهداف',
    'description': """
Budget Planning
===============
Planning and budgeting workflow that links strategic goals to the budget
lines that execute them, with step-by-step approval stages, Jalali dates
and form-level access through ``shaka_security``.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/budget_planning/static/description/icon.svg',
    'depends': ['base', 'generic_lookup', 'company_base_info', 'shaka_theme', 'jalali_date', 'holding_budget', 'category'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/budget_lookup_data.xml',
        'data/access_forms.xml',
        'views/budget_planning_views.xml',
        'views/financial_statement_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'budget_planning/static/src/js/budget_planning_steps.js',
            'budget_planning/static/src/js/financial_account_tree.js',
            'budget_planning/static/src/js/financial_statement_lines.js',
            'budget_planning/static/src/xml/financial_account_tree.xml',
            'budget_planning/static/src/xml/financial_statement_lines.xml',
            'budget_planning/static/src/scss/budget_planning.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
