# Design System Master File — Shaka ERP

> When building a specific screen, first check `design-system/shaka-erp/pages/<screen>.md`.
> If it exists, its rules override this file. Otherwise follow this file.
>
> Implemented by the `shaka_theme` addon (`addons/shaka_theme`). The SCSS variables in
> `static/src/scss/primary_variables*.scss` are the code-side copy of this file — change both together.

**Generated:** 2026-09-23 with ui-ux-pro-max `--design-system` ("enterprise ERP data dashboard business",
variance 3 / motion 3 / density 8), then adjusted for an Odoo 19 Enterprise backend used in Persian (RTL) and English.

---

## Style

**Minimalism & Swiss.** Flat, grid-based, high contrast. No glass, no blur, no ambient animation,
no decorative gradients. Hierarchy comes from type weight, spacing and one accent colour.

## Colour

Colours are applied through Odoo's own SCSS variables, so dark mode is Odoo Enterprise's dark
mode (User preferences → Dark). Addon SCSS uses only the `--shaka-*` CSS variables below and never
raw hex values or dark-mode selectors.

| Role | Light | Dark | CSS variable |
|------|-------|------|--------------|
| Primary / action | `#1E40AF` | `#60A5FA` | `--shaka-primary` |
| Secondary | `#3B82F6` | `#93C5FD` | — (`$o-info`) |
| Accent (highlights, favourites only; never a button fill) | `#D97706` | `#F59E0B` | `--shaka-accent` |
| App background | `#F8FAFC` | `#0B1220` | `--shaka-bg` |
| Surface (card, sheet, table) | `#FFFFFF` | `#111827` | `--shaka-surface` |
| Muted surface | `#E9EEF6` | `#1F2937` | `--shaka-muted-bg` |
| Text | `#0F172A` | `#E2E8F0` | `--shaka-text` |
| Muted text | `#475569` | `#94A3B8` | `--shaka-muted` |
| Border | `#E2E8F0` | `#1F2937` | `--shaka-border` |
| Success | `#15803D` | `#4ADE80` | — (`$o-success`) |
| Warning | `#B45309` | `#FBBF24` | — (`$o-warning`) |
| Danger | `#DC2626` | `#F87171` | — (`$o-danger`) |
| Focus ring | primary | primary | — |

Adjusted from the generator: its navy text (`#1E3A8A`) and blue border (`#DBEAFE`) tinted every
row of a dense table blue, so both are slate here. The dark column was not generated. It was picked for ≥4.5:1 text contrast.

## Typography

- **Family:** Vazirmatn (variable, wght 100–900, Arabic and Latin subsets), self-hosted. The generator's
  Fira Sans / Fira Code has no Persian glyphs, so it can't be used.
- **Base size:** 14px, Odoo's own default for data views. Dense ERP screens are desktop-first. The
  16px rule applies to mobile body text.
- **Weights:** 400 body, 500 labels and buttons, 600 headings, 700 only for key figures.
- **Numbers:** `font-variant-numeric: tabular-nums` in lists, pivots, monetary and float fields.
- **Monospace:** Odoo default.

## Spacing (density 8/10)

2 / 4 / 8 / 12 / 16 / 24 / 32 px. Standard padding is 8px, and 16px separates sections. Don't use
spacing above 32px inside a view.

## Shape and elevation

- Radius: 6px for controls, 8px for cards, sheets and dialogs. Pills (`999px`) are for badges, the loading indicator and the tab bar only.
- Shadows: `0 1px 2px rgb(15 23 42 / .06)` on cards, `0 8px 24px rgb(15 23 42 / .12)` on
  dropdowns and dialogs. There is nothing in between.
- The modal backdrop is a plain dim, with no blur.

## Motion (3/10)

- Colour, background and opacity transitions of 150–200ms, `ease-out`.
- Never animate width, height or layout, and nothing moves on hover.
  - **Exception: Card resize** (transitions.dev): dialogs tween their height when the content
    changes size. It uses 300ms and `cubic-bezier(0.22, 1, 0.36, 1)`, exposed as `--resize-dur` and `--resize-ease`
    in `shaka_theme/static/src/transitions/card_resize.css`. Use `.t-resize` for this and nothing else.
  - **Exception: Accordion** (transitions.dev): accordion panels tween `grid-template-rows` 0fr ↔ 1fr, with the content
    fading in from a 2px blur, over 250ms. The tokens are `--acc-*` in `transitions/accordion.scss`. It drives Odoo's
    search-menu accordions and the `shaka_ui_kit` tree. The tree's JS close delay reads `--acc-collapse`.
