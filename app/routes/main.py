from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import calendar as cal_mod
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app, abort
from flask_babel import gettext as _, format_date as babel_format_date

from extensions import db, limiter
from models import User, Transaction, ExpenseItem
from helpers import (get_setting, get_tpl, parse_amount, fmt_amount, allowed_file,
                     save_receipt, delete_receipt_file, parse_submitted_date, parse_local_datetime,
                     to_local, now_local, local_days_utc, local_month_utc, apply_balance_effect,
                     adjust_balance, redirect_back, InputError)

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

VALID_EMAIL_TX: set[str] = {'none', 'last3', 'this_week', 'this_month'}
DESCRIPTION_MAX = 500   # Transaction.description
USER_FIELD_MAX = 100    # User.name / User.email
EMAIL_RE = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
ITEM_NAME_MAX = 200     # ExpenseItem.item_name


def _user_id_field(value: object, required: bool = True) -> int | None:
    """Validate a submitted user id: must refer to an existing user."""
    if value in (None, ''):
        if required:
            raise InputError(_('Please select a user.'))
        return None
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        raise InputError(_('Unknown user.')) from None
    if not db.session.get(User, user_id):
        raise InputError(_('Unknown user.'))
    return user_id


def _receipt_upload():
    """The uploaded receipt, None if no file was chosen; rejects unsupported types."""
    file = request.files.get('receipt')
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise InputError(_('Receipts must be JPG, PNG or PDF files.'))
    return file


def _parse_items(items_json: str, with_debtor: bool) -> list[dict]:
    """Parse and validate the items_json field of the expense forms."""
    try:
        items = json.loads(items_json)
    except ValueError:
        raise InputError(_('The item list could not be read.')) from None
    if not isinstance(items, list):
        raise InputError(_('The item list could not be read.'))
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            raise InputError(_('The item list could not be read.'))
        name = str(item.get('name', '')).strip()[:ITEM_NAME_MAX]
        if not name:
            raise InputError(_('Every item needs a name.'))
        entry = {'name': name, 'price': parse_amount(item.get('price'), positive=True)}
        if with_debtor:
            entry['debtor_id'] = _user_id_field(item.get('debtor_id'))
        parsed.append(entry)
    return parsed


def _month_url(dt: datetime) -> str:
    local = to_local(dt)
    return url_for('main.view_transactions', year=local.year, month=local.month)


