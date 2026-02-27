import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import calendar as cal_mod
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app

from extensions import db, limiter
from models import User, Transaction, ExpenseItem
from helpers import (get_setting, get_tpl, parse_amount, fmt_amount, update_balance,
                     save_receipt, delete_receipt_file, parse_submitted_date, get_app_tz, to_local)

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

VALID_EMAIL_TX = {'none', 'last3', 'this_week', 'this_month'}


@main_bp.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 503


@main_bp.route('/')
def index():
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    count = int(get_setting('recent_transactions_count', '5'))
    recent = Transaction.query.order_by(Transaction.date.desc()).limit(count).all() if count else []
    show_email = get_setting('show_email_on_dashboard', '0') == '1'
    return render_template('index.html', users=users, transactions=recent, show_recent=count > 0,
                           show_email=show_email)


@main_bp.route('/user/add', methods=['POST'])
@limiter.limit("10/minute")
def add_user():
    name = request.form.get('name')
    email = request.form.get('email')

    if not name or not email:
        flash('Name and email are required!', 'error')
        return redirect(url_for('settings_bp.settings'))

    if User.query.filter_by(name=name).first():
        flash('User already exists!', 'error')
        return redirect(url_for('settings_bp.settings'))

    email_opt_in = request.form.get('email_opt_in') == '1'
    email_transactions = request.form.get('email_transactions', 'last3')
    if email_transactions not in VALID_EMAIL_TX:
        email_transactions = 'last3'

    user = User(name=name, email=email,
                email_opt_in=email_opt_in,
                email_transactions=email_transactions)
    db.session.add(user)
    db.session.commit()
    logger.info('User created: id=%s name=%s', user.id, name)
    flash(f'User {name} added successfully!', 'success')
    return redirect(url_for('settings_bp.settings'))


