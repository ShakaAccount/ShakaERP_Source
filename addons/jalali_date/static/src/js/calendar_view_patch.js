/** @odoo-module **/

/*
 * The Calendar view renders its own date axis (day/week/month headers,
 * navigation title) independently of DateField/DateTimeField. In recent
 * Odoo versions this is an OWL component around FullCalendar, roughly:
 *     addons/web/static/src/views/calendar/calendar_renderer.js
 *     addons/web/static/src/views/calendar/calendar_model.js
 *
 * Two things need patching for full Jalali support:
 *   1. calendar_model.js - the range/date-navigation logic that computes
 *      "next month" / "next week" boundaries. Keep this Gregorian
 *      internally (it drives the actual `read_group`/`search_read` date
 *      domain sent to the server) - do not convert this part.
 *   2. calendar_renderer.js - the *displayed* header text/day labels.
 *      This is the safe place to swap in Jalali labels via toJalali()
 *      from jalali_utils.js, purely for what the user sees.
 *
 * Because FullCalendar's own internal locale/header formatting API has
 * changed across Odoo versions (and across FullCalendar major versions),
 * confirm the exact prop/option name used for header formatting in your
 * v19 checkout (search for "titleFormat" or "dayHeaderFormat" in
 * calendar_renderer.js) before wiring this up.
 *
 * This file intentionally has no functional patch yet - it's a map of
 * where to look, not a tested override.
 */
