from decimal import Decimal


def test_settings_page_loads(client, app):
    response = client.get('/settings')
    assert response.status_code == 200
    assert b'Settings' in response.data or b'settings' in response.data


def test_general_update(client, app):
    with app.app_context():
        response = client.post('/settings/general', data={
            'default_item_rows': '5',
            'recent_transactions_count': '10',
            'timezone': 'UTC',
            'decimal_separator': ',',
            'currency_symbol': '$',
        }, follow_redirects=True)
        assert response.status_code == 200

        from helpers import get_setting
        assert get_setting('decimal_separator') == ','
        assert get_setting('currency_symbol') == '$'
        assert get_setting('default_item_rows') == '5'
        assert get_setting('recent_transactions_count') == '10'


def test_email_update(client, app):
    with app.app_context():
        response = client.post('/settings/email', data={
            'smtp_server': 'smtp.test.com',
            'smtp_port': '465',
            'smtp_username': 'user@test.com',
            'from_email': 'from@test.com',
            'from_name': 'Test Bank',
            'email_enabled': '1',
        }, follow_redirects=True)
        assert response.status_code == 200

        from helpers import get_setting
        assert get_setting('smtp_server') == 'smtp.test.com'
        assert get_setting('smtp_port') == '465'


def test_common_item_add_delete(client, app):
    with app.app_context():
        response = client.post('/settings/common-items/add', data={
            'name': 'TestItem',
        }, follow_redirects=True)
        assert response.status_code == 200

        from models import CommonItem
        item = CommonItem.query.filter_by(name='TestItem').first()
        assert item is not None

        response = client.post(f'/settings/common-items/{item.id}/delete',
                               follow_redirects=True)
        assert response.status_code == 200
        assert CommonItem.query.filter_by(name='TestItem').first() is None


def test_common_description_add_delete(client, app):
    with app.app_context():
        response = client.post('/settings/common-descriptions/add', data={
            'value': 'Weekly Lunch',
        }, follow_redirects=True)
        assert response.status_code == 200

        from models import CommonDescription
        item = CommonDescription.query.filter_by(value='Weekly Lunch').first()
        assert item is not None

        response = client.post(f'/settings/common-descriptions/{item.id}/delete',
                               follow_redirects=True)
        assert response.status_code == 200
        assert CommonDescription.query.filter_by(value='Weekly Lunch').first() is None


def test_common_price_add_delete(client, app):
    with app.app_context():
        response = client.post('/settings/common-prices/add', data={
            'value': '12.50',
        }, follow_redirects=True)
        assert response.status_code == 200

        from models import CommonPrice
        item = CommonPrice.query.filter_by(value=Decimal('12.50')).first()
        assert item is not None

        response = client.post(f'/settings/common-prices/{item.id}/delete',
                               follow_redirects=True)
        assert response.status_code == 200


def test_common_blacklist_add_delete(client, app):
    with app.app_context():
        response = client.post('/settings/common-blacklist/add', data={
            'type': 'item',
            'value': 'BadItem',
        }, follow_redirects=True)
        assert response.status_code == 200

        from models import CommonBlacklist
        item = CommonBlacklist.query.filter_by(type='item', value='BadItem').first()
        assert item is not None

        response = client.post(f'/settings/common-blacklist/{item.id}/delete',
                               follow_redirects=True)
        assert response.status_code == 200


def test_template_color_update(client, app):
    with app.app_context():
        response = client.post('/settings/templates', data={
            'color_navbar': '#ff0000',
            'color_email_grad_start': '#00ff00',
            'color_email_grad_end': '#0000ff',
            'color_balance_positive': '#aabbcc',
            'color_balance_negative': '#ccbbaa',
            'tpl_email_subject': 'Test Subject [Date]',
            'tpl_email_greeting': 'Hello [Name]',
            'tpl_email_intro': 'Intro',
            'tpl_email_footer1': 'Footer 1',
            'tpl_email_footer2': 'Footer 2',
            'tpl_admin_subject': 'Admin Subject',
            'tpl_admin_intro': 'Admin Intro',
            'tpl_admin_footer': 'Admin Footer',
            'tpl_backup_subject': 'Backup',
            'tpl_backup_footer': 'Backup Footer',
        }, follow_redirects=True)
        assert response.status_code == 200

        from helpers import get_setting
        assert get_setting('color_navbar') == '#ff0000'


def test_template_reset(client, app):
    with app.app_context():
        from helpers import set_setting
        set_setting('tpl_email_subject', 'Modified Subject')

        response = client.post('/settings/templates/reset', follow_redirects=True)
        assert response.status_code == 200

        from helpers import get_setting
        from config import TEMPLATE_DEFAULTS
        assert get_setting('tpl_email_subject') == TEMPLATE_DEFAULTS['tpl_email_subject']


def test_schedule_update(client, app):
    with app.app_context():
        response = client.post('/settings/schedule', data={
            'schedule_enabled': '1',
            'schedule_day': 'fri',
            'schedule_hour': '14',
            'schedule_minute': '30',
        }, follow_redirects=True)
        assert response.status_code == 200

        from helpers import get_setting
        assert get_setting('schedule_day') == 'fri'
        assert get_setting('schedule_hour') == '14'
        assert get_setting('schedule_minute') == '30'


def test_send_now(client, app):
    with app.app_context():
        response = client.post('/settings/send-now', follow_redirects=True)
        assert response.status_code == 200
        assert b'email' in response.data.lower()


def test_common_toggle(client, app):
    with app.app_context():
        response = client.post('/settings/common', data={
            'common_enabled': '1',
        }, follow_redirects=True)
        assert response.status_code == 200

        from helpers import get_setting
        assert get_setting('common_enabled') == '1'

        response = client.post('/settings/common', data={},
                               follow_redirects=True)
        assert response.status_code == 200
        assert get_setting('common_enabled') == '0'


def test_api_common_items(client, app):
    with app.app_context():
        from extensions import db
        from models import CommonItem
        from helpers import set_setting
        set_setting('common_enabled', '1')
        db.session.add(CommonItem(name='Salad'))
        db.session.commit()

        response = client.get('/api/common-items')
        assert response.status_code == 200
        data = response.get_json()
        assert any(i['name'] == 'Salad' for i in data)


def test_api_common_items_disabled(client, app):
    with app.app_context():
        from helpers import set_setting
        set_setting('common_enabled', '0')

        response = client.get('/api/common-items')
        assert response.status_code == 200
        assert response.get_json() == []


def test_backup_create(client, app, tmp_path):
    """Creating a backup should fail gracefully in test (no mysqldump)."""
    import backup_service
    original = backup_service.BACKUP_DIR
    backup_service.BACKUP_DIR = str(tmp_path)
    try:
        with app.app_context():
            response = client.post('/settings/backup/create', follow_redirects=True)
            assert response.status_code == 200
    finally:
        backup_service.BACKUP_DIR = original
