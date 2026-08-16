/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import {
    toJalali,
    toGregorian,
    jalaliMonthLength,
    JALALI_MONTH_NAMES,
    JALALI_WEEKDAY_SHORT,
    JALALI_WEEKDAY_LONG,
} from "./jalali_utils";

/*
 * CONFIRMED against a real Odoo 19.0 install:
 * addons/web/static/src/core/datetime/datetime_picker.js keeps its
 * PRECISION_LEVELS map (which builds the day/month/year grids) private -
 * it is never exported, so it can't be extended from outside. The only
 * public seam is the `activePrecisionLevel` getter, which reads from that
 * map, plus the `next()`/`previous()` navigation methods. Overriding those
 * three lets us hand the component an entirely custom Jalali grid without
 * touching the private internals.
 *
 * SCOPE: "days" (the main calendar grid), "months" (12-month picker for
 * a year), and "years" (decade picker) are all converted to Jalali here.
 * "decades" (century picker, rarely used) is left as a known remaining
 * gap - same technique would extend to it if ever needed.
 */

const DAYS_PER_WEEK = 7;
const WEEKS_PER_MONTH = 6;

// Luxon weekday: 1=Mon ... 7=Sun. Persian week: Saturday=0 ... Friday=6.
function gregWeekdayToPersianIndex(weekday) {
    const map = { 6: 0, 7: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6 };
    return map[weekday];
}

function isInRangeSafe(date, range) {
    if (!range) return true;
    const [start, end] = range;
    if (start && date < start) return false;
    if (end && date > end) return false;
    return true;
}

function isJalali() {
    return session.calendar_type === "jalali";
}

// ---------------------------------------------------------------------
// "days" precision - the main month grid
// ---------------------------------------------------------------------

function buildJalaliDaysItems(focusDate, { maxDate, minDate, showWeekNumbers, isDateValid, dayCellClass }) {
    const { jy, jm } = toJalali(focusDate.year, focusDate.month, focusDate.day);

    const firstGreg = toGregorian(jy, jm, 1);
    const firstDayLuxon = focusDate.set({ year: firstGreg.gy, month: firstGreg.gm, day: firstGreg.gd });

    const leadIn = gregWeekdayToPersianIndex(firstDayLuxon.weekday);
    let cursor = firstDayLuxon.minus({ day: leadIn });

    const todayLuxon = luxon.DateTime.local();
    const weeks = [];

    for (let w = 0; w < WEEKS_PER_MONTH; w++) {
        const weekDays = [];
        for (let d = 0; d < DAYS_PER_WEEK; d++) {
            const dayStart = cursor;
            const dayEnd = cursor.endOf("day");
            const { jy: cjy, jm: cjm, jd: cjd } = toJalali(cursor.year, cursor.month, cursor.day);
            const range = [dayStart, dayEnd];
            weekDays.push({
                id: dayStart.toISODate(),
                includesToday: dayStart.hasSame(todayLuxon, "day"),
                isOutOfRange: !(cjy === jy && cjm === jm),
                isValid:
                    isInRangeSafe(dayStart, [minDate, maxDate]) &&
                    (!isDateValid || isDateValid(dayStart)),
                label: String(cjd),
                range,
                extraClass: dayCellClass ? dayCellClass(dayStart) || "" : "",
            });
            cursor = cursor.plus({ day: 1 });
        }
        weeks.push({ number: weekDays[3].range[0].weekNumber, days: weekDays });
    }

    const daysOfWeek = JALALI_WEEKDAY_LONG.map((long, i) => [
        JALALI_WEEKDAY_SHORT[i],
        long,
        JALALI_WEEKDAY_SHORT[i],
    ]);
    if (showWeekNumbers) {
        daysOfWeek.unshift(["", "Week numbers", ""]);
    }

    return [{ id: "__month__0", number: jm, daysOfWeek, weeks }];
}

// ---------------------------------------------------------------------
// "months" precision - 12-month picker for a Jalali year
// ---------------------------------------------------------------------

function buildJalaliMonthsItems(focusDate, { maxDate, minDate }) {
    const { jy } = toJalali(focusDate.year, focusDate.month, focusDate.day);
    const todayLuxon = luxon.DateTime.local();
    const { jy: tJy, jm: tJm } = toJalali(todayLuxon.year, todayLuxon.month, todayLuxon.day);

    const items = [];
    for (let m = 1; m <= 12; m++) {
        const startG = toGregorian(jy, m, 1);
        const startLuxon = focusDate.set({ year: startG.gy, month: startG.gm, day: startG.gd });
        const len = jalaliMonthLength(jy, m);
        const endG = toGregorian(jy, m, len);
        const endLuxon = focusDate
            .set({ year: endG.gy, month: endG.gm, day: endG.gd })
            .endOf("day");
        items.push({
            id: startLuxon.toISODate(),
            includesToday: tJy === jy && tJm === m,
            isOutOfRange: false,
            isValid: isInRangeSafe(startLuxon, [minDate, maxDate]),
            label: JALALI_MONTH_NAMES[m - 1],
            range: [startLuxon, endLuxon],
        });
    }
    return items;
}

// ---------------------------------------------------------------------
// "years" precision - decade picker
// ---------------------------------------------------------------------

