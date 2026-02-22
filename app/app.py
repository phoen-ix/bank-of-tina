from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import re
import json
import smtplib
import calendar as cal_mod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-a-random-secret-key'
_db_user = os.environ.get('DB_USER', 'tina')
_db_pass = os.environ.get('DB_PASSWORD', 'tina')
_db_host = os.environ.get('DB_HOST', 'localhost')
_db_port = os.environ.get('DB_PORT', '3306')
_db_name = os.environ.get('DB_NAME', 'bank_of_tina')
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'mysql+pymysql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}'
)
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
    is_active = db.Column(db.Boolean, default=True)

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

class Setting(db.Model):
    key   = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=True)

class CommonItem(db.Model):
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)

# Helper Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_receipt(file, buyer_name):
    """Save an uploaded receipt to UPLOAD_FOLDER/YYYY/MM/DD/BUYER_filename.
    Returns the relative path for DB storage, or None if the file is invalid."""
    if not file or not file.filename or not allowed_file(file.filename):
        return None

    # Sanitize buyer name: keep letters/digits/underscore, collapse runs of _
    safe_buyer = re.sub(r'[^\w]', '_', buyer_name)
    safe_buyer = re.sub(r'_+', '_', safe_buyer).strip('_') or 'unknown'

    # Sanitize original filename (werkzeug handles unicode, spaces, traversal)
    original = secure_filename(file.filename) or 'file'

    now = datetime.now()
    rel_dir = now.strftime('%Y/%m/%d')
    abs_dir = os.path.join(app.config['UPLOAD_FOLDER'], rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{safe_buyer}_{original}"
    file.save(os.path.join(abs_dir, filename))
    return f"{rel_dir}/{filename}"


def update_balance(user_id, amount):
    user = User.query.get(user_id)
    if user:
        user.balance += amount
        db.session.commit()

def get_setting(key, default=None):
    s = Setting.query.get(key)
    return s.value if s else default

def set_setting(key, value):
    s = Setting.query.get(key) or Setting(key=key)
    s.value = value
    db.session.add(s)
    db.session.commit()

# Email logic
def build_email_html(user):
    recent_transactions = Transaction.query.filter(
        (Transaction.from_user_id == user.id) | (Transaction.to_user_id == user.id)
    ).order_by(Transaction.date.desc()).limit(10).all()

    if user.balance < 0:
        balance_class = "color: #dc3545;"
        balance_status = f"You owe €{abs(user.balance):.2f}"
    elif user.balance > 0:
        balance_class = "color: #28a745;"
        balance_status = f"You are owed €{user.balance:.2f}"
    else:
        balance_class = "color: #6c757d;"
        balance_status = "Your balance is settled"

    transactions_html = ""
    if recent_transactions:
        for trans in recent_transactions:
            if trans.from_user_id == user.id:
                direction = "→"
                other_user = trans.to_user.name if trans.to_user else "System"
                amount_class = "color: #dc3545;"
                amount_sign = "-"
            else:
                direction = "←"
                other_user = trans.from_user.name if trans.from_user else "System"
                amount_class = "color: #28a745;"
                amount_sign = "+"

            transactions_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                    {trans.date.strftime('%Y-%m-%d')}
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                    {trans.description}
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                    {direction} {other_user}
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; {amount_class}">
                    {amount_sign}€{trans.amount:.2f}
                </td>
            </tr>
            """
    else:
        transactions_html = """
        <tr>
            <td colspan="4" style="padding: 16px; text-align: center; color: #6c757d;">
                No recent transactions
            </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">🏦 Bank of Tina</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Weekly Balance Update</p>
        </div>

        <div style="background: white; padding: 30px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; margin-bottom: 20px;">Hi {user.name},</p>

            <p>Here's your weekly update from the Bank of Tina:</p>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <p style="margin: 0 0 10px 0; color: #6c757d; text-transform: uppercase; font-size: 12px; font-weight: bold;">Current Balance</p>
                <h2 style="margin: 0; font-size: 36px; {balance_class}">€{user.balance:.2f}</h2>
                <p style="margin: 10px 0 0 0; {balance_class}">{balance_status}</p>
            </div>

            <h3 style="color: #495057; margin-top: 30px;">Recent Transactions</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;">Date</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;">Description</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;">With</th>
                        <th style="padding: 10px; text-align: right; border-bottom: 2px solid #dee2e6;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {transactions_html}
                </tbody>
            </table>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 14px;">
                <p>This is an automated weekly update from the Bank of Tina system.</p>
                <p style="margin-top: 10px;">Making office lunches easier! 🥗</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_single_email(to_email, to_name, subject, html):
    smtp_server   = get_setting('smtp_server', 'smtp.gmail.com')
    smtp_port     = int(get_setting('smtp_port', '587'))
    smtp_username = get_setting('smtp_username', '')
    smtp_password = get_setting('smtp_password', '')
    from_email    = get_setting('from_email', smtp_username)
    from_name     = get_setting('from_name', 'Bank of Tina')

    if not smtp_username or not smtp_password:
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{from_name} <{from_email}>'
    msg['To'] = f'{to_name} <{to_email}>'
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.error(f"Error sending email to {to_email}: {e}")
        return False

def send_all_emails():
    users = User.query.filter_by(is_active=True).all()
    success, fail = 0, 0
    subject = f"Bank of Tina - Weekly Balance Update ({datetime.now().strftime('%Y-%m-%d')})"
    for user in users:
        html = build_email_html(user)
        if send_single_email(user.email, user.name, subject, html):
            success += 1
        else:
            fail += 1
    return success, fail

# APScheduler
scheduler = BackgroundScheduler(daemon=True)

def _add_email_job():
    day    = get_setting('schedule_day', 'mon')
    hour   = int(get_setting('schedule_hour', '9'))
    minute = int(get_setting('schedule_minute', '0'))

    def job():
        with app.app_context():
            send_all_emails()

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      id='email_job', replace_existing=True)

