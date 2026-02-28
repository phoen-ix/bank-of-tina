from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime
from decimal import Decimal

import pytz
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash, jsonify, abort, current_app

from extensions import db, scheduler, limiter
from models import (User, CommonItem, CommonDescription, CommonPrice, CommonBlacklist,
                    AutoCollectLog, EmailLog, BackupLog)
from helpers import (get_setting, set_setting, get_tpl, parse_amount, fmt_amount,
                     detect_theme, generate_and_save_icons, now_local)
from config import THEMES, TEMPLATE_DEFAULTS, BACKUP_DIR, DEFAULT_ICON_BG
from email_service import send_all_emails, build_email_html, build_admin_summary_email
from backup_service import run_backup, _list_backups, build_backup_status_email
from scheduler_jobs import (_add_email_job, _add_common_job, _add_backup_job,
                            auto_collect_common)

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings_bp', __name__)

BACKUP_FILENAME_RE: re.Pattern[str] = re.compile(r'^bot_backup_[\d_-]+\.tar\.gz$')

_db_user = os.environ.get('DB_USER', '')
_db_pass = os.environ.get('DB_PASSWORD', '')
_db_host = os.environ.get('DB_HOST', 'localhost')
_db_port = os.environ.get('DB_PORT', '3306')
_db_name = os.environ.get('DB_NAME', 'bank_of_tina')


@settings_bp.route('/settings')
def settings() -> str:
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
        'backup_enabled':      get_setting('backup_enabled',      '0'),
        'backup_debug':        get_setting('backup_debug',        '0'),
        'backup_admin_email':  get_setting('backup_admin_email',  '0'),
        'backup_day':          get_setting('backup_day',          '*'),
        'backup_hour':         get_setting('backup_hour',         '3'),
        'backup_minute':       get_setting('backup_minute',       '0'),
        'backup_keep':         get_setting('backup_keep',         '7'),
        'decimal_separator':         get_setting('decimal_separator',         '.'),
        'currency_symbol':           get_setting('currency_symbol',           '\u20ac'),
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


@settings_bp.route('/settings/email', methods=['POST'])
def settings_email() -> Response:
    set_setting('smtp_server',   request.form.get('smtp_server', '').strip())
    set_setting('smtp_port',     request.form.get('smtp_port', '587').strip())
    set_setting('smtp_username', request.form.get('smtp_username', '').strip())
    set_setting('from_email',    request.form.get('from_email', '').strip())
    set_setting('from_name',     request.form.get('from_name', '').strip())

    new_password = request.form.get('smtp_password', '').strip()
    if new_password:
        set_setting('smtp_password', new_password)

    set_setting('email_enabled',       '1' if request.form.get('email_enabled')       else '0')
    set_setting('email_debug',         '1' if request.form.get('email_debug')         else '0')
    set_setting('admin_summary_email', '1' if request.form.get('admin_summary_email') else '0')

    flash('Settings saved.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/send-now', methods=['POST'])
@limiter.limit("5/minute")
def settings_send_now() -> Response:
    success, fail, errors = send_all_emails()
    flash(f'{success} email(s) sent, {fail} failed.', 'success' if fail == 0 else 'error')
    if errors and get_setting('email_debug', '0') == '1':
        for err in errors:
            flash(f'Debug: {err}', 'error')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/email/clear-log', methods=['POST'])
def settings_email_clear_log() -> Response:
    EmailLog.query.delete()
    db.session.commit()
    flash('Email debug log cleared.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/schedule', methods=['POST'])
def settings_schedule() -> Response:
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
        _add_email_job(current_app._get_current_object())
        flash('Schedule saved and enabled.', 'success')
    else:
        if scheduler.get_job('email_job'):
            scheduler.remove_job('email_job')
        flash('Schedule disabled.', 'success')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/general', methods=['POST'])
def settings_general() -> Response:
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
            _add_email_job(current_app._get_current_object())
        if get_setting('common_auto_enabled', '0') == '1':
            _add_common_job(current_app._get_current_object())
    admin_id = request.form.get('site_admin_id', '').strip()
    if admin_id == '' or (admin_id.isdigit() and db.session.get(User, int(admin_id))):
        set_setting('site_admin_id', admin_id)
    sep = request.form.get('decimal_separator', '.')
    if sep not in ('.', ','):
        sep = '.'
    set_setting('decimal_separator', sep)
    set_setting('currency_symbol', request.form.get('currency_symbol', '\u20ac'))
    set_setting('show_email_on_dashboard', '1' if request.form.get('show_email_on_dashboard') else '0')
    flash('General settings saved.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/api/common-items')
def api_common_items() -> Response:
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = CommonItem.query.order_by(CommonItem.name).all()
    return jsonify([{'id': i.id, 'name': i.name} for i in items])


@settings_bp.route('/api/common-descriptions')
def api_common_descriptions() -> Response:
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = CommonDescription.query.order_by(CommonDescription.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])


