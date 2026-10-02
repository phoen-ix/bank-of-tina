// Amount parsing shared by the expense forms. Mirrors helpers.parse_amount():
// '.' or ',' as decimal separator, and when both appear the right-most one is
// the decimal separator ('1.234,56'). Works in integer units of 1/10000 so totals
// match what the server stores (rounded half up to 4 decimals).
const AMOUNT_UNITS = 10000;

// Returns integer units, 0 for blank input, or NaN if the text isn't an amount.
function parseUnits(raw) {
    let s = String(raw).replace(/[\s ]/g, '');
    if (!s) return 0;
    if (s.includes(',') && s.includes('.')) {
        s = s.lastIndexOf(',') > s.lastIndexOf('.')
            ? s.replace(/\./g, '').replace(',', '.')
            : s.replace(/,/g, '');
    } else {
        s = s.replace(/,/g, '.');
    }
    const m = /^([+-]?)(\d*)(?:\.(\d*))?$/.exec(s);
    if (!m || (m[2] === '' && !m[3])) return NaN;
    const frac = ((m[3] || '') + '00000').slice(0, 5);
    let units = parseInt(m[2] || '0', 10) * AMOUNT_UNITS + parseInt(frac.slice(0, 4), 10);
    if (parseInt(frac[4], 10) >= 5) units += 1;
    return m[1] === '-' ? -units : units;
}

// Formats integer units with the configured decimal separator, showing every
// decimal but at least two (mirrors helpers.amount_str): 123500 -> "12,35",
// 3975 -> "0,3975".
function fmtUnits(units, sep) {
    const sign = units < 0 ? '-' : '';
    const abs = Math.abs(units);
    const frac = String(abs % AMOUNT_UNITS).padStart(4, '0').replace(/0{1,2}$/, '');
    return sign + Math.floor(abs / AMOUNT_UNITS) + sep + frac;
}
