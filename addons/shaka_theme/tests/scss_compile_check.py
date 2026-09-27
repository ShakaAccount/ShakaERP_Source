"""Standalone check (not an Odoo test): compile every shaka_theme SCSS file
through libsass in the same concatenation order Odoo builds the light and dark
backend bundles (primary + secondary variables, backend helpers including the
enterprise .dark files, Bootstrap's _variables/_variables-dark/_maps), and
assert the variables actually resolve to the Shaka palette.

    .venv/bin/python addons/shaka_theme/tests/scss_compile_check.py
"""
import glob
import os
import re

import sass

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ADDON))
WEB = os.path.join(ROOT, 'odoo/addons/web/static')
BS = f'{WEB}/lib/bootstrap/scss'
ENT = os.path.join(ROOT, 'odoo/addons/web_enterprise/static/src/scss')
SRC = os.path.join(ADDON, 'static/src')
OURS = os.path.join(SRC, 'scss')
ENT_SRC = os.path.dirname(ENT)


def helpers(dark):
    # web._assets_helpers; the dark bundle slots enterprise's tint/shade swap
    # in after Bootstrap's _functions.
    return ([f'{BS}/_functions.scss']
            + ([f'{ENT}/bs_functions_overridden.dark.scss'] if dark else [])
            + [f'{BS}/_mixins.scss', f'{WEB}/src/scss/functions.scss',
               f'{WEB}/src/scss/mixins_forwardport.scss', f'{WEB}/src/scss/bs_mixins_overrides.scss',
               f'{WEB}/src/scss/utils.scss'])


def component_vars(root):
    return sorted(p for p in glob.glob(f'{root}/**/*.scss', recursive=True)
                  if p.endswith(('.variables.scss', '.variables.dark.scss')))


def variables(dark):
    # web._assets_primary_variables + web._assets_secondary_variables, with
    # web.dark_mode_variables' .dark files each placed before its light file.
    d = lambda path: [path.replace('.scss', '.dark.scss')] if dark else []  # noqa: E731
    return (d(f'{OURS}/primary_variables.scss') + [f'{OURS}/primary_variables.scss']
            + d(f'{ENT}/primary_variables.scss') + [f'{ENT}/primary_variables.scss']
            + [f'{WEB}/src/scss/primary_variables.scss']
            + ([f for f in component_vars(ENT_SRC) if f.endswith('.dark.scss')] if dark else [])
            + [f for f in component_vars(ENT_SRC) if not f.endswith('.dark.scss')]
            + [f for f in component_vars(f'{WEB}/src') if not f.endswith('.dark.scss')]
            + d(f'{ENT}/secondary_variables.scss') + [f'{ENT}/secondary_variables.scss']
            + [f'{WEB}/src/scss/secondary_variables.scss'])


def backend_helpers(dark):
    # web._assets_backend_helpers: ours before enterprise's; in dark, the
    # enterprise .dark file lands between them.
    return ([f'{OURS}/bootstrap_overridden.scss']
            + ([f'{ENT}/bootstrap_overridden.dark.scss'] if dark else [])
            + [f'{ENT}/bootstrap_overridden.scss', f'{WEB}/src/scss/bootstrap_overridden.scss',
               f'{WEB}/src/scss/bs_mixins_overrides_backend.scss',
               f'{WEB}/src/scss/pre_variables.scss',
               f'{BS}/_variables.scss', f'{BS}/_variables-dark.scss', f'{BS}/_maps.scss'])


def theme_files():
    """Every theme .scss (subfolders included) in manifest order: primitives,
    then the numbered surfaces, then the rest."""
    head = [f'{OURS}/{n}.scss' for n in ('fonts', 'tokens', 'backend', 'navigation')]
    chain = {f'{OURS}/primary_variables.scss', f'{OURS}/primary_variables.dark.scss',
             f'{OURS}/bootstrap_overridden.scss'}
    rest = sorted(os.path.join(d, n) for d, _, names in os.walk(SRC) for n in names if n.endswith('.scss'))
    return head + [p for p in rest if p not in chain and p not in head]


PROBES = {
    'brand': '$o-brand-primary', 'action': '$o-action', 'link': '$o-main-link-color',
    'gray-100': '$o-gray-100', 'gray-900': '$o-gray-900', 'view-bg': '$o-view-background-color',
    'webclient-bg': '$o-webclient-background-color', 'danger': '$o-danger',
    'favorite': '$o-main-favorite-color', 'text-primary': 'map-get($o-theme-text-colors, "primary")',
    'btn-primary-bg': 'map-get(map-get($o-btns-bs-override, "primary"), "background")',
    'btn-primary-color': 'map-get(map-get($o-btns-bs-override, "primary"), "color")',
    'btn-danger-color': 'map-get(map-get($o-btns-bs-override, "danger"), "color")',
    'btn-outline-primary': 'map-get(map-get($o-btns-bs-outline-override, "primary"), "color")',
    'sans': '$o-font-family-sans-serif', 'headings': '$o-headings-font-family',
    'system-fonts': '$o-system-fonts', 'radius': '$o-border-radius', 'radius-lg': '$o-border-radius-lg',
    'badge-radius': '$badge-border-radius', 'card-radius': '$card-border-radius',
    'modal-radius': '$modal-content-border-radius', 'btn-radius': '$btn-border-radius',
}


