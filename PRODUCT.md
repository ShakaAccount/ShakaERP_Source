# Shaka ERP: product context

## Product

Odoo 19 Enterprise ERP plus the Shaka DW integrations: a bridge into the Shaka SQL Server data warehouse (`raes_dw_connector`, `entity`), with category management, BI/Windows/SSAS access control (`win_access`), a Power BI portal, budget planning, payment requests and sales dashboards built on top. The web client lives at `/shaka`.

## Users

- Shaka finance, BI and operations staff: dense, repetitive data work (lists, forms, approvals, dashboards) for hours a day.
- Persian-first, with English. Persian data appears in English sessions too.
- Mostly Windows desktops, so Segoe UI is the Latin system font most people actually see.

## Brand commitments

- The gold-on-black SHAKA logo (`addons/my_debrand/static/img/SHAKA.png`, gold `#B5925F`). Gold is reserved for brand moments: logo, login, app switcher, favorites.
- Vazirmatn for Persian (Arabic-script glyphs only, via `unicode-range`); the OS system font for Latin.

## Platform

`web` (Odoo backend web client; frontend/login only for brand).

## Accessibility

- WCAG AA in both light and dark schemes: text ≥4.5:1, icons and focus ≥3:1, measured.
- Full RTL (`body.o_rtl` + rtlcss); logical properties only; no letter-spacing on UI text.
- Honors reduced motion, reduced transparency and `prefers-contrast: more`.

## Constraints

- No image generation is available, so the build is code-led: SCSS variables, tokens and CSS only.
- Design direction and house rules: `design-system/shaka-erp/redesign/PLAN.md` and `design-system/shaka-erp/MASTER.md`.
