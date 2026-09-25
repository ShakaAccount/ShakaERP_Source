# Task 17: Finish, document, ship

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- Spawn **`impeccable-finish-reviewer`** fresh, with the request, the decisions, the direction contract, `.impeccable/review/final/*` and the baseline shots. Act on its disposition, with at most 2 fix rounds.
- Spawn **`impeccable-documenter`**, which writes `DESIGN.md` plus `.impeccable/design.json` from the built theme.
- Make DESIGN.md the single authority. Cut MASTER.md down to a pointer, and update `CLAUDE.md` (UI theme layer), the manifest description and the test docstring.
- Final matrix plus `-u shaka_theme` with a clean log. **Ask before pushing**, then open a PR from `feature/shaka-apple-redesign` to `dev`.