def compile_chain(dark):
    files = helpers(dark) + variables(dark) + backend_helpers(dark) + theme_files()
    probe = '.probe{' + ''.join(f'--p-{k}: #{{{v}}};' for k, v in PROBES.items()) + '}'
    # No surface uses the material mixin yet: exercise it here.
    probe += ''.join(f'.probe-{m}{{@include shaka-material({m});}}' for m in ('thin', 'regular', 'thick'))
    blob = '\n'.join(open(p).read() for p in files) + probe
    css = sass.compile(string=blob, include_paths=[BS])
    return css, dict(re.findall(r'--p-([\w-]+): ([^;]+);', css))


def colour_keys(path):
    """Names of colour variables and colour map entries (`$var.key.key`)."""
    keys, stack = set(), []
    for line in open(path):
        line = line.split('//')[0].strip()
        m = re.match(r'\$?"?([\w-]+)"?\s*:\s*(.*)', line)
        if m:
            name, val = m.groups()
            if val.endswith('('):
                stack.append(name)
            elif re.search(r'#[0-9a-fA-F]{3,8}\b|rgba\(', val):
                keys.add('.'.join(stack + [name]))
        elif line.startswith(')') and stack:
            stack.pop()
    return keys


def main():
    light_css, light = compile_chain(dark=False)
    dark_css, dark = compile_chain(dark=True)

    # Palette (MASTER.md): action fill the same in both schemes, link per scheme.
    assert light['brand'].lower() == dark['brand'].lower() == '#0071e3', (light, dark)
    assert light['btn-primary-bg'].lower() == dark['btn-primary-bg'].lower() == '#0071e3'
    assert light['link'].lower() == light['action'].lower() == '#0066cc', light
    assert dark['link'].lower() == dark['action'].lower() == '#2997ff', dark
    assert light['gray-100'].lower() == light['webclient-bg'].lower() == '#f5f5f7', light
    assert dark['gray-100'].lower() == dark['webclient-bg'].lower() == '#1c1c1e', dark
    assert light['gray-900'].lower() == '#1d1d1f' and dark['gray-900'].lower() == '#f5f5f7'
    assert light['view-bg'].lower() == '#ffffff' and dark['view-bg'].lower() == '#2c2c2e'
    assert light['danger'].lower() == '#d70015' and dark['danger'].lower() == '#ff7b73'
    assert light['favorite'].lower() == '#8a6a3b' and dark['favorite'].lower() == '#c9a774'
    assert light['text-primary'].lower() == '#0066cc' and dark['text-primary'].lower() == '#2997ff'
    assert dark['btn-outline-primary'].lower() == '#2997ff'
    # Odoo's dark $o-white is #000: white button text must be the literal.
    for k in ('btn-primary-color', 'btn-danger-color'):
        assert light[k].lower() == dark[k].lower() == '#fff', (k, light[k], dark[k])

    # Type (interpolation drops the quotes): Vazirmatn first (Arabic script only), then the OS system font.
    for scheme in (light, dark):
        assert scheme['system-fonts'].startswith('Vazirmatn, system-ui, -apple-system'), scheme
        assert scheme['sans'].startswith('Vazirmatn, system-ui'), scheme
        assert scheme['headings'] == scheme['sans'], scheme
    assert light_css.count('unicode-range: U+0600-06FF') == 3

    # Shape: enterprise's zeroed radii are back.
    for scheme in (light, dark):
        assert scheme['radius'] == '0.375rem' and scheme['radius-lg'] == '0.625rem', scheme
        assert scheme['badge-radius'] == '999px' and scheme['modal-radius'] == '0.875rem', scheme
        assert scheme['card-radius'] == scheme['radius-lg'] and scheme['btn-radius'] == scheme['radius']

    # Tokens, per scheme; libsass passes linear() through untouched.
    assert '--shaka-surface: #FFFFFF' in light_css and '--shaka-surface: #2C2C2E' in dark_css
    assert '--shaka-link: #0066CC' in light_css and '--shaka-link: #2997FF' in dark_css
    assert '--shaka-spring: linear(0, 0.068,' in light_css
    assert 'prefers-reduced-motion: reduce' in light_css
    assert 'background-color: rgba(255, 255, 255, 0.88)' in light_css
    assert 'background-color: rgba(44, 44, 46, 0.72)' in dark_css
    for css in (light_css, dark_css):
        assert css.count('-webkit-backdrop-filter: blur(') >= 3
        assert 'prefers-reduced-transparency: reduce' in css and 'prefers-contrast: more' in css

    # Every colour set in the light file must be mirrored in the dark file,
    # otherwise the light value (loaded second, but !default) leaks into dark.
    missing = colour_keys(f'{OURS}/primary_variables.scss') - colour_keys(f'{OURS}/primary_variables.dark.scss')
    assert not missing, f'colours missing from primary_variables.dark.scss: {sorted(missing)}'

    # House rules from MASTER.md.
    for d, _, names in os.walk(OURS):
        for name in names:
            src = open(os.path.join(d, name)).read()
            assert 'data-theme' not in src and 'shaka-dark-mode' not in src, f'{name}: theme/dark gate'
            if name != 'backend.scss':
                assert '!important' not in src, f'{name}: !important'

    print(f'OK  {len(theme_files())} theme files; light {len(light_css)} B, dark {len(dark_css)} B')


if __name__ == '__main__':
    main()
