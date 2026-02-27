from decimal import Decimal


def test_index_page(client, app):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Bank of Tina' in response.data


def test_add_user(client, app):
    with app.app_context():
        response = client.post('/user/add', data={
            'name': 'Alice',
            'email': 'alice@example.com',
            'email_opt_in': '1',
            'email_transactions': 'last3',
        }, follow_redirects=True)
        assert response.status_code == 200

        from models import User
        user = User.query.filter_by(name='Alice').first()
        assert user is not None
        assert user.email == 'alice@example.com'


def test_deposit(client, app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Bob', email='bob@example.com')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        response = client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user_id),
            'amount': '50.00',
            'description': 'Test deposit',
            'date': '',
        }, follow_redirects=True)
        assert response.status_code == 200

        user = User.query.get(user_id)
        assert user.balance == Decimal('50.00')


def test_withdrawal(client, app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Carol', email='carol@example.com', balance=Decimal('100.00'))
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        response = client.post('/transaction/add', data={
            'transaction_type': 'withdrawal',
            'user_id': str(user_id),
            'amount': '30.00',
            'description': 'Test withdrawal',
            'date': '',
        }, follow_redirects=True)
        assert response.status_code == 200

        user = User.query.get(user_id)
        assert user.balance == Decimal('70.00')


def test_delete_transaction_reverses_balance(client, app):
    with app.app_context():
        from extensions import db
        from models import User, Transaction
        user = User(name='Dave', email='dave@example.com', balance=Decimal('0'))
        db.session.add(user)
        db.session.commit()

        # Create a deposit
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '25.00',
            'description': 'To delete',
            'date': '',
        })

        user = User.query.get(user.id)
        assert user.balance == Decimal('25.00')

        tx = Transaction.query.filter_by(description='To delete').first()
        assert tx is not None

        response = client.post(f'/transaction/{tx.id}/delete', follow_redirects=True)
        assert response.status_code == 200

        user = User.query.get(user.id)
        assert user.balance == Decimal('0')


def test_api_users_json(client, app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Eve', email='eve@example.com', balance=Decimal('42.00'))
        db.session.add(user)
        db.session.commit()

        response = client.get('/api/users')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Eve'
        assert data[0]['balance'] == 42.0
