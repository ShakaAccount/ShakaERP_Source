# Task 10: Mail (chatter, Discuss, systray popovers) → `surfaces/65_mail.scss`

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **Chatter** (`.o-mail-Chatter`): a calm thread. Semibold author, muted time, hairlines, and a capsule composer via `--mail-Composer-bg`, `--mail-Composer-actionHoverColor` and `--o-message-bubble-bg|border-color`. The container uses `$o-webclient-background-color`.
- **Discuss app, chat windows, and the messaging/activity systray popovers:** Messages-like, with a material popover. mail's own `*.dark.scss` files use `!important`; check dark mode carefully.
