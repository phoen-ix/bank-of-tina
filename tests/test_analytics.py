from decimal import Decimal


def test_analytics_page_loads(client, app):
    response = client.get('/analytics')
    assert response.status_code == 200


def test_analytics_data_no_transactions(client, app):
    response = client.get('/analytics/data')
    assert response.status_code == 200
    data = response.get_json()
    assert 'balances' in data
    assert 'balance_history' in data
    assert 'transaction_volume' in data
    assert 'top_items' in data
    assert data['meta']['transaction_count'] == 0


def test_analytics_data_with_transactions(client, app, make_user):
    with app.app_context():
        user = make_user(name='AnalyticsUser', balance=Decimal('50'))
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '50',
            'description': 'Analytics deposit',
            'date': '',
        })

        response = client.get('/analytics/data')
        assert response.status_code == 200
        data = response.get_json()
        assert data['meta']['transaction_count'] >= 1


def test_analytics_data_user_filter(client, app, make_user):
    with app.app_context():
        user1 = make_user(name='FilterUser1', balance=Decimal('10'))
        user2 = make_user(name='FilterUser2', balance=Decimal('20'))

        response = client.get(f'/analytics/data?users={user1.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['meta']['user_count'] == 1
        assert data['balances'][0]['name'] == 'FilterUser1'


def test_analytics_data_date_range(client, app, make_user):
    with app.app_context():
        user = make_user(name='DateRange')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '100',
            'description': 'Old deposit',
            'date': '2020-01-01T12:00',
        })

        response = client.get('/analytics/data?date_from=2019-01-01&date_to=2020-12-31')
        assert response.status_code == 200
        data = response.get_json()
        assert data['meta']['transaction_count'] >= 1
