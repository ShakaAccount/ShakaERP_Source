# shaka_ui_makeover — DEPRECATED

Replaced by [`shaka_theme`](../shaka_theme). This addon is kept for reference only and is
marked `installable: False`.

**Why:** it themed Odoo from the outside: ~4.5k lines of SCSS gated on
`html[data-theme='glass']`, heavy `!important`, and a second dark-mode system
(`theme_mode.js` / `.shaka-dark-mode`) next to Odoo Enterprise's own. It also pulled in
`point_of_sale`. `shaka_theme` overrides Odoo's SCSS variables instead, and reuses
Enterprise dark mode. Design source of truth: `design-system/shaka-erp/MASTER.md`.

**Migrating a database that still has it installed** (order matters: its `web.layout`
inherit calls Python code that disappears once the module is no longer loadable):

1. Deploy the commit *before* this one, or temporarily set `installable: True` here.
2. Install `shaka_theme`, then upgrade `budget_planning` (it now depends on
   `shaka_theme` instead of this addon).
3. Uninstall `shaka_ui_makeover` (Apps → Uninstall).
4. Deploy with `installable: False`.

**Removal:** delete this directory once no database has it installed.
