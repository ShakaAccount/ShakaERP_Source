{
    'name': 'Shaka UI Makeover + Liquid Glass',
    'version': '1.0.0',
    'category': 'Themes',
    'summary': 'Full liquid-glass UI makeover for ShakaERP — glass chrome, views, POS, settings coverage, settable button colors, Persian font, single theme',
    'description': """
Liquid Glass UI theme for ShakaERP.

A complete liquid-glass redesign that covers every backend surface:
navbar, control panel, app switcher, home dashboard, kanban, list, form,
chatter, settings, login, POS, and a subtle ambient world animation.

* Single theme ("glass") — no user toggle; the theme attribute is set
  declaratively from a QWeb template injected into ``web.layout`` head.
* Settable primary button color and button text color from
  Settings > General Settings > Shaka ERP > UI Theme (per-company).
  Applied declaratively via a server-rendered ``<style>`` block so the
  first paint already shows the configured color.
* Persian font stack with RTL polish for Jalali-aware workflows.
* Compiles cleanly through Odoo's libsass concatenation (no local @import).
* Does not modify any file in ``odoo/addons``.

Replaces the older ``shaka_skeuomorphic_ui`` addon; uninstall that one
after this theme has been validated.
""",
    'depends': ['web', 'point_of_sale'],
    'data': [
        'views/layout_inject.xml',
        'views/company_settings_views.xml',
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