- Other transitions.dev snippets live in `shaka_theme/static/src/transitions/`, one file per transition. Each file keeps
  the site's tokens and its own reduced-motion guard. None of them animates layout, and their durations are longer than
  the 150–200ms default on purpose:
  - **Dropdown menu morph**: Odoo dropdown menus grow out of their toggler. A `clip-path` grows from a box the size of
    the toggler to the full menu over 350ms with an overshoot, and shrinks back over 250ms. The content fades and slides in.
    It also applies to AutoComplete menus (many2one and other search-as-you-type fields), which grow out of their input.
    The tokens are `--morph-*` in `dropdown_menu_morph.css`. The mechanics are in `morph.js`, driven by `popover.js` and
    `autocomplete.js`.
  - **Modal open/close**: every dialog's card scales up from 0.96 and fades in over 250ms, and its dim layer fades with
    it. On close it scales back down over 150ms, accelerating out; this plays on an inert clone because Odoo removes
    dialogs at once. Closing mid-open starts from the scale on screen (`--modal-*`, `modal.css/.js`).
  - **Tooltip open/close**: Odoo tooltips scale up from 0.98 and fade in over 150ms, after an 80ms delay, and fade out
    over 50ms (`--tt-*`, `tooltip.css`).
  - **Checkbox check**: the check draws in over 350ms and retracts over 150ms, and the box colour fades over 150ms
    (`--check-box/draw/uncheck`, `checkbox_check.scss`).
  - **Toggle**: the switch thumb travels over 350ms with an overshoot built into the easing, as a transition
    (`--toggle-*`, `toggle.css`).
  - **Success check**: success notifications show a check that fades, rotates, bobs and draws in over 500ms
    (`--check-*`, `success_check.css`).
  - **Error state shake**: invalid fields and the login error shake over 280ms (`--shake-*`, `error_shake.css`).
  - **Tabs sliding**: the active-tab pill slides and resizes to the clicked tab over 250ms on
    `cubic-bezier(0.22, 1, 0.36, 1)`, and snaps without animation on first paint and on resize (`--tabs-*`,
    `tabs_sliding.css/.js/.xml`).
  - **Loading indicator**: Odoo's bottom-corner "Loading" box becomes a pill centred under the navbar with a TwinOrbit
    spinner (two dots orbiting a centre dot, 1s loop, `--t-orbit-dur`). It still appears after Odoo's 250ms delay and fades
    and slides in over 200ms (`loading_indicator.xml` / `.scss`).
  - The small blur some of these use lasts only for the motion itself. It is not the decorative blur banned below.
- **Every animation is interruptible.** Toggling a component mid-motion continues from the value on screen; it never
  jumps to an end state and restarts. State changes use CSS transitions, with `@starting-style` for enter, instead of
  keyframes. Dropdown, autocomplete, tooltip and dialog exits hand their current values between the live menu and its exit
  ghost (`morph.js`). The dialog resize is a Web Animations tween that retargets when the content changes mid-tween
  (`dialog_card_resize.js`). Delayed unmounts (accordion, tree) cancel their timer when reopened. Only one-shot feedback
  (success check, error shake, the loading orbit) uses keyframes.
- **Exits accelerate** (`cubic-bezier(0.4, 0, 1, 1)`, about 65% of the enter duration): menus, tooltips and accordions
  close on `--morph-exit-ease`, `--tt-out-ease` and `--acc-exit-ease`. A decelerating curve on an exit does almost all
  of its motion in the first frames, so the close reads as a snap.
- Everything is turned off under `prefers-reduced-motion: reduce`.
- No scroll-reveal or GSAP; they belong on marketing pages, not in an ERP.

## Components

- **Buttons:** primary is filled with the primary colour and white text; secondary has a border and a
  surface background. Height follows Odoo's `btn` sizes.
- **Lists:** compact rows with a 1px bottom border and a muted-surface hover. Headers are sticky, 500
  weight and muted text. Numbers are tabular and aligned to the end.
- **Forms:** the sheet is a surface with a border and card radius. Labels are 500 weight and muted.
  Errors appear next to the field (Odoo default).
- **Kanban:** each card is a surface with a border and the card shadow. On hover only the border
  colour changes; the card doesn't lift.
- **Tabs (notebook):** a segmented pill bar (reference `addons/shaka_theme/tab.png`). The bar is a muted surface with
  3px padding. Tabs are muted text, and the active one sits on a surface pill with the card shadow; in dark mode the pill
  is lifted toward the muted text colour so it reads above the bar. Vertical notebooks use the card radius instead of a
  pill (`shaka_theme/static/src/scss/navigation.scss`).
- **Stage bar (statusbar):** a numbered stepper in a surface card (reference `addons/shaka_theme/stepper.png`). Passed
  stages have a filled primary dot with a check, the current stage an outlined primary dot with its number, and
  upcoming stages a muted dot with their number. A solid primary connector follows a passed stage, a dashed border
  connector the others, and the connectors stretch to fill the row. Folded stages sit behind dashed `…` dots. Markup
  from `components/statusbar_stepper.xml`, styles in `navigation.scss`. Every item keeps one height: Odoo's folding
  logic compares the row height with the first item's.
- **Focus:** `outline: 2px solid var(--shaka-primary); outline-offset: 2px` on `:focus-visible`,
  never removed.

## Module icons

One recipe for every `static/description/icon.svg` (reference: `addons/category/static/description/icon.svg`):

- Glyph from [Lucide](https://lucide.dev) (ISC licence), pasted as-is: 24px grid, white stroke, width `1.6`.
- 256×256 tile, `rx="48"`, 2-stop diagonal gradient Tailwind `-700` → `-400` of one hue, drop shadow in the `-900`.
- One hue per module family; set `'icon': '/<module>/static/description/icon.svg'` in the manifest
  (Odoo never auto-discovers SVG icons) and `-u` the module to refresh it.

## RTL

Use logical properties only (`margin-inline-*`, `padding-inline-*`, `inset-inline-*`,
`text-align: start|end`). An RTL-specific override block is a smell.

## Anti-patterns

- ❌ `!important` or `html[data-theme=…]` selector gates to win specificity. Change the variable instead.
- ❌ Dark-mode selectors in addon SCSS. Use `var(--shaka-*)`.
- ❌ Emoji as icons. Use Odoo's icon font / SVG.
- ❌ Glass, blur, ornamental gradients, lift-on-hover.
- ❌ Colour as the only carrier of meaning (status badges also carry text).

## Pre-Delivery Checklist

- [ ] Text contrast ≥4.5:1 in light **and** dark
- [ ] Focus ring visible on every control (Tab through a form)
- [ ] `prefers-reduced-motion` respected
- [ ] Correct in fa_IR (RTL) and en_US
- [ ] No horizontal page scroll at 1440 / 1024 / 768
- [ ] No emoji icons; icon-only buttons have `title`/`aria-label`
