import logging

import pytz
from sqlalchemy import func

from extensions import db, scheduler
from models import (User, Transaction, ExpenseItem, CommonItem, CommonDescription,
                    CommonPrice, CommonBlacklist, AutoCollectLog)
from helpers import get_setting, get_tpl, apply_template, now_local
from email_service import send_all_emails, send_single_email
from backup_service import run_backup, _prune_old_backups, _list_backups, build_backup_status_email

logger = logging.getLogger(__name__)


def _add_email_job(app):
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
    logger.info('Email job scheduled: day=%s hour=%s minute=%s tz=%s', day, hour, minute, tz_name)


def auto_collect_common():
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
                                                  message=f'\u20ac{price_str} (blacklist)'))
                skip_count += 1
            elif not CommonPrice.query.filter_by(value=price).first():
                db.session.add(CommonPrice(value=price))
                if debug:
                    db.session.add(AutoCollectLog(level='ADDED', category='price',
                                                  message=f'Added \u20ac{price_str}'))
                added_count += 1

    if debug:
        db.session.add(AutoCollectLog(level='INFO', category='system',
                                      message=f'Run complete: {added_count} added, {skip_count} skipped'))
    db.session.commit()

    if debug:
        oldest_kept = (AutoCollectLog.query
                       .order_by(AutoCollectLog.id.desc())
                       .offset(500).first())
        if oldest_kept:
            AutoCollectLog.query.filter(AutoCollectLog.id <= oldest_kept.id).delete()
        db.session.commit()


def _add_common_job(app):
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
    logger.info('Common auto-collect job scheduled: day=%s hour=%s minute=%s', day, hour, minute)


def _add_backup_job(app):
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
    logger.info('Backup job scheduled: day=%s hour=%s minute=%s', day, hour, minute)


def _restore_schedule(app):
    if get_setting('schedule_enabled') == '1':
        _add_email_job(app)
    if get_setting('common_auto_enabled', '0') == '1':
        _add_common_job(app)
    if get_setting('backup_enabled', '0') == '1':
        _add_backup_job(app)
