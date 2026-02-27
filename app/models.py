from datetime import datetime
from extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    balance = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    email_opt_in = db.Column(db.Boolean, default=True)
    email_transactions = db.Column(db.String(20), default='last3')

    def __repr__(self):
        return f'<User {self.name}>'


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    transaction_type = db.Column(db.String(50))
    receipt_path = db.Column(db.String(500))
    notes = db.Column(db.Text, nullable=True)

    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='transactions_sent')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='transactions_received')

    def __repr__(self):
        return f'<Transaction {self.id}: {self.description}>'


class ExpenseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    item_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    transaction = db.relationship('Transaction', backref='items')
    buyer = db.relationship('User', backref='expense_items')

    def __repr__(self):
        return f'<ExpenseItem {self.item_name}>'


class Setting(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=True)


class CommonItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)


class CommonDescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(500), nullable=False, unique=True)


class CommonPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Numeric(12, 2), nullable=False, unique=True)


class CommonBlacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    value = db.Column(db.String(500), nullable=False)
    __table_args__ = (db.UniqueConstraint('type', 'value'),)


class AutoCollectLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(500), nullable=False)


class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(10), nullable=False)
    recipient = db.Column(db.String(200))
    message = db.Column(db.String(500), nullable=False)


class BackupLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(10), nullable=False)
    message = db.Column(db.String(500), nullable=False)
