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
# Order MUST match web.assets_backend in __manifest__.py
ORDER = [
    'static/src/scss/design_tokens.scss',
    'static/src/scss/mixins.scss',
    'static/src/scss/backend.scss',
    'static/src/scss/chrome.scss',
    'static/src/scss/views.scss',
    'static/src/scss/settings.scss',
    'static/src/scss/login.scss',
    'static/src/scss/pos.scss',
]


def test_all_scss_compiles():
    parts = []
    for rel in ORDER:
        path = os.path.join(ADDON_ROOT, rel)
        assert os.path.exists(path), f"missing {rel}"
        parts.append(open(path).read())
    blob = '\n'.join(parts)
    css = sass.compile(string=blob)
    assert len(css) > 5000, f"compiled CSS suspiciously small: {len(css)} bytes"
    assert 'backdrop-filter' in css or '-webkit-backdrop-filter' in css
    assert '--lg-accent' in css


if __name__ == '__main__':
    try:
        test_all_scss_compiles()
        print("OK: libsass compiled all bundles cleanly")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