@settings_bp.route('/api/common-prices')
def api_common_prices() -> Response:
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = CommonPrice.query.order_by(CommonPrice.value).all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])


@settings_bp.route('/settings/common-items/add', methods=['POST'])
def add_common_item() -> Response:
    name = request.form.get('name', '').strip()
    if not name:
        flash('Item name is required.', 'error')
        return redirect(url_for('settings_bp.settings'))
    if not CommonItem.query.filter_by(name=name).first():
        db.session.add(CommonItem(name=name))
        db.session.commit()
    flash(f'"{name}" added to common items.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-items/<int:item_id>/delete', methods=['POST'])
def delete_common_item(item_id: int) -> Response:
    item = db.session.get(CommonItem, item_id) or abort(404)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'"{name}" removed from common items.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-descriptions/add', methods=['POST'])
def add_common_description() -> Response:
    value = request.form.get('value', '').strip()
    if not value:
        flash('Description is required.', 'error')
        return redirect(url_for('settings_bp.settings'))
    if not CommonDescription.query.filter_by(value=value).first():
        db.session.add(CommonDescription(value=value))
        db.session.commit()
    flash(f'"{value}" added to common descriptions.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-descriptions/<int:item_id>/delete', methods=['POST'])
def delete_common_description(item_id: int) -> Response:
    item = db.session.get(CommonDescription, item_id) or abort(404)
    value = item.value
    db.session.delete(item)
    db.session.commit()
    flash(f'"{value}" removed from common descriptions.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-prices/add', methods=['POST'])
def add_common_price() -> Response:
    try:
        value = parse_amount(request.form.get('value', ''))
    except (ValueError, TypeError):
        flash('Valid price is required.', 'error')
        return redirect(url_for('settings_bp.settings'))
    if not CommonPrice.query.filter_by(value=value).first():
        db.session.add(CommonPrice(value=value))
        db.session.commit()
    flash(f'\u20ac{fmt_amount(value)} added to common prices.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-prices/<int:item_id>/delete', methods=['POST'])
def delete_common_price(item_id: int) -> Response:
    item = db.session.get(CommonPrice, item_id) or abort(404)
    value = item.value
    db.session.delete(item)
    db.session.commit()
    flash(f'\u20ac{fmt_amount(value)} removed from common prices.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-blacklist/add', methods=['POST'])
def add_common_blacklist() -> Response:
    bl_type = request.form.get('type', '').strip()
    value   = request.form.get('value', '').strip()
    if bl_type not in ('item', 'description', 'price') or not value:
        flash('Invalid blacklist entry.', 'error')
        return redirect(url_for('settings_bp.settings'))
    if not CommonBlacklist.query.filter_by(type=bl_type, value=value).first():
        db.session.add(CommonBlacklist(type=bl_type, value=value))
        db.session.commit()
    flash(f'"{value}" added to {bl_type} blacklist.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-blacklist/<int:item_id>/delete', methods=['POST'])
def delete_common_blacklist(item_id: int) -> Response:
    item = db.session.get(CommonBlacklist, item_id) or abort(404)
    value, bl_type = item.value, item.type
    db.session.delete(item)
    db.session.commit()
    flash(f'"{value}" removed from {bl_type} blacklist.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common', methods=['POST'])
def settings_common() -> Response:
    enabled = '1' if request.form.get('common_enabled') else '0'
    set_setting('common_enabled', enabled)
    flash('Common autocomplete settings saved.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-auto', methods=['POST'])
def settings_common_auto() -> Response:
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
        _add_common_job(current_app._get_current_object())
        flash('Auto-collect schedule saved and enabled.', 'success')
    else:
        if scheduler.get_job('common_job'):
            scheduler.remove_job('common_job')
        flash('Auto-collect schedule disabled.', 'success')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-auto/run', methods=['POST'])
def settings_common_auto_run() -> Response:
    auto_collect_common()
    flash('Auto-collect job ran successfully.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-auto/clear-log', methods=['POST'])
def settings_common_auto_clear_log() -> Response:
    AutoCollectLog.query.delete()
    db.session.commit()
    flash('Debug log cleared.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/templates', methods=['POST'])
def settings_templates() -> Response:
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
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/templates/reset', methods=['POST'])
def settings_templates_reset() -> Response:
    for key, val in TEMPLATE_DEFAULTS.items():
        set_setting(key, val)
    flash('Templates reset to defaults.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/icon', methods=['POST'])
