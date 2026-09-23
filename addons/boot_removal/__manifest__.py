{
    'name': 'Boot Removal',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'summary': 'Disables, archives, and rebrands OdooBot to ShakaBot upon initialization',
    'description': """
Boot Removal
============
On install, renames the OdooBot user and root partner to *ShakaBot*,
disables its onboarding chat and removes the default welcome posts from
the #general channel.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/boot_removal/static/description/icon.svg',
    'depends': ['base', 'mail', 'mail_bot'],
    'data': [],
    'post_init_hook': 'disable_odoobot_completely',
    'installable': True,
    'application': False,
    'auto_install': True,
}
