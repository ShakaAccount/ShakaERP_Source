/** @odoo-module **/

// Pure-JS Gregorian <-> Jalali (Persian) conversion.
// Implementation based on the well-known jalaali algorithm (Kazimierz M.
// Borkowski), reproduced here so the module has zero npm dependencies
// that would need bundling into Odoo's asset pipeline.

const breaks = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097,
    2192, 2262, 2324, 2394, 2456, 3178,
];

function div(a, b) {
    return ~~(a / b);
}
function mod(a, b) {
    return a - ~~(a / b) * b;
}

function jalCal(jy) {
    const bl = breaks.length;
    const gy = jy + 621;
    let leapJ = -14;
    let jp = breaks[0];
    let jump = 0;
    for (let i = 1; i < bl; i += 1) {
        const jm = breaks[i];
        jump = jm - jp;
        if (jy < jm) break;
        leapJ += div(jump, 33) * 8 + div(mod(jump, 33), 4);
        jp = jm;
    }
    let n = jy - jp;
    leapJ += div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
    if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
    const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
    const march = 20 + leapJ - leapG;
    if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
    let leap = mod(mod(n + 1, 33) - 1, 4);
    if (leap === -1) leap = 4;
    return { leap, gy, march };
}

function isLeapGregorian(gy) {
    return gy % 4 === 0 && !(gy % 100 === 0 && gy % 400 !== 0);
}

function gregorianToJdn(gy, gm, gd) {
    const d =
        div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
        div(153 * mod(gm + 9, 12) + 2, 5) +
        gd -
        34840408;
    return d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
}

function jdnToGregorian(jdn) {
    let j = 4 * jdn + 139361631;
    j += div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    const i = div(mod(j, 1461), 4) * 5 + 308;
    const gd = div(mod(i, 153), 5) + 1;
    const gm = mod(div(i, 153), 12) + 1;
    const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
    return { gy, gm, gd };
}

function jalaaliToJdn(jy, jm, jd) {
    const r = jalCal(jy);
    return gregorianToJdn(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

function jdnToJalaali(jdn) {
    const { gy } = jdnToGregorian(jdn);
    let jy = gy - 621;
    let r = jalCal(jy);
    let jdn1f = gregorianToJdn(gy, 3, r.march);
    let k = jdn - jdn1f;
    if (k >= 0) {
        if (k <= 185) {
            const jm = 1 + div(k, 31);
            const jd = mod(k, 31) + 1;
            return { jy, jm, jd };
        }
        k -= 186;
    } else {
        jy -= 1;
        // `r.leap` is a 0-4 "years since last leap year" cycle position,
        // not a boolean - only a value of exactly 1 means the year we
        // just moved into (jy, after decrementing) was a leap year with
        // a 30-day Esfand. Treating any nonzero value as leap (the
        // previous bug) wrongly added a day whenever leap was 2, 3, or
        // 4, producing invalid dates like 1404/12/30 in a common
        // (29-day Esfand) year.
        k += 179 + (r.leap === 1 ? 1 : 0);
    }
    const jm = 7 + div(k, 30);
    const jd = mod(k, 30) + 1;
    return { jy, jm, jd };
}

/** Convert a Gregorian y/m/d to Jalali {jy, jm, jd} */
export function toJalali(gy, gm, gd) {
    return jdnToJalaali(gregorianToJdn(gy, gm, gd));
}

/** Convert a Jalali y/m/d to Gregorian {gy, gm, gd} */
export function toGregorian(jy, jm, jd) {
    return jdnToGregorian(jalaaliToJdn(jy, jm, jd));
}

/** Is this Jalali year a leap year? */
export function isLeapJalaliYear(jy) {
    return jalCal(jy).leap === 0;
}

/** Number of days in a given Jalali month (1-12) of a given Jalali year */
export function jalaliMonthLength(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    return isLeapJalaliYear(jy) ? 30 : 29;
}

export const JALALI_MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

// Persian week order: Saturday first, Friday last.
export const JALALI_WEEKDAY_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
export const JALALI_WEEKDAY_LONG = [
    "شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه",
];

function pad(n) {
    return String(n).padStart(2, "0");
}

/** Format a Luxon DateTime (Gregorian, as Odoo stores it) as a Jalali string */
export function formatJalaliDate(luxonDateTime, { withTime = false } = {}) {
    if (!luxonDateTime) return "";
    const { jy, jm, jd } = toJalali(luxonDateTime.year, luxonDateTime.month, luxonDateTime.day);
    let out = `${jy}/${pad(jm)}/${pad(jd)}`;
    if (withTime) {
        out += ` ${pad(luxonDateTime.hour)}:${pad(luxonDateTime.minute)}`;
    }
    return out;
}

/**
 * Parse a Jalali string typed by the user (e.g. "1404/04/22" or
 * "1404/04/22 14:30") back into a Gregorian {y, m, d, hour, minute}.
 * Returns null if the string doesn't look like a valid Jalali date.
 */
export function parseJalaliString(value) {
    if (!value) return null;
    const m = value.trim().match(
        /^(\d{3,4})[/-](\d{1,2})[/-](\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?$/
    );
    if (!m) return null;
    const [, jyStr, jmStr, jdStr, hStr, minStr] = m;
    const jy = Number(jyStr);
    const jm = Number(jmStr);
    const jd = Number(jdStr);
    // toGregorian() does raw arithmetic with no bounds-checking of its
    // own - month 50 or day 50 would silently produce *some* Gregorian
    // date rather than being rejected. Validate ranges ourselves first.
    if (jm < 1 || jm > 12) return null;
    if (jd < 1 || jd > jalaliMonthLength(jy, jm)) return null;
    const hour = hStr ? Number(hStr) : 0;
    const minute = minStr ? Number(minStr) : 0;
    if (hour > 23 || minute > 59) return null;
    const { gy, gm, gd } = toGregorian(jy, jm, jd);
    return {
        year: gy,
        month: gm,
        day: gd,
        hour,
        minute,
    };
}