function buildJalaliYearsItems(focusDate, { maxDate, minDate }) {
    const { jy } = toJalali(focusDate.year, focusDate.month, focusDate.day);
    const startOfDecade = Math.floor(jy / 10) * 10;

    const items = [];
    for (let i = -1; i <= 10; i++) {
        const y = startOfDecade + i;
        const startG = toGregorian(y, 1, 1);
        const startLuxon = focusDate.set({ year: startG.gy, month: startG.gm, day: startG.gd });
        const lastLen = jalaliMonthLength(y, 12);
        const endG = toGregorian(y, 12, lastLen);
        const endLuxon = focusDate
            .set({ year: endG.gy, month: endG.gm, day: endG.gd })
            .endOf("day");
        items.push({
            id: startLuxon.toISODate(),
            includesToday: false,
            isOutOfRange: i < 0 || i >= 10,
            isValid: isInRangeSafe(startLuxon, [minDate, maxDate]),
            label: String(y),
            range: [startLuxon, endLuxon],
        });
    }
    return { items, startOfDecade };
}

// ---------------------------------------------------------------------
// Precision-level dispatch
// ---------------------------------------------------------------------

function getJalaliPrecisionInfo(precision) {
    if (precision === "days") {
        return {
            step: { month: 1 },
            getTitle: (date) => {
                const { jy, jm } = toJalali(date.year, date.month, date.day);
                return `${JALALI_MONTH_NAMES[jm - 1]} ${jy}`;
            },
            getItems: (date, params) => buildJalaliDaysItems(date, params),
        };
    }
    if (precision === "months") {
        return {
            step: { year: 1 },
            getTitle: (date) => {
                const { jy } = toJalali(date.year, date.month, date.day);
                return String(jy);
            },
            getItems: (date, params) => buildJalaliMonthsItems(date, params),
        };
    }
    if (precision === "years") {
        return {
            step: { year: 10 },
            getTitle: (date) => {
                const { startOfDecade } = buildJalaliYearsItems(date, {});
                return `${startOfDecade - 1} - ${startOfDecade + 10}`;
            },
            getItems: (date, params) => buildJalaliYearsItems(date, params).items,
        };
    }
    return null; // "decades" - not covered, falls back to Gregorian
}

function isJalaliActivePrecision(self) {
    return isJalali() && ["days", "months", "years"].includes(self.state.precision);
}

/** Advance/rewind focusDate by one Jalali step for the current precision */
function shiftJalaliFocus(self, direction) {
    const focusDate = self.state.focusDate;
    const { jy, jm } = toJalali(focusDate.year, focusDate.month, focusDate.day);

    if (self.state.precision === "days") {
        let ny = jy;
        let nm = jm + direction;
        if (nm > 12) {
            nm = 1;
            ny += 1;
        } else if (nm < 1) {
            nm = 12;
            ny -= 1;
        }
        const g = toGregorian(ny, nm, 1);
        return self.clamp(focusDate.set({ year: g.gy, month: g.gm, day: g.gd }));
    }
    if (self.state.precision === "months") {
        const ny = jy + direction;
        const g = toGregorian(ny, jm, 1);
        return self.clamp(focusDate.set({ year: g.gy, month: g.gm, day: g.gd }));
    }
    if (self.state.precision === "years") {
        const ny = jy + direction * 10;
        const g = toGregorian(ny, jm, 1);
        return self.clamp(focusDate.set({ year: g.gy, month: g.gm, day: g.gd }));
    }
    return focusDate;
}

patch(DateTimePicker.prototype, {
    get isJalaliActive() {
        return isJalali();
    },

    get activePrecisionLevel() {
        if (isJalaliActivePrecision(this)) {
            const info = getJalaliPrecisionInfo(this.state.precision);
            if (info) {
                const base = super.activePrecisionLevel;
                return { ...base, ...info };
            }
        }
        return super.activePrecisionLevel;
    },

    next(ev) {
        if (isJalaliActivePrecision(this)) {
            ev.preventDefault();
            this.state.focusDate = shiftJalaliFocus(this, 1);
            return;
        }
        super.next(ev);
    },

    previous(ev) {
        if (isJalaliActivePrecision(this)) {
            ev.preventDefault();
            this.state.focusDate = shiftJalaliFocus(this, -1);
            return;
        }
        super.previous(ev);
    },

    /**
     * Jumps to today. Rather than guessing at any private "select a
     * date" API on this component, this switches the grid to the
     * "days" precision showing today's month, then - once that render
     * lands - finds and .click()s the real today cell (marked with the
     * `o_today` class in the rendered DOM) exactly as if the user had
     * clicked it themselves. This goes through whatever internal
     * selection handler Odoo already has wired to that cell, so it's
     * guaranteed to behave identically to a real click, with nothing
     * here depending on private internals.
     */
    selectJalaliToday(ev) {
        if (!this.isJalaliActive) {
            return;
        }
        const popoverRoot = ev.target.closest(".o_datetime_picker");
        this.state.precision = "days";
        this.state.focusDate = luxon.DateTime.local();
        requestAnimationFrame(() => {
            const root = popoverRoot || document;
            const cell = root.querySelector(".o_today");
            if (cell) {
                cell.click();
            }
        });
    },
});
