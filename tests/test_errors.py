"""Error pages: 404, 500 (also with the database down) and an expired CSRF token."""

import pytest
from sqlalchemy.exc import OperationalError


def test_404_page(client):
    resp = client.get('/no-such-page')
    assert resp.status_code == 404
    assert 'Page not found.' in resp.data.decode()


@pytest.fixture
def boom(app, monkeypatch):
    """Make the dashboard raise and let Flask's 500 handler answer it."""
    monkeypatch.setitem(app.config, 'PROPAGATE_EXCEPTIONS', False)

    def fail():
        raise RuntimeError('boom')

    monkeypatch.setitem(app.view_functions, 'main.index', fail)


def test_500_page(client, boom):
    resp = client.get('/')
    assert resp.status_code == 500
    assert 'Something went wrong. Please try again.' in resp.data.decode()
    assert 'csrf-token' in resp.data.decode()  # the full base.html layout


def test_500_page_with_the_database_down(client, boom, monkeypatch):
    import helpers

    def db_down(*_a, **_k):
        raise OperationalError('SELECT', {}, Exception('gone'))

    monkeypatch.setattr(helpers.db.session, 'execute', db_down)
    resp = client.get('/')
    html = resp.data.decode()
    assert resp.status_code == 500
    assert '<html lang="de">' in html and 'Etwas ist schiefgelaufen.' in html


def test_csrf_error_redirects_back_with_a_message(app, make_user, monkeypatch):
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
    with app.app_context():
        user = make_user()
        c = app.test_client()
        resp = c.post(f'/user/{user.id}/toggle-active', headers={'Referer': f'http://localhost/user/{user.id}'})
        assert resp.status_code == 302 and resp.location.endswith(f'/user/{user.id}')
        assert 'The form has expired. Please submit it again.' in c.get(resp.location).data.decode()
        assert user.is_active


def test_csrf_error_answers_fetch_with_json(app, monkeypatch):
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
    resp = app.test_client().post('/backups/upload-chunk', headers={'X-CSRFToken': 'stale'})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'The form has expired. Please reload the page.'}
