# Jalali Date Support - Module Skeleton

## What's solid and ready to use

- **`jalali_utils.js`** - self-contained Gregorian <-> Jalali conversion
  (no external library needed). This math doesn't change between Odoo
  versions and can be trusted as-is.
- **`models/res_users.py`** - adds a `calendar_type` preference
  (Gregorian / Jalali) per user, exposes it via `ir.http.session_info()`
  so the JS client can read it as `session.calendar_type`, plus
  `jalali_date()` / `jalali_datetime()` helpers usable inside QWeb report
  templates: `<span t-esc="jalali_date(o.date_order)"/>`
  Requires `pip install jdatetime --break-system-packages` in the Odoo
  Python environment.
- **`views/res_users_views.xml`** - exposes the preference in the user's
  Preferences dialog.
- **`date_datetime_field_patch.js`** - CONFIRMED against a real Odoo
  19.0.20260607 install: there is no separate `DateField` class/module in
  v19. A single `DateTimeField` (in
  `addons/web/static/src/views/fields/datetime/datetime_field.js`)
  handles both date-only and date+time fields, branching on
  `this.field.type`. The display method is `getFormattedValue(valueIndex)`
  (a method, not a getter - v19 supports multi-value fields like date
  ranges via the `valueIndex` argument). This patch overrides that method
  directly.

## What needs verification against your v19 source before going live

- **The parse-on-input side** (converting what the user types/picks back
  to Gregorian before it's written to the record) is not yet implemented
  in this patch - only the display half. The confirmed method name for
  that hasn't been located yet. Open
  `addons/web/static/src/views/fields/datetime/datetime_field.js` and look
  for the method that receives the picker's raw output (search for where
  `getFormattedValue` is called from, or where `this.values` gets
  assigned) to find the right hook.
- **`search_panel_patch.js`** - groupby/filter labels (Year/Quarter/Month
  in the search panel). No functional code yet - a map of where to look.
- **`calendar_view_patch.js`** - Calendar view's date axis/header. Same
  situation - a map of where to look, not tested code.

## Lessons learned debugging this on a live v19 instance

- A third-party module (`persian_calendar_19` by Odoo Pishro) was tried
  alongside this and found to have multiple genuine bugs (broken asset
  paths in its manifest, a crash in its datetime picker, a crash in its
  kanban dashboard patch) - it's not a reliable reference implementation
  and was uninstalled.
- Odoo 19 merged `DateField` and `DateTimeField` into one class. If you
  see import errors referencing `@web/views/fields/date/date_field`
  anywhere (including in other third-party modules), that path does not
  exist in v19 - it needs to import from
  `@web/views/fields/datetime/datetime_field` instead.

## The calendar popup (`datetime_picker_patch.js`)

Confirmed against the real v19 source: `DateTimePicker`
(`addons/web/static/src/core/datetime/datetime_picker.js`) builds its
day/month/year grids from a private, non-exported `PRECISION_LEVELS` map.
The only usable extension point is the `activePrecisionLevel` getter -
`onWillRender()` calls `this.activePrecisionLevel` internally, so
overriding that getter to return a custom Jalali "days" precision object
(with its own `getTitle`/`getItems`) lets the rest of `onWillRender()`'s
logic run unchanged.

**What's covered:** the day-grid view - the one you actually click a
date in - now shows a real Jalali month (correct day count, correct
leap-year Esfand length, correct navigation by Jalali month via patched
`next()`/`previous()`). Each day cell still carries its real Gregorian
Luxon `DateTime` internally, so clicking a day writes a correct value
back with no separate "parse on save" step needed.

**What's not covered (known scope cut):** the "decades" (century) zoom
level still renders Gregorian - rarely used in practice. Same technique
would extend to it if needed.

**Also not covered:** manually typing a date as text into the field
input - typing is disabled (input is read-only) specifically because it
routes through a private Gregorian parser that can't be safely
intercepted (see below). All date entry goes through clicking in the
picker grid.

## The data-corruption bug and its fix (important - read this)

An earlier version of this patch wrote Jalali text directly into the
real `<input>`'s DOM value to keep it visually in sync while the picker
was open. This turned out to corrupt data: `datetimepicker_service.js`
unconditionally re-reads the input's value and Gregorian-parses it every
time the popover closes - even on a plain "click outside" with nothing
typed or selected. Since the box displayed Jalali text, every close
silently mis-parsed it as Gregorian and wrote a garbage value back.

**The fix (`datetime_field_template_patch.xml` + `jalali_date.css`):**
never touch the real input's value at all. It keeps holding whatever
Gregorian text core's own code puts there - core's internal
read-back/parse logic is therefore never fed anything unexpected. A
separate, purely decorative overlay `<span>` (with `pointer-events: none`
so clicks still reach the real input beneath it) shows the Jalali text
on top, driven by ordinary Owl template reactivity (`getFormattedValue`,
already patched) rather than manual DOM writes. There is no longer a
race to lose, because the real input's value is never wrong in the first
place.

If the overlay text looks slightly misaligned with where the real
input's padding/font would place it, adjust the `padding-left` value in
`jalali_date.css` - the current value is an approximation, not measured
against your actual theme's input styling.

## Design principles this module follows

1. **Storage stays Gregorian, always.** Only the display layer converts.
2. **Server-side domains/groupby stay Gregorian.** Only human-readable
   labels get converted, never the values sent back to `read_group` /
   `search`.
3. **Per-user opt-in** via `calendar_type`, not a global switch - matches
   how the existing community Jalali modules for older Odoo versions do it.

## Suggested next steps

1. Install `jdatetime` in your Odoo venv.
2. Install this module, set your user's Calendar Type to Jalali, confirm
   date fields on a simple form (e.g. a contact's birthday) display and
   round-trip correctly.
3. Tackle the calendar view and search groupby labels once the field-level
   piece is confirmed working - they're independent and can ship later.
