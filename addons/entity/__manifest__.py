{
    'name': 'RAES — MD Entity / Module (Shaka DW)',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'Direct Odoo models over md.entity and gnr.module.',
    'description': """
MD Entity / Module
==================
Exposes the Shaka DW metadata tables (``md.entity``, ``md.entity_column``,
``gnr.module``, ``gnr.lookup``) as Odoo models through writable mirror views,
and provides the DDL builder and Persian-normalisation query helpers reused
by ``category``, ``win_access`` and other DW-backed addons.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/entity/static/description/icon.svg',
    'depends': ['base', 'raes_dw_connector'],
    'data': [
        'security/ir.model.access.csv',
        'views/gnr_module_views.xml',
        'views/md_entity_views.xml',
        'views/gnr_lookup_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
