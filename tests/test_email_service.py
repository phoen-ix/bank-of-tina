from decimal import Decimal


def test_build_email_html_with_user(app, make_user):
    with app.app_context():
        user = make_user(name='EmailUser', email='emailuser@test.com',
                         balance=Decimal('42.00'))
        from email_service import build_email_html
        html = build_email_html(user)
        assert 'EmailUser' in html
        assert 'Bank of Tina' in html
        assert '42' in html


def test_build_admin_summary_email(app, make_user):
    with app.app_context():
        u1 = make_user(name='Admin1', email='admin1@test.com', balance=Decimal('10'))
        u2 = make_user(name='Admin2', email='admin2@test.com', balance=Decimal('-5'))
        from email_service import build_admin_summary_email
        html = build_admin_summary_email([u1, u2], include_emails=True)
        assert 'Admin1' in html
        assert 'Admin2' in html
        assert 'admin1@test.com' in html


def test_send_single_email_no_smtp(app):
    """Without SMTP credentials, send_single_email returns (False, ...)."""
    with app.app_context():
        from email_service import send_single_email
        ok, err = send_single_email('test@example.com', 'Test', 'Subject', '<p>body</p>')
        assert ok is False
        assert 'SMTP' in err or 'credentials' in err.lower() or err is not None


def test_build_backup_status_email(app):
    with app.app_context():
        from backup_service import build_backup_status_email
        html = build_backup_status_email(True, 'bot_backup_2024_01_01.tar.gz', 5, 1)
        assert 'Backup completed successfully' in html
        assert 'bot_backup_2024_01_01.tar.gz' in html
        assert '5' in html

        html_fail = build_backup_status_email(False, 'mysqldump failed', 0, 0)
        assert 'Backup failed' in html_fail
