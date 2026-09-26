from __future__ import annotations

import os
import re
import secrets
import struct
import time
import zlib
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from urllib.parse import urlsplit

import pytz
from flask import Response, current_app, g, redirect, request
from flask_babel import gettext as _
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from extensions import db
from models import Setting, Transaction, User
from config import ALLOWED_EXTENSIONS, TEMPLATE_DEFAULTS, TEMPLATE_DEFAULTS_DE

_CENT = Decimal('0.01')
# Numeric(12, 2): ten digits before the decimal point.
_MAX_AMOUNT = Decimal('9999999999.99')
_AMOUNT_RE = re.compile(r'[+-]?(\d+\.?\d*|\.\d+)')


class InputError(ValueError):
    """User input that cannot be accepted; str(e) is a message for the user."""


class AmountError(InputError):
    """An amount that is not a plain number with a finite value."""


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_receipt(file: FileStorage | None, buyer_name: str) -> str | None:
    """Save an uploaded receipt to UPLOAD_FOLDER/YYYY/MM/DD/Buyer_name_<token>.ext.

    The random token keeps two uploads of e.g. "scan.pdf" on the same day from
    overwriting each other. Callers validate the extension with allowed_file().
    """
    if not file or not file.filename or not allowed_file(file.filename):
        return None

    safe_buyer = re.sub(r'[^\w]', '_', buyer_name)
    safe_buyer = re.sub(r'_+', '_', safe_buyer).strip('_') or 'unknown'
    stem, ext = file.filename.rsplit('.', 1)
    stem = secure_filename(stem) or 'receipt'

    now = now_local()
    rel_dir = now.strftime('%Y/%m/%d')
    abs_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{safe_buyer}_{stem}_{secrets.token_hex(3)}.{ext.lower()}"
    file.save(os.path.join(abs_dir, filename))
    return f"{rel_dir}/{filename}"


def delete_receipt_file(receipt_path: str | None, exclude_transaction_id: int) -> None:
    """Delete a receipt file from disk only if no other transaction still references it."""
    if not receipt_path:
        return
    others = db.session.execute(
        db.select(Transaction).where(
            Transaction.receipt_path == receipt_path,
            Transaction.id != exclude_transaction_id
        )
    ).scalar()
    if others:
        return
    abs_path = os.path.join(current_app.config['UPLOAD_FOLDER'], receipt_path)
    try:
        os.remove(abs_path)
    except OSError:
        pass


def adjust_balance(user_id: int | None, delta: Decimal) -> None:
    """Add `delta` to a user's balance with a single SQL UPDATE (no read-modify-write
    race between concurrent requests). Does not commit."""
    if user_id is None or not delta:
        return
    db.session.execute(
        db.update(User).where(User.id == user_id)
        .values(balance=User.balance + delta)
        .execution_options(synchronize_session='fetch')
    )


def apply_balance_effect(trans: Transaction, reverse: bool = False) -> None:
    """Apply (or undo) a transaction's effect: from_user pays `amount`, to_user receives it."""
    amount = Decimal(str(trans.amount))
    if reverse:
        amount = -amount
    adjust_balance(trans.from_user_id, -amount)
    adjust_balance(trans.to_user_id, amount)


def get_setting(key: str, default: str | None = None) -> str | None:
    s = db.session.get(Setting, key)
    return s.value if s else default


def set_setting(key: str, value: str, commit: bool = True) -> None:
    s = db.session.get(Setting, key) or Setting(key=key)
    s.value = value
    db.session.add(s)
    if commit:
        db.session.commit()


def delete_setting(key: str, commit: bool = True) -> None:
    s = db.session.get(Setting, key)
    if s:
        db.session.delete(s)
    if commit:
        db.session.commit()


def now_local() -> datetime:
    """Return the current datetime in the configured app timezone."""
    tz_name = get_setting('timezone', 'UTC')
    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC
    return datetime.now(tz)


def get_tpl(key: str) -> str:
    """Get a template/theme setting, falling back to language-appropriate defaults.

    For ``tpl_*`` keys the value is stored per-language (e.g. ``tpl_email_subject_de``).
    Color keys (``color_*``) are language-independent and stored without suffix.
    """
    if key.startswith('tpl_'):
        lang = get_setting('language', 'de')
        defaults = TEMPLATE_DEFAULTS_DE if lang == 'de' else TEMPLATE_DEFAULTS
        return get_setting(f'{key}_{lang}', defaults.get(key, ''))
    return get_setting(key, TEMPLATE_DEFAULTS.get(key, ''))


def apply_template(text: str, **kwargs: str | int | None) -> str:
    """Replace [Key] placeholders in text with provided values."""
    for key, value in kwargs.items():
        text = text.replace(f'[{key}]', str(value) if value is not None else '')
    return text


def parse_amount(s: str | None, positive: bool = False) -> Decimal:
    """Parse a user-supplied amount and round it to cents.

    Accepts '.' or ',' as decimal separator; when both appear, the right-most
    one is the decimal separator and the other groups thousands ('1.234,56').
    Empty input is 0. Raises AmountError for anything else (including NaN,
    Infinity and exponents), and for values <= 0 when `positive` is set.
    """
    if s is None:
        return Decimal('0')
    cleaned = str(s).strip().replace(' ', '').replace('\u00a0', '')
    if not cleaned:
        return Decimal('0')
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    else:
        cleaned = cleaned.replace(',', '.')
    if not _AMOUNT_RE.fullmatch(cleaned):
        raise AmountError(_('"%(value)s" is not a valid amount.', value=s))
    value = Decimal(cleaned).quantize(_CENT, rounding=ROUND_HALF_UP)
    if abs(value) > _MAX_AMOUNT:
        raise AmountError(_('"%(value)s" is too large.', value=s))
    if positive and value <= 0:
        raise AmountError(_('Amounts must be greater than zero.'))
    return value


