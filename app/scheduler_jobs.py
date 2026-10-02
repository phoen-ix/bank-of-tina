from __future__ import annotations

import logging

import pytz
from flask import Flask
from sqlalchemy import func

from flask_babel import force_locale, gettext as _

from extensions import db, scheduler
from models import (User, Transaction, ExpenseItem, CommonItem, CommonDescription,
                    CommonPrice, CommonBlacklist, AutoCollectLog)
from helpers import get_setting, get_tpl, apply_template, now_local, parse_amount, amount_str, prune_log, InputError
from email_service import send_all_emails, send_single_email
from backup_service import (run_backup, _prune_old_backups, _list_backups, build_backup_status_email,
                            _backup_log)

logger = logging.getLogger(__name__)


def _add_email_job(app: Flask) -> None:
    day    = get_setting('schedule_day', 'mon')
    hour   = int(get_setting('schedule_hour', '9'))
    minute = int(get_setting('schedule_minute', '0'))
    tz_name = get_setting('timezone', 'UTC')
    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC

    def job() -> None:
        with app.app_context():
            locale = get_setting('language', 'de')
            with force_locale(locale):
                send_all_emails()

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      timezone=tz, id='email_job', replace_existing=True)
    logger.info('Email job scheduled: day=%s hour=%s minute=%s tz=%s', day, hour, minute, tz_name)


def _price_key(value: str) -> str:
    """Normalize a stored price ('3,5', '3.50') to the amount_str() form used for comparison."""
    try:
        return amount_str(parse_amount(value))
    except InputError:
        return value


def auto_collect_common() -> None:
    debug = get_setting('common_auto_debug', '0') == '1'
    added_count = 0
    skip_count = 0

    if get_setting('common_items_auto', '0') == '1':
        threshold = int(get_setting('common_items_threshold', '5'))
        blacklisted = {b.value.lower() for b in db.session.execute(db.select(CommonBlacklist).filter_by(type='item')).scalars().all()}
        rows = db.session.execute(db.select(ExpenseItem.item_name, func.count(ExpenseItem.id))
                          .group_by(ExpenseItem.item_name)
                          .having(func.count(ExpenseItem.id) >= threshold)).all()
        for name, _count in rows:
            if name.lower() in blacklisted:
                if debug:
                    db.session.add(AutoCollectLog(level='SKIP', category='item',
                                                  message=f'"{name}" (blacklist)'))
                skip_count += 1
            elif not db.session.execute(db.select(CommonItem).filter_by(name=name)).scalar():
                db.session.add(CommonItem(name=name))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='item',
                                                  message=f'Added "{name}"'))
                added_count += 1

    if get_setting('common_descriptions_auto', '0') == '1':
        threshold = int(get_setting('common_descriptions_threshold', '5'))
        blacklisted = {b.value.lower() for b in db.session.execute(db.select(CommonBlacklist).filter_by(type='description')).scalars().all()}
        rows = db.session.execute(db.select(Transaction.description, func.count(Transaction.id))
                          .group_by(Transaction.description)
                          .having(func.count(Transaction.id) >= threshold)).all()
        for desc, _count in rows:
            if desc.lower() in blacklisted:
                if debug:
                    db.session.add(AutoCollectLog(level='SKIP', category='description',
                                                  message=f'"{desc}" (blacklist)'))
                skip_count += 1
            elif not db.session.execute(db.select(CommonDescription).filter_by(value=desc)).scalar():
                db.session.add(CommonDescription(value=desc))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='description',
                                                  message=f'Added "{desc}"'))
                added_count += 1

    if get_setting('common_prices_auto', '0') == '1':
        threshold = int(get_setting('common_prices_threshold', '5'))
        blacklisted = {_price_key(b.value) for b in db.session.execute(db.select(CommonBlacklist).filter_by(type='price')).scalars().all()}
        sym = get_setting('currency_symbol', '\u20ac')
        rows = db.session.execute(db.select(ExpenseItem.price, func.count(ExpenseItem.id))
                          .group_by(ExpenseItem.price)
                          .having(func.count(ExpenseItem.id) >= threshold)).all()
        for price, _count in rows:
            price_str = amount_str(price)
            if price_str in blacklisted:
                if debug:
                    db.session.add(AutoCollectLog(level='SKIP', category='price',
                                                  message=f'{sym}{price_str} (blacklist)'))
                skip_count += 1
            elif not db.session.execute(db.select(CommonPrice).filter_by(value=price)).scalar():
                db.session.add(CommonPrice(value=price))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='price',
                                                  message=f'Added {sym}{price_str}'))
                added_count += 1

    if debug:
        db.session.add(AutoCollectLog(level='INFO', category='system',
                                      message=f'Run complete: {added_count} added, {skip_count} skipped'))
        db.session.flush()
        prune_log(AutoCollectLog)
    db.session.commit()


