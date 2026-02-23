from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import re
import json
import shutil
import smtplib
import subprocess
import tarfile
import tempfile
import calendar as cal_mod
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import pytz

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
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB per chunk (chunked upload)
BACKUP_DIR = '/backups'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

# ── Theme / template constants ─────────────────────────────────────────────

THEMES = {
    'default': {
        'label': 'Default',
        'color_navbar': '#0d6efd',
        'color_email_grad_start': '#667eea',
        'color_email_grad_end': '#764ba2',
        'color_balance_positive': '#28a745',
        'color_balance_negative': '#dc3545',
    },
    'ocean': {
        'label': 'Ocean',
        'color_navbar': '#0077b6',
        'color_email_grad_start': '#0077b6',
        'color_email_grad_end': '#00b4d8',
        'color_balance_positive': '#2ec4b6',
        'color_balance_negative': '#e76f51',
    },
    'forest': {
        'label': 'Forest',
        'color_navbar': '#2d6a4f',
        'color_email_grad_start': '#2d6a4f',
        'color_email_grad_end': '#52b788',
        'color_balance_positive': '#52b788',
        'color_balance_negative': '#e63946',
    },
    'sunset': {
        'label': 'Sunset',
        'color_navbar': '#c94b4b',
        'color_email_grad_start': '#c94b4b',
        'color_email_grad_end': '#4b134f',
        'color_balance_positive': '#28a745',
        'color_balance_negative': '#dc3545',
    },
    'slate': {
        'label': 'Slate',
        'color_navbar': '#343a40',
        'color_email_grad_start': '#343a40',
        'color_email_grad_end': '#6c757d',
        'color_balance_positive': '#28a745',
        'color_balance_negative': '#dc3545',
    },
}

TEMPLATE_DEFAULTS = {
    'color_navbar':             '#0d6efd',
    'color_email_grad_start':   '#667eea',
    'color_email_grad_end':     '#764ba2',
    'color_balance_positive':   '#28a745',
    'color_balance_negative':   '#dc3545',
    'tpl_email_subject':   'Bank of Tina - Weekly Balance Update ([Date])',
    'tpl_email_greeting':  'Hi [Name],',
    'tpl_email_intro':     "Here's your weekly update from the Bank of Tina:",
    'tpl_email_footer1':   'This is an automated weekly update from the Bank of Tina system.',
    'tpl_email_footer2':   'Making office lunches easier! 🥗',
    'tpl_admin_subject':   'Bank of Tina - Admin Summary ([Date])',
    'tpl_admin_intro':     '',
    'tpl_admin_footer':    'This is an automated admin summary from the Bank of Tina system.',
    'tpl_backup_subject':  'Bank of Tina - Backup [BackupStatus] ([Date])',
    'tpl_backup_footer':   'This is an automated backup report from the Bank of Tina system.',
}

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    email_opt_in = db.Column(db.Boolean, default=True)
    email_transactions = db.Column(db.String(20), default='last3')
    # email_transactions values: 'none' | 'last3' | 'this_week' | 'this_month'

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
    notes = db.Column(db.Text, nullable=True)

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

class CommonDescription(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(500), nullable=False, unique=True)

class CommonPrice(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False, unique=True)