def fmt_amount(value: Decimal | int | float) -> str:
    """Format a numeric value with 2 decimal places using the configured decimal separator."""
    sep = get_setting('decimal_separator', '.')
    return f'{Decimal(str(value)):.2f}'.replace('.', sep)


def hex_to_rgb(hex_color: str) -> str:
    """Convert #rrggbb to 'r, g, b' string for CSS custom properties."""
    try:
        h = hex_color.lstrip('#')
        return f'{int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)}'
    except (ValueError, IndexError):
        return '0, 0, 0'


def make_icon_png(size: int, bg_color: tuple[int, int, int],
                  fg_color: tuple[int, int, int] = (0xff, 0xff, 0xff)) -> bytes:
    """Generate a square PNG of `size` pixels with a bank silhouette."""
    width = height = size
    pixels: list[list[tuple[int, int, int]]] = [[bg_color] * width for _ in range(height)]

    pad = size * 0.15
    draw_w = size - 2 * pad
    draw_h = size - 2 * pad

    def fill_rect(x0f: float, y0f: float, x1f: float, y1f: float) -> None:
        x0 = int(pad + x0f * draw_w)
        y0 = int(pad + y0f * draw_h)
        x1 = int(pad + x1f * draw_w)
        y1 = int(pad + y1f * draw_h)
        for row in range(max(0, y0), min(height, y1)):
            for col in range(max(0, x0), min(width, x1)):
                pixels[row][col] = fg_color

    fill_rect(0.10, 0.00, 0.90, 0.18)
    fill_rect(0.20, 0.18, 0.80, 0.26)
    col_w = 0.10
    for cx in (0.20, 0.45, 0.70):
        fill_rect(cx, 0.26, cx + col_w, 0.78)
    fill_rect(0.10, 0.78, 0.90, 0.88)
    fill_rect(0.05, 0.88, 0.95, 1.00)

    raw_rows: list[bytes] = []
    for row in pixels:
        row_bytes = b'\x00' + b''.join(bytes(p) for p in row)
        raw_rows.append(row_bytes)
    raw = b''.join(raw_rows)
    compressed = zlib.compress(raw, level=9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', ihdr_data)
            + chunk(b'IDAT', compressed)
            + chunk(b'IEND', b''))


def generate_and_save_icons(bg_hex: str) -> str:
    """Generate bank silhouette icons with the given background color and save them."""
    h = bg_hex.lstrip('#')
    bg_rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    for size in (32, 192, 512):
        path = os.path.join(icons_dir, f'icon-{size}.png')
        with open(path, 'wb') as f:
            f.write(make_icon_png(size, bg_rgb))
    version = str(int(time.time()))
    set_setting('icon_version', version)
    set_setting('icon_mode', 'generated')
    return version


def detect_theme() -> str:
    """Return the key of the active preset theme, or 'custom'."""
    from config import THEMES
    color_keys = ['color_navbar', 'color_email_grad_start', 'color_email_grad_end',
                  'color_balance_positive', 'color_balance_negative']
    current = {k: get_tpl(k) for k in color_keys}
    for theme_key, theme in THEMES.items():
        if all(current[k] == theme[k] for k in color_keys):
            return theme_key
    return 'custom'


def parse_local_datetime(date_str: str) -> datetime | None:
    """Parse a datetime-local (or date) string entered in the app timezone into naive UTC.

    Returns None when the string can't be parsed."""
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            return local_to_utc(datetime.strptime(date_str, fmt))
        except ValueError:
            continue
    return None


def parse_submitted_date(date_str: str) -> datetime:
    """Like parse_local_datetime(), but falls back to the current time."""
    parsed = parse_local_datetime(date_str) if date_str else None
    return parsed or datetime.now(UTC).replace(tzinfo=None)


def get_app_tz() -> pytz.BaseTzInfo:
    """Return the configured pytz timezone, cached for the duration of the request."""
    if 'app_tz' not in g:
        tz_name = get_setting('timezone', 'UTC')
        try:
            g.app_tz = pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            g.app_tz = pytz.UTC
    return g.app_tz


def local_to_utc(naive_local: datetime) -> datetime:
    """Interpret a naive datetime in the app timezone and return it as naive UTC."""
    return get_app_tz().localize(naive_local).astimezone(pytz.UTC).replace(tzinfo=None)


def local_day_start_utc(d: date) -> datetime:
    """Naive UTC instant at which local calendar day `d` begins."""
    return local_to_utc(datetime.combine(d, datetime.min.time()))


def local_days_utc(first: date, last: date) -> tuple[datetime, datetime]:
    """Half-open UTC range [start, end) covering local days first..last inclusive."""
    return local_day_start_utc(first), local_day_start_utc(last + timedelta(days=1))


def local_month_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """Half-open UTC range [start, end) covering a local calendar month."""
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return local_day_start_utc(date(year, month, 1)), local_day_start_utc(nxt)


def to_local(dt: datetime | None) -> datetime | None:
    """Convert a naive UTC datetime to the configured local timezone."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(get_app_tz())


def redirect_back(default: str) -> Response:
    """Redirect to the referring page when it is on this host, otherwise to `default`."""
    ref = request.referrer
    if ref:
        parts = urlsplit(ref)
        if parts.scheme in ('http', 'https') and parts.netloc == request.host:
            return redirect(ref)
    return redirect(default)
