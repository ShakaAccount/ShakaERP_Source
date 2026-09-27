# Design System Master File — Shaka ERP

> When building a specific screen, first check `design-system/shaka-erp/pages/<screen>.md`.
> If it exists, its rules override this file. Otherwise follow this file.
>
> Implemented by the `shaka_theme` addon (`addons/shaka_theme`). The SCSS variables in
> `static/src/scss/primary_variables*.scss` are the code-side copy of this file — change both together.

**Generated:** 2026-09-26 for the Apple-refined redesign (`redesign/PLAN.md`, Task 2). Raw input: ui-ux-pro-max
`--design-system` ("enterprise ERP finance BI apple macOS system settings", variance 3 / motion 4 / density 7) plus
its ux/color/typography lookups, apple-design §1/4/7/12/14/15, and the impeccable direction round. The four pinned
decisions (Apple-refined, system blue, system font, macOS-compact) overrode the generator wherever they disagreed:
its Lexend/Source Sans, navy primary and `back.out` stagger were dropped. It confirmed the 4.5:1 floor, bulk-select
action bars and "no overshoot on data UI".

**Tools** (`design-system/shaka-erp/tools/`):

- `contrast.py` measures every colour pair below and exits 1 on a miss.
- `springs.py` generates the motion tokens.

Change a value → rerun → paste the new table.

---

## Style

**Apple-refined: the Inspector Workbench.** A macOS pro-app workbench (Finder, Xcode, Keynote):

- a *navigator* on the leading side (search panel, settings app list, Discuss sidebar);
- the record or list as the *canvas*;
- history and properties in a trailing *inspector* (the chatter).

Surfaces are opaque and grouped: gray grouped background, white panes, hairline separators. **Translucent material
exists only on floating layers**: menus, popovers, dialogs, the command palette, the sticky list header. Hierarchy
comes from weight, size and leading; blue marks what is interactive or selected; SHAKA gold appears only in brand
moments (logo, login, app switcher, favourites).

**Selection has two states, as in macOS.** A selected row, list item or tab is **action-filled with white text**
while its pane has focus (`:focus-within`), and **gray-filled (`--shaka-fill`) with label text** when it doesn't.
Lists, source lists, dropdown highlights, the command palette and the settings app list all follow this rule.

## Colour

Colours reach Odoo through its SCSS variables, so dark mode is Odoo Enterprise's dark mode (avatar menu → Dark
Mode). Addon SCSS uses only the `--shaka-*` custom properties and never raw hex or dark-mode selectors. **Existing
token names keep their meaning and get new values; the tokens marked *new* are added in Task 3.**

| Role | Light | Dark | CSS variable |
|------|-------|------|--------------|
| Action fill (primary buttons, selected rows, checks, toggles); same in both schemes | `#0071E3` | `#0071E3` | `--shaka-primary` |
| Link / tinted text / focus ring | `#0066CC` | `#2997FF` | `--shaka-link` *(new)* |
| Grouped background (app, behind panes) | `#F5F5F7` | `#1C1C1E` | `--shaka-bg` |
| Surface (sheet, list, card, pane) | `#FFFFFF` | `#2C2C2E` | `--shaka-surface` |
| Fill (hover, unfocused selection, quiet controls); translucent | `rgba(118,118,128,.12)` | `rgba(118,118,128,.24)` | `--shaka-fill` *(new)* |
| Muted surface (the fill, solid, for Sass and consumers) | `#EFEFF0` | `#3E3E42` | `--shaka-muted-bg` |
| Label | `#1D1D1F` | `#F5F5F7` | `--shaka-text` |
| Secondary label | `#6A6A6F` | `#AEAEB2` | `--shaka-muted` |
| Separator (hairline, decorative) | `#D2D2D7` | `#38383A` | `--shaka-border`, `--shaka-separator` *(new)* |
| Success (text) / badge tint | `#1F7F37` / 8% | `#30D158` / 12% | `--shaka-success` *(new)* |
| Warning (text) / badge tint | `#C93400` / 8% | `#FF9F0A` / 12% | `--shaka-warning` *(new)* |
| Danger (text) / badge tint | `#D70015` / 8% | `#FF7B73` / 12% | `--shaka-danger` *(new)* |
| Danger fill (destructive buttons); same in both schemes | `#D70015` | `#D70015` | — (`$o-btns-bs-override`) |
| Info | = link | = link | — (`$o-info`) |
| Gold, decoration only (logo, wallpaper glow, hairlines) | `#B5925F` | `#B5925F` | `--shaka-gold` *(new)* |
| Gold for icons that must reach 3:1 (favourite star) | `#8A6A3B` | `#C9A774` | `--shaka-accent`, `$o-main-favorite-color` |

