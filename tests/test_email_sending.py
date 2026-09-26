"""SMTP sending: TLS modes, certificate verification, headers, batching, escaping."""
import smtplib
import ssl
from datetime import datetime
from decimal import Decimal
from email.utils import getaddresses

import pytest


class FakeSMTP:
    instances = []
    fail_connect = None          # exception raised by the constructor
    disconnect_on_send = []      # send_message call numbers that raise SMTPServerDisconnected
    sends = 0

    def __init__(self, host, port, timeout=None, context=None):
        if FakeSMTP.fail_connect:
            raise FakeSMTP.fail_connect
        self.host, self.port, self.context = host, port, context
        self.starttls_context = None
        self.logged_in = None
        self.messages = []
        self.quit_called = False
        FakeSMTP.instances.append(self)

    def starttls(self, context=None):
        self.starttls_context = context

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        FakeSMTP.sends += 1
        if FakeSMTP.sends in FakeSMTP.disconnect_on_send:
            raise smtplib.SMTPServerDisconnected('gone')
        self.messages.append(msg)

    def quit(self):
        self.quit_called = True

    def close(self):
        pass


class FakeSMTPSSL(FakeSMTP):
    pass


@pytest.fixture
def smtp(app, monkeypatch):
    import email_service
    FakeSMTP.instances = []
    FakeSMTP.fail_connect = None
    FakeSMTP.disconnect_on_send = []
    FakeSMTP.sends = 0
    monkeypatch.setattr(email_service.smtplib, 'SMTP', FakeSMTP)
    monkeypatch.setattr(email_service.smtplib, 'SMTP_SSL', FakeSMTPSSL)
    with app.app_context():
        from helpers import set_setting
        for key, value in {'smtp_server': 'mail.example', 'smtp_port': '587', 'smtp_username': 'bot',
                           'smtp_password': 'pw', 'from_email': 'bot@example.com'}.items():
            set_setting(key, value)
    return FakeSMTP


def _assert_verifying(context):
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_starttls_verifies_certificate(app, smtp):
    with app.app_context():
        from email_service import send_single_email
        ok, err = send_single_email('a@example.com', 'A', 'Hi', '<p>x</p>')
        assert ok, err
        server = smtp.instances[0]
        assert type(server) is FakeSMTP
        _assert_verifying(server.starttls_context)
        assert server.logged_in == ('bot', 'pw')
        assert server.quit_called


def test_ssl_mode_uses_implicit_tls(app, smtp):
    with app.app_context():
        from helpers import set_setting
        from email_service import send_single_email
        set_setting('smtp_security', 'ssl')
        set_setting('smtp_port', '465')
        assert send_single_email('a@example.com', 'A', 'Hi', '<p>x</p>')[0]
        server = smtp.instances[0]
        assert type(server) is FakeSMTPSSL and server.port == 465
        _assert_verifying(server.context)
        assert server.starttls_context is None


def test_none_mode_skips_tls(app, smtp):
    with app.app_context():
        from helpers import set_setting
        from email_service import send_single_email
        set_setting('smtp_security', 'none')
        assert send_single_email('a@example.com', 'A', 'Hi', '<p>x</p>')[0]
        assert smtp.instances[0].starttls_context is None


def test_headers_are_well_formed(app, smtp):
    with app.app_context():
        from email_service import send_single_email
        send_single_email('john@example.com', 'Doe, John', 'Line1\nLine2', '<p>x</p>')
        msg = smtp.instances[0].messages[0]
        assert getaddresses([msg['To']]) == [('Doe, John', 'john@example.com')]
        assert msg['Date'] and msg['Message-ID'].endswith('@example.com>')
        assert '\n' not in msg['Subject']
        send_single_email('j@example.com', 'Jörg', 'Hi', '<p>x</p>')
        assert '=?utf-8?' in smtp.instances[1].messages[0]['To']


def test_batch_uses_one_connection(app, smtp, make_user):
    with app.app_context():
        from email_service import send_all_emails
        for _ in range(3):
            make_user()
        success, fail, errors = send_all_emails()
        assert (success, fail, errors) == (3, 0, [])
        assert len(smtp.instances) == 1
        assert len(smtp.instances[0].messages) == 3


