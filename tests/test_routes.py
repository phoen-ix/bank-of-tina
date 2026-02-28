import json
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

        user = db.session.get(User, user_id)
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

        user = db.session.get(User, user_id)
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

        user = db.session.get(User, user.id)
        assert user.balance == Decimal('25.00')

        tx = Transaction.query.filter_by(description='To delete').first()
        assert tx is not None

        response = client.post(f'/transaction/{tx.id}/delete', follow_redirects=True)
        assert response.status_code == 200

        user = db.session.get(User, user.id)
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


def test_expense_with_items_json(client, app, make_user):
    with app.app_context():
        buyer = make_user(name='Buyer', email='buyer@test.com', balance=Decimal('0'))
        debtor = make_user(name='Debtor', email='debtor@test.com', balance=Decimal('0'))

        items = [
            {'name': 'Pizza', 'price': '10.00', 'debtor_id': str(debtor.id)},
            {'name': 'Drink', 'price': '5.00', 'debtor_id': str(debtor.id)},
        ]
        response = client.post('/transaction/add', data={
            'transaction_type': 'expense',
            'buyer_id': str(buyer.id),
            'description': 'Lunch',
            'items_json': json.dumps(items),
            'date': '',
        }, follow_redirects=True)
        assert response.status_code == 200

        from extensions import db
        from models import User
        buyer = db.session.get(User, buyer.id)
        debtor = db.session.get(User, debtor.id)
        assert buyer.balance == Decimal('15.00')
        assert debtor.balance == Decimal('-15.00')


def test_edit_transaction_balance_reversal(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import Transaction
        user = make_user(name='EditUser', balance=Decimal('0'))

        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '100.00',
            'description': 'Original',
            'date': '',
        })

        tx = Transaction.query.filter_by(description='Original').first()
        response = client.post(f'/transaction/{tx.id}/edit', data={
            'description': 'Updated',
            'amount': '50.00',
            'to_user_id': str(user.id),
            'date': '',
        }, follow_redirects=True)
        assert response.status_code == 200

        from models import User
        user = db.session.get(User, user.id)
        assert user.balance == Decimal('50.00')


def test_search_text_query(client, app, make_user):
    with app.app_context():
        user = make_user(name='SearchUser')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'UniqueSearchTerm',
            'date': '',
        })
        response = client.get('/search?q=UniqueSearchTerm')
        assert response.status_code == 200
        assert b'UniqueSearchTerm' in response.data


def test_search_type_filter(client, app, make_user):
    with app.app_context():
        user = make_user(name='TypeFilter')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'TypeTest',
            'date': '',
        })
        response = client.get('/search?type=deposit')
        assert response.status_code == 200
        assert b'TypeTest' in response.data

        response = client.get('/search?type=withdrawal')
        assert response.status_code == 200
        assert b'TypeTest' not in response.data


def test_search_date_range(client, app, make_user):
    with app.app_context():
        user = make_user(name='DateFilter')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'DateTest',
            'date': '2024-06-15T10:00',
        })
        response = client.get('/search?date_from=2024-06-01&date_to=2024-06-30')
        assert response.status_code == 200
        assert b'DateTest' in response.data


def test_search_amount_range(client, app, make_user):
    with app.app_context():
        user = make_user(name='AmountFilter')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '50',
            'description': 'AmountTest',
            'date': '',
        })
        response = client.get('/search?amount_min=40&amount_max=60')
        assert response.status_code == 200
        assert b'AmountTest' in response.data


def test_user_detail_page(client, app, make_user):
    with app.app_context():
        user = make_user(name='DetailUser', balance=Decimal('123.45'))
        response = client.get(f'/user/{user.id}')
        assert response.status_code == 200
        assert b'DetailUser' in response.data


def test_user_edit(client, app, make_user):
    with app.app_context():
        user = make_user(name='EditMe', email='editme@test.com')
        response = client.post(f'/user/{user.id}/edit', data={
            'name': 'Edited',
            'email': 'edited@test.com',
            'created_at': '2024-01-01',
            'email_opt_in': '1',
            'email_transactions': 'last3',
        }, follow_redirects=True)
        assert response.status_code == 200

        from extensions import db
        from models import User
        u = db.session.get(User, user.id)
        assert u.name == 'Edited'
        assert u.email == 'edited@test.com'


