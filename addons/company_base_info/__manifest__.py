{
    'name': 'اطلاعات پایه شرکت',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'مدیریت سال‌های مالی شرکت‌ها',
    'description': """
Company Base Information
========================
Master data shared by the Shaka finance modules: company fiscal years,
boards of directors, ownership structure and currencies.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/company_base_info/static/description/icon.svg',
    'depends': ['base', 'jalali_date', 'shaka_security', 'generic_lookup'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/board_lookup_data.xml',
        'data/currency_lookup_data.xml',
        'data/access_forms.xml',
        'views/fiscal_year_views.xml',
        'views/board_views.xml',
        'views/ownership_views.xml',
        'views/currency_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
