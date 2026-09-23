# Shaka UI Makeover — Onboarding Guide

The `shaka_ui_makeover` addon replaces every Odoo 19 backend surface with a
bold, flat, elevated redesign — large-radius floating cards on a soft
light-green surface, not the frosted-glass/blur treatment the addon was
originally built around (blur tokens are now hard-locked to `0`; the
`glass-*` mixin/variable names are kept only for API compatibility with the
hundreds of existing call sites). This guide explains how the theme works,
how to edit it, and how to ship changes.

---

## 1. Architecture at a Glance

A pure presentation layer. No core addon in `odoo/addons/` is touched.
Four mechanisms, in order of specificity:

| Layer | File | What it does |
|---|---|---|
| 1. CSS variables | `static/src/scss/design_tokens.scss` | Defines `--lg-*` (colors, radius, shadows, type). Override at runtime via DevTools. |
| 2. Dark-mode class sync | `static/src/js/theme_mode.js` | Reads Odoo's own `color_scheme` cookie (and the OS preference as a fallback) and toggles a `.shaka-dark-mode` class on `<html>`. |
| 3. Component SCSS | `backend.scss`, `chrome.scss`, `views.scss`, `settings.scss`, `login.scss`, `pos.scss`, `global_forms.scss`, `global_theme_overrides.scss` | Uses the variables to restyle every Odoo surface. |
| 4. QWeb inheritance | `views/layout_inject.xml` | Injects a `<script>` (sets `data-theme='glass'`) and a server-rendered `<style>` block (the active Company's JSON palette, as CSS custom properties) into `web.layout` `<head>`. |

Every SCSS rule is gated on `html[data-theme='glass']`, which guarantees
higher specificity than the stock `.o_*` selectors regardless of asset
bundle ordering.

```
┌──────────────────────────────────────────────────────────┐
│  Browser renders the page                                │
│  └─ QWeb layout_inject fires before <body> parses         │
│     └─ <script> sets data-theme="glass"                   │
│     └─ <style> writes --lg-* from res.company             │
│                .shaka_theme_palette (JSON, light + dark)  │
│  └─ theme_mode.js toggles .shaka-dark-mode on <html>      │
│     based on the color_scheme cookie                      │
│  └─ web.assets_backend (or assets_frontend for login)     │
│     └─ design_tokens.scss  → --lg-* defaults on :root     │
│     └─ mixins.scss         → @mixin lg-glass-panel etc.   │
│     └─ themed files        → every surface restyled       │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Project Layout

```
addons/shaka_ui_makeover/
├── __init__.py                     # imports models
├── __manifest__.py                 # asset bundles (no local @import)
├── models/
│   ├── __init__.py
│   └── res_config_settings.py      # ResCompany.shaka_theme_palette (JSON) + Settings wizard
├── views/
│   ├── layout_inject.xml           # web.layout <head> injection
│   ├── company_settings_views.xml  # Shaka UI theme-palette settings block
│   └── login_templates.xml         # show-password icon markup swap
├── static/src/js/
│   └── theme_mode.js               # syncs the color_scheme cookie into .shaka-dark-mode
├── static/src/scss/
│   ├── design_tokens.scss          # variables: colors, radius, shadows, type
│   ├── mixins.scss                 # @mixin lg-glass-panel, lg-card-lift, lg-heading, etc.
│   ├── backend.scss                # global: navbar, modals, tables, cards
│   ├── chrome.scss                 # statusbar, searchview, pager, badges
│   ├── views.scss                  # kanban, list, form, chatter
│   ├── settings.scss               # Settings + module install
│   ├── login.scss                  # login, signup, DB list
│   ├── pos.scss                    # POS panes, products, receipt
│   ├── global_forms.scss           # generic form/list/kanban/notebook widget polish
│   └── global_theme_overrides.scss # catch-all: calendar, graph/pivot, mail/Discuss,
│                                    # Gantt, Map, notifications, popovers, search panel
└── tests/
    └── scss_compile_check.py       # libsass compile + bundle subtests
```

---

## 3. How Theming Works (No Core Edits)

All overrides flow through three channels:

1. **CSS variables** on `:root` — change `$lg-accent` in `design_tokens.scss`
   and every restyled surface updates. Dark mode is driven by the
   `.shaka-dark-mode` class that `theme_mode.js` toggles from Odoo's own
   `color_scheme` cookie (falling back to `prefers-color-scheme` only when
   the cookie hasn't been set yet) — it is not a pure CSS media query.
2. **Theme-attribute gating** — every rule is wrapped in
   `html[data-theme='glass']`, so the SCSS always wins against stock
   `.o_*` selectors at the same level.
3. **Per-Company palette** — `res.company.shaka_theme_palette` stores a JSON
   document (`{"light": {...}, "dark": {...}}`, see
   `models/res_config_settings.py:SHAKA_DEFAULT_PALETTE` for the full key
   list and shipped defaults) rendered into a `<style>` block at page-load
   time by `_shaka_runtime_css()`, so the first paint already shows the
   configured colors. The "Reload to apply" button triggers a real
   `ir.actions.client` reload.

---

## 4. Editing the Design Tokens

Open `addons/shaka_ui_makeover/static/src/scss/design_tokens.scss`.

### Common edits

| Goal | Variable |
|---|---|
| Change the brand green | `$lg-accent`, `$lg-accent-strong`, `$lg-accent-start/end` |
| Change card/panel elevation | `$lg-shadow-sm/md/lg/hover` |
| Change corner radius | `$lg-r-sm/md/lg/xl/pill` |
| Change heading boldness | `$lg-fw-heading`, `$lg-fw-heading-strong` |

`$lg-blur-*` and the `$lg-glass-dark-*`/`$lg-bg-blob-*` aliases still exist
for API compatibility with older call sites, but are locked to `0` /
transparent — this is a flat, non-blurred theme. Don't reintroduce blur
values there; add a new token instead if a future direction needs it.

All tokens have `!default` so user-side overrides still work. After
editing, refresh the page (Odoo recompiles SCSS per request in dev).

---

## 5. Editing a Component

Pick the right file:

| Surface | File |
|---|---|
| Navbar, modals, dropdowns, tables | `backend.scss` |
| Breadcrumbs, view switcher, command palette, statusbar | `chrome.scss` |
| Kanban, list, form, chatter, search panel | `views.scss` |
| Settings page + module install | `settings.scss` |
| Login / signup / DB list | `login.scss` |
| POS panes, products, receipt, ticket | `pos.scss` |
| Calendar, graph/pivot, Discuss, Gantt, Map, notifications, popovers | `global_theme_overrides.scss` (catch-all) |

Add a new rule wrapped in the theme gate:

```scss
html[data-theme='glass'] .o_my_thing {
  @include lg-glass-panel();
  border-radius: var(--lg-r-md);
  color: var(--lg-text);
}
```

Use the existing mixins (`lg-glass-panel`, `glass-elevated`,
`glass-control`, `glass-backdrop`) and the `--lg-*` variables — never
hardcode hex values.

---

## 6. Updating the Logo / Brand

The theme does **not** ship logos. The navbar uses the standard
`o_menu_brand` chip (see `backend.scss` `.o_menu_brand` rule). To add
a logo, drop the image into `addons/my_debrand/static/img/` (the
existing debrand addon) or your custom debrand module and edit
`addons/shaka_ui_makeover/static/src/scss/chrome.scss` `.o_menu_brand`
to apply a `background-image`.

---

## 7. Adding / Removing XML Template Inheritances

The addon currently inherits only one template:

- `web.layout` (via `views/layout_inject.xml`) — injects the theme
  attribute script and the Company color `<style>` block into `<head>`.

To add more inheritances, follow the **safe pattern**:

```xml
<template id="my_override" name="My Override" inherit_id="web.layout">
    <xpath expr="//head" position="inside">
        <link rel="stylesheet" href="/my_addon/static/src/css/extra.css"/>
    </xpath>
</template>
```

### Do **NOT** inherit these (they're OWL templates, not `ir.ui.view`):

- `web.webclient_brand`
- `web.kanban_view` / `web.list_view` / `web.form_view`
- `web.menu_sections`
- `web.dialog_layout`

If you need to restyle a backend widget, **do it via SCSS** (the
recommended pattern) rather than via template inheritance. Example:
to restyle kanban cards, add to `views.scss`:

```scss
html[data-theme='glass'] .o_kanban_view .o_kanban_record {
  /* your styles here */
}
```

---

## 8. Local Development Workflow

### Iterating on SCSS only (fast)

SCSS is compiled per-request in dev mode (`--dev=xml,assets`). Save
the `.scss` file, hard-reload the browser (`Ctrl+Shift+R`), and check
the browser console for SCSS compile errors.

### Iterating on XML templates (requires restart)

Template changes need a registry reload. The cleanest path:

```bash
cd /home/russellzparadox/work/ShakaERP_Source
./deploy_update.sh
```

Or surgically:

```bash
docker exec odoo_19_web ./odoo-bin -c /etc/odoo/odoo.conf \
    -d admin -u shaka_ui_makeover --stop-after-init
```

The flag `--stop-after-init` exits cleanly after the update, so the
running web service picks up the changes on its next request cycle.

### Iterating on Python (models)

Python also requires a `-u`:

```bash
docker exec odoo_19_web ./odoo-bin -c /etc/odoo/odoo.conf \
    -d admin -u shaka_ui_makeover --stop-after-init
```

---

## 9. Deploying Changes

The addon lives in `addons/shaka_ui_makeover/` inside the directory
that's bind-mounted into the web container. To deploy:

1. **Stage your changes** on the host:
   ```bash
   cd /home/russellzparadox/work/ShakaERP_Source
   git status
   git diff
   ```

2. **Commit** (the project is git-tracked; this is a fork, so commits
   stay local unless you push):
   ```bash
   git add addons/shaka_ui_makeover
   git commit -m "Shaka Liquid Glass: describe change"
   ```

3. **Trigger an Odoo update** for the addon:
   ```bash
   docker exec odoo_19_web ./odoo-bin -c /etc/odoo/odoo.conf \
       -d admin -u shaka_ui_makeover --stop-after-init
   ```

4. **No container rebuild needed** — the addon is read live from the
   host volume.

5. **No database migration** for SCSS or template-only changes.
   If you add Python models, run with `-u shaka_ui_makeover`.

---

## 10. Dark Mode

Dark mode is **class-driven**, not a pure CSS media query. `theme_mode.js`
reads Odoo's own `color_scheme` cookie (set by Odoo's own Dark/Light
selector) and toggles a `.shaka-dark-mode` class on `<html>`; if the cookie
hasn't been set yet it falls back to `prefers-color-scheme: dark` for the
first paint. Component rules key off
`html[data-theme='glass'].shaka-dark-mode` (see `global_theme_overrides.scss`
for the bulk of them). The Company's `shaka_theme_palette` JSON also carries
a `dark` key, rendered into the same class selector by `_shaka_runtime_css()`.

To tune dark mode:

1. Open `global_theme_overrides.scss` → search for
   `html[data-theme='glass'].shaka-dark-mode`.
2. Adjust the variable overrides inside that selector, or the `dark` half
   of `SHAKA_DEFAULT_PALETTE` in `models/res_config_settings.py` for the
   Company-configurable palette.
3. Verify that any new component you add has acceptable contrast in
   both modes.

**Contrast rule of thumb:** body text on dark surfaces must hit 4.5:1
minimum. Use a contrast checker before shipping.

---

## 11. Per-Company Brand Colors

`res.company.shaka_theme_palette` is a JSON text field holding a full
light + dark color document (keys: `bg`, `surface`, `elevated`, `border`,
`input`, `hover`, `text`, `muted`, `primary`, `primary_dark`, `on_primary`,
`link`, `pill_bg`, `pill_text`, `success`, `warning`, `danger` — see
`SHAKA_DEFAULT_PALETTE` in `models/res_config_settings.py` for the shipped
values). Any key left out, or the whole field left blank, falls back to the
shipped default for that key; an unrecognised key or invalid hex value is
rejected on save (`ResCompany._check_shaka_theme_palette`).

Edit it in **Settings > General Settings > Shaka ERP > UI Theme** as a JSON
textarea. After saving, click **Reload to apply** (or just navigate to
another page) — the palette is re-rendered into the `<style>` block in
`web.layout` `<head>` on every page load. **Reset to Shipped Defaults**
restores `SHAKA_DEFAULT_PALETTE` verbatim.

---

## 12. Accessibility Checklist

Before merging changes, run through this list:

- [ ] All interactive elements have a visible `:focus-visible` outline
      (the theme provides a 2 px `--lg-accent` ring).
- [ ] Body text contrast ≥ 4.5:1 in both light and dark modes.
- [ ] Decorative icons beside visible text are hidden from screen
      readers (`aria-hidden="true"`).
- [ ] Buttons have descriptive labels or `aria-label`.
- [ ] No layout shifts on hover/press (transforms use `translateY`
      only, not `width/height`).
- [ ] `@media (prefers-reduced-motion: reduce)` is honored
      (the addon disables animations and transitions under it).
- [ ] Form fields have associated `<label>` elements.
- [ ] Errors are announced to assistive tech (the `.alert` styles
      include `role="alert"`).

---

## 13. Troubleshooting

### My SCSS changes don't show up

1. Hard reload the browser (`Ctrl+Shift+R`).
2. Check the browser console for SCSS compile errors. The most
   common are:
   - `Undefined variable` → you referenced a SCSS variable that
     doesn't exist; check the import order (it must match
     `__manifest__.py`).
   - `expected selector` → check for missing `{` or `}`.
3. Clear the asset bundle cache:
   ```bash
   docker exec odoo_19_web ./odoo-bin -c /etc/odoo/odoo.conf \
       -d admin -u shaka_ui_makeover --stop-after-init
   ```

### The theme isn't being applied (looks like stock Odoo)

1. Open DevTools → Elements → check `<html>` for
   `data-theme="glass"`. If missing, the layout_inject.xml template
   didn't render.
2. Check `Settings > Technical > User Interface > Views` for
   `Shaka Liquid Glass Layout` — its `inherit_id` should be
   `web.layout`.
3. Re-install: `docker exec odoo_19_web ... -u shaka_ui_makeover`.

### "Forbidden local `@import`" error

The Odoo SCSS compiler bans `@import` of local files. Use
**manifest ordering** instead — the addon already lists all SCSS
files in the right concatenation order in `__manifest__.py`. To add
a new file, append it to the list in the right place.

### "Can't load unknown file type" error on install

Your `data` list in `__manifest__.py` contains a non-XML file (e.g.
a `.py`). Python loads via the `__init__.py` chain, **not** via
`data`. Remove the `.py` entry from `data`.

### Asset bundle 500 error

This is a SCSS compile failure. Look in the Odoo logs:

```bash
docker logs odoo_19_web --tail 100 | grep -iE "scss|sass|error|compile"
```

The error will point to a file and line number — fix the SCSS and
reload.

### Styles work in one browser but another

- Use **standard CSS**. The theme is flat (no `backdrop-filter`/blur in the
  current design) so there are no vendor-prefix concerns to worry about.
- Test in **both** light and dark modes.

---

## 14. Performance Notes

- **No raster textures** in the bundle. All surfaces are pure CSS
  (gradients + soft box-shadows). The cost is a handful of extra paint
  layers, not network requests.
- **One self-hosted font family.** `fonts.scss` ships the Vazirmatn
  (Persian) weights as `.woff2` under `static/src/fonts/` — no external
  font-host request, but do budget for the font-load delay on first paint.
- **No JS** in the addon at all. The theme attribute is set by a
  tiny inline `<script>` in `web.layout` `<head>`, and Company
  colors are server-rendered. No bundle to download, no patch
  overhead.
- **Cache-friendly.** The compiled CSS is content-hashed and
  served from `/web/assets/...`. Hard-reload once after a deploy,
  then the browser caches aggressively.
- **Reduced-motion friendly.** All animations and transforms are
  disabled under `prefers-reduced-motion: reduce`.

---

## Quick Reference: Most-Edited Files

| Goal | File to edit |
|---|---|
| Change a color | `static/src/scss/design_tokens.scss` |
| Change card/modal elevation | `static/src/scss/design_tokens.scss` |
| Change corner radius | `static/src/scss/design_tokens.scss` |
| Tweak the navbar | `static/src/scss/backend.scss` |
| Tweak the control panel | `static/src/scss/backend.scss` |
| Tweak kanban cards | `static/src/scss/views.scss` |
| Tweak chatter | `static/src/scss/views.scss` |
| Tweak the form statusbar | `static/src/scss/chrome.scss` |
| Tweak the search bar | `static/src/scss/chrome.scss` |
| Tweak settings layout | `static/src/scss/settings.scss` |
| Tweak login | `static/src/scss/login.scss` |
| Tweak POS | `static/src/scss/pos.scss` |
| Tweak Discuss, Gantt, Map, calendar, graph/pivot | `static/src/scss/global_theme_overrides.scss` |
| Add a Company palette key | `models/res_config_settings.py` (`SHAKA_DEFAULT_PALETTE`) |
| Inject a script/style in head | `views/layout_inject.xml` |
| Add a Settings field | `views/company_settings_views.xml` |
