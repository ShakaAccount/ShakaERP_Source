{
    'name': 'Shaka Security',
    'version': '19.0.1.0.0',
    'category': 'Administration',
    'summary': 'Central roles and access levels for Shaka modules',
    'description': """
Shaka Security
==============
Provides ``shaka.access.mixin``: form-level access control keyed by
``shaka.access.form`` and per-user ``shaka.user.form.access`` records, plus
a workflow-stage access check. Superusers and Settings administrators
always bypass it.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/shaka_security/static/description/icon.svg',
    'depends': ['base', 'raes_dw_connector'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/access_forms.xml',
        'data/cleanup_legacy_access.xml',
        'views/users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