Adjusted from the Task 2 starting point, by measurement:

- Secondary label `#6E6E73` → `#6A6A6F` and `#98989D` → `#AEAEB2`, so muted text holds 4.5:1 on a hovered or
  filled row too.
- Success `#248A3D` → `#1F7F37`: it was 4.0:1 on the grouped background.
- Dark danger `#FF6961` → `#FF7B73`, for 4.5:1 on its own badge tint. Dark status colours are too light to carry
  white text, so destructive buttons use the danger fill in both schemes, just as primary buttons use the action
  fill.
- The focus ring is the link blue: `#0071E3` fell to 2.9:1 on the dark surface.

**Measured contrast** (WCAG 2.x, `contrast.py`). Translucent colours are composited over what they sit on. Floors:
text 4.5, ui (icons, focus) 3.0, deco none.

| Pair | Kind | Light | Dark |
|---|---|---|---|
| label on bg | text | 15.46 | 15.63 |
| label on surface | text | 16.83 | 12.80 |
| label on fill@surface | text | 14.59 | 9.81 |
| secondary on bg | text | 4.94 | 7.69 |
| secondary on surface | text | 5.38 | 6.30 |
| secondary on fill@surface | text | 4.66 | 4.83 |
| link on bg | text | 5.11 | 5.64 |
| link on surface | text | 5.57 | 4.62 |
| on-action on action | text | 4.70 | 4.70 |
| focus on bg | ui | 5.11 | 5.64 |
| focus on surface | ui | 5.57 | 4.62 |
| success on surface | text | 5.06 | 6.89 |
| warning on surface | text | 5.28 | 6.78 |
| danger on surface | text | 5.38 | 5.53 |
| success on bg | text | 4.65 | 8.42 |
| warning on bg | text | 4.85 | 8.28 |
| danger on bg | text | 4.94 | 6.75 |
| success on success-tint@surface | text | 4.55 | 5.51 |
| warning on warning-tint@surface | text | 4.68 | 5.41 |
| danger on danger-tint@surface | text | 4.66 | 4.56 |
| on-action on danger-fill | text | 5.38 | 5.38 |
| gold-deep on surface | ui | 4.99 | 6.15 |
| gold-deep on bg | ui | 4.59 | 7.51 |
| gold on surface | deco | 2.90 | 4.81 |
| gold on #000000 | deco | 7.24 | 7.24 |
| label on thin@bg | text | 16.27 | 13.94 |
| secondary on thin@bg | text | 5.20 | 6.87 |
| label on regular@action | text | 14.27 | 9.89 |
| secondary on regular@action | text | 4.56 | 4.87 |
| label on thick@action | text | 15.51 | 11.27 |
| secondary on thick@action | text | 4.96 | 5.55 |
| separator on surface | deco | 1.51 | 1.19 |

