import atexit
import logging
import os
from decimal import Decimal

from flask import Flask
from flask.json.provider import DefaultJSONProvider

from extensions import db, csrf, scheduler
from helpers import get_setting, get_tpl, hex_to_rgb, to_local
from config import TEMPLATE_DEFAULTS


def setup_logging():
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
    def default(self, o):
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

_db_user = os.environ.get('DB_USER', 'tina')
_db_pass = os.environ.get('DB_PASSWORD', 'tina')
_db_host = os.environ.get('DB_HOST', 'localhost')
_db_port = os.environ.get('DB_PORT', '3306')
_db_name = os.environ.get('DB_NAME', 'bank_of_tina')
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

app.json_provider_class = DecimalJSONProvider
app.json = DecimalJSONProvider(app)

db.init_app(app)
csrf.init_app(app)

# Import models so they are registered with SQLAlchemy
import models  # noqa: F401

from routes import register_blueprints
register_blueprints(app)


@app.template_filter('money')
def money_filter(value):
    from decimal import InvalidOperation
    from helpers import fmt_amount
    try:
        return fmt_amount(Decimal(str(value)))
    except (ValueError, TypeError, InvalidOperation):
        sep = get_setting('decimal_separator', '.')
        return '0' + sep + '00'


@app.template_filter('localdt')
def localdt_filter(dt, fmt='%Y-%m-%d %H:%M'):
    if dt is None:
        return ''
    return to_local(dt).strftime(fmt)


@app.context_processor
def inject_theme():
    """Inject theme colors into every template for dynamic CSS."""
    navbar = get_tpl('color_navbar')
    pos    = get_tpl('color_balance_positive')
    neg    = get_tpl('color_balance_negative')
    return dict(
        theme_navbar=navbar,
        theme_navbar_rgb=hex_to_rgb(navbar),
        theme_balance_positive=pos,
        theme_balance_negative=neg,
        decimal_sep=get_setting('decimal_separator', '.'),
        currency_symbol=get_setting('currency_symbol', '\u20ac'),
        icon_version=get_setting('icon_version', '0'),
    )


def _migrate_db():
    """Add any new columns / modify types that db.create_all() won't handle."""
    with db.engine.connect() as conn:
        for col, definition in [
            ('email_opt_in',       'BOOLEAN NOT NULL DEFAULT 1'),
            ('email_transactions', "VARCHAR(20) NOT NULL DEFAULT 'last3'"),
        ]:
            try:
                conn.execute(db.text(f'ALTER TABLE user ADD COLUMN {col} {definition}'))
                conn.commit()
            except Exception:
                pass
        try:
            conn.execute(db.text('ALTER TABLE `transaction` ADD COLUMN notes TEXT'))
            conn.commit()
        except Exception:
            pass
        for table, column in [
            ('user', 'balance'),
            ('`transaction`', 'amount'),
            ('expense_item', 'price'),
            ('common_price', 'value'),
        ]:
            try:
                conn.execute(db.text(f'ALTER TABLE {table} MODIFY COLUMN {column} DECIMAL(12,2)'))
                conn.commit()
            except Exception:
                pass


if os.environ.get('FLASK_TESTING') != '1':
    with app.app_context():
        db.create_all()
        logger.info('Database tables created / verified')
        _migrate_db()
        from scheduler_jobs import _restore_schedule
        _restore_schedule(app)
    scheduler.start()
    logger.info('APScheduler started')
    atexit.register(lambda: scheduler.shutdown(wait=False))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
