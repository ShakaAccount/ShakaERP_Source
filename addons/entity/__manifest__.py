{
    'name': 'RAES — MD Entity / Module (Shaka DW)',
    'version': '19.0.1.0.0',
    'summary': 'Direct Odoo models over md.entity and gnr.module.',
    'author': 'RAES',
    'category': 'Technical',
    'license': 'LGPL-3',
    'depends': ['base'],
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
}