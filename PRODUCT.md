# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Shaka finance, BI and operations staff. Persian-first, with English; Persian data appears in English sessions too. Mostly on Windows desktops, in long working sessions of dense, repetitive data work. No single job dominates; the mix is:

- finance: payment requests, budget planning, workflow-stage approvals;
- BI and access admin: DW categories, AD/SSAS/PBIRS access, the Power BI portal;
- sales and operations monitoring: daily sales performance, sales analysis, company dashboards.

## Product Purpose

Shaka ERP is Odoo 19 Enterprise plus the Shaka DW integrations. It runs the company's ERP workflows and gives staff governed access to the Shaka SQL Server data warehouse from the same place. The web client lives at `/shaka`.

## Positioning

ERP workflows, live warehouse data and BI access control in one app, instead of separate tools. The DW bridge (`raes_dw_connector`, `entity`) is what stock Odoo cannot offer; `category`, `win_access`, `powerbi_portal` and the dashboards are built on it.

## Operating Context

- Backend web client on Windows desktops (Segoe UI is the Latin system font most users see), light and dark schemes.
- RTL for Persian sessions (`body.o_rtl` + rtlcss). The backend `<html>` has no `lang`, so language can't be targeted by `:lang()`.
- Jalali dates (`jalali_date`) alongside Gregorian.

## Capabilities and Constraints

- The theme lives in `addons/shaka_theme` and works through Odoo's SCSS variables and exported `--shaka-*` tokens. Existing `--shaka-*`, `--acc-*` (ms) tokens and JS hook classes must never be renamed or removed; other addons consume them.
- Out of scope for design work, smoke-checked only: POS, PDF reports, portal/website, Studio, spreadsheet.
- No image generation is available, so the build is code-led.

## Brand Commitments

- The gold-on-black SHAKA logo: `addons/my_debrand/static/img/SHAKA.png`, gold `#B5925F`.
- Vazirmatn for Persian (Arabic-script glyphs).

## Evidence on Hand

- Logo: `addons/my_debrand/static/img/SHAKA.png`.
- Design source of truth: `design-system/shaka-erp/MASTER.md`; redesign plan: `design-system/shaka-erp/redesign/PLAN.md`.
- QA database `shaka_design` with demo data (see PLAN.md Task 0). No user research or metrics exist; don't invent them.

## Product Principles

1. Data first: dense, scannable, consistent screens for long working sessions beat expression.
2. Persian and English are equal citizens: every screen works in RTL and with mixed-script data.
3. One place: DW data and access sit inside normal ERP workflows, not bolted on beside them.
4. Don't break consumers: other addons build on the theme's tokens and hooks.

## Accessibility & Inclusion

- WCAG AA in both light and dark: text ≥4.5:1, icons and focus ≥3:1, measured.
- Full RTL; logical properties only; no letter-spacing on UI text (it breaks Arabic-script joining).
- Honors reduced motion, reduced transparency and `prefers-contrast: more`.
