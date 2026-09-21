{
    'name': 'برنامه و بودجه',
    'version': '19.0.1.0.0',
    'category': 'Operations/Planning',
    'summary': 'مدیریت برنامه‌ریزی، بودجه و زنجیره اجرای اهداف',
    'author': 'ShakaERP',
    'license': 'LGPL-3',
    'icon': '/budget_planning/static/description/icon.svg',
    'depends': ['base', 'generic_lookup', 'company_base_info', 'shaka_ui_makeover', 'jalali_date'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/budget_lookup_data.xml',
        'data/access_forms.xml',
        'views/budget_planning_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'budget_planning/static/src/js/budget_planning_steps.js',
            'budget_planning/static/src/scss/budget_planning.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
