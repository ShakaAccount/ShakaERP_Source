# Task 7: Control panel, search and search panel → `surfaces/40_control_panel.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Breadcrumbs:** current title at 20px semibold; parents as muted links with `›`.
- **Search:** Spotlight capsule. `--SearchBar-background-color` is declared on `.o_searchview` itself, so set it there.
- **Facets** (`.o_searchview_facet.bg-200`, label `.btn-primary` / `.text-bg-action`) become tinted capsules: override `--background-color`, never `!important`.
- **View switcher** (`.o_cp_switch_buttons .o_switch_view`, a `.btn-secondary`): a macOS segmented control through scoped selectors. **Pager** is compact; "New" is primary.
- **Search panel** (`.o_search_panel`, the left filter column): sidebar list styling. Its width is hard-assigned, so no width variable.
- The row reads as one toolbar at 1440 and wraps cleanly at 768.
