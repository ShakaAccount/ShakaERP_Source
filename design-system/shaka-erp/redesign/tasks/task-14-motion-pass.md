# Task 14: Motion pass (apple-design + `/impeccable animate`) → `transitions/*`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Enters** use `--shaka-spring`, critically damped. **Remove every overshoot:** `detect` flags `dropdown_menu_morph.css:12`, `success_check.css:19` and `toggle.css:13`.
- **Exits** use `--shaka-ease-exit` at about 65% of the enter time.
- **Material surfaces materialize:** opacity, scale from .96, and blur from 6px to 0, together.
- **Press feedback** is the same across buttons, cards and app icons.
- **Keep all token names;** `--acc-*` stays in ms.
- **Verify:**
  - Interruptibility: rapid open and close of menus, dialogs and tree nodes.
  - Reduced motion (cross-fade) and reduced transparency (solid), via DevTools emulation.
- Update MASTER's motion section.
