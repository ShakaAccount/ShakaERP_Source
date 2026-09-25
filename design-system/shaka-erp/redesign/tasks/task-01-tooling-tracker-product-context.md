# Task 1: Tooling, tracker, product context

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- `ln -s ../../.agents/skills/apple-design ~/.claude/skills/apple-design`, the same way the other `~/.agents` skills are linked.
- `uipro init --ai claude --global`, then check that `~/.claude/skills/ui-ux-pro-max/scripts/search.py` exists.
- Tracker already exists at `design-system/shaka-erp/redesign/PLAN.md`; add a notes line for skipped modules.
- `.gitignore`: dotfiles are ignored by `.*`, so share only the durable impeccable files. Add `!/.impeccable/`, `/.impeccable/*`, `!/.impeccable/config.json`, `!/.impeccable/design.json` and `!/.impeccable/surfaces/`.
- `/impeccable init` writes `PRODUCT.md`:
  - **Users:** Shaka finance/BI/ops staff, Persian-first plus English, mostly Windows desktops.
  - **Product:** Odoo 19 Enterprise ERP plus the Shaka DW integrations.
  - **Brand commitments:** the gold-on-black SHAKA logo (`addons/my_debrand/static/img/SHAKA.png`), Vazirmatn for Persian.
  - **Platform:** `web`. **Accessibility:** AA in both schemes, RTL.
  - No image generation is available here, so the build is code-led.
- Done when both skills load in a fresh session and PRODUCT.md is committed.
