"""Compile every SCSS file in manifest order via libsass and assert no errors.

This is the same concatenation order Odoo uses for its asset bundles
(libsass has no local @import in Odoo, files are concatenated as listed in
the `assets` key of __manifest__.py).  If this script passes, the bundle
is valid SCSS and produces the liquid-glass surface.
"""
import os
import sys
import sass  # python-sass (Libsass binding) — importable as `sass`

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCSS_DIR = os.path.join(ADDON_ROOT, 'static/src/scss')

# Order MUST match web.assets_backend in __manifest__.py
BACKEND_ORDER = [
    'design_tokens.scss',
    'mixins.scss',
    'backend.scss',
    'chrome.scss',
    'views.scss',
    'settings.scss',
    'login.scss',
    'pos.scss',
]

# web.assets_frontend (login only)
FRONTEND_ORDER = [
    'design_tokens.scss',
    'mixins.scss',
    'login.scss',
]

# point_of_sale.assets_pos and point_of_sale.base_app
POS_ORDER = [
    'design_tokens.scss',
    'mixins.scss',
    'pos.scss',
]


def _read_concat(order):
    paths = []
    for name in order:
        p = os.path.join(SCSS_DIR, name)
        assert os.path.exists(p), f'missing {name}'
        paths.append(p)
    return '\n'.join(open(p).read() for p in paths), paths


def test_backend_bundle():
    blob, paths = _read_concat(BACKEND_ORDER)
    css = sass.compile(string=blob)
    assert len(css) > 30_000, f'backend bundle too small: {len(css)} bytes'
    # Sanity: glass surface is present
    assert 'backdrop-filter' in css or '-webkit-backdrop-filter' in css, \
        'no backdrop-filter in compiled backend CSS'
    # The --lg-* design tokens are exported to :root
    assert '--lg-accent' in css, 'no --lg-accent in compiled backend CSS'
    # Theme gate appears many times
    gate = "data-theme='glass'"
    assert css.count(gate) > 100, \
        f'expected >100 theme gates, got {css.count(gate)}'
    # Dark mode is wired in
    assert 'prefers-color-scheme: dark' in css, 'no dark-mode media query'
    # Reduced-motion respected
    assert 'prefers-reduced-motion: reduce' in css, \
        'no reduced-motion media query'
    return len(css)


def test_frontend_bundle():
    blob, paths = _read_concat(FRONTEND_ORDER)
    css = sass.compile(string=blob)
    assert len(css) > 5_000, f'frontend bundle too small: {len(css)} bytes'
    assert 'backdrop-filter' in css or '-webkit-backdrop-filter' in css
    assert '.oe_login_form' in css, 'login form selector missing'
    return len(css)


def test_pos_bundle():
    blob, paths = _read_concat(POS_ORDER)
    css = sass.compile(string=blob)
    assert len(css) > 5_000, f'POS bundle too small: {len(css)} bytes'
    assert 'backdrop-filter' in css or '-webkit-backdrop-filter' in css
    # POS classes verified during development
    assert '.pos' in css, 'no .pos selector in compiled POS CSS'
    return len(css)


def test_no_unused_mixins():
    """Make sure every @mixin defined in mixins.scss is actually used at
    least once in the themed files.  A dead mixin means either dead code
    or a refactor that left an orphan."""
    mixins_blob = open(os.path.join(SCSS_DIR, 'mixins.scss')).read()
    # Naive: extract @mixin names
    names = []
    for line in mixins_blob.splitlines():
        line = line.strip()
        if line.startswith('@mixin '):
            names.append(line.split()[1].split('(')[0])
    assert names, 'no @mixin definitions found in mixins.scss'
    # Concatenate the rest (skip mixins.scss to avoid self-usage)
    rest = '\n'.join(
        open(os.path.join(SCSS_DIR, f)).read()
        for f in BACKEND_ORDER if f != 'mixins.scss'
    )
    unused = [n for n in names if f'@include {n}' not in rest]
    assert not unused, f'unused mixins: {unused}'


if __name__ == '__main__':
    failures = []
    for name, fn in [
        ('backend bundle', test_backend_bundle),
        ('frontend bundle', test_frontend_bundle),
        ('POS bundle', test_pos_bundle),
        ('no unused mixins', test_no_unused_mixins),
    ]:
        try:
            size = fn()
            print(f'OK   {name:<22} {size:,} bytes' if size else f'OK   {name}')
        except AssertionError as e:
            print(f'FAIL {name:<22} {e}')
            failures.append(name)
        except Exception as e:
            print(f'ERR  {name:<22} {type(e).__name__}: {e}')
            failures.append(name)
    if failures:
        print(f'\n{len(failures)} failure(s): {failures}')
        sys.exit(1)
    print('\nAll libsass compile checks passed.')
