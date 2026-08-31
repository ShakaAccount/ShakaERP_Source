# Shaka Liquid Glass — Onboarding Guide

The `shaka_ui_makeover` addon replaces every Odoo 19 surface with a
frosted-glass UI. This guide explains how the theme works, how to edit it,
and how to ship changes.

---

## 1. Architecture at a Glance

A pure presentation layer. No core addon in `odoo/addons/` is touched.
Three mechanisms, in order of specificity:

| Layer | File | What it does |
|---|---|---|
| 1. CSS variables | `static/src/scss/design_tokens.scss` | Defines `--lg-*` (colors, gradients, shadows, blurs). Override at runtime via DevTools. |
| 2. Component SCSS | `backend.scss`, `chrome.scss`, `views.scss`, `settings.scss`, `login.scss`, `pos.scss` | Uses the variables to restyle every Odoo surface. |
| 3. QWeb inheritance | `views/layout_inject.xml` | Injects a `<script>` (sets `data-theme='glass'`) and a `<style>` block (Company color CSS vars) into `web.layout` `<head>`. |

Every SCSS rule is gated on `html[data-theme='glass']`, which guarantees
higher specificity than the stock `.o_*` selectors regardless of asset
bundle ordering.

```
┌──────────────────────────────────────────────────────────┐
│  Browser renders the page                                │
│  └─ QWeb layout_inject fires before <body> parses       │
│     └─ <script> sets data-theme="glass"                  │
│     └─ <style> writes --lg-btn-primary / --lg-btn-text  │
│                from res.company.shaka_*_color            │
│  └─ web.assets_backend (or assets_frontend for login)    │
│     └─ design_tokens.scss  → --lg-* on :root            │
│     └─ mixins.scss         → @mixin lg-glass-panel etc.  │
│     └─ themed files        → every surface is glass     │
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
│   └── res_config_settings.py      # Settings fields + apply action
├── views/
│   ├── layout_inject.xml           # web.layout <head> injection
│   └── company_settings_views.xml  # Shaka UI settings block
├── static/src/scss/
│   ├── design_tokens.scss          # variables, gradients, shadows
│   ├── mixins.scss                 # @mixin lg-glass-panel, etc.
│   ├── backend.scss                # global: navbar, modals, tables
│   ├── chrome.scss                 # statusbar, searchview, pager
│   ├── views.scss                  # kanban, list, form, chatter
│   ├── settings.scss               # Settings + module install
│   ├── login.scss                  # login, signup, DB list
│   └── pos.scss                    # POS panes, products, receipt
└── tests/
    └── scss_compile_check.py       # libsass compile + bundle subtests
```

---

## 3. How Theming Works (No Core Edits)

All overrides flow through three channels:

1. **CSS variables** on `:root` — change `$lg-accent` in `design_tokens.scss`
   and every glass surface updates. Dark mode is automatic via
   `prefers-color-scheme: dark`.
2. **Theme-attribute gating** — every rule is wrapped in
   `html[data-theme='glass']`, so the SCSS always wins against stock
   `.o_*` selectors at the same level.
3. **Per-Company colors** — `res.company.shaka_primary_color` and
   `res.company.shaka_button_text_color` are rendered into a `<style>`
   block at page-load time, so the first paint already shows the
   configured color. The "Reload to apply" button triggers a
   real `ir.actions.client` reload.

---

## 4. Editing the Design Tokens

Open `addons/shaka_ui_makeover/static/src/scss/design_tokens.scss`.

### Common edits

| Goal | Variable |
|---|---|
| Change the brand blue | `$lg-accent`, `$lg-accent-strong` |
| Change the dark-glass tints | `$lg-glass-dark-1/2/3` |
| Change blur intensity | `$lg-blur-sm/md/lg` |
| Change corner radius | `$lg-r-sm/md/lg/pill` |
| Change world backdrop blobs | `$lg-bg-blob-a/b/c` |

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

Dark mode is implemented via `@media (prefers-color-scheme: dark)`
inside the `html[data-theme='glass']` gate in `design_tokens.scss`.
The dark override re-binds the same `--lg-*` variables to dark
equivalents and adjusts the world backdrop blobs to deeper blues
and purples.

To tune dark mode:

1. Open `design_tokens.scss` → search for
   `@media (prefers-color-scheme: dark)`.
2. Adjust the variable overrides inside the `html[data-theme='glass']`
   block.
3. Verify that any new component you add has acceptable contrast in
   both modes.

**Contrast rule of thumb:** body text on dark surfaces must hit 4.5:1
minimum. Use a contrast checker before shipping.

---

## 11. Per-Company Brand Colors

Two optional Company fields control the primary button color and the
button text color:

- `res.company.shaka_primary_color` (e.g. `#4E8DFF`)
- `res.company.shaka_button_text_color` (e.g. `#FFFFFF`)

Edit them in **Settings > General Settings > Shaka ERP > UI Theme**.
After saving, click **Reload to apply** (or just navigate to another
page) — the colors are re-rendered into the `<style>` block in
`web.layout` `<head>` on every page load.

The fields are optional. If left blank, the theme uses the design
token defaults (`$lg-accent-strong` and `#FFFFFF`).

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

- Use **standard CSS** (no hand-rolled vendor prefixes; the theme
  provides `-webkit-` fallbacks for `backdrop-filter`).
- Test in **both** light and dark modes.

---

## 14. Performance Notes

- **No raster textures** in the bundle. All surfaces are pure CSS
  (gradients + `backdrop-filter`). The cost is GPU compositing,
  not network requests.
- **No external fonts.** The CSS uses a system stack
  (`"Shaka Persian", "Inter", -apple-system, ...`) so there's no
  font-load delay.
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
| Change a gradient | `static/src/scss/design_tokens.scss` |
| Change a blur intensity | `static/src/scss/design_tokens.scss` |
| Tweak the navbar | `static/src/scss/backend.scss` |
| Tweak the control panel | `static/src/scss/backend.scss` |
| Tweak kanban cards | `static/src/scss/views.scss` |
| Tweak chatter | `static/src/scss/views.scss` |
| Tweak the form statusbar | `static/src/scss/chrome.scss` |
| Tweak the search bar | `static/src/scss/chrome.scss` |
| Tweak settings layout | `static/src/scss/settings.scss` |
| Tweak login | `static/src/scss/login.scss` |
| Tweak POS | `static/src/scss/pos.scss` |
| Add a Company color | `models/res_config_settings.py` |
| Inject a script/style in head | `views/layout_inject.xml` |
| Add a Settings field | `views/company_settings_views.xml` |
