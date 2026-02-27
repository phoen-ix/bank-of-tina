from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, Response, render_template, request, jsonify

from models import User, Transaction, ExpenseItem
from helpers import now_local

analytics_bp = Blueprint('analytics_bp', __name__)


@analytics_bp.route('/analytics')
def analytics() -> str:
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    today     = now_local().date()
    def_from  = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    def_to    = today.strftime('%Y-%m-%d')
    return render_template('analytics.html', users=users,
                           default_from=def_from, default_to=def_to)


@analytics_bp.route('/analytics/data')
def analytics_data() -> Response:
    today = now_local().date()

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

    balances = [{'name': u.name, 'balance': round(u.balance, 2)} for u in users]

    sample_dates: list[datetime.date] = []
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
    history_datasets: dict[str, list[float]] = {}

    for user in users:
        all_user_tx = Transaction.query.filter(
            (Transaction.from_user_id == user.id) | (Transaction.to_user_id == user.id)
        ).all()

        series: list[float] = []
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

    vol: dict[str, dict[str, int | Decimal]] = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
    for tx in transactions:
        if delta_days <= 90:
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

    expense_ids = [tx.id for tx in transactions if tx.transaction_type == 'expense']
    item_stats: dict[str, dict[str, int | Decimal]] = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})

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
