# Task 6: App shell → `surfaces/30_shell.scss` (+ `my_debrand` cleanup)

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Navbar:** a macOS unified toolbar. Surface-colored with a hairline, no blur because content doesn't scroll under it. Semibold app name, section buttons with a `--shaka-fill` hover, monochrome systray, round avatar.
  - Hooks: `$o-navbar-*` (`!default`) and the **custom properties** `--NavBar-entry-color(--hover|--active)`, `--NavBar-entry-backgroundColor(--hover|--focus|--active)`, `--NavBar-brand-color` and `--NavBar-menuToggle-color`. Enterprise sets the hover and active properties from `$o-gray-200`.
  - **Delete the `--NavBar-*` lines from `addons/my_debrand/static/src/scss/debrand.scss`.**
- **App switcher, a gold brand moment:** Launchpad-style grid. Icons get the squircle radius, a soft shadow and a press scale. The background is a quiet graphite-and-gold wallpaper from tokens behind a material layer.
  - Hooks: `--homeMenu-bg-color|bg-image` (move the rule out of `tokens.scss`), `--AppSwitcherIcon-background|inset-shadow` and `--homeMenuCaption-color`. The `$o-home-menu-*` sizes can't be set.
  - The navbar turns transparent while the home menu is open. The login page shares this wallpaper through `o_home_menu_background`; Task 13 decides whether they diverge.
- Check at 390 wide: the burger menu and the mobile app switcher.