def _add_common_job(app: Flask) -> None:
    day    = get_setting('common_auto_day', '*')
    hour   = int(get_setting('common_auto_hour', '2'))
    minute = int(get_setting('common_auto_minute', '0'))
    try:
        tz = pytz.timezone(get_setting('timezone', 'UTC'))
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC

    def job() -> None:
        with app.app_context():
            auto_collect_common()

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      timezone=tz, id='common_job', replace_existing=True)
    logger.info('Common auto-collect job scheduled: day=%s hour=%s minute=%s', day, hour, minute)


def _add_backup_job(app: Flask) -> None:
    day    = get_setting('backup_day', '*')
    hour   = int(get_setting('backup_hour', '3'))
    minute = int(get_setting('backup_minute', '0'))
    keep   = int(get_setting('backup_keep', '7'))
    try:
        tz = pytz.timezone(get_setting('timezone', 'UTC'))
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC

    def job() -> None:
        with app.app_context():
            locale = get_setting('language', 'de')
            with force_locale(locale):
                ok, result = run_backup()
                pruned = 0
                if ok and keep > 0:
                    before = len(_list_backups())
                    _prune_old_backups(keep)
                    pruned = max(0, before - len(_list_backups()))

                if get_setting('backup_admin_email', '0') == '1':
                    admin_id = get_setting('site_admin_id', '')
                    admin = db.session.get(User, int(admin_id)) if admin_id.isdigit() else None
                    if admin:
                        kept = len(_list_backups())
                        html = build_backup_status_email(ok, result, kept, pruned)
                        subject = apply_template(get_tpl('tpl_backup_subject'),
                                                 Date=now_local().strftime('%Y-%m-%d'),
                                                 BackupStatus=_('Success') if ok else _('Failed'))
                        sent, err = send_single_email(admin.email, admin.name, subject, html)
                        if not sent:
                            _backup_log('ERROR', f'Status email to {admin.email} failed: {err}')

    scheduler.add_job(job, 'cron', day_of_week=day, hour=hour, minute=minute,
                      timezone=tz, id='backup_job', replace_existing=True)
    logger.info('Backup job scheduled: day=%s hour=%s minute=%s', day, hour, minute)


def _restore_schedule(app: Flask) -> None:
    """Add the enabled jobs. A job with broken settings is logged and skipped so it
    cannot keep the app from starting."""
    for enabled_key, add_job in (('schedule_enabled', _add_email_job),
                                 ('common_auto_enabled', _add_common_job),
                                 ('backup_enabled', _add_backup_job)):
        if get_setting(enabled_key, '0') == '1':
            try:
                add_job(app)
            except Exception:
                logger.exception('Could not schedule %s', add_job.__name__)


def reschedule_all(app: Flask) -> None:
    """Re-create every job from the current settings (after a timezone change or a restore)."""
    for job_id in ('email_job', 'common_job', 'backup_job'):
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    _restore_schedule(app)
