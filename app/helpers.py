from __future__ import annotations

import os
import re
import struct
import time
import zlib
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import pytz
from flask import current_app, g
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from extensions import db
from models import Setting, Transaction
from config import ALLOWED_EXTENSIONS, TEMPLATE_DEFAULTS, DEFAULT_ICON_BG


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_receipt(file: FileStorage | None, buyer_name: str) -> str | None:
    """Save an uploaded receipt to UPLOAD_FOLDER/YYYY/MM/DD/BUYER_filename."""
    if not file or not file.filename or not allowed_file(file.filename):
        return None

    safe_buyer = re.sub(r'[^\w]', '_', buyer_name)
    safe_buyer = re.sub(r'_+', '_', safe_buyer).strip('_') or 'unknown'
    original = secure_filename(file.filename) or 'file'

    now = datetime.now()
    rel_dir = now.strftime('%Y/%m/%d')
    abs_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{safe_buyer}_{original}"
    file.save(os.path.join(abs_dir, filename))
    return f"{rel_dir}/{filename}"


def delete_receipt_file(receipt_path: str | None, exclude_transaction_id: int) -> None:
    """Delete a receipt file from disk only if no other transaction still references it."""
    if not receipt_path:
        return
    others = Transaction.query.filter(
        Transaction.receipt_path == receipt_path,
        Transaction.id != exclude_transaction_id
    ).first()
    if others:
        return
    abs_path = os.path.join(current_app.config['UPLOAD_FOLDER'], receipt_path)
    try:
        os.remove(abs_path)
    except OSError:
        pass


def update_balance(user_id: int, amount: Decimal) -> None:
    from models import User
    user = db.session.get(User, user_id)
    if user:
        user.balance += amount
        db.session.commit()


def get_setting(key: str, default: str | None = None) -> str | None:
    s = db.session.get(Setting, key)
    return s.value if s else default


def set_setting(key: str, value: str) -> None:
    s = db.session.get(Setting, key) or Setting(key=key)
    s.value = value
    db.session.add(s)
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
    """Get a template/theme setting, falling back to TEMPLATE_DEFAULTS."""
    return get_setting(key, TEMPLATE_DEFAULTS.get(key, ''))


def apply_template(text: str, **kwargs: str | int | None) -> str:
    """Replace [Key] placeholders in text with provided values."""
    for key, value in kwargs.items():
        text = text.replace(f'[{key}]', str(value) if value is not None else '')
    return text


def parse_amount(s: str | None) -> Decimal:
    """Parse a user-supplied decimal string, accepting both '.' and ',' as separator."""
    if s is None:
        return Decimal('0')
    return Decimal(str(s).strip().replace(',', '.'))


def fmt_amount(value: Decimal | int | float) -> str:
    """Format a numeric value with 2 decimal places using the configured decimal separator."""
    sep = get_setting('decimal_separator', '.')
    return f'{Decimal(str(value)):.2f}'.replace('.', sep)


def hex_to_rgb(hex_color: str) -> str:
    """Convert #rrggbb to 'r, g, b' string for CSS custom properties."""
    try:
        h = hex_color.lstrip('#')
        return f'{int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)}'
    except Exception:
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
    for size in (192, 512):
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


def parse_submitted_date(date_str: str) -> datetime:
    """Parse a datetime-local string entered in the app timezone and return a naive UTC datetime."""
    if not date_str:
        return datetime.now(UTC).replace(tzinfo=None)
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            naive = datetime.strptime(date_str, fmt)
            tz_name = get_setting('timezone', 'UTC')
            tz = pytz.timezone(tz_name)
            return tz.localize(naive).astimezone(pytz.UTC).replace(tzinfo=None)
        except (ValueError, pytz.exceptions.UnknownTimeZoneError):
            continue
    return datetime.now(UTC).replace(tzinfo=None)


def get_app_tz() -> pytz.BaseTzInfo:
    """Return the configured pytz timezone, cached for the duration of the request."""
    if 'app_tz' not in g:
        tz_name = get_setting('timezone', 'UTC')
        try:
            g.app_tz = pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            g.app_tz = pytz.UTC
    return g.app_tz


def to_local(dt: datetime | None) -> datetime | None:
    """Convert a naive UTC datetime to the configured local timezone."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(get_app_tz())
