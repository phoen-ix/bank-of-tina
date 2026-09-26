"""Regression tests for balance integrity, amount handling and timezone handling."""
import io
import json
import os
from datetime import date, datetime
from decimal import Decimal


def _balance(user_id):
    from extensions import db
    from models import User
    db.session.expire_all()
    return Decimal(str(db.session.get(User, user_id).balance))


def _expense(client, buyer, items, **extra):
    data = {'transaction_type': 'expense', 'buyer_id': str(buyer.id), 'description': 'Lunch',
            'date': '', 'items_json': json.dumps(items), **extra}
    return client.post('/transaction/add', data=data, content_type='multipart/form-data')


def test_expense_with_bad_price_changes_nothing(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import Transaction
        buyer, a, b = make_user(), make_user(), make_user()
        response = _expense(client, buyer, [
            {'name': 'Soup', 'price': '4.00', 'debtor_id': str(a.id)},
            {'name': 'Pie', 'price': 'abc', 'debtor_id': str(b.id)},
        ])
        assert response.status_code == 302
        assert db.session.execute(db.select(Transaction)).first() is None
        assert _balance(buyer.id) == _balance(a.id) == Decimal('0')


def test_expense_owed_by_nobody_is_rejected(client, app, make_user, backup_dir):
    with app.app_context():
        from extensions import db
        from models import Transaction
        buyer = make_user()
        response = _expense(client, buyer, [{'name': 'Soup', 'price': '4', 'debtor_id': str(buyer.id)}],
                            receipt=(io.BytesIO(b'%PDF'), 'r.pdf'))
        assert response.status_code == 302
        assert db.session.execute(db.select(Transaction)).first() is None
        assert os.listdir(app.config['UPLOAD_FOLDER']) == []


def test_expense_rejects_unknown_debtor_and_bad_json(client, app, make_user):
    with app.app_context():
        buyer = make_user()
        assert _expense(client, buyer, [{'name': 'X', 'price': '1', 'debtor_id': '999'}]).status_code == 302
        response = client.post('/transaction/add', data={
            'transaction_type': 'expense', 'buyer_id': str(buyer.id), 'items_json': '{nope'})
        assert response.status_code == 302


def test_deposit_input_errors_do_not_500(client, app, make_user):
    with app.app_context():
        user = make_user()
        for data in ({'user_id': ''}, {'user_id': 'x'}, {'user_id': '999'},
                     {'user_id': str(user.id), 'amount': 'NaN'},
                     {'user_id': str(user.id), 'amount': '-5'},
                     {'user_id': str(user.id), 'amount': '1e9'}):
            response = client.post('/transaction/add', data={'transaction_type': 'deposit', 'amount': '5', **data})
            assert response.status_code == 302, data
        assert _balance(user.id) == Decimal('0')


def test_amount_rounding_does_not_drift(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import Transaction
        user = make_user()
        client.post('/transaction/add', data={'transaction_type': 'deposit', 'user_id': str(user.id),
                                              'amount': '1.005', 'date': ''})
        assert _balance(user.id) == Decimal('1.01')
        tx = db.session.execute(db.select(Transaction)).scalar()
        client.post(f'/transaction/{tx.id}/delete')
        assert _balance(user.id) == Decimal('0')


def test_adjust_balance_is_atomic_sql(app, make_user):
    """The update happens in SQL, so a stale in-memory value can't be written back."""
    with app.app_context():
        from extensions import db
        from helpers import adjust_balance
        user = make_user(balance=Decimal('10'))
        adjust_balance(user.id, Decimal('2.50'))
        adjust_balance(user.id, Decimal('-1.25'))
        db.session.commit()
        assert _balance(user.id) == Decimal('11.25')


def test_edit_form_round_trips_local_time(client, app, make_user):
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from models import Transaction
        set_setting('timezone', 'Europe/Vienna')
        user = make_user()
        client.post('/transaction/add', data={'transaction_type': 'deposit', 'user_id': str(user.id),
                                              'amount': '5', 'date': '2026-03-10T09:30'})
        tx = db.session.execute(db.select(Transaction)).scalar()
        assert tx.date == datetime(2026, 3, 10, 8, 30)  # stored as UTC

        page = client.get(f'/transaction/{tx.id}/edit').data
        assert b'value="2026-03-10T09:30"' in page

        response = client.post(f'/transaction/{tx.id}/edit', data={
            'description': 'x', 'amount': '5', 'date': '2026-03-10T09:30',
            'to_user_id': str(user.id), 'items_json': '[]'})
        assert response.headers['Location'].endswith('/transactions?year=2026&month=3')
        db.session.expire_all()
        assert db.session.get(Transaction, tx.id).date == datetime(2026, 3, 10, 8, 30)


def _make_expense_tx(make_user, client):
    from extensions import db
    from models import Transaction
    buyer, debtor = make_user(), make_user()
    _expense(client, buyer, [{'name': 'Soup', 'price': '4', 'debtor_id': str(debtor.id)},
                             {'name': 'Tea', 'price': '2', 'debtor_id': str(debtor.id)}])
    return buyer, debtor, db.session.execute(db.select(Transaction)).scalar()


def test_edit_with_bad_item_keeps_everything(client, app, make_user):
    with app.app_context():
        buyer, debtor, tx = _make_expense_tx(make_user, client)
        response = client.post(f'/transaction/{tx.id}/edit', data={
            'description': 'Lunch', 'amount': '6', 'from_user_id': str(debtor.id), 'to_user_id': str(buyer.id),
            'items_json': json.dumps([{'name': 'Soup', 'price': 'oops'}])})
        assert response.headers['Location'].endswith(f'/transaction/{tx.id}/edit')
        assert len(tx.items) == 2
        assert _balance(debtor.id) == Decimal('-6.00')


def test_edit_blank_items_json_keeps_items(client, app, make_user):
    with app.app_context():
        from extensions import db
        buyer, debtor, tx = _make_expense_tx(make_user, client)
        form = {'description': 'Lunch', 'amount': '6', 'from_user_id': str(debtor.id),
                'to_user_id': str(buyer.id)}
        client.post(f'/transaction/{tx.id}/edit', data={**form, 'items_json': ''})
        db.session.expire_all()
        assert len(tx.items) == 2

        client.post(f'/transaction/{tx.id}/edit', data={**form, 'amount': '3', 'items_json': '[]'})
        db.session.expire_all()
        assert tx.items == []
        assert _balance(debtor.id) == Decimal('-3.00')
        assert _balance(buyer.id) == Decimal('3.00')


def test_edit_moves_balance_between_users(client, app, make_user):
    with app.app_context():
        buyer, debtor, tx = _make_expense_tx(make_user, client)
        other = make_user()
        client.post(f'/transaction/{tx.id}/edit', data={
            'description': 'Lunch', 'amount': '6', 'from_user_id': str(other.id),
            'to_user_id': str(buyer.id), 'items_json': json.dumps([{'name': 'Soup', 'price': '5'}])})
        assert _balance(debtor.id) == Decimal('0')
        assert _balance(other.id) == Decimal('-5.00')
        assert _balance(buyer.id) == Decimal('5.00')


def test_shared_receipt_survives_until_last_delete(client, app, make_user, backup_dir):
    with app.app_context():
        from extensions import db
        from models import Transaction
        buyer, a, b = make_user(), make_user(), make_user()
        _expense(client, buyer, [{'name': 'Soup', 'price': '4', 'debtor_id': str(a.id)},
                                 {'name': 'Tea', 'price': '2', 'debtor_id': str(b.id)}],
                 receipt=(io.BytesIO(b'%PDF'), 'bill.pdf'))
        txs = db.session.execute(db.select(Transaction)).scalars().all()
        assert len(txs) == 2 and txs[0].receipt_path == txs[1].receipt_path
        path = os.path.join(app.config['UPLOAD_FOLDER'], txs[0].receipt_path)
        ids = [t.id for t in txs]

        client.post(f'/transaction/{ids[0]}/delete')
        assert os.path.exists(path)
        client.post(f'/transaction/{ids[1]}/delete')
        assert not os.path.exists(path)
        assert _balance(buyer.id) == _balance(a.id) == _balance(b.id) == Decimal('0')


def test_receipts_with_same_name_do_not_overwrite(app, backup_dir):
    from werkzeug.datastructures import FileStorage
    with app.app_context():
        from helpers import save_receipt
        first = save_receipt(FileStorage(io.BytesIO(b'one'), filename='scan.pdf'), 'Tina')
        second = save_receipt(FileStorage(io.BytesIO(b'two'), filename='scan.pdf'), 'Tina')
        assert first != second
        assert first.endswith('.pdf') and os.path.basename(first).startswith('Tina_scan_')
        with open(os.path.join(app.config['UPLOAD_FOLDER'], first), 'rb') as f:
            assert f.read() == b'one'


def test_receipt_with_unsupported_type_is_rejected(client, app, make_user):
    with app.app_context():
        buyer, debtor = make_user(), make_user()
        response = _expense(client, buyer, [{'name': 'Soup', 'price': '4', 'debtor_id': str(debtor.id)}],
                            receipt=(io.BytesIO(b'x'), 'photo.heic'))
        assert response.headers['Location'].endswith('/transaction/add')
        assert _balance(debtor.id) == Decimal('0')


def test_month_view_uses_local_month(client, app, make_user):
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from models import Transaction
        set_setting('timezone', 'Europe/Vienna')
        user = make_user()
        # 23:30 UTC on Feb 28 is 00:30 on March 1 in Vienna.
        db.session.add(Transaction(description='Boundary', amount=Decimal('1'), to_user_id=user.id,
                                   transaction_type='deposit', date=datetime(2026, 2, 28, 23, 30)))
        db.session.commit()
        assert b'Boundary' in client.get('/transactions?year=2026&month=3').data
        assert b'Boundary' not in client.get('/transactions?year=2026&month=2').data
        assert client.get('/transactions?year=abc&month=zz').status_code == 200


def test_search_dates_are_local_days(client, app, make_user):
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from models import Transaction
        set_setting('timezone', 'Europe/Vienna')
        user = make_user()
        db.session.add(Transaction(description='LateNight', amount=Decimal('1'), to_user_id=user.id,
                                   transaction_type='deposit', date=datetime(2026, 2, 28, 23, 30)))
        db.session.commit()
        assert b'LateNight' in client.get('/search?date_from=2026-03-01&date_to=2026-03-01').data
        assert b'LateNight' not in client.get('/search?date_from=2026-02-28&date_to=2026-02-28').data


def test_local_month_bounds(app):
    with app.app_context():
        from helpers import set_setting, local_month_utc
        set_setting('timezone', 'Europe/Vienna')
        start, end = local_month_utc(2026, 3)
        assert start == datetime(2026, 2, 28, 23, 0)   # CET, UTC+1
        assert end == datetime(2026, 3, 31, 22, 0)     # CEST, UTC+2
        start, end = local_month_utc(2026, 12)
        assert end == datetime(2026, 12, 31, 23, 0)


def test_transactions_page_totals_per_type(client, app, make_user):
    with app.app_context():
        user = make_user()
        today = date.today()
        for tx_type, amount in (('deposit', '10'), ('withdrawal', '3')):
            client.post('/transaction/add', data={'transaction_type': tx_type, 'user_id': str(user.id),
                                                  'amount': amount, 'date': ''})
        page = client.get(f'/transactions?year={today.year}&month={today.month}').data.decode()
        assert 'Deposit: €10.00' in page
        assert 'Withdrawal: €3.00' in page


def test_default_theme_is_detected_and_presets_persist(client, app):
    with app.app_context():
        from config import THEMES
        from extensions import db
        from helpers import detect_theme
        from models import Setting
        assert detect_theme() == 'default'

        classic = {k: v for k, v in THEMES['classic'].items() if k.startswith('color_')}
        client.post('/settings/templates', data=classic)
        assert detect_theme() == 'classic'
        assert db.session.get(Setting, 'color_navbar').value == '#0d6efd'


def test_templates_store_only_customizations(client, app):
    with app.app_context():
        from config import TEMPLATE_DEFAULTS
        from extensions import db
        from helpers import get_tpl
        from models import Setting
        form = {k: v for k, v in TEMPLATE_DEFAULTS.items() if k.startswith('tpl_')}
        form['tpl_email_greeting'] = 'Yo [Name]'
        client.post('/settings/templates', data=form)
        assert db.session.get(Setting, 'tpl_email_subject_en') is None
        assert db.session.get(Setting, 'tpl_email_greeting_en').value == 'Yo [Name]'

        client.post('/settings/templates/reset')
        assert db.session.get(Setting, 'tpl_email_greeting_en') is None
        assert get_tpl('tpl_email_greeting') == TEMPLATE_DEFAULTS['tpl_email_greeting']