def test_reconnects_once_after_disconnect(app, smtp, make_user):
    with app.app_context():
        from email_service import send_all_emails
        for _ in range(2):
            make_user()
        smtp.disconnect_on_send = [2]
        success, fail, _ = send_all_emails()
        assert (success, fail) == (2, 0)
        assert len(smtp.instances) == 2


def test_connection_failure_fails_fast_and_is_logged(app, smtp, make_user):
    with app.app_context():
        from extensions import db
        from email_service import send_all_emails
        from models import EmailLog
        for _ in range(3):
            make_user()
        smtp.fail_connect = ssl.SSLCertVerificationError('certificate verify failed')
        success, fail, errors = send_all_emails()
        assert (success, fail) == (0, 3)
        assert all('certificate verify failed' in e for e in errors)
        # debug is off, but failures are still recorded
        levels = db.session.execute(db.select(EmailLog.level)).scalars().all()
        assert levels == ['FAIL', 'FAIL', 'FAIL']


def test_admin_summary_failure_is_reported(app, smtp, make_user, monkeypatch):
    with app.app_context():
        from email_service import Mailer, send_all_emails
        from helpers import set_setting
        admin = make_user(name='Tina', email_opt_in=False)
        make_user()
        set_setting('site_admin_id', str(admin.id))
        set_setting('admin_summary_email', '1')
        original = Mailer.send

        def send(self, to_email, *args):
            if to_email == admin.email:
                return False, 'mailbox full'
            return original(self, to_email, *args)
        monkeypatch.setattr(Mailer, 'send', send)

        success, fail, errors = send_all_emails()
        assert success == 1
        assert any('mailbox full' in e for e in errors)


def test_invalid_security_setting_is_refused(app, smtp):
    with app.app_context():
        from helpers import set_setting
        from email_service import send_single_email
        set_setting('smtp_security', 'sometimes')
        ok, err = send_single_email('a@example.com', 'A', 'Hi', '<p>x</p>')
        assert not ok and smtp.instances == []


def test_email_settings_store_security_mode(client, app):
    with app.app_context():
        from helpers import get_setting
        client.post('/settings/email', data={'smtp_port': '465', 'smtp_security': 'ssl'})
        assert get_setting('smtp_security') == 'ssl'
        client.post('/settings/email', data={'smtp_port': '465', 'smtp_security': 'bogus'})
        assert get_setting('smtp_security') == 'starttls'


def test_email_body_escapes_user_values(app, make_user):
    with app.app_context():
        from helpers import set_setting
        from email_service import build_email_html
        set_setting('currency_symbol', '<i>')
        user = make_user(name='<b>Eve</b>', balance=Decimal('3'))
        body = build_email_html(user)
        assert '<b>Eve</b>' not in body and '&lt;b&gt;Eve&lt;/b&gt;' in body
        assert '<i>' not in body


def test_email_transaction_dates_are_local(app, make_user):
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from email_service import build_email_html
        from models import Transaction
        set_setting('timezone', 'Europe/Vienna')
        user = make_user()
        db.session.add(Transaction(description='Late', amount=Decimal('1'), to_user_id=user.id,
                                   transaction_type='deposit', date=datetime(2026, 2, 28, 23, 30)))
        db.session.commit()
        assert '2026-03-01' in build_email_html(user)


def test_backup_status_mail_failure_is_logged(app, smtp, make_user, monkeypatch):
    import scheduler_jobs
    from extensions import scheduler
    monkeypatch.setattr(scheduler_jobs, 'run_backup', lambda: (True, 'bot_backup_x.tar.gz'))
    monkeypatch.setattr(scheduler_jobs, '_list_backups', lambda: [])
    monkeypatch.setattr(scheduler_jobs, 'send_single_email', lambda *a: (False, 'boom'))
    with app.app_context():
        from extensions import db
        from helpers import set_setting
        from models import BackupLog
        admin = make_user()
        set_setting('site_admin_id', str(admin.id))
        set_setting('backup_admin_email', '1')
        set_setting('backup_keep', '0')
        scheduler_jobs._add_backup_job(app)
        try:
            scheduler.get_job('backup_job').func()
        finally:
            scheduler.remove_all_jobs()
        db.session.expire_all()
        messages = db.session.execute(db.select(BackupLog.message)).scalars().all()
        assert any('boom' in m for m in messages)
