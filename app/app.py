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
from flask_babel import gettext as _, format_date as babel_format_date
from extensions import db, csrf, migrate, limiter, scheduler, babel
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

app.config['BABEL_DEFAULT_LOCALE'] = 'de'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'


def get_locale() -> str:
    try:
        return get_setting('language', 'de')
    except Exception:
        return 'de'


db.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)
limiter.init_app(app)
babel.init_app(app, locale_selector=get_locale)

# Import models so they are registered with SQLAlchemy
import models  # noqa: F401

from routes import register_blueprints
register_blueprints(app)


@app.errorhandler(429)
def ratelimit_handler(e: Exception) -> tuple[Response, int] | Response:
    if request.is_json:
        return jsonify({'status': 'error', 'detail': str(e.description)}), 429
    flash(_('Too many requests. Please wait and try again.'), 'error')
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


@app.template_filter('format_date_babel')
def format_date_babel_filter(value: datetime, fmt: str = 'EEEE, d MMMM') -> str:
    return babel_format_date(value, fmt)


@app.template_filter('tx_type')
def tx_type_filter(value: str) -> str:
    return {
        'deposit': _('deposit'),
        'withdrawal': _('withdrawal'),
        'expense': _('expense'),
    }.get(value, value)


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
        current_locale=get_locale(),
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

                # Migrate unsuffixed tpl_* keys to per-language keys.
                # Only keep genuinely customized values; delete defaults so
                # get_tpl() falls through to the language-appropriate defaults.
                from helpers import set_setting as _set
                from models import Setting
                from config import TEMPLATE_DEFAULTS as _EN_DEFAULTS, TEMPLATE_DEFAULTS_DE as _DE_DEFAULTS
                _tpl_keys = ['tpl_email_subject', 'tpl_email_greeting', 'tpl_email_intro',
                             'tpl_email_footer1', 'tpl_email_footer2',
                             'tpl_admin_subject', 'tpl_admin_intro', 'tpl_admin_footer',
                             'tpl_backup_subject', 'tpl_backup_footer']
                _has_old = any(db.session.get(Setting, k) for k in _tpl_keys)
                _has_new = any(db.session.get(Setting, f'{k}_{l}')
                               for k in _tpl_keys[:1] for l in ('de', 'en'))
                if _has_old and not _has_new:
                    _lang = get_setting('language', 'de')
                    for _k in _tpl_keys:
                        _old = db.session.get(Setting, _k)
                        if _old:
                            _is_default = (_old.value == _EN_DEFAULTS.get(_k, '')
                                           or _old.value == _DE_DEFAULTS.get(_k, ''))
                            if not _is_default:
                                _set(f'{_k}_{_lang}', _old.value, commit=False)
                            db.session.delete(_old)
                    db.session.commit()
                    logger.info('Migrated email templates to per-language keys (%s)', _lang)
                # Clean up bad migration and redundant entries: remove suffixed
                # keys whose value matches any default (wrong-language or own)
                # so get_tpl() falls through to the correct defaults.
                for _k in _tpl_keys:
                    for _l in ('de', 'en'):
                        _s = db.session.get(Setting, f'{_k}_{_l}')
                        if _s and _s.value in (_EN_DEFAULTS.get(_k, ''),
                                               _DE_DEFAULTS.get(_k, '')):
                            db.session.delete(_s)
                db.session.commit()

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
