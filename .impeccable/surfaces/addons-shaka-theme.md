---
version: 1
slug: "addons-shaka-theme"
primary_target: "addons/shaka_theme"
related_targets: []
---

# Surface brief: Shaka ERP backend theme (`addons/shaka_theme`)

**Scope:** the whole Odoo 19 backend web client at `/shaka`, plus login. Visitor mode: **Operate**.

**Audience and job:** Shaka finance, BI and operations staff on Windows desktops, in long sessions of dense data
work in Persian and English. They scan lists, edit records, approve workflow stages and manage DW access.

**Constraints:** four pinned decisions (Apple-refined world; system blue for interaction, SHAKA gold only for brand
moments; system font with Vazirmatn for Arabic script; macOS-compact density at 14px and 32px rows). Token and hook
names never change. Materials only on floating layers. Spec: `design-system/shaka-erp/MASTER.md`; plan:
`design-system/shaka-erp/redesign/PLAN.md`.

## Direction contract

THESIS: Every screen is a macOS pro-app workbench: navigator on the leading side, the record or list as the canvas,
history and properties in a trailing inspector. It refuses the category default of a stock Odoo layout recoloured
in corporate blue.

OWN-WORLD: grouped gray background `#F5F5F7`/`#1C1C1E` under white/`#2C2C2E` panes; hairline separators; blue
`#0071E3` for action and selection only; system-font type in weight steps 12/13/14/17/20/24. Glass only where
things float. Selection has two states: blue fill in the focused pane, gray fill elsewhere. Gold appears only on the
logo, login, app switcher and favourites.

STORY: The user always knows where they are (the navigator), what they are working on (the canvas) and what
happened to it (the inspector). Selection shows which pane has their attention. Nothing moves unless they moved it,
and then it settles without bounce.

FIRST VIEWPORT: 44px unified toolbar (app name 17/600, capsule sections). Below it, a 44px control-panel row:
breadcrumb 20/600 at the start, Spotlight capsule search in the middle, segmented view switcher at the end.
- List: 240px source-list search panel | canvas of 32px rows under a sticky thin-material header.
- Form: sheet card on the grouped ground | chatter inspector at ≥1440px. The primary action ("New"/"Save") is
  action-filled at the toolbar's start.

FORM: Inspector Workbench (Xcode/Keynote/Finder navigator-canvas-inspector), #4 on the ordered grounded list; seed
key f6570b8f (roll ran degraded, no challengers). Signature interaction: the two-state pane-focus selection. Motion
grammar: one critically damped spring (`--shaka-spring`); menus grow from their trigger; exits accelerate.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md,
and every shipping raster carrying its provenance

## Unresolved

- Where the inspector collapses between 1280 and 1440 (Task 9 decides from the matrix).
- The squircle ×1.5 radius factor (verify in Task 3).
