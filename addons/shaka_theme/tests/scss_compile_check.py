"""Standalone check (not an Odoo test): compile shaka_theme through libsass in
the same concatenation order Odoo builds the light and dark bundles, and assert
the variables actually resolve to the Shaka palette.

    .venv/bin/python addons/shaka_theme/tests/scss_compile_check.py
"""
import os
import re

import sass

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ADDON))
WEB = os.path.join(ROOT, 'odoo/addons/web/static')
ENT = os.path.join(ROOT, 'odoo/addons/web_enterprise/static/src/scss')
OURS = os.path.join(ADDON, 'static/src/scss')

HELPERS = [
    f'{WEB}/lib/bootstrap/scss/_functions.scss',
    f'{WEB}/lib/bootstrap/scss/_mixins.scss',
    f'{WEB}/src/scss/functions.scss',
    f'{WEB}/src/scss/mixins_forwardport.scss',
    f'{WEB}/src/scss/bs_mixins_overrides.scss',
    f'{WEB}/src/scss/utils.scss',
]
LIGHT = [f'{OURS}/primary_variables.scss', f'{ENT}/primary_variables.scss',
         f'{WEB}/src/scss/primary_variables.scss']
# web.dark_mode_variables: ours.dark before ours, enterprise dark before enterprise.
DARK = [f'{OURS}/primary_variables.dark.scss', f'{OURS}/primary_variables.scss',
        f'{ENT}/primary_variables.dark.scss', f'{ENT}/primary_variables.scss',
        f'{WEB}/src/scss/primary_variables.scss']
BUNDLE = [f'{OURS}/fonts.scss', f'{OURS}/tokens.scss', f'{OURS}/backend.scss']

PROBES = ['o-brand-primary', 'o-action', 'o-gray-100', 'o-gray-900', 'o-danger',
          'o-font-family-sans-serif', 'o-border-radius']


def compile_chain(variables):
    probe = '.probe{' + ''.join(f'--{p}: #{{${p}}};' for p in PROBES) + '}'
    blob = '\n'.join(open(p).read() for p in HELPERS + variables + BUNDLE) + probe
    css = sass.compile(string=blob, include_paths=[f'{WEB}/lib/bootstrap/scss'])
    return css, dict(re.findall(r'--([\w-]+): ([^;]+);', css.split('.probe')[-1]))


def colour_vars(path):
    return set(re.findall(r'^\$([\w-]+):\s*#', open(path).read(), re.M))


def main():
    light_css, light = compile_chain(LIGHT)
    dark_css, dark = compile_chain(DARK)

    assert light['o-brand-primary'].lower() == '#1e40af', light
    assert light['o-gray-100'].lower() == '#f8fafc', light
    assert dark['o-brand-primary'].lower() == '#2563eb', dark
    assert dark['o-gray-100'].lower() == '#0b1220', dark
    assert light['o-font-family-sans-serif'].startswith('Vazirmatn'), light
    assert dark['o-font-family-sans-serif'] == light['o-font-family-sans-serif']
    assert '--shaka-surface: #FFFFFF' in light_css
    assert '--shaka-surface: #111827' in dark_css
    assert 'prefers-reduced-motion: reduce' in light_css

    # Every colour set in the light file must be mirrored in the dark file,
    # otherwise the light value (loaded second, but !default) leaks into dark.
    missing = colour_vars(f'{OURS}/primary_variables.scss') - colour_vars(f'{OURS}/primary_variables.dark.scss')
    assert not missing, f'colours missing from primary_variables.dark.scss: {missing}'

    # House rules from MASTER.md.
    for name in os.listdir(OURS):
        src = open(os.path.join(OURS, name)).read()
        assert "data-theme" not in src and 'shaka-dark-mode' not in src, f'{name}: theme/dark gate'
        if name != 'backend.scss':
            assert '!important' not in src, f'{name}: !important'

    print(f'OK  light {len(light_css)} B, dark {len(dark_css)} B')


if __name__ == '__main__':
    main()