@main_bp.route('/health')
def health() -> tuple[Response, int]:
    checks: dict[str, str] = {}

    # DB check
    try:
        db.session.execute(db.text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception as e:
        logger.error('Health check: database error: %s', e)
        checks['database'] = 'error'

    # Scheduler check
    from extensions import scheduler
    checks['scheduler'] = 'ok' if scheduler.running else 'not running'

    # Icons directory writable
    icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
    checks['icons_writable'] = 'ok' if os.access(icons_dir, os.W_OK) else 'not writable'

    db_ok = checks['database'] == 'ok'
    overall = 'ok' if db_ok else 'error'
    status_code = 200 if db_ok else 503
    return jsonify({'status': overall, 'checks': checks}), status_code


@main_bp.route('/')
def index() -> str:
    admin_id = get_setting('site_admin_id')
    q = db.select(User).filter_by(is_active=True)
    if admin_id:
        q = q.filter(User.id != int(admin_id))
    users = db.session.execute(q.order_by(User.name)).scalars().all()
    count = int(get_setting('recent_transactions_count', '5'))
    recent = db.session.execute(db.select(Transaction).order_by(Transaction.date.desc()).limit(count)).scalars().all() if count else []
    show_email = get_setting('show_email_on_dashboard', '0') == '1'
    return render_template('index.html', users=users, transactions=recent, show_recent=count > 0,
                           show_email=show_email)


def _user_form_error(name: str, email: str, user_id: int | None = None) -> str | None:
    """Validation message for the add/edit user forms, or None when valid."""
    if not name or not email:
        return _('Name and email are required!')
    if len(name) > USER_FIELD_MAX or len(email) > USER_FIELD_MAX:
        return _('Name and email can be at most %(max)d characters.', max=USER_FIELD_MAX)
    if not EMAIL_RE.fullmatch(email):
        return _('Please enter a valid email address.')
    others = db.select(User.id)
    if user_id is not None:
        others = others.where(User.id != user_id)
    # Case-insensitive, like MariaDB's default collation on the unique indexes.
    if db.session.execute(others.where(db.func.lower(User.name) == name.lower())).first():
        return _('Another user with that name already exists!')
    if db.session.execute(others.where(db.func.lower(User.email) == email.lower())).first():
        return _('Another user with that email already exists!')
    return None


@main_bp.route('/user/add', methods=['POST'])
@limiter.limit("10/minute")
def add_user() -> Response:
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()

    error = _user_form_error(name, email)
    if error:
        flash(error, 'error')
        return redirect(url_for('settings_bp.settings', tab='users'))

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
    flash(_('User %(name)s added successfully!', name=name), 'success')
    return redirect(url_for('settings_bp.settings', tab='users'))


@main_bp.route('/user/<int:user_id>/edit', methods=['POST'])
def edit_user(user_id: int) -> Response:
    user = db.session.get(User, user_id) or abort(404)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    created_at_str = request.form.get('created_at', '').strip()

    error = _user_form_error(name, email, user_id) or (None if created_at_str else _('All fields are required!'))
    if error:
        flash(error, 'error')
        return redirect(url_for('main.user_detail', user_id=user_id))

    try:
        user.created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
    except ValueError:
        flash(_('Invalid date format!'), 'error')
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
    flash(_('User updated successfully!'), 'success')
    return redirect(url_for('main.user_detail', user_id=user_id))


@main_bp.route('/user/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id: int) -> Response:
    user = db.session.get(User, user_id) or abort(404)
    user.is_active = not user.is_active
    db.session.commit()
    logger.info('User toggled: id=%s name=%s active=%s', user_id, user.name, user.is_active)
    if user.is_active:
        flash(_('User %(name)s has been activated.', name=user.name), 'success')
    else:
        flash(_('User %(name)s has been deactivated.', name=user.name), 'success')
    return redirect_back(url_for('settings_bp.settings'))


@main_bp.route('/transaction/add', methods=['GET', 'POST'])
@limiter.limit("30/minute", methods=["POST"])
def add_transaction() -> str | Response:
    if request.method == 'GET':
        users = db.session.execute(db.select(User).filter_by(is_active=True).order_by(User.name)).scalars().all()
        default_item_rows = int(get_setting('default_item_rows', '3'))
        default_date = now_local().strftime('%Y-%m-%dT%H:%M')
        return render_template('add_transaction.html', users=users,
                               default_item_rows=default_item_rows, default_date=default_date)

    transaction_type = request.form.get('transaction_type')
    submitted_date = parse_submitted_date(request.form.get('date', ''))
    notes = request.form.get('notes', '').strip() or None
    description = request.form.get('description', '').strip()[:DESCRIPTION_MAX]
    sym = get_setting('currency_symbol', '\u20ac')

    try:
        if transaction_type in ('deposit', 'withdrawal'):
            user_id = _user_id_field(request.form.get('user_id'))
            amount = parse_amount(request.form.get('amount'), positive=True)
            transaction = Transaction(
                description=description,
                amount=amount,
                transaction_type=transaction_type,
                date=submitted_date,
                notes=notes,
            )
            if transaction_type == 'deposit':
                transaction.to_user_id = user_id
                message = _('Deposit of %(sym)s%(amount)s added successfully!', sym=sym, amount=fmt_amount(amount))
            else:
                transaction.from_user_id = user_id
                message = _('Withdrawal of %(sym)s%(amount)s processed successfully!', sym=sym, amount=fmt_amount(amount))
            db.session.add(transaction)
            apply_balance_effect(transaction)
            db.session.commit()
            logger.info('Transaction created: %s id=%s amount=%s', transaction_type, transaction.id, amount)
            flash(message, 'success')

        elif transaction_type == 'expense':
            buyer_id = _user_id_field(request.form.get('buyer_id'))
            items = _parse_items(request.form.get('items_json') or '[]', with_debtor=True)
            if not items:
                raise InputError(_('At least one item is required for an expense.'))
            receipt = _receipt_upload()

            # The buyer's own items cost nobody anything; one transaction per debtor.
            debts: dict[int, Decimal] = {}
            for item in items:
                if item['debtor_id'] != buyer_id:
                    debts[item['debtor_id']] = debts.get(item['debtor_id'], Decimal('0')) + item['price']
            if not debts:
                raise InputError(_('Nobody owes anything: all items belong to the buyer.'))

            buyer = db.session.get(User, buyer_id)
            receipt_path = save_receipt(receipt, buyer.name)
            for debtor_id, total_amount in debts.items():
                transaction = Transaction(
                    description=description,
                    amount=total_amount,
                    from_user_id=debtor_id,
                    to_user_id=buyer_id,
                    transaction_type='expense',
                    receipt_path=receipt_path,
                    date=submitted_date,
                    notes=notes,
                )
                db.session.add(transaction)
                for item in items:
                    if item['debtor_id'] == debtor_id:
                        db.session.add(ExpenseItem(transaction=transaction, item_name=item['name'],
                                                   price=item['price'], buyer_id=buyer_id))
                adjust_balance(debtor_id, -total_amount)
                adjust_balance(buyer_id, total_amount)

            db.session.commit()
            logger.info('Transaction created: expense buyer_id=%s debtors=%s', buyer_id, len(debts))
            flash(_('Expense recorded successfully!'), 'success')

        else:
            raise InputError(_('Unknown transaction type.'))

    except InputError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('main.add_transaction'))

    return redirect(url_for('main.index'))


@main_bp.route('/transactions')
def view_transactions() -> str:
    today = now_local().date()
    year  = max(2000, min(2100, request.args.get('year',  today.year,  type=int)))
    month = max(1,    min(12,   request.args.get('month', today.month, type=int)))

    start, end = local_month_utc(year, month)
    transactions = db.session.execute(db.select(Transaction).where(
        Transaction.date >= start,
        Transaction.date < end,
    ).order_by(Transaction.date.desc())).scalars().all()

    by_day = defaultdict(list)
    for t in transactions:
        by_day[to_local(t.date).date()].append(t)
    grouped = sorted(by_day.items(), reverse=True)

    prev_month = month - 1 or 12
    prev_year  = year - (1 if month == 1 else 0)
    next_month = (month % 12) + 1
    next_year  = year + (1 if month == 12 else 0)

    first_date = db.session.execute(db.select(db.func.min(Transaction.date))).scalar()
    start_year = min(to_local(first_date).year, today.year) if first_date else today.year
    year_range = list(range(start_year, today.year + 1))

    localized_months = [babel_format_date(datetime(2000, m, 1), 'MMMM') for m in range(1, 13)]

    # Deposits, withdrawals and expenses move money in different directions,
    # so a single sum over all of them means nothing; total them per type.
    tx_totals: dict[str, Decimal] = {}
    for t in transactions:
        tx_totals[t.transaction_type] = tx_totals.get(t.transaction_type, Decimal('0')) + Decimal(str(t.amount))

    return render_template('transactions.html',
        grouped=grouped,
        year=year, month=month,
        month_name=babel_format_date(datetime(year, month, 1), 'MMMM'),
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        is_current_month=(year == today.year and month == today.month),
        year_range=year_range,
        tx_count=len(transactions),
        tx_totals=sorted(tx_totals.items()),
        localized_months=localized_months,
    )


@main_bp.route('/search')
def search() -> str:
    q           = request.args.get('q', '').strip()
    tx_type     = request.args.get('type', '')
    user_id     = request.args.get('user', None, type=int)
    date_from   = request.args.get('date_from', '')
    date_to     = request.args.get('date_to', '')
    amount_min  = request.args.get('amount_min', '')
    amount_max  = request.args.get('amount_max', '')
    has_receipt = request.args.get('has_receipt', '')
    page        = request.args.get('page', 1, type=int)

    searched = any([q, tx_type, user_id, date_from, date_to, amount_min, amount_max, has_receipt])
    pagination = None

    if searched:
        stmt = db.select(Transaction)

        if q:
            q_escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            stmt = stmt.where(
                db.or_(
                    Transaction.description.ilike(f'%{q_escaped}%', escape='\\'),
                    Transaction.notes.ilike(f'%{q_escaped}%', escape='\\'),
                    Transaction.items.any(ExpenseItem.item_name.ilike(f'%{q_escaped}%', escape='\\'))
                )
            )
        if tx_type:
            stmt = stmt.where(Transaction.transaction_type == tx_type)
        if user_id:
            stmt = stmt.where(
                db.or_(Transaction.from_user_id == user_id,
                       Transaction.to_user_id   == user_id)
            )
        # The form's dates are local calendar days; stored dates are UTC.
        if date_from:
            try:
                d = datetime.strptime(date_from, '%Y-%m-%d').date()
                stmt = stmt.where(Transaction.date >= local_days_utc(d, d)[0])
            except ValueError:
                pass
        if date_to:
            try:
                d = datetime.strptime(date_to, '%Y-%m-%d').date()
                stmt = stmt.where(Transaction.date < local_days_utc(d, d)[1])
            except ValueError:
                pass
        if amount_min:
            try:
                stmt = stmt.where(Transaction.amount >= parse_amount(amount_min))
            except InputError:
                pass
        if amount_max:
            try:
                stmt = stmt.where(Transaction.amount <= parse_amount(amount_max))
            except InputError:
                pass
        if has_receipt:
            stmt = stmt.where(Transaction.receipt_path.isnot(None),
                              Transaction.receipt_path != '')

        pagination = db.paginate(stmt.order_by(Transaction.date.desc()),
                                 page=page, per_page=25, error_out=False)

    all_users = db.session.execute(
        db.select(User).filter_by(is_active=True).order_by(User.name)
    ).scalars().all()

    # Build kwargs for pagination links (preserve all query params except page)
    page_kwargs = {}
    if q: page_kwargs['q'] = q
    if tx_type: page_kwargs['type'] = tx_type
    if user_id: page_kwargs['user'] = user_id
    if date_from: page_kwargs['date_from'] = date_from
    if date_to: page_kwargs['date_to'] = date_to
    if amount_min: page_kwargs['amount_min'] = amount_min
    if amount_max: page_kwargs['amount_max'] = amount_max
    if has_receipt: page_kwargs['has_receipt'] = has_receipt

    return render_template('search.html',
        pagination=pagination, searched=searched, all_users=all_users,
        q=q, tx_type=tx_type, user_id=user_id,
        date_from=date_from, date_to=date_to,
        amount_min=amount_min, amount_max=amount_max,
        has_receipt=has_receipt, page_kwargs=page_kwargs)


@main_bp.route('/user/<int:user_id>')
def user_detail(user_id: int) -> str:
    user = db.session.get(User, user_id) or abort(404)
    page = request.args.get('page', 1, type=int)
    stmt = db.select(Transaction).where(
        (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
    ).order_by(Transaction.date.desc())
    pagination = db.paginate(stmt, page=page, per_page=20, error_out=False)
    return render_template('user_detail.html', user=user, pagination=pagination)


@main_bp.route('/receipt/<path:filepath>')
def view_receipt(filepath: str) -> Response:
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filepath)


@main_bp.route('/favicon.ico')
def favicon() -> Response:
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'icons'),
        'icon-32.png',
        mimetype='image/png',
        max_age=86400,
    )


