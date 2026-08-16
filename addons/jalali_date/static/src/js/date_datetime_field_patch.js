/** @odoo-module **/

import { useEffect, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { localization } from "@web/core/l10n/localization";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";
import { formatJalaliDate, parseJalaliString } from "./jalali_utils";

/*
 * CONFIRMED against a real Odoo 19.0 install: there is no separate
 * DateField class/module in v19. DateTimeField (in
 * addons/web/static/src/views/fields/datetime/datetime_field.js) handles
 * both date-only and date+time fields, branching internally on
 * `this.field.type` ("date" vs "datetime"). This single patch covers
 * both cases - no separate date_field_patch.js needed.
 *
 * WHY setup() IS ALSO PATCHED (not just getFormattedValue):
 * getFormattedValue only feeds the read-only span/button. The editable
 * <input> element's text (addons/web/static/src/views/fields/datetime/
 * datetime_field.xml) has no `value` binding in the template at all - it's
 * written to imperatively by datetimepicker_service.js's updateInput(),
 * using the raw core formatDate/formatDateTime, every time the picker
 * opens/navigates. That service's formatting functions - AND the
 * matching parseDate/parseDateTime it uses when the popover closes - are
 * private module-level consts, not exported, so they can't be patched or
 * called directly from here.
 *
 * HOW MANUAL TYPING WORKS WITHOUT TOUCHING THAT PRIVATE CODE:
 * We never try to intercept or replace the private parser. Instead, right
 * before it gets a chance to run (on blur, Enter/Tab, or a click outside
 * that never blurs the input at all), our own handler fires first and
 * rewrites the box's raw text from Jalali into Gregorian text - formatted
 * using `localization.dateFormat`/`dateTimeFormat`, which is the exact
 * same *public* format string the private parser already expects, since
 * both it and the formatter are driven by that same locale config. By the
 * time the private code reads the input, it only ever sees valid
 * Gregorian text in its own expected format, so it parses correctly.
 * If what the user typed doesn't parse as a valid Jalali date, we revert
 * the box to the last known-good value instead of letting bad text reach
 * the private parser - so a bad edit is discarded, never silently
 * corrupted.
 *
 * ORDERING GUARANTEE THIS RELIES ON:
 * - blur/keydown listeners bound directly on the input (via the Owl
 *   template) run in target phase, before any listener on an ancestor
 *   (like a document-level "click outside" handler) can run - and before
 *   any same-target listener the picker service registers later (it only
 *   attaches its own listeners once the popover opens, after ours is
 *   already registered at component mount).
 * - for the "click outside without ever blurring the input" case, we
 *   register our own capture-phase `pointerdown` listener on `document`
 *   at mount time. Capture-phase listeners on an ancestor always run to
 *   completion before ANY bubble-phase listener anywhere in the tree, so
 *   this fires before the service's own (bubble-phase) close handling.
 * This is a best-effort race against private, unexported internals - it
 * has no dependency on their timing being source-stable, only on how the
 * DOM's capture/bubble/target phases are ordered, which is spec-guaranteed.
 * Still, treat this as needing real-world testing: if you ever see a
 * corrupted value again, it means some interaction path skips both of
 * our interception points - tell me exactly how you triggered it (typed
 * text + how you left the field) so we can add a matching hook.
 */

patch(DateTimeField.prototype, {
    get isJalaliActive() {
        return session.calendar_type === "jalali";
    },

    setup() {
        super.setup();

        // Tracks, per input (0 = start, 1 = end), whether the user is
        // currently typing raw Jalali text into the real input (mask off,
        // overlay hidden) vs. the normal masked/overlay display.
        this.jalaliEditing = useState({ 0: false, 1: false });
        // Tracks whether the user actually typed anything during the
        // current focus session (set on real 'input' events only, never
        // by our own programmatic writes to el.value). Used by
        // commitJalaliText to skip the Jalali round-trip entirely when
        // nothing was edited - see the comment there for why that matters.
        this.jalaliDirty = useState({ 0: false, 1: false });
        // The box's exact original text, captured the instant before we
        // overwrite it with Jalali text on focus. This lets us restore
        // it byte-for-byte on an untouched focus/blur, with zero
        // dependency on reconstructing a matching format ourselves.
        this.jalaliOriginalText = { 0: null, 1: null };

        // Pre-bound per-index handlers, referenced from the template as
        // bare identifiers (t-on-focus="onJalaliFocusStart", etc). This
        // is deliberate: Owl's t-on here does NOT support call-expression
        // syntax like "onJalaliFocus(0)" the way plain JS would suggest -
        // it evaluates that immediately at render time instead of
        // deferring it to the real event, so it crashes before you ever
        // click anything. Wrapping in an inline arrow in the template
        // ("() => onJalaliFocus(0)") defers it correctly, but Owl's
        // compiler extracts the referenced method into a bare variable
        // and calls it unbound, losing `this`. Bare identifiers pointing
        // at these arrow-function instance properties avoid both
        // problems: Owl treats a bare identifier as a normal deferred
        // handler (matching how the pre-existing "onInput" binding
        // already works), and each arrow function's `this` is fixed
        // lexically at the point it's created here, immune to whatever
        // calling convention Owl uses internally.
        this.onJalaliFocusStart = () => this.onJalaliFocus(0);
        this.onJalaliFocusEnd = () => this.onJalaliFocus(1);
        this.onJalaliBlurStart = () => this.onJalaliBlur(0);
        this.onJalaliBlurEnd = () => this.onJalaliBlur(1);
        this.onJalaliKeydownStart = (ev) => this.onJalaliKeydown(0, ev);
        this.onJalaliKeydownEnd = (ev) => this.onJalaliKeydown(1, ev);
        this.onJalaliInputStart = (ev) => {
            this.onInput(ev);
            this.jalaliDirty[0] = true;
        };
        this.onJalaliInputEnd = (ev) => {
            this.onInput(ev);
            this.jalaliDirty[1] = true;
        };

        useEffect(() => {
            if (!this.isJalaliActive) {
                return;
            }
            // Typing is allowed now - we no longer force readOnly. Data
            // integrity is protected by commitJalaliText() below instead.
            for (const ref of [this.startDate, this.endDate]) {
                if (ref.el) ref.el.readOnly = false;
            }
        });

        useEffect(() => {
            if (!this.isJalaliActive) {
                return;
            }
            // Backstop for "click outside" closes that never fire a blur
            // on the input at all (e.g. clicking a non-focusable part of
            // the calendar chrome, or clicking fully outside the picker).
            const onDocPointerDown = (ev) => {
                for (const [idx, ref] of [[0, this.startDate], [1, this.endDate]]) {
                    if (this.jalaliEditing[idx] && ref.el && !ref.el.contains(ev.target)) {
                        this.commitJalaliText(idx);
                    }
                }
            };
            document.addEventListener("pointerdown", onDocPointerDown, true);
            return () => document.removeEventListener("pointerdown", onDocPointerDown, true);
        });
    },

    getFormattedValue(valueIndex) {
        if (session.calendar_type !== "jalali") {
            return super.getFormattedValue(valueIndex);
        }
        const value = this.values[valueIndex];
        if (!value) return "";
        const withTime = this.field.type !== "date";
        return formatJalaliDate(value, { withTime });
    },

    isJalaliEditingRaw(valueIndex) {
        return this.isJalaliActive && this.jalaliEditing[valueIndex];
    },

    /** Focus handler for both the start and end inputs (valueIndex 0/1). */
    onJalaliFocus(valueIndex) {
        // Preserve the original behaviour (telling the picker which input
        // is active) regardless of Jalali mode.
        this.picker.activeInput = valueIndex === 0 ? this.startDateField : this.endDateField;
        // Deliberately does NOT touch el.value here. A raw edit session
        // (capturing original text, swapping to editable Jalali) only
        // starts on the first real keystroke - see onJalaliKeydown /
        // beginJalaliEdit. This means a plain "click in, click out" with
        // no typing at all never writes to the real input, exactly like
        // the original read-only design - nothing to revert, because
        // nothing was ever changed.
    },

    onJalaliBlur(valueIndex) {
        if (!this.isJalaliActive || !this.jalaliEditing[valueIndex]) {
            return;
        }
        this.commitJalaliText(valueIndex);
    },

    onJalaliKeydown(valueIndex, ev) {
        if (!this.isJalaliActive) {
            return;
        }
        if (!this.jalaliEditing[valueIndex]) {
            // Only a real character/edit key should start an edit
            // session - ignore Tab, Shift, arrow keys, etc. so merely
            // tabbing through or navigating past the field never touches
            // its value.
            const isCharKey = ev.key.length === 1;
            if (!isCharKey && ev.key !== "Backspace" && ev.key !== "Delete") {
                return;
            }
            this.beginJalaliEdit(valueIndex, ev.target);
            // Let the browser process this same keystroke normally
            // against the now-selected Jalali text (select() below makes
            // the keystroke replace the whole field, like starting fresh).
            return;
        }
        if (ev.key === "Enter" || ev.key === "Tab") {
            this.commitJalaliText(valueIndex);
        }
    },

    /** Starts a raw Jalali edit session on the given input. */
    beginJalaliEdit(valueIndex, el) {
        this.jalaliEditing[valueIndex] = true;
        this.jalaliDirty[valueIndex] = false;
        this.jalaliOriginalText[valueIndex] = el.value;
        el.value = this.getFormattedValue(valueIndex);
        el.select();
    },

    /**
     * Last-resort fallback, used only if we have no captured original
     * text to restore (shouldn't normally happen, but guards against it).
     * Writes the field's real, current (Gregorian) record value into the
     * box, formatted in Odoo's own locale format.
     */
    writeGregorianFromRecordValue(valueIndex) {
        const ref = valueIndex === 0 ? this.startDate : this.endDate;
        if (!ref.el) {
            return;
        }
        const value = this.values[valueIndex];
        if (!value) {
            ref.el.value = "";
            return;
        }
        const withTime = this.field.type !== "date";
        const fmt = withTime ? localization.dateTimeFormat : localization.dateFormat;
        ref.el.value = value.toFormat(fmt);
    },

    /** Restore the box to exactly what it held before we touched it. */
    restoreJalaliOriginalText(valueIndex) {
        const ref = valueIndex === 0 ? this.startDate : this.endDate;
        if (!ref.el) {
            return;
        }
        const original = this.jalaliOriginalText[valueIndex];
        if (original == null) {
            // Shouldn't happen (onJalaliFocus always captures this first),
            // but don't leave Jalali text sitting in the box if it does.
            this.writeGregorianFromRecordValue(valueIndex);
            return;
        }
        ref.el.value = original;
    },

    /**
     * If the user actually typed something this focus session AND it
     * parses as a genuinely different, valid Jalali date, converts it to
     * Gregorian text (in Odoo's own locale format) and writes it back
     * into the real input. In every other case - nothing was typed, or
     * what was typed doesn't parse as a valid Jalali date - nothing
     * actually needs to change, so we restore the box to its exact
     * original text (captured verbatim at focus time) instead of
     * reconstructing anything ourselves. This is deliberate: the only
     * place this code needs to *guess* at Odoo's expected text format is
     * for a real, new value - every "nothing changed" path is immune to
     * that guess being wrong.
     * Either way, by the time this returns, the box holds text the
     * private parser can read safely.
     */
    commitJalaliText(valueIndex) {
        const ref = valueIndex === 0 ? this.startDate : this.endDate;
        const wasDirty = this.jalaliDirty[valueIndex];
        this.jalaliEditing[valueIndex] = false;
        this.jalaliDirty[valueIndex] = false;
        if (!ref.el) {
            return;
        }
        if (!wasDirty) {
            this.restoreJalaliOriginalText(valueIndex);
            return;
        }
        const withTime = this.field.type !== "date";
        const parsed = parseJalaliString(ref.el.value);
        if (!parsed) {
            this.restoreJalaliOriginalText(valueIndex);
            return;
        }
        const dt = luxon.DateTime.fromObject({
            year: parsed.year,
            month: parsed.month,
            day: parsed.day,
            hour: parsed.hour,
            minute: parsed.minute,
            second: 0,
        });
        if (!dt.isValid) {
            this.restoreJalaliOriginalText(valueIndex);
            return;
        }
        const fmt = withTime ? localization.dateTimeFormat : localization.dateFormat;
        const newText = dt.toFormat(fmt);
        // eslint-disable-next-line no-console
        console.debug(
            "[jalali_date] writing new Gregorian text for private parser:",
            newText, "(format used:", fmt, ")"
        );
        ref.el.value = newText;
    },
});
