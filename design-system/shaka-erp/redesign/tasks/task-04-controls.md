# Task 4: Controls → `surfaces/10_controls.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Buttons.** Primary is filled with the accent. Secondary is a macOS push button: surface fill, hairline border, faint shadow; raised fill in dark. `.btn-link` and icon buttons use a tinted glyph with `--shaka-fill` on hover. Pressed: `scale(.97)` on `:active` (apple-design §1). Colors come from Task 3's maps; this file adds shape, press and focus.
- **Inputs:** quiet at rest, macOS field on hover and focus. Drive them through `--o-input-border-color`, which is state-driven (`web/static/src/views/fields/fields.scss:26-44`), plus `--o-input-background-color` and `--o-caret-color`. **Re-align the `jalali_date` overlay.**
- **Checkbox, radio and toggle** use the accent; keep `checkbox_check.scss` and `toggle.css`.
- **Badges and tags** (`.badge`, `.o_tag`, `.o_field_badge`, `.o_status`): capsule, 12–15% tint, and the text always carries the meaning.
