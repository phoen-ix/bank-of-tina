"""Tests for internationalization (i18n) support."""
from helpers import set_setting, get_setting


def test_language_setting_controls_locale(app, client, clean_db):
    """Verify that changing language setting changes active locale."""
    with app.app_context():
        set_setting('language', 'de')
        assert get_setting('language') == 'de'
        set_setting('language', 'en')
        assert get_setting('language') == 'en'


def test_language_selector_on_settings_page(app, client, clean_db):
    """Verify language dropdown renders on the settings page."""
    resp = client.get('/settings')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'name="language"' in html
    assert 'Deutsch' in html
    assert 'English' in html


def test_flash_messages_translate_german(app, client, clean_db):
    """Verify flash messages appear in German when language is de."""
    with app.app_context():
        set_setting('language', 'de')
    resp = client.post('/user/add', data={'name': '', 'email': ''},
                       follow_redirects=True)
    html = resp.data.decode()
    # Should contain the German translation
    assert 'Name und E-Mail sind erforderlich!' in html


def test_flash_messages_english(app, client, clean_db):
    """Verify flash messages appear in English when language is en."""
    with app.app_context():
        set_setting('language', 'en')
    resp = client.post('/user/add', data={'name': '', 'email': ''},
                       follow_redirects=True)
    html = resp.data.decode()
    assert 'Name and email are required!' in html


def test_tx_type_filter_translates(app, client, clean_db):
    """Verify the tx_type filter translates transaction types."""
    from flask import g

    # Create a user and deposit via routes
    client.post('/user/add', data={'name': 'TestUser', 'email': 't@x.com'})
    client.post('/transaction/add', data={
        'transaction_type': 'deposit',
        'user_id': '1', 'amount': '50', 'description': 'Test dep',
    }, follow_redirects=True)

    # English mode — badge should show 'deposit'
    resp = client.get('/')
    html = resp.data.decode()
    assert 'deposit' in html

    # Switch to German via settings POST
    client.post('/settings/general', data={
        'language': 'de', 'default_item_rows': '3',
        'recent_transactions_count': '5', 'timezone': 'UTC',
        'decimal_separator': '.', 'currency_symbol': '€',
    })
    # Clear Babel's cached locale on the fixture's g so next request re-evaluates
    if hasattr(g, '_flask_babel') and hasattr(g._flask_babel, 'babel_locale'):
        del g._flask_babel.babel_locale

    resp = client.get('/')
    html = resp.data.decode()
    assert 'Einzahlung' in html


def test_language_post_saves_setting(app, client, clean_db):
    """Verify POST to settings/general saves the language setting."""
    resp = client.post('/settings/general', data={
        'language': 'en',
        'default_item_rows': '3',
        'recent_transactions_count': '5',
        'timezone': 'UTC',
        'decimal_separator': '.',
        'currency_symbol': '€',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert get_setting('language') == 'en'


def test_html_lang_attribute(app, client, clean_db):
    """Verify <html lang> attribute reflects the current locale."""
    with app.app_context():
        set_setting('language', 'de')
    resp = client.get('/')
    assert b'<html lang="de">' in resp.data

    with app.app_context():
        set_setting('language', 'en')
    resp = client.get('/')
    assert b'<html lang="en">' in resp.data
