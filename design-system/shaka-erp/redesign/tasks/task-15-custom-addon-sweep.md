# Task 15: Custom addon sweep (one commit per addon, each checked in the matrix)

> Before starting: read `../PLAN.md` (Context, How every task runs, House rules). When done: tick this task in `../PLAN.md`, then commit.

- **`daily_sales_performance`:** rename its `--shaka-*` redefinitions to `--sales-*` and map them to tokens. Drop the 72 raw hex values.
- **`sales_analysis`:** rename the leaking `$black` / `$green` / `$muted`… to `$sa-*`, and add dark support through tokens.
- **`budget_planning`:** remove the hex fallbacks; put the teal header and step rail on tokens.
- **`category`:** `#fff` → tokens; the hand-built modal (`category_manager.xml:447`) gets Task 5 dialog styling; `#FD3B3B` → danger.
- **`win_access`, `powerbi_portal` and the `shaka_ui_kit` tree:** the selected node gets a Finder-sidebar accent highlight.
- **`jalali_date.css`:** `padding-left` → `padding-inline-start`, matched to the new input padding.