def _restore_schedule():
    if get_setting('schedule_enabled') == '1':
        _add_email_job()

# Routes
@app.route('/')
def index():
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    count = int(get_setting('recent_transactions_count', '5'))
    recent = Transaction.query.order_by(Transaction.date.desc()).limit(count).all() if count else []
    return render_template('index.html', users=users, transactions=recent, show_recent=count > 0)

@app.route('/user/add', methods=['POST'])
def add_user():
    name = request.form.get('name')
    email = request.form.get('email')

    if not name or not email:
        flash('Name and email are required!', 'error')
        return redirect(url_for('settings'))

    if User.query.filter_by(name=name).first():
        flash('User already exists!', 'error')
        return redirect(url_for('settings'))

    user = User(name=name, email=email)
    db.session.add(user)
    db.session.commit()
    flash(f'User {name} added successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/user/<int:user_id>/edit', methods=['POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    created_at_str = request.form.get('created_at', '').strip()

    if not name or not email or not created_at_str:
        flash('All fields are required!', 'error')
        return redirect(url_for('user_detail', user_id=user_id))

    existing = User.query.filter(User.name == name, User.id != user_id).first()
    if existing:
        flash('Another user with that name already exists!', 'error')
        return redirect(url_for('user_detail', user_id=user_id))

    existing_email = User.query.filter(User.email == email, User.id != user_id).first()
    if existing_email:
        flash('Another user with that email already exists!', 'error')
        return redirect(url_for('user_detail', user_id=user_id))

    try:
        user.created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format!', 'error')
        return redirect(url_for('user_detail', user_id=user_id))

    user.name = name
    user.email = email
    db.session.commit()
    flash('User updated successfully!', 'success')
    return redirect(url_for('user_detail', user_id=user_id))


@app.route('/user/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.name} has been {status}.', 'success')
    return redirect(request.referrer or url_for('settings'))


@app.route('/transaction/add', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'GET':
        users = User.query.filter_by(is_active=True).order_by(User.name).all()
        default_item_rows = int(get_setting('default_item_rows', '3'))
        return render_template('add_transaction.html', users=users, default_item_rows=default_item_rows)

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
        buyer = User.query.get(buyer_id)
        buyer_name = buyer.name if buyer else 'unknown'
        receipt_path = save_receipt(request.files.get('receipt'), buyer_name)

        # Get expense items
        items_data = request.form.get('items_json')
        if items_data:
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
                    description=description,
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
    from collections import defaultdict
    today = datetime.today()
    year  = max(2000, min(2100, int(request.args.get('year',  today.year))))
    month = max(1,    min(12,   int(request.args.get('month', today.month))))

    _, last = cal_mod.monthrange(year, month)
    transactions = Transaction.query.filter(
        Transaction.date >= datetime(year, month, 1),
        Transaction.date <= datetime(year, month, last, 23, 59, 59),
    ).order_by(Transaction.date.desc()).all()

    by_day = defaultdict(list)
    for t in transactions:
        by_day[t.date.date()].append(t)
    grouped = sorted(by_day.items(), reverse=True)

    prev_month = month - 1 or 12
    prev_year  = year - (1 if month == 1 else 0)
    next_month = (month % 12) + 1
    next_year  = year + (1 if month == 12 else 0)

    first = Transaction.query.order_by(Transaction.date.asc()).first()
    start_year = first.date.year if first else today.year
    year_range = list(range(start_year, today.year + 1))

    return render_template('transactions.html',
        grouped=grouped,
        year=year, month=month,
        month_name=datetime(year, month, 1).strftime('%B'),
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        is_current_month=(year == today.year and month == today.month),
        year_range=year_range,
        tx_count=len(transactions),
        tx_total=sum(t.amount for t in transactions),
    )

@app.route('/user/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    transactions = Transaction.query.filter(
        (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
    ).order_by(Transaction.date.desc()).all()
    return render_template('user_detail.html', user=user, transactions=transactions)

@app.route('/receipt/<path:filepath>')
def view_receipt(filepath):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)

@app.route('/transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    trans = Transaction.query.get_or_404(transaction_id)
    users = User.query.order_by(User.name).all()

    if request.method == 'GET':
        return render_template('edit_transaction.html', trans=trans, users=users)

    # Capture old amount before any changes for balance reversal
    old_amount = trans.amount

    # Reverse old balance effects
    if trans.from_user_id:
        old_from = User.query.get(trans.from_user_id)
        if old_from:
            old_from.balance += old_amount
    if trans.to_user_id:
        old_to = User.query.get(trans.to_user_id)
        if old_to:
            old_to.balance -= old_amount

    # Update basic fields
    trans.description = request.form.get('description', trans.description).strip()

    date_str = request.form.get('date', '').strip()
    if date_str:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
            try:
                trans.date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue

    from_id = request.form.get('from_user_id') or None
    to_id   = request.form.get('to_user_id')   or None
    trans.from_user_id = int(from_id) if from_id else None
    trans.to_user_id   = int(to_id)   if to_id   else None

    # Handle expense items: always replace with submitted list
    ExpenseItem.query.filter_by(transaction_id=trans.id).delete()
    items_json_str = request.form.get('items_json', '').strip()
    new_items_total = None
    if items_json_str:
        try:
            items = json.loads(items_json_str)
            if items:
                total = 0.0
                for item in items:
                    price = float(item['price'])
                    db.session.add(ExpenseItem(
                        transaction_id=trans.id,
                        item_name=item['name'],
                        price=price,
                        buyer_id=trans.to_user_id,
                    ))
                    total += price
                new_items_total = total
        except (ValueError, KeyError):
            pass

    # Amount: use items total when items are present, otherwise use the form field
    if new_items_total is not None:
        trans.amount = new_items_total
    else:
        try:
            trans.amount = float(request.form.get('amount', old_amount))
        except ValueError:
            trans.amount = old_amount

    # Apply new balance effects
    if trans.from_user_id:
        new_from = User.query.get(trans.from_user_id)
        if new_from:
            new_from.balance -= trans.amount
    if trans.to_user_id:
        new_to = User.query.get(trans.to_user_id)
        if new_to:
            new_to.balance += trans.amount

    db.session.commit()
    flash('Transaction updated successfully!', 'success')
    return redirect(url_for('view_transactions'))


@app.route('/transaction/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id):
    trans = Transaction.query.get_or_404(transaction_id)

    # Reverse balance effects
    if trans.from_user_id:
        from_user = User.query.get(trans.from_user_id)
        if from_user:
            from_user.balance += trans.amount
    if trans.to_user_id:
        to_user = User.query.get(trans.to_user_id)
        if to_user:
            to_user.balance -= trans.amount

    ExpenseItem.query.filter_by(transaction_id=trans.id).delete()
    db.session.delete(trans)
    db.session.commit()

    flash('Transaction deleted.', 'success')
    return redirect(url_for('view_transactions'))


@app.route('/api/users')
def api_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'balance': u.balance} for u in users])

@app.route('/settings')
def settings():
    cfg = {
        'smtp_server':   get_setting('smtp_server', 'smtp.gmail.com'),
        'smtp_port':     get_setting('smtp_port', '587'),
        'smtp_username': get_setting('smtp_username', ''),
        'smtp_password': get_setting('smtp_password', ''),
        'from_email':    get_setting('from_email', ''),
        'from_name':     get_setting('from_name', 'Bank of Tina'),
        'schedule_enabled': get_setting('schedule_enabled', '0'),
        'schedule_day':  get_setting('schedule_day', 'mon'),
        'schedule_hour': get_setting('schedule_hour', '9'),
        'schedule_minute':   get_setting('schedule_minute', '0'),
        'default_item_rows': get_setting('default_item_rows', '3'),
        'recent_transactions_count': get_setting('recent_transactions_count', '5'),
    }
    common_items = CommonItem.query.order_by(CommonItem.name).all()
    all_users = User.query.order_by(User.name).all()
    return render_template('settings.html', cfg=cfg, common_items=common_items, all_users=all_users)

@app.route('/settings/email', methods=['POST'])
def settings_email():
    set_setting('smtp_server',   request.form.get('smtp_server', '').strip())
    set_setting('smtp_port',     request.form.get('smtp_port', '587').strip())
    set_setting('smtp_username', request.form.get('smtp_username', '').strip())
    set_setting('from_email',    request.form.get('from_email', '').strip())
    set_setting('from_name',     request.form.get('from_name', '').strip())

    # Only update password if a new one was provided
    new_password = request.form.get('smtp_password', '').strip()
    if new_password:
        set_setting('smtp_password', new_password)

    flash('Settings saved.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/send-now', methods=['POST'])
def settings_send_now():
    success, fail = send_all_emails()
    flash(f'{success} email(s) sent, {fail} failed.', 'success' if fail == 0 else 'error')
    return redirect(url_for('settings'))

@app.route('/settings/schedule', methods=['POST'])
def settings_schedule():
    enabled = '1' if request.form.get('schedule_enabled') else '0'
    day    = request.form.get('schedule_day', 'mon')
    try:
        hour   = str(max(0, min(23, int(request.form.get('schedule_hour',   '9')))))
        minute = str(max(0, min(55, int(request.form.get('schedule_minute', '0')))))
    except ValueError:
        hour, minute = '9', '0'

    set_setting('schedule_enabled', enabled)
    set_setting('schedule_day',     day)
    set_setting('schedule_hour',    hour)
    set_setting('schedule_minute',  minute)

    if enabled == '1':
        _add_email_job()
        flash('Schedule saved and enabled.', 'success')
    else:
        if scheduler.get_job('email_job'):
            scheduler.remove_job('email_job')
        flash('Schedule disabled.', 'success')

    return redirect(url_for('settings'))


@app.route('/settings/general', methods=['POST'])
def settings_general():
    try:
        rows = max(0, min(20, int(request.form.get('default_item_rows', '3'))))
    except ValueError:
        rows = 3
    set_setting('default_item_rows', str(rows))
    try:
        count = max(0, min(50, int(request.form.get('recent_transactions_count', '5'))))
    except ValueError:
        count = 5
    set_setting('recent_transactions_count', str(count))
    flash('General settings saved.', 'success')
    return redirect(url_for('settings'))


@app.route('/api/common-items')
def api_common_items():
    items = CommonItem.query.order_by(CommonItem.name).all()
    return jsonify([{'id': i.id, 'name': i.name} for i in items])

@app.route('/settings/common-items/add', methods=['POST'])
def add_common_item():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Item name is required.', 'error')
        return redirect(url_for('settings'))
    if not CommonItem.query.filter_by(name=name).first():
        db.session.add(CommonItem(name=name))
        db.session.commit()
    flash(f'"{name}" added to common items.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-items/<int:item_id>/delete', methods=['POST'])
def delete_common_item(item_id):
    item = CommonItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'"{name}" removed from common items.', 'success')
    return redirect(url_for('settings'))


# Initialize database
with app.app_context():
    db.create_all()
    _restore_schedule()

scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