def settings_icon() -> Response:
    action = request.form.get('action', '')
    icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    if action == 'generate':
        bg = get_tpl('color_navbar')
        generate_and_save_icons(bg)
        flash('Icon regenerated with current navbar color.', 'success')

    elif action == 'reset':
        generate_and_save_icons(DEFAULT_ICON_BG)
        flash('Icon reset to default.', 'success')

    elif action == 'upload':
        file = request.files.get('icon_file')
        if not file or not file.filename:
            flash('No file selected.', 'danger')
            return redirect(url_for('settings_bp.settings'))

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ('png', 'jpg', 'jpeg'):
            flash('Only PNG or JPG files are accepted.', 'danger')
            return redirect(url_for('settings_bp.settings'))

        try:
            from PIL import Image
            img = Image.open(file.stream)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            for size in (192, 512):
                resized = img.resize((size, size), Image.LANCZOS)
                path = os.path.join(icons_dir, f'icon-{size}.png')
                resized.save(path, 'PNG')
            version = str(int(time.time()))
            set_setting('icon_version', version)
            set_setting('icon_mode', 'custom')
            flash('Custom icon uploaded.', 'success')
        except ImportError:
            flash('Pillow is not installed \u2014 cannot process uploaded images.', 'danger')
        except Exception as e:
            flash(f'Failed to process image: {e}', 'danger')
    else:
        flash('Unknown action.', 'danger')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/templates/preview/email')
def preview_email() -> str:
    user = User.query.filter_by(is_active=True).order_by(User.name).first()
    if not user:
        class _Dummy:
            name = 'Jane Doe'; email = 'jane@example.com'; balance = Decimal('12.50'); id = 0
            from_user_id = None; to_user_id = None
            email_transactions = 'last3'; email_opt_in = True
        user = _Dummy()
        user._dummy = True
    html = build_email_html(user)
    return html


@settings_bp.route('/settings/templates/preview/admin-summary')
def preview_admin_summary() -> str:
    users = User.query.filter_by(is_active=True).order_by(User.name).all()
    if not users:
        class _D:
            def __init__(self, n, e, b): self.name=n; self.email=e; self.balance=b
        users = [_D('Alice Smith','alice@example.com',Decimal('24.50')),
                 _D('Bob Jones','bob@example.com',Decimal('-12.00')),
                 _D('Carol White','carol@example.com',Decimal('0.00'))]
    return build_admin_summary_email(users, include_emails=get_setting('admin_summary_include_emails', '0') == '1')


@settings_bp.route('/settings/templates/preview/backup')
def preview_backup() -> str:
    return build_backup_status_email(
        True, f'bot_backup_{now_local().strftime("%Y_%m_%d")}_03-00-00.tar.gz', 5, 1)


@settings_bp.route('/settings/backup', methods=['POST'])
def settings_backup() -> Response:
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
        _add_backup_job(current_app._get_current_object())
        flash('Backup schedule saved and enabled.', 'success')
    else:
        if scheduler.get_job('backup_job'):
            scheduler.remove_job('backup_job')
        flash('Backup schedule disabled.', 'success')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/backup/create', methods=['POST'])
@limiter.limit("5/minute")
def settings_backup_create() -> Response:
    ok, result = run_backup()
    if ok:
        flash(f'Backup created: {result}', 'success')
    else:
        flash(f'Backup failed: {result}', 'error')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/backup/clear-log', methods=['POST'])
def settings_backup_clear_log() -> Response:
    BackupLog.query.delete()
    db.session.commit()
    flash('Backup debug log cleared.', 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/backups/download/<filename>')
def backup_download(filename: str) -> Response:
    from flask import send_from_directory
    if not BACKUP_FILENAME_RE.match(filename):
        abort(404)
    return send_from_directory(BACKUP_DIR, filename, as_attachment=True)


@settings_bp.route('/backups/delete/<filename>', methods=['POST'])
def backup_delete(filename: str) -> Response:
    if not BACKUP_FILENAME_RE.match(filename):
        flash('Invalid filename.', 'error')
        return redirect(url_for('settings_bp.settings'))
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        flash(f'{filename} deleted.', 'success')
    else:
        flash('Backup file not found.', 'error')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/backups/upload-chunk', methods=['POST'])
def backup_upload_chunk() -> tuple[Response, int] | Response:
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


@settings_bp.route('/backups/restore/<filename>', methods=['POST'])
@limiter.limit("3/minute")
def backup_restore(filename: str) -> Response:
    if not BACKUP_FILENAME_RE.match(filename):
        flash('Invalid filename.', 'error')
        return redirect(url_for('settings_bp.settings'))

    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        flash('Backup file not found.', 'error')
        return redirect(url_for('settings_bp.settings'))

    try:
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(path, 'r:gz') as tar:
                safe = [m for m in tar.getmembers()
                        if not m.name.startswith('/') and '..' not in m.name]
                tar.extractall(tmp, members=safe)

            receipts_src = os.path.join(tmp, 'receipts')
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if os.path.exists(receipts_src):
                for item in os.listdir(upload_folder):
                    item_path = os.path.join(upload_folder, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                shutil.copytree(receipts_src, upload_folder, dirs_exist_ok=True)

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
                    return redirect(url_for('settings_bp.settings'))

        logger.info('Backup restored: %s', filename)
        flash(f'Restore from {filename} completed successfully. '
              f'Check the .env file inside the backup if credentials changed.', 'success')

    except Exception as e:
        logger.error('Backup restore failed: %s', str(e)[:200])
        flash(f'Restore failed: {str(e)[:200]}', 'error')

    return redirect(url_for('settings_bp.settings'))
