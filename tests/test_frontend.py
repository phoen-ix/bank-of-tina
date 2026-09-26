"""Rendered-page regressions: script injection, offline page, settings tabs, localized labels."""
import re
from datetime import datetime
from decimal import Decimal


def _scripts(html):
    return re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.S)


def test_user_names_never_reach_javascript(client, app, make_user):
    """A name was pasted into a JS template literal, so `${...}` ran as code."""
    name = 'Zqx`${alert(1)}`</option>'
    with app.app_context():
        make_user(name=name)
        html = client.get('/transaction/add').data.decode()
        assert all('Zqx' not in script for script in _scripts(html))
        assert 'Zqx`${alert(1)}`&lt;/option&gt;' in html   # escaped, inside the <template>


def test_edit_form_items_are_json_encoded(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import ExpenseItem, Transaction
        buyer, debtor = make_user(), make_user()
        tx = Transaction(description='x', amount=Decimal('2'), from_user_id=debtor.id, to_user_id=buyer.id,
                         transaction_type='expense', date=datetime(2026, 1, 1))
        db.session.add(tx)
        db.session.add(ExpenseItem(transaction=tx, item_name='a"b</script>', price=Decimal('2'), buyer_id=buyer.id))
        db.session.commit()
        html = client.get(f'/transaction/{tx.id}/edit').data.decode()
        assert 'a"b</script>' not in html
        assert '"a\\"b\\u003c/script\\u003e"' in html


def test_currency_symbol_not_injected_as_html(client, app):
    with app.app_context():
        from helpers import set_setting
        set_setting('currency_symbol', '<img src=x>')
        for page in ('/transaction/add', '/settings', '/analytics'):
            assert '<img src=x>' not in client.get(page).data.decode(), page


def test_offline_page_is_translated_and_script_free(client, app):
    with app.app_context():
        from helpers import set_setting
        set_setting('language', 'de')
        html = client.get('/offline').data.decode()
    assert '<html lang="de">' in html
    assert 'onclick' not in html and '<script' not in html
    assert 'href="/"' in html


def test_service_worker_only_handles_navigations(client):
    js = client.get('/sw.js').data.decode()
    assert "e.request.mode !== 'navigate'" in js
    assert "'/offline'" in js
    assert '!response.ok' not in js


def test_settings_general_tab_active_without_js(client, app):
    html = client.get('/settings').data.decode()
    assert 'class="tab-pane fade show active" id="tab-general"' in html
    assert html.count('show active') == 1


def test_settings_js_strings_are_json_encoded(client, app):
    html = client.get('/settings').data.decode()
    script = _scripts(html)[-1]
    assert "confirm('" not in script
    assert "alert('" not in script


def test_analytics_volume_labels_follow_locale(client, app, make_user):
    from flask import g
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from models import Transaction
        user = make_user()
        db.session.add(Transaction(description='x', amount=Decimal('1'), to_user_id=user.id,
                                   transaction_type='deposit', date=datetime(2026, 3, 4, 12)))
        db.session.commit()
        set_setting('language', 'de')
        if hasattr(g, '_flask_babel') and hasattr(g._flask_babel, 'babel_locale'):
            del g._flask_babel.babel_locale
        data = client.get(f'/analytics/data?date_from=2026-03-01&date_to=2026-03-20&users={user.id}').get_json()
        assert data['transaction_volume']['labels'] == ['2 März']
