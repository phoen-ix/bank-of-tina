from decimal import Decimal


def test_create_user(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Test User', email='test@example.com', balance=Decimal('100.00'))
        db.session.add(user)
        db.session.commit()

        fetched = User.query.filter_by(name='Test User').first()
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

        fetched = User.query.filter_by(name='Zero User').first()
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

        fetched = User.query.filter_by(name='Precision Test').first()
        assert fetched.balance == Decimal('1.00')


def test_user_is_active_default(app):
    with app.app_context():
        from extensions import db
        from models import User
        user = User(name='Active User', email='active@example.com')
        db.session.add(user)
        db.session.commit()

        fetched = User.query.filter_by(name='Active User').first()
        assert fetched.is_active is True
