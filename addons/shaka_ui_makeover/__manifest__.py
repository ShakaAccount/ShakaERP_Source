{
    'name': 'Shaka UI Makeover + Liquid Glass',
    'version': '1.0.0',
    'category': 'Themes',
    'summary': 'Full liquid-glass UI makeover for ShakaERP — glass chrome, views, POS, settings coverage, settable button colors, Persian font, theme toggle',
    'description': """
Liquid Glass UI theme for ShakaERP.

Provides a complete liquid-glass redesign that covers all backend surfaces,
views, POS UI, settings pages and the login screen. Ships its own design tokens
and mixins (self-contained, no dependency on the skeuomorphic addon):
    * Glass default-on for everyone, with a user-menu theme toggle.
    * Settable button color + button text color in Settings (Company).
    * Self-hosted Persian font with LTR/RTL support.
    * Fully validates through Odoo's libsass concatenation (no @import).

The previous skeuomorphic addon is intentionally left untouched and can be
uninstalled separately once this theme is approved.
""",
    'depends': ['web', 'point_of_sale'],
    'data': [
        'views/theme_toggle.xml',
        'views/company_settings_views.xml',
        'models/res_config_settings.py',
    ],
    'assets': {
        # NOTE: Odoo concatenates assets in list order (no local @import), so
        # design tokens -> mixins -> themed files must appear in that order.
        'web.assets_backend': [
            # design tokens & mixins first
            'shaka_ui_makeover/static/src/scss/design_tokens.scss',
            'shaka_ui_makeover/static/src/scss/mixins.scss',
            # themed surfaces
            'shaka_ui_makeover/static/src/scss/backend.scss',
            'shaka_ui_makeover/static/src/scss/chrome.scss',
            'shaka_ui_makeover/static/src/scss/views.scss',
            'shaka_ui_makeover/static/src/scss/settings.scss',
            'shaka_ui_makeover/static/src/scss/login.scss',
            # theme toggle JS
            'shaka_ui_makeover/static/src/theme_switch/theme_switch.js',
        ],
        'web.assets_frontend': [
            'shaka_ui_makeover/static/src/scss/design_tokens.scss',
            'shaka_ui_makeover/static/src/scss/mixins.scss',
            'shaka_ui_makeover/static/src/scss/login.scss',
        ],
        'point_of_sale.assets_pos': [
            'shaka_ui_makeover/static/src/scss/design_tokens.scss',
            'shaka_ui_makeover/static/src/scss/mixins.scss',
            'shaka_ui_makeover/static/src/scss/pos.scss',
        ],
        # POS UI actually loads from base_app/_assets_pos; add pos skin there too
        'point_of_sale.base_app': [
            'shaka_ui_makeover/static/src/scss/design_tokens.scss',
            'shaka_ui_makeover/static/src/scss/mixins.scss',
            'shaka_ui_makeover/static/src/scss/pos.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}