The material rows measure each material over the worst thing that realistically scrolls under it: the page for
the thin header, a solid action-blue control for menus and dialogs. Blur only pulls contrast toward the mean, so
these numbers are floors. Plain gold on white is 2.9:1, which is why it stays decorative. Separators are
decorative by design; a boundary that carries meaning (an input's edge, a focused field) uses the focus colour or
secondary label instead.

## Typography

- **Latin:** the OS system font: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica
  Neue", Arial, sans-serif` plus the emoji fonts. That is SF Pro on macOS and Segoe UI on the Windows desktops most
  users have.
- **Persian:** Vazirmatn, self-hosted. It is listed first but limited to Arabic-script glyphs by `unicode-range`, so
  Latin falls through to the system font and mixed-script cells render each script in its own face.
- **Scale.** px sizes; `rem` in code via `o-to-rem`. Persian leading is +2px at 12–14px, because Arabic script needs
  taller lines.

  | Step | Size / leading | Weight | Use |
  |------|----------------|--------|-----|
  | Caption | 12 / 16 | 400; 500 in badges | badges, counts, timestamps, help text |
  | Footnote | 13 / 18 | 500 | field labels, list headers, section headers, secondary rows |
  | Body | 14 / 20 | 400; 500 on buttons | cells, inputs, menus, chatter body |
  | Headline | 17 / 22 | 600 | dialog titles, group titles, settings section titles |
  | Title 2 | 20 / 25 | 600 | breadcrumb current title, app name |
  | Title 1 | 24 / 30 | 600; 700 for key figures | form record title (`.oe_title`), dashboard figures |

- Hierarchy comes from weight, size and leading as a set (apple-design §15); emphasis comes from weight. **No
  `letter-spacing` on UI text:** the system font carries its own tracking, and tracking breaks Arabic-script
  joining. This overrides apple-design's size-specific tracking and vibrancy tracking bump.
- **Numbers:** `font-variant-numeric: tabular-nums` in lists, pivots, monetary and float fields.
- **Monospace:** Odoo default.

## Spacing and layout (density 7/10)

- A 4pt grid: 4 / 8 / 12 / 16 / 20 / 24 / 32 px. 8px is the standard gap and 16px separates sections. Nothing above
  32px inside a view.
- **Heights:** list rows 32px (`--shaka-row-h`, *new*); controls (inputs, buttons, segmented) 28px, small 24px;
  navbar and control panel rows 44px; dropdown items 28px with a 5px inset menu padding.
- **Panes:** navigator (search panel, settings list) 240px; inspector (chatter) as Odoo sizes it at ≥1440, stacked
  under the sheet below that. The form sheet keeps Odoo's max width.

## Shape and elevation

- **Radii:**

  | Token | Radius | Use |
  |-------|--------|-----|
  | `--shaka-radius-sm` *(new)* | 4px | checkboxes, small chips |
  | `--shaka-radius` | 6px | controls: buttons, inputs, segmented, menu items |
  | `--shaka-radius-card` | 10px | cards, sheets, menus, popovers, kanban cards (was 8px) |
  | `--shaka-radius-lg` *(new)* | 10px | alias of the card radius, for Bootstrap `-lg` |
  | `--shaka-radius-xl` *(new)* | 14px | dialogs, notifications, command palette |
  | `--shaka-radius-pill` *(new)* | 999px | capsules: badges, tags, search field, tab bar |

  Under `@supports (corner-shape: squircle)`, cards, dialogs and app icons also get `corner-shape: squircle` with
  the radius ×1.5, so the visible curve matches the round corner it replaces. Verify that factor in Task 3; the
  round radius stays the fallback.
- **Shadows (depth):** three, never mixed. Dark versions deepen the shadow and add a 0.5px light inner hairline,
  because a shadow alone disappears on dark.

  | Token | Light | Dark | Use |
  |-------|-------|------|-----|
  | `--shaka-shadow-card` | `0 0 0 .5px rgba(0,0,0,.05), 0 1px 2px rgba(0,0,0,.06)` | `0 0 0 .5px rgba(255,255,255,.06), 0 1px 2px rgba(0,0,0,.4)` | sheets, kanban cards, tab pill |
  | `--shaka-shadow-pop` | `0 0 0 .5px rgba(0,0,0,.08), 0 8px 24px rgba(0,0,0,.12)` | `0 0 0 .5px rgba(255,255,255,.1), 0 8px 24px rgba(0,0,0,.5)` | menus, popovers, tooltips, drag ghost |
  | `--shaka-shadow-dialog` *(new)* | `0 0 0 .5px rgba(0,0,0,.08), 0 24px 64px rgba(0,0,0,.2)` | `0 0 0 .5px rgba(255,255,255,.1), 0 24px 64px rgba(0,0,0,.6)` | dialogs, command palette, notifications |

- **Materials:** floating layers only, always through the `shaka-material($level)` mixin. Bigger surfaces read
  thicker (apple-design §12).

  | Level | Light | Dark | Blur | Use |
  |-------|-------|------|------|-----|
  | thin | `rgba(255,255,255,.6)` | `rgba(44,44,46,.6)` | 20px, saturate 180% | sticky list header |
  | regular | `rgba(255,255,255,.88)` | `rgba(44,44,46,.72)` | 30px, saturate 180% | menus, popovers, tooltips, autocomplete |
  | thick | `rgba(255,255,255,.94)` | `rgba(44,44,46,.85)` | 40px, saturate 180% | dialogs, command palette, notifications |

  The mixin also carries the fallbacks, and every one of them gives a solid surface with no blur:
  `prefers-reduced-transparency: reduce`, `@supports not (backdrop-filter: …)`, and `prefers-contrast: more`
  (which also adds a label-colour hairline). Never stack one material on another. **Scroll edge instead of a
  divider:** a sticky header gets a short fade mask where content meets it, only while content is scrolled beneath.
- The modal backdrop is a dim (`rgba(0,0,0,.2)` light, `.45` dark) with no blur: dim to focus (§12).

## Motion (4/10)

- **Springs, not curves** (apple-design §4). Every enter uses one critically damped spring (damping 1.0, no
  overshoot anywhere), as a CSS `linear()` easing generated by `tools/springs.py`. A critically damped spring has
  the same normalised shape at any response, so there is one easing and one duration per response. The duration is
  the settle time (within 0.2% of the target).

  | Token | Damping | Response | Duration | Use |
  |---|---|---|---|---|
  | `--shaka-spring-press` | 1.0 | 0.15s | 203ms | press feedback, toggles, checks |
  | `--shaka-spring-snappy` | 1.0 | 0.25s | 337ms | menus, popovers, tooltips, autocomplete |
  | `--shaka-spring` | 1.0 | 0.35s | 472ms | dialogs, tabs pill, accordion, palette |
  | `--shaka-spring-gentle` | 1.0 | 0.5s | 673ms | large surfaces: card resize, sheet height |

  ```css
  --shaka-spring: linear(0, 0.068, 0.209, 0.363, 0.506, 0.626, 0.722, 0.796, 0.852, 0.894, 0.925, 0.947, 0.962, 0.974, 0.982, 0.987, 0.991, 0.994, 0.996, 0.997, 1);
  --shaka-spring-press-dur: 203ms;
  --shaka-spring-snappy-dur: 337ms;
  --shaka-spring-dur: 472ms;
  --shaka-spring-gentle-dur: 673ms;
  --shaka-ease-exit: cubic-bezier(0.4, 0, 1, 1);
  ```

  `linear()` needs Chrome 113, Firefox 112 or Safari 17.2. Declare `cubic-bezier(0.22, 1, 0.36, 1)` first as the
  fallback. Task 3's compile check proves libsass passes `linear()` through untouched.
- **Exits accelerate** on `--shaka-ease-exit`, at about 65% of the enter's visible time: 150ms for menus and
  tooltips, 200ms for dialogs.
- **Existing token names stay** (other addons and the theme's JS read them). Their values (Task 14):

  | Token | New value |
  |-------|-----------|
  | `--morph-ease`, `--morph-close-ease` | `var(--shaka-spring)`: the overshoot curve is removed |
  | `--morph-open-dur`, `--morph-fade-dur` | `var(--shaka-spring-snappy-dur)` |
  | `--morph-close-dur` | 150ms |
  | `--morph-scale` / `--morph-blur` / `--morph-slide` | .96 / 6px / 8px (the clip carries the growth) |
  | `--morph-exit-ease` | `var(--shaka-ease-exit)` |
  | `--morph-r-closed` / `--morph-r-open` | `var(--shaka-radius)` / `var(--shaka-radius-card)` |
  | `--modal-ease` | `var(--shaka-spring)` |
  | `--modal-open-dur` | `var(--shaka-spring-dur)` |
  | `--modal-close-dur` | 200ms |
  | `--modal-exit-ease` | exit ease |
  | `--modal-scale`, new `--modal-blur` | .96, 6px |
  | `--tt-in-dur` / `--tt-in-ease` | snappy spring |
  | `--tt-out-dur` / `--tt-out-ease` | 150ms, exit ease |
  | `--tt-scale`, new `--tt-blur` | .96, 6px |
  | `--tabs-ease` | `var(--shaka-spring)` |
  | `--tabs-dur` | `var(--shaka-spring-dur)` |
  | `--acc-ease` | `var(--shaka-spring)` |
  | `--acc-expand` / `--acc-chevron` | 472ms / 337ms |
  | `--acc-collapse` | 250ms. **All `--acc-*` durations stay literal ms**: three addons parse `--acc-collapse` in JS |
  | `--acc-exit-ease` | exit ease |
  | `--toggle-ease` / `--toggle-dur` | spring / press duration (the snippet's overshoot is gone) |
  | `--check-ease`, `--check-ease-*` | `var(--shaka-spring)` (the success check's bob overshot) |
  | `--resize-dur` / `--resize-ease` | 673ms, **literal ms** (`dialog_card_resize.js` parses it) / spring |

- **Press feedback** (§1): `:active { transform: scale(var(--shaka-press-scale)) }` (.97) on buttons, kanban cards,
  app icons and the login button, over `--shaka-spring-press`. It fires on pointer-down and is the same everywhere.
- **Menus grow from their trigger** (§7): `transform-origin` and the `morph.js` clip-path start at the toggler, and
  the exit returns along the same path. Dialogs scale from .96 at the centre, because they have no trigger in view.
- **Materials materialize** (§12): opacity, scale from .96 and blur 6px → 0 together, never a bare fade. Menus
  (the content inside the growing clip), tooltips and dialogs. The resting value is `filter: none`, never
  `blur(0)`: any filter traps fixed descendants, and a filter or `will-change` on `.modal-dialog` makes it a
  backdrop root, which flattens the card's material.
- Only transform, opacity, filter (blur) and clip-path animate. Height is the one exception: `.t-resize` card
  resize and the `grid-template-rows` accordion.
- **Every animation is interruptible.** Toggling mid-motion continues from the value on screen. State changes use
  CSS transitions with `@starting-style` for enter. Exit ghosts hand over their current values (`morph.js`). The
  dialog resize retargets (`dialog_card_resize.js`). Delayed unmounts cancel on reopen. Only one-shot feedback
  (success check, error shake, loading orbit) uses keyframes.
- **Reduced motion** (§14): `prefers-reduced-motion: reduce` replaces every slide, scale and spring with a 150ms
  opacity cross-fade and keeps colour changes. `backend.scss` cuts every transition to .01ms except the floating
  layers (`.t-morph` and its content, `.t-tt`, `.t-modal`, `.t-modal-backdrop`, `.t-acc-panel-inner`, the loading
  pill), whose own files swap their motion for the cross-fade; exit ghosts still play so the close fades too. **Reduced transparency** makes materials solid. **More contrast**
  gives solid surfaces and defined borders.
- The transitions.dev snippets stay, one file each in `transitions/`, each with its own tokens and guard: dropdown
  morph, modal, tooltip, checkbox check, toggle, success check, error shake, tabs sliding, accordion, card resize,
  loading indicator. No overshoot is left in any of them; the error shake is the one keyframe that swings past
  zero, by design.
- No scroll-reveal, stagger or GSAP: that is marketing-page motion, not ERP motion.

## Components

One spec per surface task. The task file owns the hooks; this is the look.

- **Controls (Task 4, `10_controls`):**
  - **Buttons:** the primary is an action fill with white text, 28px tall and 6px radius. The secondary is a macOS
    push button: surface fill, separator hairline and the card shadow; in dark it gets a raised `#3A3A3C` fill.
    Destructive uses the danger fill. `.btn-link` and icon buttons use a link-tinted glyph with a `--shaka-fill`
    hover.
  - **Inputs:** quiet at rest (hairline bottom border on a surface, as Odoo lays them out), macOS field on hover and
    focus: `--shaka-fill` ground, then a 3px link-blue focus ring at 50% alpha outside a 1px link border.
  - **Checkbox, radio and toggle:** action fill.
  - **Badges and tags:** 12px/500 capsules on an 8% (dark 12%) tint of their status, and the text carries the
    meaning.
- **Overlays (Task 5, `20_overlays`):**
  - **Menus and popovers:** the regular material, 10px radius, 5px inset, 28px items with a 6px radius. The
    highlight follows the selection rule (action fill with white text). Hairline separators.
  - **Tooltips:** the regular material, 12px text.
  - **Dialogs:** the thick material, 14px radius, dialog shadow and dim backdrop. No header divider, a 17px/600
    title, and the footer's primary action at the end.
  - **Notifications:** the thick material card, 14px radius.
  - **Command palette (Spotlight):** a thick-material panel 640px wide, a 44px capsule field with 17px text, 32px
    result rows, and the selected row action-filled.
  - **Below 768px:** dropdowns render as a bottom sheet with a 14px top radius.
- **App shell (Task 6, `30_shell`):**
  - **Navbar:** a macOS unified toolbar, 44px, surface-coloured with a bottom hairline and no blur (nothing scrolls
    under it). The app name is 17px/600. Section buttons are 28px capsules with a `--shaka-fill` hover and action
    text when active. The systray is monochrome secondary label; the avatar is round.
  - **App switcher (gold brand moment):** a Launchpad grid of squircle icons with the card shadow and a press scale
    on a graphite wallpaper (`#1C1C1E` → `#000`) with a faint gold radial glow. Captions are white 13px/500. The
    navbar is transparent over it.
- **Control panel (Task 7, `40_control_panel`):**
  - **Layout:** one 44px toolbar row. Breadcrumb parents are secondary-label links separated by `›`; the current
    title is 20px/600.
  - **Search:** a Spotlight capsule on `--shaka-fill` with a leading magnifier. Facets are tinted capsules
    (link-blue at 12%, link text).
  - **View switcher:** a segmented control (fill track, surface pill with the card shadow).
  - **Pager:** compact; "New" is primary.
  - **Search panel:** the navigator, a source list with 28px rows, 13px/600 secondary-label section headers, and
    selection by the rule.
- **List (Task 8, `50_list`):** the canvas.
  - **Header:** sticky, thin material with a scroll-edge fade, 13px/500 secondary label. No vertical rules.
  - **Rows:** 32px with hairline separators (no zebra) and a `--shaka-fill` hover.
  - **Selection** follows the rule; the record checkbox selection (`.o_data_row_selected`) is a 12% action tint,
    because several rows may be selected at once.
  - **Group rows:** 13px/600 section headers with a chevron that rotates on `--shaka-spring-snappy`.
  - **Editing row:** a 1px link-blue outline.
  - **Footer:** tabular numbers, end-aligned.
  - **Empty state:** a glyph, a 17px title and one line of help.
- **Form (Task 9, `60_form`):** sheet as canvas, chatter as inspector.
  - **Sheet:** a surface card (10px radius, card shadow) on the grouped background. The title is 24px/600.
  - **Stat buttons:** compact 44px tiles on `--shaka-fill`, value 17px/600 over a 12px label.
  - **Groups:** 13px/500 secondary labels; `.o_horizontal_separator` is a 13px/600 section header.
  - **Notebook:** the segmented control (fill track, 3px padding, surface pill with the card shadow; a lifted fill in
    dark).
  - **Statusbar stepper:** it keeps its markup. Passed stages are action-filled dots with a check, the current
    stage an action ring with its number, upcoming stages fill dots. Connectors: action solid after passed stages,
    separator dashed otherwise.
- **Mail (Task 10, `65_mail`):**
  - **Chatter:** the inspector, a calm thread on the grouped background. Authors 14px/600, times 12px secondary,
    hairlines between messages. The composer is a capsule field on `--shaka-fill`. Notes get a faint warning tint.
  - **Discuss:** a Messages-like layout with the navigator sidebar and the selection rule.
  - **Systray popovers:** the regular material.
- **Kanban and secondary views (Task 11, `70_kanban` / `80_views`):**
  - **Kanban:** cards at 10px radius with a hairline and the card shadow. Hover changes only the shadow; press is
    `scale(.99)`; the drag ghost lifts (`scale(1.02)`, pop shadow). Column titles are 14px/600 with a count capsule.
    Progress bars use the status colours.
  - **Calendar:** today is an action-filled circle.
  - **Pivot and graph:** same header treatment as the list.
- **Settings (Task 12, `90_settings`):** macOS System Settings. The navigator is the app list with squircle icons,
  and the selected app follows the rule. The pane shows grouped inset sections (10px radius) with 13px/600 headers
  above, hairline rows and 32px minimum rows. Search is a Spotlight capsule.
- **Login (Task 13, `login.scss`, gold brand moment):** the app switcher's graphite wallpaper with the gold glow, the
  same in both schemes. A 360px thick-material card on the dark material. The logo is sized in CSS. Capsule fields,
  the primary button, and visible passkey/2FA and database links.
- **Focus (all):** `outline: 2px solid var(--shaka-link); outline-offset: 2px` on `:focus-visible`, never removed.

## Module icons

One recipe for every `static/description/icon.svg` (reference: `addons/category/static/description/icon.svg`):

- Glyph from [Lucide](https://lucide.dev) (ISC licence), pasted as-is: 24px grid, white stroke, width `1.6`.
- 256×256 tile, `rx="48"`, 2-stop diagonal gradient Tailwind `-700` → `-400` of one hue, drop shadow in the `-900`.
- One hue per module family; set `'icon': '/<module>/static/description/icon.svg'` in the manifest
  (Odoo never auto-discovers SVG icons) and `-u` the module to refresh it.

## RTL

Use logical properties only (`margin-inline-*`, `padding-inline-*`, `inset-inline-*`,
`text-align: start|end`). RTL is `body.o_rtl` plus rtlcss; `:lang()` never matches in the backend. An RTL-specific
override block is a smell. The navigator and inspector swap sides with the direction automatically.

## Anti-patterns

- ❌ `!important` or `html[data-theme=…]` selector gates to win specificity. Change the variable instead.
- ❌ Dark-mode selectors in addon SCSS. Use `var(--shaka-*)`, or `@if $o-webclient-color-scheme == dark` inside the
  theme.
- ❌ Emoji as icons. Use Odoo's icon font / SVG.
- ❌ Glass on anything that doesn't float. Material only on menus, popovers, tooltips, dialogs, notifications, the
  command palette and the sticky list header, only through `shaka-material()`, and never stacked.
- ❌ Overshoot or bounce on any UI motion; lift-on-hover; ornamental gradients (the gold wallpaper glow is the one
  brand exception).
- ❌ Gold as a text colour or on interactive controls. Blue owns interaction.
- ❌ `letter-spacing` on UI text.
- ❌ Colour as the only carrier of meaning (status badges also carry text).

## Pre-Delivery Checklist

- [ ] Text contrast ≥4.5:1 and icons/focus ≥3:1 in light **and** dark (`tools/contrast.py` passes for any new pair)
- [ ] Focus ring visible on every control (Tab through a form)
- [ ] `prefers-reduced-motion`, `prefers-reduced-transparency` and `prefers-contrast: more` respected
- [ ] Correct in fa_IR (RTL) and en_US
- [ ] No horizontal page scroll at 1440 / 1024 / 768
- [ ] No emoji icons; icon-only buttons have `title`/`aria-label`
- [ ] Material only on floating layers; no overshoot in any easing