def test_toggle_user_active(client, app, make_user):
    with app.app_context():
        user = make_user(name='ToggleMe')
        assert user.is_active is True

        client.post(f'/user/{user.id}/toggle-active', follow_redirects=True)
        from extensions import db
        from models import User
        u = db.session.get(User, user.id)
        assert u.is_active is False


def test_duplicate_name_validation(client, app, make_user):
    with app.app_context():
        make_user(name='DupName', email='dup1@test.com')
        response = client.post('/user/add', data={
            'name': 'DupName',
            'email': 'dup2@test.com',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'already exists' in response.data


def test_duplicate_email_validation(client, app, make_user):
    with app.app_context():
        user = make_user(name='User1', email='same@test.com')
        user2 = make_user(name='User2', email='other@test.com')
        response = client.post(f'/user/{user2.id}/edit', data={
            'name': 'User2',
            'email': 'same@test.com',
            'created_at': '2024-01-01',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Another user with that email' in response.data


def test_deposit_with_notes(client, app, make_user):
    with app.app_context():
        user = make_user(name='NotesUser')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'Noted Deposit',
            'notes': 'Some important notes',
            'date': '',
        })
        from models import Transaction
        tx = Transaction.query.filter_by(description='Noted Deposit').first()
        assert tx is not None
        assert tx.notes == 'Some important notes'


def test_withdrawal_overdraw(client, app, make_user):
    with app.app_context():
        user = make_user(name='Overdraw', balance=Decimal('10'))
        response = client.post('/transaction/add', data={
            'transaction_type': 'withdrawal',
            'user_id': str(user.id),
            'amount': '20',
            'description': 'Overdraw',
            'date': '',
        }, follow_redirects=True)
        assert response.status_code == 200
        from extensions import db
        from models import User
        u = db.session.get(User, user.id)
        assert u.balance == Decimal('-10.00')


def test_pwa_manifest(client, app):
    response = client.get('/manifest.json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['name'] == 'Bank of Tina'
    assert 'icons' in data


def test_transactions_list_page(client, app, make_user):
    with app.app_context():
        user = make_user(name='ListUser')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'ListTest',
            'date': '',
        })
        response = client.get('/transactions')
        assert response.status_code == 200


def test_add_transaction_get(client, app):
    response = client.get('/transaction/add')
    assert response.status_code == 200


def test_edit_transaction_receipt_removal(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import Transaction
        user = make_user(name='ReceiptUser')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'WithReceipt',
            'date': '',
        })
        tx = Transaction.query.filter_by(description='WithReceipt').first()
        tx.receipt_path = 'some/fake/path.pdf'
        db.session.commit()

        response = client.post(f'/transaction/{tx.id}/edit', data={
            'description': 'WithReceipt',
            'amount': '10',
            'to_user_id': str(user.id),
            'remove_receipt': '1',
            'date': '',
        }, follow_redirects=True)
        assert response.status_code == 200

        tx = db.session.get(Transaction, tx.id)
        assert tx.receipt_path is None


def test_search_has_receipt(client, app, make_user):
    with app.app_context():
        from extensions import db
        from models import Transaction
        user = make_user(name='ReceiptSearch')
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '10',
            'description': 'NoReceipt',
            'date': '',
        })
        client.post('/transaction/add', data={
            'transaction_type': 'deposit',
            'user_id': str(user.id),
            'amount': '20',
            'description': 'HasReceipt',
            'date': '',
        })
        tx = Transaction.query.filter_by(description='HasReceipt').first()
        tx.receipt_path = 'some/path.pdf'
        db.session.commit()

        response = client.get('/search?has_receipt=1')
        assert response.status_code == 200
        assert b'HasReceipt' in response.data
        assert b'NoReceipt' not in response.data
