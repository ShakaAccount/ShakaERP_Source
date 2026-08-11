{
    'name': 'Boot Removal',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'summary': 'Disables, archives, and rebrands OdooBot to ShakaBot upon initialization',
    'depends': ['base', 'mail', 'mail_bot'],
    'post_init_hook': 'disable_odoobot_completely',
    'auto_install': True,
    'installable': True,
}