@main_bp.route('/sw.js')
def service_worker() -> Response:
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'sw.js',
        mimetype='application/javascript',
        max_age=0,
    )


@main_bp.route('/manifest.json')
def pwa_manifest() -> Response:
    color = get_tpl('color_navbar')
    data = {
        "name": _("Bank of Tina"),
        "short_name": _("Bank of Tina"),
        "description": _("Track shared expenses and balances"),
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
def edit_transaction(transaction_id: int) -> str | Response:
    # Row lock on POST: a double-submitted edit must not reverse the old amount twice.
    trans = db.session.get(Transaction, transaction_id,
                           with_for_update=True if request.method == 'POST' else None) or abort(404)
    users = db.session.execute(db.select(User).order_by(User.name)).scalars().all()

    if request.method == 'GET':
        return render_template('edit_transaction.html', trans=trans, users=users)

    # Validate everything before touching balances or items.
    try:
        from_id = _user_id_field(request.form.get('from_user_id'), required=False)
        to_id = _user_id_field(request.form.get('to_user_id'), required=False)

        new_date = trans.date
        date_str = request.form.get('date', '').strip()
        if date_str:
            new_date = parse_local_datetime(date_str)
            if new_date is None:
                raise InputError(_('Could not parse the date.'))

        # Blank items_json means the form script did not run: leave items alone.
        # "[]" means the user removed every item.
        items_json = request.form.get('items_json', '').strip()
        new_items = _parse_items(items_json, with_debtor=False) if items_json else None
        if new_items:
            amount = sum((i['price'] for i in new_items), Decimal('0'))
        else:
            amount = parse_amount(request.form.get('amount'), positive=True)
        receipt = _receipt_upload()
    except InputError as e:
        flash(str(e), 'error')
        return redirect(url_for('main.edit_transaction', transaction_id=trans.id))

    apply_balance_effect(trans, reverse=True)

    trans.description = request.form.get('description', '').strip()[:DESCRIPTION_MAX]
    trans.notes = request.form.get('notes', '').strip() or None
    trans.date = new_date
    trans.from_user_id = from_id
    trans.to_user_id = to_id
    trans.amount = amount

    if new_items is not None:
        db.session.execute(db.delete(ExpenseItem).filter_by(transaction_id=trans.id))
        for item in new_items:
            db.session.add(ExpenseItem(transaction_id=trans.id, item_name=item['name'],
                                       price=item['price'], buyer_id=trans.to_user_id))

    apply_balance_effect(trans)

    if request.form.get('remove_receipt') or receipt:
        delete_receipt_file(trans.receipt_path, trans.id)
        trans.receipt_path = None
    if receipt:
        # Receipts are named after whoever paid: the buyer (to_user) of an expense.
        payer_id = trans.to_user_id if trans.transaction_type == 'expense' else (trans.from_user_id or trans.to_user_id)
        payer = db.session.get(User, payer_id) if payer_id else None
        trans.receipt_path = save_receipt(receipt, payer.name if payer else 'unknown')

    db.session.commit()
    logger.info('Transaction edited: id=%s type=%s amount=%s', trans.id, trans.transaction_type, trans.amount)
    flash(_('Transaction updated successfully!'), 'success')
    return redirect(_month_url(trans.date))


@main_bp.route('/transaction/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id: int) -> Response:
    trans = db.session.get(Transaction, transaction_id, with_for_update=True) or abort(404)
    receipt_path, back = trans.receipt_path, _month_url(trans.date)

    apply_balance_effect(trans, reverse=True)
    db.session.execute(db.delete(ExpenseItem).filter_by(transaction_id=trans.id))
    db.session.delete(trans)
    db.session.commit()
    # Only after the commit: the file may be shared with the other debtors' transactions.
    delete_receipt_file(receipt_path, transaction_id)
    logger.info('Transaction deleted: id=%s type=%s amount=%s', transaction_id, trans.transaction_type, trans.amount)

    flash(_('Transaction deleted.'), 'success')
    return redirect(back)
