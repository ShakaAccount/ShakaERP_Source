{
    'name': 'Shaka Theme',
    'summary': 'Minimal, dense backend theme for Shaka ERP (light + dark, Persian/RTL)',
    'description': """
Replaces the deprecated ``shaka_ui_makeover``.

Themes Odoo through its own SCSS variables (``web._assets_primary_variables`` /
``web.dark_mode_variables``) instead of selector overrides, so every view picks
it up and Odoo Enterprise's dark mode (User preferences) just works.

Design source of truth: ``design-system/shaka-erp/MASTER.md``.
Addon SCSS should use the ``var(--shaka-*)`` tokens, never dark-mode selectors.
""",
    'author': 'RAES',
    'category': 'Themes',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'icon': '/shaka_theme/static/description/icon.svg',
    'depends': ['web', 'web_enterprise'],
    'assets': {
        # Before web_enterprise's variables: first `!default` definition wins.
        'web._assets_primary_variables': [
            ('before', 'web_enterprise/static/src/scss/primary_variables.scss',
             'shaka_theme/static/src/scss/primary_variables.scss'),
        ],
        # Dark bundle: dark values load before the light ones, so they win.
        'web.dark_mode_variables': [
            ('before', 'shaka_theme/static/src/scss/primary_variables.scss',
             'shaka_theme/static/src/scss/primary_variables.dark.scss'),
        ],
        'web.assets_backend': [
            'shaka_theme/static/src/scss/fonts.scss',
            'shaka_theme/static/src/scss/tokens.scss',
            'shaka_theme/static/src/scss/backend.scss',
            'shaka_theme/static/src/transitions/card_resize.css',
            'shaka_theme/static/src/transitions/dialog_card_resize.js',
            'shaka_theme/static/src/transitions/menu_dropdown.css',
            'shaka_theme/static/src/transitions/dropdown_menu.js',
        ],
        'web.assets_frontend': [
            'shaka_theme/static/src/scss/fonts.scss',
            'shaka_theme/static/src/scss/tokens.scss',
        ],
    },
    'installable': True,
    'application': False,
}
