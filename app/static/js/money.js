// Amount parsing shared by the expense forms. Mirrors helpers.parse_amount():
// '.' or ',' as decimal separator, and when both appear the right-most one is
// the decimal separator ('1.234,56'). Works in integer cents so totals match
// what the server stores (rounded half up to 2 decimals).

// Returns integer cents, 0 for blank input, or NaN if the text isn't an amount.
function parseCents(raw) {
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
    const frac = ((m[3] || '') + '000').slice(0, 3);
    let cents = parseInt(m[2] || '0', 10) * 100 + parseInt(frac.slice(0, 2), 10);
    if (parseInt(frac[2], 10) >= 5) cents += 1;
    return m[1] === '-' ? -cents : cents;
}

// Formats integer cents with the configured decimal separator: 1234 -> "12,34".
function fmtCents(cents, sep) {
    const sign = cents < 0 ? '-' : '';
    const abs = Math.abs(cents);
    return sign + Math.floor(abs / 100) + sep + String(abs % 100).padStart(2, '0');
}
