"""Input validation and robustness regressions (no 500s, no unbootable settings)."""
from decimal import Decimal

import pytest


@pytest.fixture
def no_jobs(app):
    """The global scheduler; clean_db removes the jobs a test added."""
    from extensions import scheduler
    return scheduler


def test_invalid_schedule_day_is_not_stored(client, app, no_jobs):
    with app.app_context():
        from helpers import get_setting
        for url, field, default in (('/settings/schedule', 'schedule_day', 'mon'),
                                    ('/settings/common-auto', 'common_auto_day', '*'),
                                    ('/settings/backup', 'backup_day', '*')):
            response = client.post(url, data={field: 'someday', field.replace('_day', '_enabled'): '1'})
            assert response.status_code == 302
            assert get_setting(field) == default


def test_broken_schedule_settings_do_not_block_startup(app, no_jobs):
    with app.app_context():
        from helpers import set_setting
        from scheduler_jobs import _restore_schedule
        set_setting('schedule_enabled', '1')
        set_setting('schedule_day', 'someday')
        set_setting('backup_enabled', '1')
        _restore_schedule(app)  # must not raise
        assert no_jobs.get_job('email_job') is None
        assert no_jobs.get_job('backup_job') is not None


def test_timezone_change_reschedules_backup_job(client, app, no_jobs):
    with app.app_context():
        from helpers import set_setting
        from scheduler_jobs import _add_backup_job
        set_setting('backup_enabled', '1')
        _add_backup_job(app)
        client.post('/settings/general', data={'timezone': 'Asia/Tokyo', 'language': 'en'})
        assert str(no_jobs.get_job('backup_job').trigger.timezone) == 'Asia/Tokyo'


def test_smtp_port_must_be_numeric(client, app):
    with app.app_context():
        from helpers import get_setting
        client.post('/settings/email', data={'smtp_port': 'abc', 'smtp_server': 'mail.example'})
        assert get_setting('smtp_port') is None
        assert get_setting('smtp_server') is None
        client.post('/settings/email', data={'smtp_port': '465', 'smtp_server': 'mail.example'})
        assert get_setting('smtp_port') == '465'


def test_currency_symbol_whitelist(client, app):
    with app.app_context():
        from helpers import get_setting, set_setting
        set_setting('currency_symbol', '£')
        client.post('/settings/general', data={'currency_symbol': '<b>x</b>', 'language': 'en'})
        assert get_setting('currency_symbol') == '£'
        client.post('/settings/general', data={'currency_symbol': 'R$', 'language': 'en'})
        assert get_setting('currency_symbol') == 'R$'


def test_unknown_stored_currency_stays_selected(client, app):
    with app.app_context():
        from helpers import set_setting
        set_setting('currency_symbol', 'CHF')
        page = client.get('/settings').data.decode()
        assert '<option value="CHF" selected>' in page


@pytest.mark.parametrize('name, email', [
    ('alice', 'new@example.com'),        # name differs only by case
    ('Someone', 'ALICE@example.com'),    # email differs only by case
    ('Bob', 'not-an-email'),
    ('B' * 101, 'b@example.com'),
    ('   ', 'b@example.com'),
])
def test_add_user_rejects_bad_input(client, app, make_user, name, email):
    with app.app_context():
        from extensions import db
        from models import User
        make_user(name='Alice', email='alice@example.com')
        response = client.post('/user/add', data={'name': name, 'email': email})
        assert response.status_code == 302
        assert db.session.execute(db.select(db.func.count(User.id))).scalar() == 1


def test_add_user_strips_name(client, app):
    with app.app_context():
        from extensions import db
        from models import User
        client.post('/user/add', data={'name': '  Dana  ', 'email': ' dana@example.com '})
        user = db.session.execute(db.select(User)).scalar()
        assert (user.name, user.email) == ('Dana', 'dana@example.com')


def test_edit_user_rejects_duplicate_email_case_insensitive(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import User
        make_user(name='Alice', email='alice@example.com')
        bob = make_user(name='Bob', email='bob@example.com')
        client.post(f'/user/{bob.id}/edit', data={'name': 'Bob', 'email': 'Alice@Example.com',
                                                  'created_at': '2026-01-01'})
        db.session.expire_all()
        assert db.session.get(User, bob.id).email == 'bob@example.com'


def test_common_price_requires_positive_value(client, app):
    with app.app_context():
        from extensions import db
        from models import CommonPrice
        for value in ('', 'abc', '0'):
            assert client.post('/settings/common-prices/add', data={'value': value}).status_code == 302
        assert db.session.execute(db.select(CommonPrice)).first() is None
        client.post('/settings/common-prices/add', data={'value': '2,5'})
        assert db.session.execute(db.select(CommonPrice.value)).scalar() == Decimal('2.50')


def test_price_blacklist_is_normalized_and_matches(client, app, make_user):
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from models import CommonBlacklist, CommonPrice, ExpenseItem, Transaction
        from scheduler_jobs import auto_collect_common

        client.post('/settings/common-blacklist/add', data={'type': 'price', 'value': '3,5'})
        assert db.session.execute(db.select(CommonBlacklist.value)).scalar() == '3.50'
        db.session.add(CommonBlacklist(type='price', value='4,00'))  # stored by an older version

        user = make_user()
        for price in ('3.50', '4.00', '5.00'):
            tx = Transaction(description='x', amount=Decimal(price), from_user_id=user.id,
                             transaction_type='expense')
            db.session.add(tx)
            db.session.add(ExpenseItem(transaction=tx, item_name='x', price=Decimal(price), buyer_id=user.id))
        db.session.commit()
        set_setting('common_prices_auto', '1')
        set_setting('common_prices_threshold', '1')

        auto_collect_common()
        prices = {Decimal(str(p)) for p in db.session.execute(db.select(CommonPrice.value)).scalars()}
        assert prices == {Decimal('5.00')}


def test_log_messages_are_clipped_to_column_length(app):
    with app.app_context():
        from models import AutoCollectLog, BackupLog, EmailLog
        log = EmailLog(level='FAIL', recipient='r' * 300, message='m' * 900)
        assert len(log.recipient) == 200 and len(log.message) == 500
        assert len(BackupLog(level='ERROR', message='m' * 900).message) == 500
        assert len(AutoCollectLog(level='SKIP', category='item', message='m' * 900).message) == 500


def test_prune_log_keeps_newest(app):
    with app.app_context():
        from extensions import db
        from helpers import prune_log
        from models import BackupLog
        for i in range(5):
            db.session.add(BackupLog(level='INFO', message=str(i)))
        db.session.commit()
        prune_log(BackupLog, keep=3)
        db.session.commit()
        assert db.session.execute(db.select(BackupLog.message).order_by(BackupLog.id)).scalars().all() == ['2', '3', '4']


def test_inactive_site_admin_stays_selected(client, app, make_user):
    with app.app_context():
        from helpers import set_setting
        admin = make_user(name='Tina', is_active=False)
        set_setting('site_admin_id', str(admin.id))
        page = client.get('/settings').data.decode()
        assert f'<option value="{admin.id}" selected>' in page
