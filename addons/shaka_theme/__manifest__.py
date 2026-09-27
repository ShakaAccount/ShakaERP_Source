{
    'name': 'Shaka Theme',
    'summary': 'Apple-refined backend theme for Shaka ERP: system blue, system font + Vazirmatn, macOS-compact (light + dark, Persian/RTL)',
    'description': """
Replaces the deprecated ``shaka_ui_makeover``.

Themes Odoo through its own SCSS variables (``web._assets_primary_variables`` /
``web.dark_mode_variables``) instead of selector overrides, so every view picks
it up and Odoo Enterprise's dark mode (User preferences) just works.

Design source of truth: ``design-system/shaka-erp/MASTER.md``.
Addon SCSS should use the ``var(--shaka-*)`` tokens, never dark-mode selectors.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'category': 'Themes/Backend',
    'version': '19.0.2.0.0',
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
        # Bootstrap variables, where the $o-* values already exist per scheme.
        'web._assets_backend_helpers': [
            ('before', 'web_enterprise/static/src/scss/bootstrap_overridden.scss',
             'shaka_theme/static/src/scss/bootstrap_overridden.scss'),
        ],
        'web.assets_backend': [
            'shaka_theme/static/src/scss/fonts.scss',
            'shaka_theme/static/src/scss/tokens.scss',
            'shaka_theme/static/src/scss/backend.scss',
            'shaka_theme/static/src/scss/navigation.scss',
            'shaka_theme/static/src/scss/surfaces/*.scss',
            'shaka_theme/static/src/transitions/*',
            'shaka_theme/static/src/components/*',
        ],
        # Odoo appends its *.dark.scss after the backend bundle; re-append the
        # surface files so they win at equal specificity in dark mode too.
        'web.assets_web_dark': [
            ('remove', 'shaka_theme/static/src/scss/navigation.scss'),
            'shaka_theme/static/src/scss/navigation.scss',
            ('remove', 'shaka_theme/static/src/scss/surfaces/*.scss'),
            'shaka_theme/static/src/scss/surfaces/*.scss',
        ],
        'web.assets_frontend': [
            'shaka_theme/static/src/scss/fonts.scss',
            'shaka_theme/static/src/scss/tokens.scss',
            'shaka_theme/static/src/scss/surfaces/30_shell.scss',  # login wallpaper
            'shaka_theme/static/src/transitions/error_shake.css',  # login error
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
