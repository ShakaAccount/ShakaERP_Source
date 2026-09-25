# Task 3: Foundations (the whole app re-skins through variables)

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **`primary_variables.scss` / `.dark.scss`** (literal values only):
  - The MASTER palette → the `$o-gray-*` ramp, `$o-enterprise-color` / `-action-color`, the status colors, `$o-theme-text-colors`, `$o-view-background-color`, and `$o-main-favorite-color` (gold).
  - The `$o-btns-bs-override` / `-outline-override` maps: all 9 states, both files, literal `#FFF` text in dark.
  - `$o-font-size-base*`, `$o-border-radius*` and `$o-input-padding-*`.
  - Fonts: `$o-system-fonts: ("Vazirmatn", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji")`, with `$o-font-family-sans-serif: o-add-unicode-support-font($o-system-fonts)` and headings equal to that. Setting `$o-system-fonts` is what gets the stack onto the login page.
  - Every color mirrored in the dark file.
- **New `scss/bootstrap_overridden.scss`** in `web._assets_backend_helpers`, `('before', 'web_enterprise/static/src/scss/bootstrap_overridden.scss', …)`:
  - Radii: `$btn-border-radius*`, `$dropdown-border-radius`, `$modal-content-border-radius`, `$popover-border-radius`, plus the ones enterprise zeroes (`$badge-`, `$card-`, `$toast-`, `$nav-pills-`, `$form-check-input-`, `$list-group-`, `$progress-`, `$accordion-border-radius`).
  - Paddings: `$dropdown-padding-*`, `$badge-padding-*`, `$input-btn-padding-*`, `$tooltip-*`.
  - These may reference `$o-*` values, so they need no dark copy.
- **`fonts.scss`:** add `unicode-range: U+0600-06FF, U+0750-077F, U+08A0-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200F` to all three Vazirmatn faces.
- **`tokens.scss`:**
  - **Keep every existing token**, and add `--shaka-link`, `--shaka-gold`, `--shaka-separator`, `--shaka-fill`, `--shaka-radius-sm|lg|xl|pill`, `--shaka-shadow-dialog`, `--shaka-spring`, `--shaka-ease-exit` and `--shaka-row-h`.
  - Add a `shaka-material($level)` mixin (thin, regular or thick background plus `backdrop-filter` and `-webkit-backdrop-filter`) with its fallbacks.
  - Leave the home-menu background rule in place; Task 6 replaces it. Note that it also paints the login background until Task 13.
- **`backend.scss`:** themed `::selection`, `caret-color`, thin scrollbars from tokens (Odoo has no global scrollbar style), and an Apple-style focus ring ≥3:1. Keep tabular nums and the reduced-motion block.
- **`__manifest__.py`:**
  - Version `19.0.2.0.0`.
  - Add `'shaka_theme/static/src/scss/surfaces/*.scss'` after `navigation.scss` in `web.assets_backend`.
  - Add `'web.assets_web_dark': [('remove', X), X]` for `navigation.scss` and the surfaces glob, so they load after Odoo's `*.dark.scss`.
  - Add the helpers entry above and update the summary.
  - The empty glob logs a harmless "did not resolve" warning until Task 4.
- **`tests/scss_compile_check.py`:**
  - Build the full chain (secondary variables, backend helpers including enterprise `.dark` files, Bootstrap `_variables` / `_variables-dark` / `_maps`) and compile **every** theme `.scss`, `surfaces/` included, light and dark.
  - Walk directories (today's `os.listdir` + `open` crashes on subfolders).
  - Mirror-check `rgba()` and map values, not just `#hex`.
  - New palette and font assertions.
- Restart, since the manifest changed. Done when the check passes and a list, form and kanban show the new palette, type and radii in the whole matrix. Also smoke-check one invoice PDF preview and the login page: the palette reaches both.
