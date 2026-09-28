{
    'name': 'Telegram',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Telegram bot notifications, templates and two-way chat',
    'description': """
Telegram Bot Integration
========================
* Forwards users' Odoo notifications (mentions, direct messages, followed
  records) to their Telegram chat.
* Send messages to contacts from any record through a composer and templates.
* "Send Telegram" server action for Automation Rules.
* Two-way chat: messages sent to the bot open Telegram channels in Discuss.

Inbound messages are fetched by polling ``getUpdates`` from a cron, so the
server does not need to be reachable from Telegram. All API calls go through
the proxy set in Settings (``telegram.proxy_url``).
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/telegram/static/description/icon.svg',
    'depends': ['mail', 'base_setup', 'calendar'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/telegram_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/calendar_alarm_data.xml',
        'wizard/telegram_composer_views.xml',
        'views/telegram_bot_views.xml',
        'views/telegram_message_views.xml',
        'views/telegram_template_views.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/ir_actions_server_views.xml',
        'views/res_config_settings_views.xml',
        'views/telegram_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'telegram/static/src/discuss/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
