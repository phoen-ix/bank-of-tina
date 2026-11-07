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
        client.post(
            '/transaction/add',
            data={
                'transaction_type': 'deposit',
                'user_id': str(user.id),
                'amount': '50',
                'description': 'Analytics deposit',
                'date': '',
            },
        )

        response = client.get('/analytics/data')
        assert response.status_code == 200
        data = response.get_json()
        assert data['meta']['transaction_count'] >= 1


def test_analytics_data_user_filter(client, app, make_user):
    with app.app_context():
        user1 = make_user(name='FilterUser1', balance=Decimal('10'))
        make_user(name='FilterUser2', balance=Decimal('20'))

        response = client.get(f'/analytics/data?users={user1.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['meta']['user_count'] == 1
        assert data['balances'][0]['name'] == 'FilterUser1'


def test_analytics_data_date_range(client, app, make_user):
    with app.app_context():
        user = make_user(name='DateRange')
        client.post(
            '/transaction/add',
            data={
                'transaction_type': 'deposit',
                'user_id': str(user.id),
                'amount': '100',
                'description': 'Old deposit',
                'date': '2020-01-01T12:00',
            },
        )

        response = client.get('/analytics/data?date_from=2019-01-01&date_to=2020-12-31')
        assert response.status_code == 200
        data = response.get_json()
        assert data['meta']['transaction_count'] >= 1


def test_balance_history_reverses_only_later_transactions(client, app, make_user):
    with app.app_context():
        user = make_user(name='History')
        for amount, when in (
            ('100', '2020-01-01T12:00'),
            ('1000', '2020-01-10T12:00'),
            ('10', '2020-03-10T12:00'),
            ('1', '2020-06-01T12:00'),
        ):
            client.post(
                '/transaction/add',
                data={
                    'transaction_type': 'deposit',
                    'user_id': str(user.id),
                    'amount': amount,
                    'description': 'h',
                    'date': when,
                },
            )

        weekly = client.get(f'/analytics/data?users={user.id}&date_from=2020-03-01&date_to=2020-03-31').get_json()
        assert weekly['balance_history']['labels'][0] == '2020-03-01'
        assert weekly['balance_history']['datasets']['History'] == [1100, 1100, 1110, 1110, 1110, 1110]

        # Monthly samples start on the 1st, before date_from: the 2020-01-10 deposit is still undone.
        monthly = client.get(f'/analytics/data?users={user.id}&date_from=2020-01-15&date_to=2020-06-30').get_json()
        assert monthly['balance_history']['labels'][:2] == ['2020-01-01', '2020-02-01']
        assert monthly['balance_history']['datasets']['History'][:2] == [100, 1100]
        assert monthly['balance_history']['datasets']['History'][-1] == 1111
