# Task 8: List view → `surfaces/50_list.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- Finder-style table. **The scroll container is `.o_list_renderer`, with a sticky `thead`.**
  - Header: `shaka-material(thin)` with a scroll-edge fade instead of a hard border; 12–13px medium, secondary label color. No vertical rules.
  - Rows: 32px, hairline or zebra per MASTER, `--shaka-fill` hover.
  - Selected rows (`.o_data_row_selected.table-info`) get an accent tint. Group rows (`tr.o_group_header`) are section headers with a rotating chevron. The editing row (`.o_selected_row`) has clear focus. The footer uses `$o-list-footer-*`, with tabular numbers aligned to the end.
- Hooks on `.o_list_renderer`: `--ListRenderer-thead-bg-color|thead-padding-y|table-padding-x|data-row-border-bottom-width` and `.o_list_table { --table-bg }`. The `tfoot-bg` and `thead-border-end` properties are dead.
- **Empty state (`.o_view_nocontent`):** a glyph, a title and one line of help.
- Profile a 1,000-row scroll; if the material header drops frames, make it solid.
