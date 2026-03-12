import os
import sys

# Must set env vars BEFORE importing app
os.environ['FLASK_TESTING'] = '1'
os.environ['SECRET_KEY'] = 'test-key-not-for-production'
os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

# Add the app directory to sys.path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from sqlalchemy import event, Numeric
from app import app as _app
from extensions import db as _db


def _coerce_numeric_to_float(target, _context):
    """Simulate MariaDB/PyMySQL behavior: Numeric columns are returned as float.

    SQLite returns Decimal natively, which hides type mismatches that only
    surface in production with MariaDB.  This listener fires after every ORM
    load and converts every Numeric column value to float so that tests fail
    when code does ``Decimal + float`` or ``float += Decimal``.
    """
    mapper = type(target).__mapper__  # type: ignore[attr-defined]
    for col in mapper.columns:
        if isinstance(col.type, Numeric):
            val = getattr(target, col.key, None)
            if val is not None:
                setattr(target, col.key, float(val))


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    _app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'RATELIMIT_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'UPLOAD_FOLDER': '/tmp/bot_test_uploads',
    })
    os.makedirs('/tmp/bot_test_uploads', exist_ok=True)
    with _app.app_context():
        _db.create_all()
    # Simulate MariaDB/PyMySQL: coerce all Numeric columns to float on load
    event.listen(_db.Model, 'load', _coerce_numeric_to_float, propagate=True)
    yield _app


@pytest.fixture(autouse=True)
def clean_db(app):
    """Roll back all changes after each test."""
    from helpers import set_setting
    with app.app_context():
        _db.create_all()
        set_setting('language', 'en')
        yield
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    """A Flask test client."""
    return app.test_client()


@pytest.fixture
def make_user(app):
    """Factory fixture to create users quickly.

    Must be called inside a ``with app.app_context():`` block.
    """
    from decimal import Decimal
    from models import User

    _counter = [0]

    def _make(name=None, email=None, balance=Decimal('0'), is_active=True,
              email_opt_in=True, email_transactions='last3'):
        _counter[0] += 1
        if name is None:
            name = f'User{_counter[0]}'
        if email is None:
            email = f'user{_counter[0]}@example.com'
        user = User(name=name, email=email, balance=balance,
                    is_active=is_active, email_opt_in=email_opt_in,
                    email_transactions=email_transactions)
        _db.session.add(user)
        _db.session.commit()
        return user

    return _make
