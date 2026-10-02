from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, Response, render_template, request, jsonify
from flask_babel import format_date

from extensions import db
from models import User, Transaction, ExpenseItem
from helpers import now_local, to_local, local_days_utc, local_day_start_utc

analytics_bp = Blueprint('analytics_bp', __name__)


@analytics_bp.route('/analytics')
def analytics() -> str:
    users = db.session.execute(db.select(User).filter_by(is_active=True).order_by(User.name)).scalars().all()
    today     = now_local().date()
    def_from  = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    def_to    = today.strftime('%Y-%m-%d')
    first     = db.session.execute(db.select(db.func.min(Transaction.date))).scalar()
    all_from  = to_local(first).strftime('%Y-%m-%d') if first else def_to
    return render_template('analytics.html', users=users,
                           default_from=def_from, default_to=def_to, all_from=all_from)


@analytics_bp.route('/analytics/data')
def analytics_data() -> Response:
    today = now_local().date()

    date_from_str = request.args.get('date_from', (today - timedelta(days=90)).strftime('%Y-%m-%d'))
    date_to_str   = request.args.get('date_to',   today.strftime('%Y-%m-%d'))
    users_param   = request.args.get('users', '')

    # Requested dates are local calendar days; stored transaction dates are UTC.
    try:
        day_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
    except ValueError:
        day_from = today - timedelta(days=90)
    try:
        day_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except ValueError:
        day_to = today
    range_start, range_end = local_days_utc(day_from, day_to)

    if users_param:
        uid_list = [int(x) for x in users_param.split(',') if x.strip().isdigit()]
        users = db.session.execute(db.select(User).where(User.id.in_(uid_list)).order_by(User.name)).scalars().all()
    else:
        users = db.session.execute(db.select(User).filter_by(is_active=True).order_by(User.name)).scalars().all()

    all_uid = [u.id for u in users]

    tx_stmt = db.select(Transaction).where(
        Transaction.date >= range_start,
        Transaction.date < range_end,
    )
    if all_uid:
        tx_stmt = tx_stmt.where(
            (Transaction.from_user_id.in_(all_uid)) | (Transaction.to_user_id.in_(all_uid))
        )
    transactions = db.session.execute(tx_stmt.order_by(Transaction.date)).scalars().all()

    delta_days = (day_to - day_from).days

    balances = [{'name': u.name, 'balance': round(Decimal(str(u.balance)), 4)} for u in users]

    sample_dates: list[date] = []
    if delta_days <= 90:
        d = day_from
        while d <= day_to:
            sample_dates.append(d)
            d += timedelta(days=7)
    else:
        y, m = day_from.year, day_from.month
        while True:
            sample_dates.append(date(y, m, 1))
            m += 1
            if m > 12:
                m, y = 1, y + 1
            if date(y, m, 1) > day_to:
                break
    if not sample_dates or sample_dates[-1] < day_to:
        sample_dates.append(day_to)

    history_labels   = [d.strftime('%Y-%m-%d') for d in sample_dates]
    history_datasets: dict[str, list[float]] = {}

    all_user_tx_stmt = db.select(Transaction).where(
        (Transaction.from_user_id.in_(all_uid)) | (Transaction.to_user_id.in_(all_uid))
    )
    all_user_tx_list = db.session.execute(all_user_tx_stmt).scalars().all()
    tx_by_user: dict[int, list] = {uid: [] for uid in all_uid}
    for tx in all_user_tx_list:
        if tx.from_user_id in tx_by_user:
            tx_by_user[tx.from_user_id].append(tx)
        if tx.to_user_id in tx_by_user and tx.to_user_id != tx.from_user_id:
            tx_by_user[tx.to_user_id].append(tx)

    for user in users:
        user_txs = tx_by_user.get(user.id, [])

        series: list[float] = []
        for d in sample_dates:
            # Balance at the end of local day d: undo everything from the next day on.
            cutoff = local_day_start_utc(d + timedelta(days=1))
            bal = Decimal(str(user.balance))
            for tx in user_txs:
                if tx.date >= cutoff:
                    if tx.to_user_id == user.id:
                        bal -= Decimal(str(tx.amount))
                    elif tx.from_user_id == user.id:
                        bal += Decimal(str(tx.amount))
            series.append(round(bal, 4))

        history_datasets[user.name] = series

    vol: dict[str, dict[str, int | Decimal]] = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
    for tx in transactions:
        local_day = to_local(tx.date).date()
        if delta_days <= 90:
            key = (local_day - timedelta(days=local_day.weekday())).strftime('%Y-%m-%d')
        else:
            key = local_day.strftime('%Y-%m')
        vol[key]['count']  += 1
        vol[key]['amount'] += Decimal(str(tx.amount))

    sorted_vol_keys = sorted(vol.keys())
    if delta_days <= 90:
        vol_labels = [format_date(datetime.strptime(k, '%Y-%m-%d'), 'd MMM') for k in sorted_vol_keys]
    else:
        vol_labels = [format_date(datetime.strptime(k + '-01', '%Y-%m-%d'), 'MMM yyyy') for k in sorted_vol_keys]

    transaction_volume = {
        'labels':  vol_labels,
        'counts':  [vol[k]['count']           for k in sorted_vol_keys],
        'amounts': [round(vol[k]['amount'], 4) for k in sorted_vol_keys],
    }

    expense_ids = [tx.id for tx in transactions if tx.transaction_type == 'expense']
    item_stats: dict[str, dict[str, int | Decimal]] = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})

    if expense_ids:
        for item in db.session.execute(db.select(ExpenseItem).where(ExpenseItem.transaction_id.in_(expense_ids))).scalars().all():
            name = item.item_name.strip()
            item_stats[name]['count'] += 1
            item_stats[name]['total'] += Decimal(str(item.price))

    top_sorted = sorted(item_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:15]
    top_items = {
        'names':  [x[0]                         for x in top_sorted],
        'counts': [x[1]['count']                for x in top_sorted],
        'totals': [round(x[1]['total'], 4)      for x in top_sorted],
    }

    return jsonify({
        'balances':            balances,
        'balance_history':     {'labels': history_labels, 'datasets': history_datasets},
        'transaction_volume':  transaction_volume,
        'top_items':           top_items,
        'meta': {
            'date_from':          date_from_str,
            'date_to':            date_to_str,
            'transaction_count':  len(transactions),
            'user_count':         len(users),
        },
    })
