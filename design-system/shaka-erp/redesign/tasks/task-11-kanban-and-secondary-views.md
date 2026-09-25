# Task 11: Kanban and secondary views → `surfaces/70_kanban.scss`, `surfaces/80_views.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Kanban:** cards at 10px radius, hairline plus card shadow. Hover changes only the border or shadow; pressed is `scale(.99)`; the drag ghost lifts (1.02 plus pop shadow). Column title plus count capsule, progress bars from status tokens.
  - Hooks: `--Kanban-*`, `--KanbanGroup-*`, `--KanbanRecord-*` and `$o-kanban-background`.
- **Calendar:** `--fc-*` and `--o-cw-*`; today is an accent circle through a selector. **Activity:** token pass.
- **Pivot and graph live in the lazy bundle** (`web.assets_backend_lazy` plus its dark twin). Add a `scss/lazy_views.scss` there in the manifest (restart). Pivot headers use `!important` grays, so check specificity.
- *Optional:* move the chart palette to Apple system colors with a small `patch()` in `static/src/components/`. The colors live in `web/static/src/core/colors/colors.js:7-90` and `graph_renderer.js:29-33`. Skip it if the default palette sits well.
