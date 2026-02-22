from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-a-random-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////database/bank_of_tina.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.name}>'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    transaction_type = db.Column(db.String(50))  # 'transfer', 'deposit', 'withdrawal', 'expense'
    receipt_path = db.Column(db.String(500))
    
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='transactions_sent')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='transactions_received')
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.description}>'

class ExpenseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    item_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    transaction = db.relationship('Transaction', backref='items')
    buyer = db.relationship('User', backref='expense_items')
    
    def __repr__(self):
        return f'<ExpenseItem {self.item_name}>'

# Helper Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_balance(user_id, amount):
    user = User.query.get(user_id)
    if user:
        user.balance += amount
        db.session.commit()

# Routes
@app.route('/')
def index():
    users = User.query.order_by(User.name).all()
    recent_transactions = Transaction.query.order_by(Transaction.date.desc()).limit(10).all()
    return render_template('index.html', users=users, transactions=recent_transactions)

@app.route('/user/add', methods=['POST'])
def add_user():
    name = request.form.get('name')
    email = request.form.get('email')
    
    if not name or not email:
        flash('Name and email are required!', 'error')
        return redirect(url_for('index'))
    
    if User.query.filter_by(name=name).first():
        flash('User already exists!', 'error')
        return redirect(url_for('index'))
    
    user = User(name=name, email=email)
    db.session.add(user)
    db.session.commit()
    flash(f'User {name} added successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/transaction/add', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'GET':
        users = User.query.order_by(User.name).all()
        return render_template('add_transaction.html', users=users)
    
    transaction_type = request.form.get('transaction_type')
    
    if transaction_type == 'deposit':
        user_id = int(request.form.get('user_id'))
        amount = float(request.form.get('amount'))
        description = request.form.get('description', 'Deposit')
        
        transaction = Transaction(
            description=description,
            amount=amount,
            to_user_id=user_id,
            transaction_type='deposit'
        )
        db.session.add(transaction)
        update_balance(user_id, amount)
        flash(f'Deposit of €{amount:.2f} added successfully!', 'success')
    
    elif transaction_type == 'withdrawal':
        user_id = int(request.form.get('user_id'))
        amount = float(request.form.get('amount'))
        description = request.form.get('description', 'Withdrawal')
        
        transaction = Transaction(
            description=description,
            amount=amount,
            from_user_id=user_id,
            transaction_type='withdrawal'
        )
        db.session.add(transaction)
        update_balance(user_id, -amount)
        flash(f'Withdrawal of €{amount:.2f} processed successfully!', 'success')
    
    elif transaction_type == 'expense':
        buyer_id = int(request.form.get('buyer_id'))
        description = request.form.get('description', 'Expense')
        
        # Handle receipt upload
        receipt_path = None
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                receipt_path = filename
        
        # Get expense items
        items_data = request.form.get('items_json')
        if items_data:
            import json
            items = json.loads(items_data)
            
            # Group items by who owes what
            debts = {}
            for item in items:
                debtor_id = int(item['debtor_id'])
                price = float(item['price'])
                if debtor_id != buyer_id:
                    debts[debtor_id] = debts.get(debtor_id, 0) + price
            
            # Create transactions for each debt
            for debtor_id, total_amount in debts.items():
                transaction = Transaction(
                    description=f"{description} - {User.query.get(debtor_id).name} owes {User.query.get(buyer_id).name}",
                    amount=total_amount,
                    from_user_id=debtor_id,
                    to_user_id=buyer_id,
                    transaction_type='expense',
                    receipt_path=receipt_path
                )
                db.session.add(transaction)
                
                # Update balances
                update_balance(debtor_id, -total_amount)
                update_balance(buyer_id, total_amount)
                
                # Add expense items
                for item in items:
                    if int(item['debtor_id']) == debtor_id:
                        expense_item = ExpenseItem(
                            transaction=transaction,
                            item_name=item['name'],
                            price=float(item['price']),
                            buyer_id=buyer_id
                        )
                        db.session.add(expense_item)
            
            db.session.commit()
            flash('Expense recorded successfully!', 'success')
    
    return redirect(url_for('index'))

@app.route('/transactions')
def view_transactions():
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return render_template('transactions.html', transactions=transactions)

@app.route('/user/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    transactions = Transaction.query.filter(
        (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
    ).order_by(Transaction.date.desc()).all()
    return render_template('user_detail.html', user=user, transactions=transactions)

@app.route('/receipt/<filename>')
def view_receipt(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/users')
def api_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'balance': u.balance} for u in users])

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
