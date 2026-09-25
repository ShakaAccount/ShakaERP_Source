# Task 13: Login and brand → `scss/login.scss` in `web.assets_frontend`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- The main gold brand moment. A graphite/black wallpaper with a subtle gold glow, the same in both schemes. A centered material card, the SHAKA logo sized in CSS (drop `my_debrand`'s inline 200px), capsule fields, the primary button, visible passkey/2FA, and the database-selector link.
- **Gotchas:**
  - The frontend has its own Bootstrap overrides, so style `.oe_login_form .btn-primary` here.
  - The card's `bg-white` is `var(--background-color) !important`, so override `--background-color`.
  - The body carries `o_home_menu_background`.
- **Delete `addons/my_debrand/static/src/scss/login.scss`.** Mine the deprecated `shaka_ui_makeover/.../login.scss` for DOM gotchas (the white `.card-body`, autofill, RTL, passkey), not for its look. Manifest edit → restart.
