from datetime import datetime
from decimal import Decimal

import pytest


def test_create_user(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Test User', email='test@example.com', balance=Decimal('100.00'))
        db.session.add(user)
        db.session.commit()

        fetched = db.session.execute(db.select(User).filter_by(name='Test User')).scalar()
        assert fetched is not None
        assert fetched.email == 'test@example.com'
        assert fetched.balance == Decimal('100.00')


def test_user_default_balance(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Zero User', email='zero@example.com')
        db.session.add(user)
        db.session.commit()

        fetched = db.session.execute(db.select(User).filter_by(name='Zero User')).scalar()
        assert fetched.balance == 0


def test_balance_precision_no_float_drift(app):
    """Adding 0.10 ten times should equal exactly 1.00 (not 0.9999...)."""
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Precision Test', email='prec@example.com', balance=Decimal('0'))
        db.session.add(user)
        db.session.commit()

        for _ in range(10):
            user.balance += Decimal('0.10')
        db.session.commit()

        fetched = db.session.execute(db.select(User).filter_by(name='Precision Test')).scalar()
        assert fetched.balance == Decimal('1.00')


def test_user_is_active_default(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Active User', email='active@example.com')
        db.session.add(user)
        db.session.commit()

        fetched = db.session.execute(db.select(User).filter_by(name='Active User')).scalar()
        assert fetched.is_active is True


def test_transaction_creation_all_fields(app):
    with app.app_context():
        from extensions import db
        from models import User, Transaction
        sender = User(name='Sender', email='sender@test.com')
        receiver = User(name='Receiver', email='receiver@test.com')
        db.session.add_all([sender, receiver])
        db.session.commit()

        tx = Transaction(
            description='Test expense',
            amount=Decimal('25.50'),
            from_user_id=sender.id,
            to_user_id=receiver.id,
            transaction_type='expense',
            receipt_path='2024/01/01/receipt.pdf',
            notes='Test notes',
        )
        db.session.add(tx)
        db.session.commit()

        fetched = db.session.execute(db.select(Transaction)).scalar()
        assert fetched.description == 'Test expense'
        assert fetched.amount == Decimal('25.50')
        assert fetched.from_user_id == sender.id
        assert fetched.to_user_id == receiver.id
        assert fetched.transaction_type == 'expense'
        assert fetched.receipt_path == '2024/01/01/receipt.pdf'
        assert fetched.notes == 'Test notes'


def test_expense_item_relationship(app):
    with app.app_context():
        from extensions import db
        from models import User, Transaction, ExpenseItem
        buyer = User(name='Buyer', email='buyer@test.com')
        db.session.add(buyer)
        db.session.commit()

        tx = Transaction(description='Lunch', amount=Decimal('15.00'),
                         to_user_id=buyer.id, transaction_type='expense')
        db.session.add(tx)
        db.session.commit()

        item = ExpenseItem(transaction_id=tx.id, item_name='Pizza',
                           price=Decimal('15.00'), buyer_id=buyer.id)
        db.session.add(item)
        db.session.commit()

        assert len(tx.items) == 1
        assert tx.items[0].item_name == 'Pizza'
        assert item.transaction.description == 'Lunch'


def test_setting_get_set(app):
    with app.app_context():
        from models import Setting
        from extensions import db
        s = Setting(key='test_key', value='test_value')
        db.session.add(s)
        db.session.commit()

        fetched = db.session.get(Setting, 'test_key')
        assert fetched.value == 'test_value'


def test_common_item_uniqueness(app):
    with app.app_context():
        from extensions import db
        from models import CommonItem
        db.session.add(CommonItem(name='Apple'))
        db.session.commit()

        with pytest.raises(Exception):
            db.session.add(CommonItem(name='Apple'))
            db.session.commit()


def test_user_is_active_toggle(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Toggle User', email='toggle@test.com')
        db.session.add(user)
        db.session.commit()
        assert user.is_active is True

        user.is_active = False
        db.session.commit()
        fetched = db.session.execute(db.select(User).filter_by(name='Toggle User')).scalar()
        assert fetched.is_active is False


def test_user_negative_balance(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Debt User', email='debt@test.com', balance=Decimal('-42.50'))
        db.session.add(user)
        db.session.commit()

        fetched = db.session.execute(db.select(User).filter_by(name='Debt User')).scalar()
        assert fetched.balance == Decimal('-42.50')


def test_transaction_types(app):
    with app.app_context():
        from extensions import db
        from models import User, Transaction
        user = User(name='Types User', email='types@test.com')
        db.session.add(user)
        db.session.commit()

        for tx_type in ['deposit', 'withdrawal', 'expense']:
            tx = Transaction(description=f'Test {tx_type}', amount=Decimal('10'),
                             transaction_type=tx_type, to_user_id=user.id)
            db.session.add(tx)
        db.session.commit()

        txs = db.session.execute(db.select(Transaction)).scalars().all()
        assert len(txs) == 3
        types = {t.transaction_type for t in txs}
        assert types == {'deposit', 'withdrawal', 'expense'}


def test_user_relationship_navigation(app):
    with app.app_context():
        from extensions import db
        from models import User, Transaction
        alice = User(name='Alice R', email='alicer@test.com')
        bob = User(name='Bob R', email='bobr@test.com')
        db.session.add_all([alice, bob])
        db.session.commit()

        tx = Transaction(description='Transfer', amount=Decimal('20'),
                         from_user_id=alice.id, to_user_id=bob.id,
                         transaction_type='expense')
        db.session.add(tx)
        db.session.commit()

        assert tx.from_user.name == 'Alice R'
        assert tx.to_user.name == 'Bob R'
        assert tx in alice.transactions_sent
        assert tx in bob.transactions_received