class CommonBlacklist(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    type  = db.Column(db.String(20), nullable=False)   # 'item' | 'description' | 'price'
    value = db.Column(db.String(500), nullable=False)
    __table_args__ = (db.UniqueConstraint('type', 'value'),)

class AutoCollectLog(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    ran_at   = db.Column(db.DateTime, default=datetime.utcnow)
    level    = db.Column(db.String(10), nullable=False)   # 'INFO' | 'ADDED' | 'SKIP' | 'ERROR'
    category = db.Column(db.String(20), nullable=False)   # 'item' | 'description' | 'price' | 'system'
    message  = db.Column(db.String(500), nullable=False)

class EmailLog(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    sent_at   = db.Column(db.DateTime, default=datetime.utcnow)
    level     = db.Column(db.String(10), nullable=False)   # 'SUCCESS' | 'FAIL' | 'INFO'
    recipient = db.Column(db.String(200))                  # "Name <email>" or None for system lines
    message   = db.Column(db.String(500), nullable=False)

class BackupLog(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    ran_at   = db.Column(db.DateTime, default=datetime.utcnow)
    level    = db.Column(db.String(10), nullable=False)   # 'INFO' | 'SUCCESS' | 'ERROR'
    message  = db.Column(db.String(500), nullable=False)

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


def delete_receipt_file(receipt_path, exclude_transaction_id):
    """Delete a receipt file from disk only if no other transaction still references it."""
    if not receipt_path:
        return
    others = Transaction.query.filter(
        Transaction.receipt_path == receipt_path,
        Transaction.id != exclude_transaction_id
    ).first()
    if others:
        return  # still in use — only unlink the current transaction, don't touch the file
    abs_path = os.path.join(app.config['UPLOAD_FOLDER'], receipt_path)
    try:
        os.remove(abs_path)
    except OSError:
        pass

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

def now_local():
    """Return the current datetime in the configured app timezone.
    Works in both request and scheduler (background) contexts."""
    tz_name = get_setting('timezone', 'UTC')
    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC
    return datetime.now(tz)

def get_tpl(key):
    """Get a template/theme setting, falling back to TEMPLATE_DEFAULTS."""
    return get_setting(key, TEMPLATE_DEFAULTS.get(key, ''))

def apply_template(text, **kwargs):
    """Replace [Key] placeholders in text with provided values."""
    for key, value in kwargs.items():
        text = text.replace(f'[{key}]', str(value) if value is not None else '')
    return text

def parse_amount(s):
    """Parse a user-supplied decimal string, accepting both '.' and ',' as separator."""
    if s is None:
        return 0.0
    return float(str(s).strip().replace(',', '.'))

def fmt_amount(value):
    """Format a float with 2 decimal places using the configured decimal separator."""
    sep = get_setting('decimal_separator', '.')
    return f'{value:.2f}'.replace('.', sep)

@app.template_filter('money')
def money_filter(value):
    """Jinja filter: format a float as 2 decimal places using the configured decimal separator."""
    try:
        return fmt_amount(float(value))
    except (ValueError, TypeError):
        sep = get_setting('decimal_separator', '.')
        return '0' + sep + '00'

def hex_to_rgb(hex_color):
    """Convert #rrggbb to 'r, g, b' string for CSS custom properties."""
    try:
        h = hex_color.lstrip('#')
        return f'{int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)}'
    except Exception:
        return '0, 0, 0'

def detect_theme():
    """Return the key of the active preset theme, or 'custom'."""
    color_keys = ['color_navbar', 'color_email_grad_start', 'color_email_grad_end',
                  'color_balance_positive', 'color_balance_negative']
    current = {k: get_tpl(k) for k in color_keys}
    for theme_key, theme in THEMES.items():
        if all(current[k] == theme[k] for k in color_keys):
            return theme_key
    return 'custom'

@app.context_processor
def inject_theme():
    """Inject theme colors into every template for dynamic CSS."""
    navbar  = get_tpl('color_navbar')
    pos     = get_tpl('color_balance_positive')
    neg     = get_tpl('color_balance_negative')
    return dict(
        theme_navbar=navbar,
        theme_navbar_rgb=hex_to_rgb(navbar),
        theme_balance_positive=pos,
        theme_balance_negative=neg,
        decimal_sep=get_setting('decimal_separator', '.'),
        currency_symbol=get_setting('currency_symbol', '€'),
    )

# Email logic
def build_email_html(user):
    tx_pref = user.email_transactions  # 'none' | 'last3' | 'this_week' | 'this_month'

    if tx_pref == 'none':
        recent_transactions = []
        show_tx_section = False
    else:
        show_tx_section = True
        base_q = Transaction.query.filter(
            (Transaction.from_user_id == user.id) | (Transaction.to_user_id == user.id)
        ).order_by(Transaction.date.desc())

        if tx_pref == 'last3':
            recent_transactions = base_q.limit(3).all()
        elif tx_pref == 'this_week':
            local_tz = pytz.timezone(get_setting('timezone', 'UTC'))
            now_lt = datetime.now(local_tz)
            week_start = (now_lt - timedelta(days=now_lt.weekday())).replace(
                            hour=0, minute=0, second=0, microsecond=0)
            week_start_utc = week_start.astimezone(pytz.UTC).replace(tzinfo=None)
            recent_transactions = base_q.filter(Transaction.date >= week_start_utc).all()
        elif tx_pref == 'this_month':
            local_tz = pytz.timezone(get_setting('timezone', 'UTC'))
            now_lt = datetime.now(local_tz)
            month_start = now_lt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_start_utc = month_start.astimezone(pytz.UTC).replace(tzinfo=None)
            recent_transactions = base_q.filter(Transaction.date >= month_start_utc).all()
        else:
            recent_transactions = base_q.limit(3).all()

    sym = get_setting('currency_symbol', '€')
    if user.balance < 0:
        balance_class = "color: #dc3545;"
        balance_status = f"You owe {sym}{fmt_amount(abs(user.balance))}"
    elif user.balance > 0:
        balance_class = "color: #28a745;"
        balance_status = f"You are owed {sym}{fmt_amount(user.balance)}"
    else:
        balance_class = "color: #6c757d;"
        balance_status = "Your balance is settled"

    transactions_section_html = ""
    if show_tx_section:
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
                        {amount_sign}{sym}{fmt_amount(trans.amount)}
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

        transactions_section_html = f"""
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
            </table>"""

    grad_start = get_tpl('color_email_grad_start')
    grad_end   = get_tpl('color_email_grad_end')
    tpl_vars   = dict(Name=user.name, Balance=f'{sym}{fmt_amount(user.balance)}',
                      BalanceStatus=balance_status, Date=now_local().strftime('%Y-%m-%d'))

    greeting = apply_template(get_tpl('tpl_email_greeting'), **tpl_vars)
    intro    = apply_template(get_tpl('tpl_email_intro'),    **tpl_vars)
    footer1  = apply_template(get_tpl('tpl_email_footer1'),  **tpl_vars)
    footer2  = apply_template(get_tpl('tpl_email_footer2'),  **tpl_vars)

    greeting_html = f'<p style="font-size: 16px; margin-bottom: 20px;">{greeting}</p>' if greeting.strip() else ''
    intro_html    = f'<p>{intro}</p>' if intro.strip() else ''
    footer1_html  = f'<p>{footer1}</p>' if footer1.strip() else ''
    footer2_html  = f'<p style="margin-top: 10px;">{footer2}</p>' if footer2.strip() else ''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, {grad_start} 0%, {grad_end} 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">🏦 Bank of Tina</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Weekly Balance Update</p>
        </div>

        <div style="background: white; padding: 30px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 10px 10px;">
            {greeting_html}
            {intro_html}

            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <p style="margin: 0 0 10px 0; color: #6c757d; text-transform: uppercase; font-size: 12px; font-weight: bold;">Current Balance</p>
                <h2 style="margin: 0; font-size: 36px; {balance_class}">{sym}{fmt_amount(user.balance)}</h2>
            </div>

            {transactions_section_html}

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 14px;">
                {footer1_html}
                {footer2_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html

def build_admin_summary_email(users, include_emails=False):
    sym        = get_setting('currency_symbol', '€')
    date_str   = now_local().strftime('%Y-%m-%d')
    grad_start = get_tpl('color_email_grad_start')
    grad_end   = get_tpl('color_email_grad_end')
    tpl_vars   = dict(Date=date_str, UserCount=len(users))

    intro  = apply_template(get_tpl('tpl_admin_intro'),  **tpl_vars)
    footer = apply_template(get_tpl('tpl_admin_footer'), **tpl_vars)

    intro_html  = f'<p style="margin-bottom:20px;">{intro}</p>' if intro.strip() else ''
    footer_html = f'<p>{footer}</p>' if footer.strip() else ''

    pos_color = get_tpl('color_balance_positive')
    neg_color = get_tpl('color_balance_negative')
    rows_html = ''
    for user in users:
        color = neg_color if user.balance < 0 else (pos_color if user.balance > 0 else '#6c757d')
        email_cell = f'<td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; color: #6c757d; font-size: 0.9em;">{user.email}</td>' if include_emails else ''
        rows_html += f"""
            <tr>
                <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6;">{user.name}</td>
                {email_cell}
                <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold; color: {color};">{sym}{fmt_amount(user.balance)}</td>
            </tr>"""

    email_header = '<th style="padding: 10px 8px; text-align: left; border-bottom: 2px solid #dee2e6;">Email</th>' if include_emails else ''

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, {grad_start} 0%, {grad_end} 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🏦 Bank of Tina</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Admin Summary — {date_str}</p>
    </div>
    <div style="background: white; padding: 30px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 10px 10px;">
        {intro_html}
        <h3 style="color: #495057; margin-top: 0;">All Active Users</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 10px 8px; text-align: left; border-bottom: 2px solid #dee2e6;">Name</th>
                    {email_header}
                    <th style="padding: 10px 8px; text-align: right; border-bottom: 2px solid #dee2e6;">Balance</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 13px;">
            {footer_html}
        </div>
    </div>
</body>
</html>"""


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
        return True, None
    except Exception as e:
        app.logger.error(f"Error sending email to {to_email}: {e}")
        return False, str(e)

def send_all_emails():
    if get_setting('email_enabled', '1') != '1':
        return 0, 0, ['Email sending is disabled in General settings.']

    all_active_users = User.query.filter_by(is_active=True).all()
    opted_in_users   = [u for u in all_active_users if u.email_opt_in]
    success, fail = 0, 0
    errors = []
    debug = get_setting('email_debug', '0') == '1'
    subject = apply_template(get_tpl('tpl_email_subject'), Date=now_local().strftime('%Y-%m-%d'))
    for user in opted_in_users:
        html = build_email_html(user)
        ok, err = send_single_email(user.email, user.name, subject, html)
        if ok:
            success += 1
            if debug:
                db.session.add(EmailLog(level='SUCCESS',
                                        recipient=f'{user.name} <{user.email}>',
                                        message='Email sent successfully'))
        else:
            fail += 1
            errors.append(f"{user.name} <{user.email}>: {err}")
            if debug:
                db.session.add(EmailLog(level='FAIL',
                                        recipient=f'{user.name} <{user.email}>',
                                        message=err or 'Unknown error'))

    # Admin summary email — always uses all active users regardless of opt-in
    admin_id = get_setting('site_admin_id', '')
    if get_setting('admin_summary_email', '0') == '1' and admin_id:
        admin = User.query.get(int(admin_id)) if admin_id.isdigit() else None
        if admin:
            summary_subject = apply_template(get_tpl('tpl_admin_subject'),
                                             Date=now_local().strftime('%Y-%m-%d'),
                                             UserCount=len(all_active_users))
            summary_html = build_admin_summary_email(all_active_users, include_emails=get_setting('admin_summary_include_emails', '0') == '1')
            ok, err = send_single_email(admin.email, admin.name, summary_subject, summary_html)
            if debug:
                if ok:
                    db.session.add(EmailLog(level='INFO', recipient=None,
                                            message=f'Admin summary sent to {admin.name} <{admin.email}>'))
                else:
                    db.session.add(EmailLog(level='FAIL', recipient=f'{admin.name} <{admin.email}>',
                                            message=f'Admin summary failed: {err}'))

    if debug:
        db.session.add(EmailLog(level='INFO', recipient=None,
                                message=f'Run complete: {success} sent, {fail} failed'))
        db.session.commit()
        oldest_kept = (EmailLog.query.order_by(EmailLog.id.desc()).offset(500).first())
        if oldest_kept:
            EmailLog.query.filter(EmailLog.id <= oldest_kept.id).delete()
        db.session.commit()

    return success, fail, errors

# Backup logic
def _backup_log(level, message):
    db.session.add(BackupLog(level=level, message=message))
    db.session.commit()

def run_backup():
    """Create a full backup tar.gz in BACKUP_DIR. Returns (True, filename) or (False, error_msg)."""
    debug = get_setting('backup_debug', '0') == '1'

    def log(level, msg):
        if debug:
            _backup_log(level, msg)

    ts = now_local().strftime('%Y_%m_%d_%H-%M-%S')
    filename = f'bot_backup_{ts}.tar.gz'
    dest = os.path.join(BACKUP_DIR, filename)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            # 1. SQL dump written directly to file (no memory buffering)
            dump_path = os.path.join(tmp, 'dump.sql')
            with open(dump_path, 'wb') as dump_file:
                result = subprocess.run(
                    ['mysqldump', '-h', _db_host, '-P', _db_port,
                     f'-u{_db_user}', f'-p{_db_pass}',
                     '--add-drop-table', _db_name],
                    stdout=dump_file, stderr=subprocess.PIPE, timeout=300
                )
            if result.returncode != 0:
                err = result.stderr.decode(errors='replace')[:300]
                log('ERROR', f'mysqldump failed: {err}')
                return False, f'mysqldump failed: {err}'
            log('INFO', 'SQL dump created')

            # 2. Copy receipts
            receipts_dest = os.path.join(tmp, 'receipts')
            upload_folder = app.config['UPLOAD_FOLDER']
            if os.path.exists(upload_folder):
                shutil.copytree(upload_folder, receipts_dest)
            else:
                os.makedirs(receipts_dest)
            log('INFO', 'Receipts copied')

            # 3. Reconstruct .env from environment variables
            env_keys = ['DB_ROOT_PASSWORD', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
                        'SECRET_KEY', 'SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME',
                        'SMTP_PASSWORD', 'FROM_EMAIL', 'FROM_NAME']
            env_lines = [f'{k}={os.environ.get(k, "")}' for k in env_keys if os.environ.get(k)]
            with open(os.path.join(tmp, '.env'), 'w') as f:
                f.write('\n'.join(env_lines) + '\n')
            log('INFO', '.env reconstructed')

            # 4. Create tar.gz
            with tarfile.open(dest, 'w:gz') as tar:
                tar.add(dump_path, arcname='dump.sql')
                tar.add(receipts_dest, arcname='receipts')
                tar.add(os.path.join(tmp, '.env'), arcname='.env')

        log('SUCCESS', f'Backup created: {filename}')
        return True, filename

    except Exception as e:
        err = str(e)[:300]
        log('ERROR', err)
        if os.path.exists(dest):
            os.remove(dest)
        return False, err


def _prune_old_backups(keep):
    """Delete oldest backups keeping only the most recent `keep` files."""
    if keep <= 0:
        return
    files = sorted([
        f for f in os.listdir(BACKUP_DIR)
        if re.match(r'^bot_backup_[\d_-]+\.tar\.gz$', f)
    ])
    while len(files) > keep:
        os.remove(os.path.join(BACKUP_DIR, files.pop(0)))


def _list_backups():
    """Return list of dicts with backup file info, newest first."""
    backups = []
    if os.path.exists(BACKUP_DIR):
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if re.match(r'^bot_backup_[\d_-]+\.tar\.gz$', f):
                fpath = os.path.join(BACKUP_DIR, f)
                stat = os.stat(fpath)
                backups.append({
                    'filename': f,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                })
    return backups


# APScheduler
scheduler = BackgroundScheduler(daemon=True)

def _add_email_job():
    day    = get_setting('schedule_day', 'mon')
    hour   = int(get_setting('schedule_hour', '9'))
    minute = int(get_setting('schedule_minute', '0'))
    tz_name = get_setting('timezone', 'UTC')
    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC

    def job():
        with app.app_context():
            send_all_emails()

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      timezone=tz, id='email_job', replace_existing=True)

def auto_collect_common():
    from sqlalchemy import func
    debug = get_setting('common_auto_debug', '0') == '1'
    added_count = 0
    skip_count = 0

    if get_setting('common_items_auto', '0') == '1':
        threshold = int(get_setting('common_items_threshold', '5'))
        blacklisted = {b.value.lower() for b in CommonBlacklist.query.filter_by(type='item').all()}
        rows = (db.session.query(ExpenseItem.item_name, func.count(ExpenseItem.id))
                          .group_by(ExpenseItem.item_name)
                          .having(func.count(ExpenseItem.id) >= threshold).all())
        for name, _ in rows:
            if name.lower() in blacklisted:
                if debug:
                    db.session.add(AutoCollectLog(level='SKIP', category='item',
                                                  message=f'"{name}" (blacklist)'))
                skip_count += 1
            elif not CommonItem.query.filter_by(name=name).first():
                db.session.add(CommonItem(name=name))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='item',
                                                  message=f'Added "{name}"'))
                added_count += 1

    if get_setting('common_descriptions_auto', '0') == '1':
        threshold = int(get_setting('common_descriptions_threshold', '5'))
        blacklisted = {b.value.lower() for b in CommonBlacklist.query.filter_by(type='description').all()}
        rows = (db.session.query(Transaction.description, func.count(Transaction.id))
                          .group_by(Transaction.description)
                          .having(func.count(Transaction.id) >= threshold).all())
        for desc, _ in rows:
            if desc.lower() in blacklisted:
                if debug:
                    db.session.add(AutoCollectLog(level='SKIP', category='description',
                                                  message=f'"{desc}" (blacklist)'))
                skip_count += 1
            elif not CommonDescription.query.filter_by(value=desc).first():
                db.session.add(CommonDescription(value=desc))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='description',
                                                  message=f'Added "{desc}"'))
                added_count += 1

    if get_setting('common_prices_auto', '0') == '1':
        threshold = int(get_setting('common_prices_threshold', '5'))
        blacklisted = {b.value for b in CommonBlacklist.query.filter_by(type='price').all()}
        rows = (db.session.query(ExpenseItem.price, func.count(ExpenseItem.id))
                          .group_by(ExpenseItem.price)
                          .having(func.count(ExpenseItem.id) >= threshold).all())
        for price, _ in rows:
            price_str = f"{price:.2f}"
            if price_str in blacklisted:
                if debug:
                    db.session.add(AutoCollectLog(level='SKIP', category='price',
                                                  message=f'€{price_str} (blacklist)'))
                skip_count += 1
            elif not CommonPrice.query.filter_by(value=price).first():
                db.session.add(CommonPrice(value=price))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='price',
                                                  message=f'Added €{price_str}'))
                added_count += 1

    if debug:
        db.session.add(AutoCollectLog(level='INFO', category='system',
                                      message=f'Run complete: {added_count} added, {skip_count} skipped'))
    db.session.commit()

    # Prune log table to last 500 entries
    if debug:
        oldest_kept = (AutoCollectLog.query
                       .order_by(AutoCollectLog.id.desc())
                       .offset(500).first())
        if oldest_kept:
            AutoCollectLog.query.filter(AutoCollectLog.id <= oldest_kept.id).delete()
        db.session.commit()


def _add_common_job():
    day    = get_setting('common_auto_day', '*')
    hour   = int(get_setting('common_auto_hour', '2'))
    minute = int(get_setting('common_auto_minute', '0'))
    try:
        tz = pytz.timezone(get_setting('timezone', 'UTC'))
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC

    def job():
        with app.app_context():
            auto_collect_common()

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      timezone=tz, id='common_job', replace_existing=True)


def build_backup_status_email(ok, result, kept, pruned):
    date_str   = now_local().strftime('%Y-%m-%d %H:%M')
    grad_start = get_tpl('color_email_grad_start')
    grad_end   = get_tpl('color_email_grad_end')
    footer     = apply_template(get_tpl('tpl_backup_footer'), Date=date_str)
    footer_html = f'<p>{footer}</p>' if footer.strip() else ''

    if ok:
        status_color = '#28a745'
        status_icon  = '✔'
        status_text  = 'Backup completed successfully'
        detail_rows  = f"""
            <tr><td style="padding:8px;color:#6c757d;width:140px;">File</td>
                <td style="padding:8px;font-family:monospace;">{result}</td></tr>
            <tr><td style="padding:8px;color:#6c757d;">Backups kept</td>
                <td style="padding:8px;">{kept}</td></tr>"""
        if pruned:
            detail_rows += f"""
            <tr><td style="padding:8px;color:#6c757d;">Pruned</td>
                <td style="padding:8px;">{pruned} old backup(s) deleted</td></tr>"""
    else:
        status_color = '#dc3545'
        status_icon  = '✘'
        status_text  = 'Backup failed'
        detail_rows  = f"""
            <tr><td style="padding:8px;color:#6c757d;width:140px;">Error</td>
                <td style="padding:8px;color:#dc3545;">{result}</td></tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height:1.6; color:#333; max-width:600px; margin:0 auto; padding:20px;">
    <div style="background:linear-gradient(135deg,{grad_start} 0%,{grad_end} 100%); color:white; padding:30px; border-radius:10px 10px 0 0; text-align:center;">
        <h1 style="margin:0; font-size:28px;">🏦 Bank of Tina</h1>
        <p style="margin:10px 0 0 0; opacity:0.9;">Scheduled Backup Report — {date_str}</p>
    </div>
    <div style="background:white; padding:30px; border:1px solid #dee2e6; border-top:none; border-radius:0 0 10px 10px;">
        <div style="background:#f8f9fa; padding:16px 20px; border-radius:8px; margin-bottom:24px; border-left:4px solid {status_color};">
            <span style="font-size:1.1em; font-weight:bold; color:{status_color};">{status_icon} {status_text}</span>
        </div>
        <table style="width:100%; border-collapse:collapse; font-size:0.95em;">
            <tbody>{detail_rows}
            </tbody>
        </table>
        <div style="margin-top:24px; padding-top:16px; border-top:1px solid #dee2e6; text-align:center; color:#6c757d; font-size:13px;">
            {footer_html}
        </div>
    </div>
</body>
</html>"""


def _add_backup_job():
    day    = get_setting('backup_day', '*')
    hour   = int(get_setting('backup_hour', '3'))
    minute = int(get_setting('backup_minute', '0'))
    keep   = int(get_setting('backup_keep', '7'))
    try:
        tz = pytz.timezone(get_setting('timezone', 'UTC'))
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC

    def job():
        with app.app_context():
            ok, result = run_backup()
            pruned = 0
            if ok and keep > 0:
                before = len(_list_backups())
                _prune_old_backups(keep)
                pruned = max(0, before - len(_list_backups()))

            if get_setting('backup_admin_email', '0') == '1':
                admin_id = get_setting('site_admin_id', '')
                admin = User.query.get(int(admin_id)) if admin_id.isdigit() else None
                if admin:
                    kept = len(_list_backups())
                    html = build_backup_status_email(ok, result, kept, pruned)
                    subject = apply_template(get_tpl('tpl_backup_subject'),
                                             Date=now_local().strftime('%Y-%m-%d'),
                                             BackupStatus='Success' if ok else 'Failed')
                    send_single_email(admin.email, admin.name, subject, html)

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      timezone=tz, id='backup_job', replace_existing=True)


def _migrate_db():
    """Add any new columns to existing tables that db.create_all() won't add."""
    with db.engine.connect() as conn:
        for col, definition in [
            ('email_opt_in',       'BOOLEAN NOT NULL DEFAULT 1'),
            ('email_transactions', "VARCHAR(20) NOT NULL DEFAULT 'last3'"),
        ]:
            try:
                conn.execute(db.text(f'ALTER TABLE user ADD COLUMN {col} {definition}'))
                conn.commit()
            except Exception:
                pass
        try:
            conn.execute(db.text('ALTER TABLE `transaction` ADD COLUMN notes TEXT'))
            conn.commit()
        except Exception:
            pass


def _restore_schedule():
    if get_setting('schedule_enabled') == '1':
        _add_email_job()
    if get_setting('common_auto_enabled', '0') == '1':
        _add_common_job()
    if get_setting('backup_enabled', '0') == '1':
        _add_backup_job()

def parse_submitted_date(date_str):
    """Parse a datetime-local string entered in the app timezone and return a naive UTC datetime."""
    if not date_str:
        return datetime.utcnow()
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            naive = datetime.strptime(date_str, fmt)
            tz_name = get_setting('timezone', 'UTC')
            tz = pytz.timezone(tz_name)
            return tz.localize(naive).astimezone(pytz.UTC).replace(tzinfo=None)
        except (ValueError, pytz.exceptions.UnknownTimeZoneError):
            continue
    return datetime.utcnow()


# Timezone helpers
def get_app_tz():
    """Return the configured pytz timezone, cached for the duration of the request."""
    if 'app_tz' not in g:
        tz_name = get_setting('timezone', 'UTC')
        try:
            g.app_tz = pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            g.app_tz = pytz.UTC
    return g.app_tz

def to_local(dt):
    """Convert a naive UTC datetime to the configured local timezone."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(get_app_tz())

@app.template_filter('localdt')
def localdt_filter(dt, fmt='%Y-%m-%d %H:%M'):
    if dt is None:
        return ''
    return to_local(dt).strftime(fmt)


# Routes
@app.route('/')
def index():
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    count = int(get_setting('recent_transactions_count', '5'))
    recent = Transaction.query.order_by(Transaction.date.desc()).limit(count).all() if count else []
    show_email = get_setting('show_email_on_dashboard', '0') == '1'
    return render_template('index.html', users=users, transactions=recent, show_recent=count > 0,
                           show_email=show_email)

VALID_EMAIL_TX = {'none', 'last3', 'this_week', 'this_month'}

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

    email_opt_in = request.form.get('email_opt_in') == '1'
    email_transactions = request.form.get('email_transactions', 'last3')
    if email_transactions not in VALID_EMAIL_TX:
        email_transactions = 'last3'

    user = User(name=name, email=email,
                email_opt_in=email_opt_in,
                email_transactions=email_transactions)
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
    user.email_opt_in = request.form.get('email_opt_in') == '1'
    email_transactions = request.form.get('email_transactions', 'last3')
    if email_transactions not in VALID_EMAIL_TX:
        email_transactions = 'last3'
    user.email_transactions = email_transactions
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
        default_date = datetime.now(get_app_tz()).strftime('%Y-%m-%dT%H:%M')
        return render_template('add_transaction.html', users=users,
                               default_item_rows=default_item_rows, default_date=default_date)

    transaction_type = request.form.get('transaction_type')

    submitted_date = parse_submitted_date(request.form.get('date', ''))
    notes = request.form.get('notes', '').strip() or None

    if transaction_type == 'deposit':
        user_id = int(request.form.get('user_id'))
        amount = parse_amount(request.form.get('amount'))
        description = request.form.get('description', 'Deposit')

        transaction = Transaction(
            description=description,
            amount=amount,
            to_user_id=user_id,
            transaction_type='deposit',
            date=submitted_date,
            notes=notes
        )
        db.session.add(transaction)
        update_balance(user_id, amount)
        flash(f'Deposit of €{fmt_amount(amount)} added successfully!', 'success')

    elif transaction_type == 'withdrawal':
        user_id = int(request.form.get('user_id'))
        amount = parse_amount(request.form.get('amount'))
        description = request.form.get('description', 'Withdrawal')

        transaction = Transaction(
            description=description,
            amount=amount,
            from_user_id=user_id,
            transaction_type='withdrawal',
            date=submitted_date,
            notes=notes
        )
        db.session.add(transaction)
        update_balance(user_id, -amount)
        flash(f'Withdrawal of €{fmt_amount(amount)} processed successfully!', 'success')

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
                price = parse_amount(item['price'])
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
                    receipt_path=receipt_path,
                    date=submitted_date,
                    notes=notes
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
                            price=parse_amount(item['price']),
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
        by_day[to_local(t.date).date()].append(t)
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

@app.route('/search')
def search():
    q           = request.args.get('q', '').strip()
    tx_type     = request.args.get('type', '')
    user_id     = request.args.get('user', None, type=int)
    date_from   = request.args.get('date_from', '')
    date_to     = request.args.get('date_to', '')
    amount_min  = request.args.get('amount_min', '')
    amount_max  = request.args.get('amount_max', '')
    has_receipt = request.args.get('has_receipt', '')

    searched = any([q, tx_type, user_id, date_from, date_to, amount_min, amount_max, has_receipt])
    results  = []

    if searched:
        qry = Transaction.query

        if q:
            qry = qry.filter(
                db.or_(
                    Transaction.description.ilike(f'%{q}%'),
                    Transaction.notes.ilike(f'%{q}%'),
                    Transaction.items.any(ExpenseItem.item_name.ilike(f'%{q}%'))
                )
            )
        if tx_type:
            qry = qry.filter(Transaction.transaction_type == tx_type)
        if user_id:
            qry = qry.filter(
                db.or_(Transaction.from_user_id == user_id,
                       Transaction.to_user_id   == user_id)
            )
        if date_from:
            try:
                qry = qry.filter(Transaction.date >= datetime.strptime(date_from, '%Y-%m-%d'))
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                qry = qry.filter(Transaction.date <= dt)
            except ValueError:
                pass
        if amount_min:
            try:
                qry = qry.filter(Transaction.amount >= parse_amount(amount_min))
            except (ValueError, TypeError):
                pass
        if amount_max:
            try:
                qry = qry.filter(Transaction.amount <= parse_amount(amount_max))
            except (ValueError, TypeError):
                pass
        if has_receipt:
            qry = qry.filter(Transaction.receipt_path.isnot(None),
                             Transaction.receipt_path != '')

        results = qry.order_by(Transaction.date.desc()).all()

    all_users = User.query.filter_by(is_active=True).order_by(User.name).all()
    return render_template('search.html',
        results=results, searched=searched, all_users=all_users,
        q=q, tx_type=tx_type, user_id=user_id,
        date_from=date_from, date_to=date_to,
        amount_min=amount_min, amount_max=amount_max,
        has_receipt=has_receipt)


@app.route('/user/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    transactions = Transaction.query.filter(
        (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
    ).order_by(Transaction.date.desc()).limit(5).all()
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
    trans.notes = request.form.get('notes', '').strip() or None

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
                    price = parse_amount(item['price'])
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
            trans.amount = parse_amount(request.form.get('amount', old_amount))
        except (ValueError, TypeError):
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

    # Receipt: remove first, then upload (upload wins if both submitted)
    if request.form.get('remove_receipt'):
        delete_receipt_file(trans.receipt_path, trans.id)
        trans.receipt_path = None

    new_file = request.files.get('receipt')
    if new_file and new_file.filename:
        # Delete old file if there was one and we're replacing it
        if trans.receipt_path:
            delete_receipt_file(trans.receipt_path, trans.id)
        buyer = User.query.get(trans.from_user_id) if trans.from_user_id else None
        buyer_name = buyer.name if buyer else 'unknown'
        saved = save_receipt(new_file, buyer_name)
        if saved:
            trans.receipt_path = saved

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

    delete_receipt_file(trans.receipt_path, trans.id)
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
        'site_admin_id': get_setting('site_admin_id', ''),
        'email_enabled': get_setting('email_enabled', '1'),
        'email_debug': get_setting('email_debug', '0'),
        'admin_summary_email': get_setting('admin_summary_email', '0'),
        'timezone': get_setting('timezone', 'UTC'),
        'common_enabled':                get_setting('common_enabled', '1'),
        'common_auto_enabled':           get_setting('common_auto_enabled', '0'),
        'common_auto_debug':             get_setting('common_auto_debug', '0'),
        'common_auto_day':               get_setting('common_auto_day', '*'),
        'common_auto_hour':              get_setting('common_auto_hour', '2'),
        'common_auto_minute':            get_setting('common_auto_minute', '0'),
        'common_items_auto':             get_setting('common_items_auto', '0'),
        'common_items_threshold':        get_setting('common_items_threshold', '5'),
        'common_descriptions_auto':      get_setting('common_descriptions_auto', '0'),
        'common_descriptions_threshold': get_setting('common_descriptions_threshold', '5'),
        'common_prices_auto':            get_setting('common_prices_auto', '0'),
        'common_prices_threshold':       get_setting('common_prices_threshold', '5'),
        # Templates
        'color_navbar':             get_tpl('color_navbar'),
        'color_email_grad_start':   get_tpl('color_email_grad_start'),
        'color_email_grad_end':     get_tpl('color_email_grad_end'),
        'color_balance_positive':   get_tpl('color_balance_positive'),
        'color_balance_negative':   get_tpl('color_balance_negative'),
        'tpl_email_subject':   get_tpl('tpl_email_subject'),
        'tpl_email_greeting':  get_tpl('tpl_email_greeting'),
        'tpl_email_intro':     get_tpl('tpl_email_intro'),
        'tpl_email_footer1':   get_tpl('tpl_email_footer1'),
        'tpl_email_footer2':   get_tpl('tpl_email_footer2'),
        'tpl_admin_subject':   get_tpl('tpl_admin_subject'),
        'tpl_admin_intro':     get_tpl('tpl_admin_intro'),
        'tpl_admin_footer':    get_tpl('tpl_admin_footer'),
        'admin_summary_include_emails': get_setting('admin_summary_include_emails', '0'),
        'tpl_backup_subject':  get_tpl('tpl_backup_subject'),
        'tpl_backup_footer':   get_tpl('tpl_backup_footer'),
        # Backup
        'backup_enabled':      get_setting('backup_enabled',      '0'),
        'backup_debug':        get_setting('backup_debug',        '0'),
        'backup_admin_email':  get_setting('backup_admin_email',  '0'),
        'backup_day':          get_setting('backup_day',          '*'),
        'backup_hour':         get_setting('backup_hour',         '3'),
        'backup_minute':       get_setting('backup_minute',       '0'),
        'backup_keep':         get_setting('backup_keep',         '7'),
        'decimal_separator':         get_setting('decimal_separator',         '.'),
        'currency_symbol':           get_setting('currency_symbol',           '€'),
        'show_email_on_dashboard':   get_setting('show_email_on_dashboard',   '0'),
    }
    common_items        = CommonItem.query.order_by(CommonItem.name).all()
    common_descriptions = CommonDescription.query.order_by(CommonDescription.value).all()
    common_prices       = CommonPrice.query.order_by(CommonPrice.value).all()
    common_blacklist    = CommonBlacklist.query.order_by(CommonBlacklist.type, CommonBlacklist.value).all()
    auto_collect_logs   = AutoCollectLog.query.order_by(AutoCollectLog.id.desc()).limit(500).all()
    email_logs          = EmailLog.query.order_by(EmailLog.id.desc()).limit(500).all()
    backup_logs         = BackupLog.query.order_by(BackupLog.id.desc()).limit(500).all()
    backups             = _list_backups()
    all_users = User.query.order_by(User.name).all()
    timezone_groups = {}
    for tz in pytz.common_timezones:
        region = tz.split('/')[0]
        timezone_groups.setdefault(region, []).append(tz)
    return render_template('settings.html', cfg=cfg, common_items=common_items,
                           common_descriptions=common_descriptions, common_prices=common_prices,
                           common_blacklist=common_blacklist, auto_collect_logs=auto_collect_logs,
                           email_logs=email_logs, backup_logs=backup_logs, backups=backups,
                           all_users=all_users, timezone_groups=timezone_groups,
                           themes=THEMES, current_theme=detect_theme())

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

    set_setting('email_enabled',       '1' if request.form.get('email_enabled')       else '0')
    set_setting('email_debug',         '1' if request.form.get('email_debug')         else '0')
    set_setting('admin_summary_email', '1' if request.form.get('admin_summary_email') else '0')

    flash('Settings saved.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/send-now', methods=['POST'])
def settings_send_now():
    success, fail, errors = send_all_emails()
    flash(f'{success} email(s) sent, {fail} failed.', 'success' if fail == 0 else 'error')
    if errors and get_setting('email_debug', '0') == '1':
        for err in errors:
            flash(f'Debug: {err}', 'error')
    return redirect(url_for('settings'))

@app.route('/settings/email/clear-log', methods=['POST'])
def settings_email_clear_log():
    EmailLog.query.delete()
    db.session.commit()
    flash('Email debug log cleared.', 'success')
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
    timezone = request.form.get('timezone', 'UTC')
    if timezone in pytz.common_timezones:
        set_setting('timezone', timezone)
        if get_setting('schedule_enabled') == '1':
            _add_email_job()
        if get_setting('common_auto_enabled', '0') == '1':
            _add_common_job()
    admin_id = request.form.get('site_admin_id', '').strip()
    if admin_id == '' or (admin_id.isdigit() and User.query.get(int(admin_id))):
        set_setting('site_admin_id', admin_id)
    sep = request.form.get('decimal_separator', '.')
    if sep not in ('.', ','):
        sep = '.'
    set_setting('decimal_separator', sep)
    set_setting('currency_symbol', request.form.get('currency_symbol', '€'))
    set_setting('show_email_on_dashboard', '1' if request.form.get('show_email_on_dashboard') else '0')
    flash('General settings saved.', 'success')
    return redirect(url_for('settings'))


@app.route('/api/common-items')
def api_common_items():
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = CommonItem.query.order_by(CommonItem.name).all()
    return jsonify([{'id': i.id, 'name': i.name} for i in items])

@app.route('/api/common-descriptions')
def api_common_descriptions():
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = CommonDescription.query.order_by(CommonDescription.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

@app.route('/api/common-prices')
def api_common_prices():
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = CommonPrice.query.order_by(CommonPrice.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])

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

@app.route('/settings/common-descriptions/add', methods=['POST'])
def add_common_description():
    value = request.form.get('value', '').strip()
    if not value:
        flash('Description is required.', 'error')
        return redirect(url_for('settings'))
    if not CommonDescription.query.filter_by(value=value).first():
        db.session.add(CommonDescription(value=value))
        db.session.commit()
    flash(f'"{value}" added to common descriptions.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-descriptions/<int:item_id>/delete', methods=['POST'])
def delete_common_description(item_id):
    item = CommonDescription.query.get_or_404(item_id)
    value = item.value
    db.session.delete(item)
    db.session.commit()
    flash(f'"{value}" removed from common descriptions.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-prices/add', methods=['POST'])
def add_common_price():
    try:
        value = parse_amount(request.form.get('value', ''))
    except (ValueError, TypeError):
        flash('Valid price is required.', 'error')
        return redirect(url_for('settings'))
    if not CommonPrice.query.filter_by(value=value).first():
        db.session.add(CommonPrice(value=value))
        db.session.commit()
    flash(f'€{fmt_amount(value)} added to common prices.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-prices/<int:item_id>/delete', methods=['POST'])
def delete_common_price(item_id):
    item = CommonPrice.query.get_or_404(item_id)
    value = item.value
    db.session.delete(item)
    db.session.commit()
    flash(f'€{fmt_amount(value)} removed from common prices.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-blacklist/add', methods=['POST'])
def add_common_blacklist():
    bl_type = request.form.get('type', '').strip()
    value   = request.form.get('value', '').strip()
    if bl_type not in ('item', 'description', 'price') or not value:
        flash('Invalid blacklist entry.', 'error')
        return redirect(url_for('settings'))
    if not CommonBlacklist.query.filter_by(type=bl_type, value=value).first():
        db.session.add(CommonBlacklist(type=bl_type, value=value))
        db.session.commit()
    flash(f'"{value}" added to {bl_type} blacklist.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-blacklist/<int:item_id>/delete', methods=['POST'])
def delete_common_blacklist(item_id):
    item = CommonBlacklist.query.get_or_404(item_id)
    value, bl_type = item.value, item.type
    db.session.delete(item)
    db.session.commit()
    flash(f'"{value}" removed from {bl_type} blacklist.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common', methods=['POST'])
def settings_common():
    enabled = '1' if request.form.get('common_enabled') else '0'
    set_setting('common_enabled', enabled)
    flash('Common autocomplete settings saved.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-auto', methods=['POST'])
def settings_common_auto():
    enabled = '1' if request.form.get('common_auto_enabled') else '0'
    debug   = '1' if request.form.get('common_auto_debug')   else '0'
    day     = request.form.get('common_auto_day', '*')
    try:
        hour   = str(max(0, min(23, int(request.form.get('common_auto_hour',   '2')))))
        minute = str(max(0, min(55, int(request.form.get('common_auto_minute', '0')))))
    except ValueError:
        hour, minute = '2', '0'
    items_auto = '1' if request.form.get('common_items_auto') else '0'
    try:
        items_threshold = str(max(1, int(request.form.get('common_items_threshold', '5'))))
    except ValueError:
        items_threshold = '5'
    descriptions_auto = '1' if request.form.get('common_descriptions_auto') else '0'
    try:
        descriptions_threshold = str(max(1, int(request.form.get('common_descriptions_threshold', '5'))))
    except ValueError:
        descriptions_threshold = '5'
    prices_auto = '1' if request.form.get('common_prices_auto') else '0'
    try:
        prices_threshold = str(max(1, int(request.form.get('common_prices_threshold', '5'))))
    except ValueError:
        prices_threshold = '5'

    set_setting('common_auto_enabled',           enabled)
    set_setting('common_auto_debug',             debug)
    set_setting('common_auto_day',               day)
    set_setting('common_auto_hour',              hour)
    set_setting('common_auto_minute',            minute)
    set_setting('common_items_auto',             items_auto)
    set_setting('common_items_threshold',        items_threshold)
    set_setting('common_descriptions_auto',      descriptions_auto)
    set_setting('common_descriptions_threshold', descriptions_threshold)
    set_setting('common_prices_auto',            prices_auto)
    set_setting('common_prices_threshold',       prices_threshold)

    if enabled == '1':
        _add_common_job()
        flash('Auto-collect schedule saved and enabled.', 'success')
    else:
        if scheduler.get_job('common_job'):
            scheduler.remove_job('common_job')
        flash('Auto-collect schedule disabled.', 'success')

    return redirect(url_for('settings'))

@app.route('/settings/common-auto/run', methods=['POST'])
def settings_common_auto_run():
    auto_collect_common()
    flash('Auto-collect job ran successfully.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/common-auto/clear-log', methods=['POST'])
def settings_common_auto_clear_log():
    AutoCollectLog.query.delete()
    db.session.commit()
    flash('Debug log cleared.', 'success')
    return redirect(url_for('settings'))


# ── Templates routes ──────────────────────────────────────────────────────

@app.route('/settings/templates', methods=['POST'])
def settings_templates():
    color_keys = ['color_navbar', 'color_email_grad_start', 'color_email_grad_end',
                  'color_balance_positive', 'color_balance_negative']
    for key in color_keys:
        val = request.form.get(key, '').strip()
        if re.match(r'^#[0-9a-fA-F]{6}$', val):
            set_setting(key, val)

    text_keys = ['tpl_email_subject', 'tpl_email_greeting', 'tpl_email_intro',
                 'tpl_email_footer1', 'tpl_email_footer2',
                 'tpl_admin_subject', 'tpl_admin_intro', 'tpl_admin_footer',
                 'tpl_backup_subject', 'tpl_backup_footer']
    for key in text_keys:
        set_setting(key, request.form.get(key, '')[:500])

    set_setting('admin_summary_include_emails', '1' if request.form.get('admin_summary_include_emails') else '0')

    flash('Templates saved.', 'success')
    return redirect(url_for('settings'))


@app.route('/settings/templates/reset', methods=['POST'])
def settings_templates_reset():
    for key, val in TEMPLATE_DEFAULTS.items():
        set_setting(key, val)
    flash('Templates reset to defaults.', 'success')
    return redirect(url_for('settings'))


@app.route('/settings/templates/preview/email')
def preview_email():
    user = User.query.filter_by(is_active=True).order_by(User.name).first()
    if not user:
        class _Dummy:
            name = 'Jane Doe'; email = 'jane@example.com'; balance = 12.50; id = 0
            from_user_id = None; to_user_id = None
        user = _Dummy()
        # patch recent_transactions query to return empty list
        user._dummy = True
    html = build_email_html(user)
    return html


@app.route('/settings/templates/preview/admin-summary')
def preview_admin_summary():
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    if not users:
        class _D:
            def __init__(self, n, e, b): self.name=n; self.email=e; self.balance=b
        users = [_D('Alice Smith','alice@example.com',24.50),
                 _D('Bob Jones','bob@example.com',-12.00),
                 _D('Carol White','carol@example.com',0.00)]
    return build_admin_summary_email(users, include_emails=get_setting('admin_summary_include_emails', '0') == '1')


@app.route('/settings/templates/preview/backup')
def preview_backup():
    return build_backup_status_email(
        True, f'bot_backup_{now_local().strftime("%Y_%m_%d")}_03-00-00.tar.gz', 5, 1)


# ── Backup / Restore routes ────────────────────────────────────────────────

BACKUP_FILENAME_RE = re.compile(r'^bot_backup_[\d_-]+\.tar\.gz$')

@app.route('/settings/backup', methods=['POST'])
def settings_backup():
    enabled = '1' if request.form.get('backup_enabled') else '0'
    debug   = '1' if request.form.get('backup_debug')   else '0'
    day     = request.form.get('backup_day', '*')
    try:
        hour   = str(max(0, min(23, int(request.form.get('backup_hour',   '3')))))
        minute = str(max(0, min(55, int(request.form.get('backup_minute', '0')))))
    except ValueError:
        hour, minute = '3', '0'
    try:
        keep = str(max(1, min(365, int(request.form.get('backup_keep', '7')))))
    except ValueError:
        keep = '7'

    admin_email = '1' if request.form.get('backup_admin_email') else '0'
    set_setting('backup_enabled',     enabled)
    set_setting('backup_debug',       debug)
    set_setting('backup_admin_email', admin_email)
    set_setting('backup_day',     day)
    set_setting('backup_hour',    hour)
    set_setting('backup_minute',  minute)
    set_setting('backup_keep',    keep)

    if enabled == '1':
        _add_backup_job()
        flash('Backup schedule saved and enabled.', 'success')
    else:
        if scheduler.get_job('backup_job'):
            scheduler.remove_job('backup_job')
        flash('Backup schedule disabled.', 'success')

    return redirect(url_for('settings'))


@app.route('/settings/backup/create', methods=['POST'])
def settings_backup_create():
    ok, result = run_backup()
    if ok:
        flash(f'Backup created: {result}', 'success')
    else:
        flash(f'Backup failed: {result}', 'error')
    return redirect(url_for('settings'))


@app.route('/settings/backup/clear-log', methods=['POST'])
def settings_backup_clear_log():
    BackupLog.query.delete()
    db.session.commit()
    flash('Backup debug log cleared.', 'success')
    return redirect(url_for('settings'))


@app.route('/backups/download/<filename>')
def backup_download(filename):
    from flask import send_from_directory
    if not BACKUP_FILENAME_RE.match(filename):
        abort(404)
    return send_from_directory(BACKUP_DIR, filename, as_attachment=True)


@app.route('/backups/delete/<filename>', methods=['POST'])
def backup_delete(filename):
    if not BACKUP_FILENAME_RE.match(filename):
        flash('Invalid filename.', 'error')
        return redirect(url_for('settings'))
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        flash(f'{filename} deleted.', 'success')
    else:
        flash('Backup file not found.', 'error')
    return redirect(url_for('settings'))


@app.route('/backups/upload-chunk', methods=['POST'])
def backup_upload_chunk():
    upload_id   = request.form.get('uploadId', '')
    chunk_index = request.form.get('chunkIndex', '')
    total_chunks = request.form.get('totalChunks', '')
    chunk_file  = request.files.get('chunk')

    if not re.match(r'^[a-f0-9\-]{36}$', upload_id):
        return jsonify({'error': 'Invalid upload ID'}), 400
    try:
        chunk_index  = int(chunk_index)
        total_chunks = int(total_chunks)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid chunk parameters'}), 400
    if not chunk_file:
        return jsonify({'error': 'No chunk data'}), 400

    tmp_dir = os.path.join(BACKUP_DIR, '.tmp', upload_id)
    os.makedirs(tmp_dir, exist_ok=True)
    chunk_file.save(os.path.join(tmp_dir, f'{chunk_index:05d}'))

    received = len([f for f in os.listdir(tmp_dir) if f.isdigit() or f[:-1].isdigit()])
    if received >= total_chunks:
        # Assemble chunks in order
        ts = now_local().strftime('%Y_%m_%d_%H-%M-%S')
        filename = f'bot_backup_{ts}.tar.gz'
        dest = os.path.join(BACKUP_DIR, filename)
        with open(dest, 'wb') as out:
            for i in range(total_chunks):
                chunk_path = os.path.join(tmp_dir, f'{i:05d}')
                with open(chunk_path, 'rb') as c:
                    out.write(c.read())
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({'done': True, 'filename': filename})

    return jsonify({'done': False, 'received': received, 'total': total_chunks})


@app.route('/backups/restore/<filename>', methods=['POST'])
def backup_restore(filename):
    if not BACKUP_FILENAME_RE.match(filename):
        flash('Invalid filename.', 'error')
        return redirect(url_for('settings'))

    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        flash('Backup file not found.', 'error')
        return redirect(url_for('settings'))

    try:
        with tempfile.TemporaryDirectory() as tmp:
            # Safe extraction — only allow known top-level entries
            with tarfile.open(path, 'r:gz') as tar:
                safe = [m for m in tar.getmembers()
                        if not m.name.startswith('/') and '..' not in m.name]
                tar.extractall(tmp, members=safe)

            # 1. Restore receipts FIRST — so if this fails, the DB is still untouched
            receipts_src = os.path.join(tmp, 'receipts')
            upload_folder = app.config['UPLOAD_FOLDER']
            if os.path.exists(receipts_src):
                # Clear contents without removing the directory itself
                # (it may be a bind-mount and can't be deleted)
                for item in os.listdir(upload_folder):
                    item_path = os.path.join(upload_folder, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                shutil.copytree(receipts_src, upload_folder, dirs_exist_ok=True)

            # 2. Restore database
            dump_path = os.path.join(tmp, 'dump.sql')
            if os.path.exists(dump_path):
                with open(dump_path, 'rb') as f:
                    result = subprocess.run(
                        ['mysql', '-h', _db_host, '-P', _db_port,
                         f'-u{_db_user}', f'-p{_db_pass}', _db_name],
                        stdin=f, stderr=subprocess.PIPE, timeout=300
                    )
                if result.returncode != 0:
                    err = result.stderr.decode(errors='replace')[:300]
                    flash(f'Database restore failed: {err}', 'error')
                    return redirect(url_for('settings'))

        flash(f'Restore from {filename} completed successfully. '
              f'Check the .env file inside the backup if credentials changed.', 'success')

    except Exception as e:
        flash(f'Restore failed: {str(e)[:200]}', 'error')

    return redirect(url_for('settings'))


# ── Analytics ──────────────────────────────────────────────────────────────

@app.route('/analytics')
def analytics():
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    today     = now_local().date()
    def_from  = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    def_to    = today.strftime('%Y-%m-%d')
    return render_template('analytics.html', users=users,
                           default_from=def_from, default_to=def_to)


@app.route('/analytics/data')
def analytics_data():
    today = now_local().date()

    # ── Parse filters ──────────────────────────────────────────────────────
    date_from_str = request.args.get('date_from', (today - timedelta(days=90)).strftime('%Y-%m-%d'))
    date_to_str   = request.args.get('date_to',   today.strftime('%Y-%m-%d'))
    users_param   = request.args.get('users', '')

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
    except ValueError:
        date_from = datetime.combine(today - timedelta(days=90), datetime.min.time())

    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        date_to = datetime.combine(today, datetime.min.time()).replace(hour=23, minute=59, second=59)

    if users_param:
        uid_list = [int(x) for x in users_param.split(',') if x.strip().isdigit()]
        users = User.query.filter(User.id.in_(uid_list)).order_by(User.name).all()
    else:
        users = User.query.filter_by(is_active=True).order_by(User.name).all()

    all_uid = [u.id for u in users]

    # ── Transactions in date+user filter window ────────────────────────────
    tx_q = Transaction.query.filter(
        Transaction.date >= date_from,
        Transaction.date <= date_to,
    )
    if all_uid:
        tx_q = tx_q.filter(
            (Transaction.from_user_id.in_(all_uid)) | (Transaction.to_user_id.in_(all_uid))
        )
    transactions = tx_q.order_by(Transaction.date).all()

    delta_days = (date_to.date() - date_from.date()).days

    # ── 1. Current Balances ────────────────────────────────────────────────
    balances = [{'name': u.name, 'balance': round(u.balance, 2)} for u in users]

    # ── 2. Balance History ─────────────────────────────────────────────────
    # Build sample date points across the selected range
    sample_dates = []
    if delta_days <= 90:
        d = date_from.date()
        while d <= date_to.date():
            sample_dates.append(d)
            d += timedelta(days=7)
    else:
        y, m = date_from.year, date_from.month
        while True:
            sample_dates.append(datetime(y, m, 1).date())
            m += 1
            if m > 12:
                m, y = 1, y + 1
            if datetime(y, m, 1).date() > date_to.date():
                break
    if not sample_dates or sample_dates[-1] < date_to.date():
        sample_dates.append(date_to.date())

    history_labels   = [d.strftime('%Y-%m-%d') for d in sample_dates]
    history_datasets = {}

    for user in users:
        # Need ALL of this user's transactions to walk balance backwards from now
        all_user_tx = Transaction.query.filter(
            (Transaction.from_user_id == user.id) | (Transaction.to_user_id == user.id)
        ).all()

        series = []
        for d in sample_dates:
            cutoff = datetime.combine(d, datetime.max.time())
            bal = user.balance
            for tx in all_user_tx:
                if tx.date > cutoff:
                    if tx.to_user_id == user.id:
                        bal -= tx.amount
                    elif tx.from_user_id == user.id:
                        bal += tx.amount
            series.append(round(bal, 2))

        history_datasets[user.name] = series

    # ── 3. Transaction Volume ──────────────────────────────────────────────
    vol = defaultdict(lambda: {'count': 0, 'amount': 0.0})
    for tx in transactions:
        if delta_days <= 90:
            # Group by week (Monday)
            key = (tx.date.date() - timedelta(days=tx.date.weekday())).strftime('%Y-%m-%d')
        else:
            key = tx.date.strftime('%Y-%m')
        vol[key]['count']  += 1
        vol[key]['amount'] += tx.amount

    sorted_vol_keys = sorted(vol.keys())
    if delta_days <= 90:
        vol_labels = [datetime.strptime(k, '%Y-%m-%d').strftime('%b %d') for k in sorted_vol_keys]
    else:
        vol_labels = [datetime.strptime(k + '-01', '%Y-%m-%d').strftime('%b %Y') for k in sorted_vol_keys]

    transaction_volume = {
        'labels':  vol_labels,
        'counts':  [vol[k]['count']           for k in sorted_vol_keys],
        'amounts': [round(vol[k]['amount'], 2) for k in sorted_vol_keys],
    }

    # ── 4. Top Expense Items ───────────────────────────────────────────────
    expense_ids = [tx.id for tx in transactions if tx.transaction_type == 'expense']
    item_stats  = defaultdict(lambda: {'count': 0, 'total': 0.0})

    if expense_ids:
        for item in ExpenseItem.query.filter(ExpenseItem.transaction_id.in_(expense_ids)).all():
            name = item.item_name.strip()
            item_stats[name]['count'] += 1
            item_stats[name]['total'] += item.price

    top_sorted = sorted(item_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:15]
    top_items = {
        'names':  [x[0]                         for x in top_sorted],
        'counts': [x[1]['count']                for x in top_sorted],
        'totals': [round(x[1]['total'], 2)      for x in top_sorted],
    }

    # ── 5. Type Breakdown ──────────────────────────────────────────────────
    type_stats = defaultdict(lambda: {'count': 0, 'amount': 0.0})
    for tx in transactions:
        t = tx.transaction_type or 'other'
        type_stats[t]['count']  += 1
        type_stats[t]['amount'] += tx.amount

    type_breakdown = {
        t: {'count': v['count'], 'amount': round(v['amount'], 2)}
        for t, v in type_stats.items()
    }

    return jsonify({
        'balances':            balances,
        'balance_history':     {'labels': history_labels, 'datasets': history_datasets},
        'transaction_volume':  transaction_volume,
        'top_items':           top_items,
        'type_breakdown':      type_breakdown,
        'meta': {
            'date_from':          date_from_str,
            'date_to':            date_to_str,
            'transaction_count':  len(transactions),
            'user_count':         len(users),
        },
    })


# Initialize database
with app.app_context():
    db.create_all()
    _migrate_db()
    _restore_schedule()

scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
