/** @odoo-module **/

/*
 * The search view's date groupby options ("2026", "Q2 2026", "July 2026"
 * etc.) and the date filter menu are generated separately from the field
 * widgets patched above - they come from the search model / control panel,
 * not from DateField/DateTimeField. This is the part flagged as
 * incomplete even in past community attempts (see odoo/odoo#73599).
 *
 * There is no single stable file/hook name to point at across versions
 * here, so treat this file as a worked TODO rather than drop-in code:
 *
 * 1. Find where groupby date labels are built. In recent versions this
 *    lives in the search model, roughly:
 *        addons/web/static/src/search/search_model.js
 *    look for the function that turns a "date:month" groupby into a
 *    human label (something like `getGroupByDateLabel` or similar).
 *
 * 2. Patch that function so that when `user.settings.calendar_type ===
 *    "jalali"`, the label is built from `toJalali()` (see
 *    jalali_utils.js) instead of the Gregorian year/month/quarter.
 *
 * 3. Do NOT change the underlying domain/groupby value sent to the
 *    server - only the human-readable label. The server-side grouping
 *    must stay Gregorian, since ORM date functions, `read_group`, and
 *    every report relying on them assume Gregorian.
 *
 * This file intentionally has no functional patch yet - fill it in once
 * you've located the exact function in your v19 source tree.
 */
