#!/usr/bin/env python3
import sys
import libsass

# Test design_tokens.scss compilation
scss = open('/home/russellzparadox/work/ShakaERP_Source/addons/shaka_ui_makeover/static/src/scss/design_tokens.scss').read()
try:
    css = libsass.compile(string=scss)
    print('design_tokens.scss: OK - compiled successfully')
except Exception as e:
    print('design_tokens.scss: ERROR', e)
    sys.exit(1)

# Test all SCSS files concatenated in manifest order (backend)
scss_files = [
    'design_tokens.scss',
    'mixins.scss',
    'backend.scss',
    'chrome.scss',
    'views.scss',
    'settings.scss',
    'login.scss',
]
full_scss = ''
for f in scss_files:
    content = open(f'/home/russellzparadox/work/ShakaERP_Source/addons/shaka_ui_makeover/static/src/scss/{f}').read()
    full_scss += content + '\n'

try:
    css = libsass.compile(string=full_scss)
    print('Full backend bundle: OK - compiled successfully')
except Exception as e:
    print('Full backend bundle: ERROR', e)
    sys.exit(1)

# Test POS bundle
pos_files = [
    'design_tokens.scss',
    'mixins.scss',
    'pos.scss',
]
pos_scss = ''
for f in pos_files:
    content = open(f'/home/russellzparadox/work/ShakaERP_Source/addons/shaka_ui_makeover/static/src/scss/{f}').read()
    pos_scss += content + '\n'

try:
    css = libsass.compile(string=pos_scss)
    print('POS bundle: OK - compiled successfully')
except Exception as e:
    print('POS bundle: ERROR', e)
    sys.exit(1)

# Test frontend bundle (login only)
frontend_files = [
    'design_tokens.scss',
    'mixins.scss',
    'login.scss',
]
frontend_scss = ''
for f in frontend_files:
    content = open(f'/home/russellzparadox/work/ShakaERP_Source/addons/shaka_ui_makeover/static/src/scss/{f}').read()
    frontend_scss += content + '\n'

try:
    css = libsass.compile(string=frontend_scss)
    print('Frontend bundle: OK - compiled successfully')
except Exception as e:
    print('Frontend bundle: ERROR', e)
    sys.exit(1)

print('\nAll bundles compiled successfully!')