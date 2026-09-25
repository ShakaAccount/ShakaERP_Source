# Task 5: Overlays and the command palette → `surfaces/20_overlays.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Dropdowns and menus:** `shaka-material(regular)`, 10px radius, 5px inset. The highlight is an accent fill with white text on `.dropdown-item.focus` / `:hover`, as a **selector**, because `$dropdown-link-hover-bg` is reused elsewhere. Hairline separators.
- **Popovers, autocomplete and tooltips** (`.o_popover`, `.o-tooltip` → `--tooltip-*`) use the same material. Check that the `morph.js` clip-path still matches the new radius.
- **Dialogs:** 14px radius, header without a divider, 17px semibold title, primary action at the end. `modal.css` / `modal.js` keep working.
- **Notifications** (`--Notification__background-color`): material card, 14px radius.
- **BottomSheet:** how dropdowns render below 768px.
- **Command palette** (`.o_command_palette`, Ctrl+K; typing on the home menu opens it): **Spotlight**. Material panel, capsule field, accent-filled selected row.