@main_bp.route('/user/<int:user_id>/edit', methods=['POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    created_at_str = request.form.get('created_at', '').strip()

    if not name or not email or not created_at_str:
        flash('All fields are required!', 'error')
        return redirect(url_for('main.user_detail', user_id=user_id))

    existing = User.query.filter(User.name == name, User.id != user_id).first()
    if existing:
        flash('Another user with that name already exists!', 'error')
        return redirect(url_for('main.user_detail', user_id=user_id))

    existing_email = User.query.filter(User.email == email, User.id != user_id).first()
    if existing_email:
        flash('Another user with that email already exists!', 'error')
        return redirect(url_for('main.user_detail', user_id=user_id))

    try:
        user.created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format!', 'error')
        return redirect(url_for('main.user_detail', user_id=user_id))

    user.name = name
    user.email = email
    user.email_opt_in = request.form.get('email_opt_in') == '1'
    email_transactions = request.form.get('email_transactions', 'last3')
    if email_transactions not in VALID_EMAIL_TX:
        email_transactions = 'last3'
    user.email_transactions = email_transactions
    db.session.commit()
    logger.info('User edited: id=%s name=%s', user_id, name)
    flash('User updated successfully!', 'success')
    return redirect(url_for('main.user_detail', user_id=user_id))


@main_bp.route('/user/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    logger.info('User toggled: id=%s name=%s active=%s', user_id, user.name, user.is_active)
    flash(f'User {user.name} has been {status}.', 'success')
    return redirect(request.referrer or url_for('settings_bp.settings'))


@main_bp.route('/transaction/add', methods=['GET', 'POST'])
@limiter.limit("30/minute", methods=["POST"])
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
        logger.info('Transaction created: deposit id=%s amount=%s', transaction.id, amount)
        flash(f'Deposit of \u20ac{fmt_amount(amount)} added successfully!', 'success')

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
        logger.info('Transaction created: withdrawal id=%s amount=%s', transaction.id, amount)
        flash(f'Withdrawal of \u20ac{fmt_amount(amount)} processed successfully!', 'success')

    elif transaction_type == 'expense':
        buyer_id = int(request.form.get('buyer_id'))
        description = request.form.get('description', 'Expense')

        buyer = User.query.get(buyer_id)
        buyer_name = buyer.name if buyer else 'unknown'
        receipt_path = save_receipt(request.files.get('receipt'), buyer_name)

        items_data = request.form.get('items_json')
        if items_data:
            items = json.loads(items_data)

            debts = {}
            for item in items:
                debtor_id = int(item['debtor_id'])
                price = parse_amount(item['price'])
                if debtor_id != buyer_id:
                    debts[debtor_id] = debts.get(debtor_id, 0) + price

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

                update_balance(debtor_id, -total_amount)
                update_balance(buyer_id, total_amount)

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
            logger.info('Transaction created: expense buyer_id=%s', buyer_id)
            flash('Expense recorded successfully!', 'success')

    return redirect(url_for('main.index'))


@main_bp.route('/transactions')
def view_transactions():
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


@main_bp.route('/search')
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


@main_bp.route('/user/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    transactions = Transaction.query.filter(
        (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
    ).order_by(Transaction.date.desc()).limit(5).all()
    return render_template('user_detail.html', user=user, transactions=transactions)


@main_bp.route('/receipt/<path:filepath>')
def view_receipt(filepath):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filepath)


@main_bp.route('/manifest.json')
def pwa_manifest():
    color = get_tpl('color_navbar')
    data = {
        "name": "Bank of Tina",
        "short_name": "Bank of Tina",
        "description": "Track shared expenses and balances",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": color,
        "icons": [
            {"src": f"/static/icons/icon-192.png?v={get_setting('icon_version', '0')}",
             "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": f"/static/icons/icon-512.png?v={get_setting('icon_version', '0')}",
             "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return current_app.response_class(
        json.dumps(data), mimetype='application/manifest+json'
    )


@main_bp.route('/transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    trans = Transaction.query.get_or_404(transaction_id)
    users = User.query.order_by(User.name).all()

    if request.method == 'GET':
        return render_template('edit_transaction.html', trans=trans, users=users)

    old_amount = trans.amount

    if trans.from_user_id:
        old_from = User.query.get(trans.from_user_id)
        if old_from:
            old_from.balance += old_amount
    if trans.to_user_id:
        old_to = User.query.get(trans.to_user_id)
        if old_to:
            old_to.balance -= old_amount

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

    ExpenseItem.query.filter_by(transaction_id=trans.id).delete()
    items_json_str = request.form.get('items_json', '').strip()
    new_items_total = None
    if items_json_str:
        try:
            items = json.loads(items_json_str)
            if items:
                total = Decimal('0')
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

    if new_items_total is not None:
        trans.amount = new_items_total
    else:
        try:
            trans.amount = parse_amount(request.form.get('amount', old_amount))
        except (ValueError, TypeError):
            trans.amount = old_amount

    if trans.from_user_id:
        new_from = User.query.get(trans.from_user_id)
        if new_from:
            new_from.balance -= trans.amount
    if trans.to_user_id:
        new_to = User.query.get(trans.to_user_id)
        if new_to:
            new_to.balance += trans.amount

    if request.form.get('remove_receipt'):
        delete_receipt_file(trans.receipt_path, trans.id)
        trans.receipt_path = None

    new_file = request.files.get('receipt')
    if new_file and new_file.filename:
        if trans.receipt_path:
            delete_receipt_file(trans.receipt_path, trans.id)
        buyer = User.query.get(trans.from_user_id) if trans.from_user_id else None
        buyer_name = buyer.name if buyer else 'unknown'
        saved = save_receipt(new_file, buyer_name)
        if saved:
            trans.receipt_path = saved

    db.session.commit()
    logger.info('Transaction edited: id=%s type=%s amount=%s', trans.id, trans.transaction_type, trans.amount)
    flash('Transaction updated successfully!', 'success')
    return redirect(url_for('main.view_transactions'))


@main_bp.route('/transaction/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id):
    trans = Transaction.query.get_or_404(transaction_id)

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
    logger.info('Transaction deleted: id=%s type=%s amount=%s', transaction_id, trans.transaction_type, trans.amount)

    flash('Transaction deleted.', 'success')
    return redirect(url_for('main.view_transactions'))


@main_bp.route('/api/users')
def api_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'balance': u.balance} for u in users])
