import os
import sys

# Must set env vars BEFORE importing app
os.environ['FLASK_TESTING'] = '1'
os.environ['SECRET_KEY'] = 'test-key-not-for-production'
os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

# Add the app directory to sys.path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from app import app as _app
from extensions import db as _db


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
    yield _app


@pytest.fixture(autouse=True)
def clean_db(app):
    """Roll back all changes after each test."""
    with app.app_context():
        _db.create_all()
        yield
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    """A Flask test client."""
    return app.test_client()
