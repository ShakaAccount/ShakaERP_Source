# Task 9: Form view → `surfaces/60_form.scss` + retune `navigation.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Sheet:** a surface card on the grouped background, via `--formView-sheet-padding-x|y`, `-border-width` and `-border-radius` (each with `-md` variants) and `$o-form-view-sheet-max-width`. Title (`.oe_title`) at 24px semibold.
- **Stat buttons** (`.o-form-buttonbox .oe_stat_button`, `--o-stat-text-color`, `--o-stat-button-color`, `--button-box-*`) become compact tiles.
- **Groups:** secondary-color labels, 13px medium. `.o_horizontal_separator` becomes a small section header. Fields use Task 4.
- **Notebook:** the MASTER segmented control. **Keep the `data-name` / `a[name]` hooks.**
- **Statusbar stepper:** new tokens (`--o-statusbar-*` on `.o_statusbar_status`); markup unchanged.
- Check the Budget Plan form, with its own step rail, next to a stock form.
