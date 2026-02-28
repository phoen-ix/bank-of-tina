from __future__ import annotations

import atexit
import logging
import os
import secrets
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

from flask import Flask, Response, g
from flask.json.provider import DefaultJSONProvider

from flask import request, redirect, url_for, flash, jsonify
from extensions import db, csrf, migrate, limiter, scheduler
from helpers import get_setting, get_tpl, hex_to_rgb, to_local
from config import TEMPLATE_DEFAULTS


def setup_logging() -> None:
    """Configure structured logging to stdout."""
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    ))
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))
    root.addHandler(handler)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


class DecimalJSONProvider(DefaultJSONProvider):
    """Serialize Decimal values as floats so jsonify() works transparently."""
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


app = Flask(__name__)

_secret = os.environ.get('SECRET_KEY', '')
if not _secret or _secret == 'change-this-to-a-random-secret-key':
    raise RuntimeError(
        'SECRET_KEY is not set or is the insecure default. '
        'Set a strong random value in your .env file. '
        'Generate one with: python3 -c "import secrets; print(secrets.token_hex(32))"'
    )
app.config['SECRET_KEY'] = _secret

_db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', '')
if not _db_uri:
    _db_user = os.environ.get('DB_USER', '')
    _db_pass = os.environ.get('DB_PASSWORD', '')
    if not _db_user or not _db_pass:
        raise RuntimeError(
            'DB_USER and DB_PASSWORD must be set in your .env file '
            '(or set SQLALCHEMY_DATABASE_URI directly).'
        )
    _db_host = os.environ.get('DB_HOST', 'localhost')
    _db_port = os.environ.get('DB_PORT', '3306')
    _db_name = os.environ.get('DB_NAME', 'bank_of_tina')
    _db_uri = f'mysql+pymysql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}'
app.config['SQLALCHEMY_DATABASE_URI'] = _db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

app.json_provider_class = DecimalJSONProvider
app.json = DecimalJSONProvider(app)

db.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)
limiter.init_app(app)

# Import models so they are registered with SQLAlchemy
import models  # noqa: F401

from routes import register_blueprints
register_blueprints(app)


@app.errorhandler(429)
def ratelimit_handler(e: Exception) -> tuple[Response, int] | Response:
    if request.is_json:
        return jsonify({'status': 'error', 'detail': str(e.description)}), 429
    flash('Too many requests. Please wait and try again.', 'error')
    return redirect(request.referrer or url_for('main.index'))


@app.template_filter('money')
def money_filter(value: Any) -> str:
    from decimal import InvalidOperation
    from helpers import fmt_amount
    try:
        return fmt_amount(Decimal(str(value)))
    except (ValueError, TypeError, InvalidOperation):
        sep = get_setting('decimal_separator', '.')
        return '0' + sep + '00'


@app.template_filter('localdt')
def localdt_filter(dt: datetime | None, fmt: str = '%Y-%m-%d %H:%M') -> str:
    if dt is None:
        return ''
    return to_local(dt).strftime(fmt)


@app.context_processor
def inject_theme() -> dict[str, str]:
    """Inject theme colors and CSP nonce into every template."""
    navbar = get_tpl('color_navbar')
    pos    = get_tpl('color_balance_positive')
    neg    = get_tpl('color_balance_negative')
    nonce  = secrets.token_urlsafe(16)
    g.csp_nonce = nonce
    return dict(
        theme_navbar=navbar,
        theme_navbar_rgb=hex_to_rgb(navbar),
        theme_balance_positive=pos,
        theme_balance_negative=neg,
        decimal_sep=get_setting('decimal_separator', '.'),
        currency_symbol=get_setting('currency_symbol', '\u20ac'),
        icon_version=get_setting('icon_version', '0'),
        csp_nonce=nonce,
    )


@app.after_request
def set_csp_header(response: Response) -> Response:
    """Set Content-Security-Policy header on HTML responses."""
    if 'text/html' in response.content_type:
        nonce = g.get('csp_nonce', '')
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        )
    return response


if os.environ.get('FLASK_TESTING') != '1':
    from sqlalchemy.exc import OperationalError

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            with app.app_context():
                db.session.execute(db.text('SELECT 1'))

                from flask_migrate import upgrade, stamp
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                has_alembic = 'alembic_version' in tables
                has_tables = 'user' in tables

                if has_tables and not has_alembic:
                    stamp(revision='head')
                    logger.info('Existing database stamped at current migration head')
                elif not has_tables:
                    upgrade()
                    logger.info('Database created via migrations')
                else:
                    upgrade()
                    logger.info('Database migrations up to date')

                icons_dir = os.path.join(app.root_path, 'static', 'icons')
                if not os.path.exists(os.path.join(icons_dir, 'icon-192.png')) or not os.path.exists(os.path.join(icons_dir, 'icon-32.png')):
                    from config import DEFAULT_ICON_BG
                    from helpers import generate_and_save_icons
                    os.makedirs(icons_dir, exist_ok=True)
                    generate_and_save_icons(DEFAULT_ICON_BG)
                    logger.info('Generated default PWA icons')

                from scheduler_jobs import _restore_schedule
                _restore_schedule(app)
            break
        except OperationalError:
            if attempt == max_retries:
                logger.error('Could not connect to database after %d attempts', max_retries)
                raise
            delay = 2 ** (attempt - 1)
            logger.warning('DB not ready, retrying in %ds... (%d/%d)', delay, attempt, max_retries)
            time.sleep(delay)

    scheduler.start()
    logger.info('APScheduler started')
    atexit.register(lambda: scheduler.shutdown(wait=False))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
