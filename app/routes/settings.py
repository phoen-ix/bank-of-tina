from __future__ import annotations

import logging
import os
import re
import time
from decimal import Decimal

import pytz
from flask import (Blueprint, Response, render_template, request, redirect, url_for, flash, jsonify,
                   abort, current_app, send_from_directory)
from flask_babel import gettext as _

from extensions import db, scheduler, limiter
from models import (User, CommonItem, CommonDescription, CommonPrice, CommonBlacklist,
                    AutoCollectLog, EmailLog, BackupLog)
from helpers import (get_setting, set_setting, delete_setting, get_tpl, parse_amount, fmt_amount,
                     detect_theme, generate_and_save_icons, now_local, InputError)
from config import (THEMES, TEMPLATE_DEFAULTS, TEMPLATE_DEFAULTS_DE, BACKUP_DIR, DEFAULT_ICON_BG,
                    CURRENCIES, CRON_DAYS)
from email_service import send_all_emails, build_email_html, build_admin_summary_email, SMTP_SECURITY_MODES
from backup_service import (run_backup, run_restore, assemble_upload, sweep_stale_uploads,
                            _list_backups, build_backup_status_email,
                            BACKUP_FILENAME_RE, MAX_UPLOAD_CHUNKS)
from scheduler_jobs import (_add_email_job, _add_common_job, _add_backup_job,
                            auto_collect_common, reschedule_all)

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings_bp', __name__)

UPLOAD_ID_RE: re.Pattern[str] = re.compile(r'^[a-f0-9\-]{36}$')


def _cron_day(field: str, default: str) -> str:
    """A schedule day from the form; unknown values would make APScheduler raise."""
    day = request.form.get(field, default)
    return day if day in CRON_DAYS else default


@settings_bp.route('/settings')
def settings() -> str:
    cfg = {
        'smtp_server':   get_setting('smtp_server', 'smtp.gmail.com'),
        'smtp_port':     get_setting('smtp_port', '587'),
        'smtp_security': get_setting('smtp_security', 'starttls'),
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
        'language': get_setting('language', 'de'),
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
    common_items        = db.session.execute(db.select(CommonItem).order_by(CommonItem.name)).scalars().all()
    common_descriptions = db.session.execute(db.select(CommonDescription).order_by(CommonDescription.value)).scalars().all()
    common_prices       = db.session.execute(db.select(CommonPrice).order_by(CommonPrice.value)).scalars().all()
    common_blacklist    = db.session.execute(db.select(CommonBlacklist).order_by(CommonBlacklist.type, CommonBlacklist.value)).scalars().all()
    auto_collect_logs   = db.session.execute(db.select(AutoCollectLog).order_by(AutoCollectLog.id.desc()).limit(500)).scalars().all()
    email_logs          = db.session.execute(db.select(EmailLog).order_by(EmailLog.id.desc()).limit(500)).scalars().all()
    backup_logs         = db.session.execute(db.select(BackupLog).order_by(BackupLog.id.desc()).limit(500)).scalars().all()
    backups             = _list_backups()
    all_users = db.session.execute(db.select(User).order_by(User.name)).scalars().all()
    timezone_groups = {}
    for tz in pytz.common_timezones:
        region = tz.split('/')[0]
        timezone_groups.setdefault(region, []).append(tz)
    return render_template('settings.html', cfg=cfg, common_items=common_items,
                           common_descriptions=common_descriptions, common_prices=common_prices,
                           common_blacklist=common_blacklist, auto_collect_logs=auto_collect_logs,
                           email_logs=email_logs, backup_logs=backup_logs, backups=backups,
                           all_users=all_users, timezone_groups=timezone_groups,
                           themes=THEMES, current_theme=detect_theme(), currencies=CURRENCIES,
                           tpl_defaults=TEMPLATE_DEFAULTS_DE if cfg['language'] == 'de' else TEMPLATE_DEFAULTS)


@settings_bp.route('/settings/email', methods=['POST'])
def settings_email() -> Response:
    port = request.form.get('smtp_port', '587').strip()
    if not (port.isdigit() and 0 < int(port) < 65536):
        flash(_('SMTP port must be a number between 1 and 65535.'), 'error')
        return redirect(url_for('settings_bp.settings'))
    security = request.form.get('smtp_security', 'starttls')
    if security not in SMTP_SECURITY_MODES:
        security = 'starttls'
    set_setting('smtp_server',   request.form.get('smtp_server', '').strip())
    set_setting('smtp_port',     port)
    set_setting('smtp_security', security)
    set_setting('smtp_username', request.form.get('smtp_username', '').strip())
    set_setting('from_email',    request.form.get('from_email', '').strip())
    set_setting('from_name',     request.form.get('from_name', '').strip())

    new_password = request.form.get('smtp_password', '').strip()
    if new_password:
        set_setting('smtp_password', new_password)

    set_setting('email_enabled',       '1' if request.form.get('email_enabled')       else '0')
    set_setting('email_debug',         '1' if request.form.get('email_debug')         else '0')
    set_setting('admin_summary_email', '1' if request.form.get('admin_summary_email') else '0')

    flash(_('Settings saved.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/send-now', methods=['POST'])
@limiter.limit("5/minute")
def settings_send_now() -> Response:
    success, fail, errors = send_all_emails()
    flash(_('%(success)s email(s) sent, %(fail)s failed.', success=success, fail=fail), 'success' if fail == 0 else 'error')
    if errors and get_setting('email_debug', '0') == '1':
        for err in errors:
            flash(_('Debug: %(err)s', err=err), 'error')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/email/clear-log', methods=['POST'])
def settings_email_clear_log() -> Response:
    db.session.execute(db.delete(EmailLog))
    db.session.commit()
    flash(_('Email debug log cleared.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/schedule', methods=['POST'])
def settings_schedule() -> Response:
    enabled = '1' if request.form.get('schedule_enabled') else '0'
    day    = _cron_day('schedule_day', 'mon')
    try:
        hour   = str(max(0, min(23, int(request.form.get('schedule_hour',   '9')))))
        minute = str(max(0, min(59, int(request.form.get('schedule_minute', '0')))))
    except ValueError:
        hour, minute = '9', '0'

    set_setting('schedule_enabled', enabled)
    set_setting('schedule_day',     day)
    set_setting('schedule_hour',    hour)
    set_setting('schedule_minute',  minute)

    if enabled == '1':
        _add_email_job(current_app._get_current_object())
        flash(_('Schedule saved and enabled.'), 'success')
    else:
        if scheduler.get_job('email_job'):
            scheduler.remove_job('email_job')
        flash(_('Schedule disabled.'), 'success')

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
    language = request.form.get('language', 'de')
    if language in ('de', 'en'):
        set_setting('language', language)

    timezone = request.form.get('timezone', 'UTC')
    if timezone in pytz.common_timezones:
        set_setting('timezone', timezone)
        reschedule_all(current_app._get_current_object())
    admin_id = request.form.get('site_admin_id', '').strip()
    if admin_id == '' or (admin_id.isdigit() and db.session.get(User, int(admin_id))):
        set_setting('site_admin_id', admin_id)
    sep = request.form.get('decimal_separator', '.')
    if sep not in ('.', ','):
        sep = '.'
    set_setting('decimal_separator', sep)
    currency = request.form.get('currency_symbol', '')
    if currency in {sym for sym, _name in CURRENCIES}:
        set_setting('currency_symbol', currency)
    set_setting('show_email_on_dashboard', '1' if request.form.get('show_email_on_dashboard') else '0')
    flash(_('General settings saved.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/api/common-items')
def api_common_items() -> Response:
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = db.session.execute(db.select(CommonItem).order_by(CommonItem.name)).scalars().all()
    return jsonify([{'id': i.id, 'name': i.name} for i in items])


@settings_bp.route('/api/common-descriptions')
def api_common_descriptions() -> Response:
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = db.session.execute(db.select(CommonDescription).order_by(CommonDescription.value)).scalars().all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])


@settings_bp.route('/api/common-prices')
def api_common_prices() -> Response:
    if get_setting('common_enabled', '1') != '1':
        return jsonify([])
    items = db.session.execute(db.select(CommonPrice).order_by(CommonPrice.value)).scalars().all()
    return jsonify([{'id': i.id, 'value': i.value} for i in items])


@settings_bp.route('/settings/common-items/add', methods=['POST'])
def add_common_item() -> Response:
    name = request.form.get('name', '').strip()
    if not name:
        flash(_('Item name is required.'), 'error')
        return redirect(url_for('settings_bp.settings'))
    if not db.session.execute(db.select(CommonItem).filter_by(name=name)).scalar():
        db.session.add(CommonItem(name=name))
        db.session.commit()
    flash(_('"%(name)s" added to common items.', name=name), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-items/<int:item_id>/delete', methods=['POST'])
def delete_common_item(item_id: int) -> Response:
    item = db.session.get(CommonItem, item_id) or abort(404)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(_('"%(name)s" removed from common items.', name=name), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-descriptions/add', methods=['POST'])
def add_common_description() -> Response:
    value = request.form.get('value', '').strip()
    if not value:
        flash(_('Description is required.'), 'error')
        return redirect(url_for('settings_bp.settings'))
    if not db.session.execute(db.select(CommonDescription).filter_by(value=value)).scalar():
        db.session.add(CommonDescription(value=value))
        db.session.commit()
    flash(_('"%(value)s" added to common descriptions.', value=value), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-descriptions/<int:item_id>/delete', methods=['POST'])
def delete_common_description(item_id: int) -> Response:
    item = db.session.get(CommonDescription, item_id) or abort(404)
    value = item.value
    db.session.delete(item)
    db.session.commit()
    flash(_('"%(value)s" removed from common descriptions.', value=value), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-prices/add', methods=['POST'])
def add_common_price() -> Response:
    try:
        value = parse_amount(request.form.get('value', ''), positive=True)
    except InputError:
        flash(_('Valid price is required.'), 'error')
        return redirect(url_for('settings_bp.settings'))
    if not db.session.execute(db.select(CommonPrice).filter_by(value=value)).scalar():
        db.session.add(CommonPrice(value=value))
        db.session.commit()
    flash(_('%(sym)s%(amount)s added to common prices.', sym=get_setting("currency_symbol", "\u20ac"), amount=fmt_amount(value)), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-prices/<int:item_id>/delete', methods=['POST'])
def delete_common_price(item_id: int) -> Response:
    item = db.session.get(CommonPrice, item_id) or abort(404)
    value = item.value
    db.session.delete(item)
    db.session.commit()
    flash(_('%(sym)s%(amount)s removed from common prices.', sym=get_setting("currency_symbol", "\u20ac"), amount=fmt_amount(value)), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-blacklist/add', methods=['POST'])
def add_common_blacklist() -> Response:
    bl_type = request.form.get('type', '').strip()
    value   = request.form.get('value', '').strip()
    if bl_type not in ('item', 'description', 'price') or not value:
        flash(_('Invalid blacklist entry.'), 'error')
        return redirect(url_for('settings_bp.settings'))
    if bl_type == 'price':
        # Stored like auto-collect compares it: '3,5' -> '3.50'.
        try:
            value = f'{parse_amount(value, positive=True):.2f}'
        except InputError:
            flash(_('Valid price is required.'), 'error')
            return redirect(url_for('settings_bp.settings'))
    if not db.session.execute(db.select(CommonBlacklist).filter_by(type=bl_type, value=value)).scalar():
        db.session.add(CommonBlacklist(type=bl_type, value=value))
        db.session.commit()
    flash(_('"%(value)s" added to %(type)s blacklist.', value=value, type=bl_type), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-blacklist/<int:item_id>/delete', methods=['POST'])
def delete_common_blacklist(item_id: int) -> Response:
    item = db.session.get(CommonBlacklist, item_id) or abort(404)
    value, bl_type = item.value, item.type
    db.session.delete(item)
    db.session.commit()
    flash(_('"%(value)s" removed from %(type)s blacklist.', value=value, type=bl_type), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common', methods=['POST'])
def settings_common() -> Response:
    enabled = '1' if request.form.get('common_enabled') else '0'
    set_setting('common_enabled', enabled)
    flash(_('Common autocomplete settings saved.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-auto', methods=['POST'])
def settings_common_auto() -> Response:
    enabled = '1' if request.form.get('common_auto_enabled') else '0'
    debug   = '1' if request.form.get('common_auto_debug')   else '0'
    day     = _cron_day('common_auto_day', '*')
    try:
        hour   = str(max(0, min(23, int(request.form.get('common_auto_hour',   '2')))))
        minute = str(max(0, min(59, int(request.form.get('common_auto_minute', '0')))))
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
        flash(_('Auto-collect schedule saved and enabled.'), 'success')
    else:
        if scheduler.get_job('common_job'):
            scheduler.remove_job('common_job')
        flash(_('Auto-collect schedule disabled.'), 'success')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-auto/run', methods=['POST'])
def settings_common_auto_run() -> Response:
    auto_collect_common()
    flash(_('Auto-collect job ran successfully.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/common-auto/clear-log', methods=['POST'])
def settings_common_auto_clear_log() -> Response:
    db.session.execute(db.delete(AutoCollectLog))
    db.session.commit()
    flash(_('Debug log cleared.'), 'success')
    return redirect(url_for('settings_bp.settings'))


TEMPLATE_COLOR_KEYS = ['color_navbar', 'color_email_grad_start', 'color_email_grad_end',
                       'color_balance_positive', 'color_balance_negative']
TEMPLATE_TEXT_KEYS = ['tpl_email_subject', 'tpl_email_greeting', 'tpl_email_intro',
                      'tpl_email_footer1', 'tpl_email_footer2',
                      'tpl_admin_subject', 'tpl_admin_intro', 'tpl_admin_footer',
                      'tpl_backup_subject', 'tpl_backup_footer']


def _store_unless_default(key: str, value: str, default: str) -> None:
    """Store a customized value; drop the row when it equals the default so that
    get_tpl() keeps falling through to the (language-specific) default."""
    if value == default:
        delete_setting(key, commit=False)
    else:
        set_setting(key, value, commit=False)


@settings_bp.route('/settings/templates', methods=['POST'])
def settings_templates() -> Response:
    for key in TEMPLATE_COLOR_KEYS:
        val = request.form.get(key, '').strip().lower()
        if re.match(r'^#[0-9a-f]{6}$', val):
            _store_unless_default(key, val, TEMPLATE_DEFAULTS[key])

    lang = get_setting('language', 'de')
    defaults = TEMPLATE_DEFAULTS_DE if lang == 'de' else TEMPLATE_DEFAULTS
    for key in TEMPLATE_TEXT_KEYS:
        _store_unless_default(f'{key}_{lang}', request.form.get(key, '')[:500], defaults[key])

    set_setting('admin_summary_include_emails', '1' if request.form.get('admin_summary_include_emails') else '0', commit=False)
    db.session.commit()

    flash(_('Templates saved.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/templates/reset', methods=['POST'])
def settings_templates_reset() -> Response:
    lang = get_setting('language', 'de')
    for key in TEMPLATE_TEXT_KEYS:
        delete_setting(f'{key}_{lang}', commit=False)
    for key in TEMPLATE_COLOR_KEYS:
        delete_setting(key, commit=False)
    db.session.commit()
    flash(_('Templates reset to defaults.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/icon', methods=['POST'])
def settings_icon() -> Response:
    action = request.form.get('action', '')
    icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    if action == 'generate':
        bg = get_tpl('color_navbar')
        generate_and_save_icons(bg)
        flash(_('Icon regenerated with current navbar color.'), 'success')

    elif action == 'reset':
        generate_and_save_icons(DEFAULT_ICON_BG)
        flash(_('Icon reset to default.'), 'success')

    elif action == 'upload':
        file = request.files.get('icon_file')
        if not file or not file.filename:
            flash(_('No file selected.'), 'danger')
            return redirect(url_for('settings_bp.settings'))

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ('png', 'jpg', 'jpeg'):
            flash(_('Only PNG or JPG files are accepted.'), 'danger')
            return redirect(url_for('settings_bp.settings'))

        try:
            from PIL import Image
            img = Image.open(file.stream)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            for size in (32, 192, 512):
                resized = img.resize((size, size), Image.LANCZOS)
                path = os.path.join(icons_dir, f'icon-{size}.png')
                resized.save(path, 'PNG')
            set_setting('icon_version', str(int(time.time())))
            flash(_('Custom icon uploaded.'), 'success')
        except ImportError:
            flash(_('Pillow is not installed \u2014 cannot process uploaded images.'), 'danger')
        except Exception as e:
            flash(_('Failed to process image: %(error)s', error=e), 'danger')
    else:
        flash(_('Unknown action.'), 'danger')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/templates/preview/email')
def preview_email() -> str:
    user = db.session.execute(db.select(User).filter_by(is_active=True).order_by(User.name)).scalar()
    if not user:
        # Transient sample user (never added to the session) so the preview works on an empty install.
        user = User(id=0, name='Jane Doe', email='jane@example.com', balance=Decimal('12.50'),
                    email_transactions='last3', email_opt_in=True)
    return build_email_html(user)


@settings_bp.route('/settings/templates/preview/admin-summary')
def preview_admin_summary() -> str:
    admin_id = get_setting('site_admin_id')
    users = db.session.execute(db.select(User).filter_by(is_active=True).order_by(User.name)).scalars().all()
    if admin_id:
        users = [u for u in users if str(u.id) != admin_id]
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
    day     = _cron_day('backup_day', '*')
    try:
        hour   = str(max(0, min(23, int(request.form.get('backup_hour',   '3')))))
        minute = str(max(0, min(59, int(request.form.get('backup_minute', '0')))))
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
        flash(_('Backup schedule saved and enabled.'), 'success')
    else:
        if scheduler.get_job('backup_job'):
            scheduler.remove_job('backup_job')
        flash(_('Backup schedule disabled.'), 'success')

    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/backup/create', methods=['POST'])
@limiter.limit("5/minute")
def settings_backup_create() -> Response:
    ok, result = run_backup()
    if ok:
        flash(_('Backup created: %(result)s', result=result), 'success')
    else:
        flash(_('Backup failed: %(result)s', result=result), 'error')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/settings/backup/clear-log', methods=['POST'])
def settings_backup_clear_log() -> Response:
    db.session.execute(db.delete(BackupLog))
    db.session.commit()
    flash(_('Backup debug log cleared.'), 'success')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/backups/download/<filename>')
def backup_download(filename: str) -> Response:
    if not BACKUP_FILENAME_RE.match(filename):
        abort(404)
    return send_from_directory(BACKUP_DIR, filename, as_attachment=True)


@settings_bp.route('/backups/delete/<filename>', methods=['POST'])
def backup_delete(filename: str) -> Response:
    if not BACKUP_FILENAME_RE.match(filename):
        flash(_('Invalid filename.'), 'error')
        return redirect(url_for('settings_bp.settings'))
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        flash(_('%(filename)s deleted.', filename=filename), 'success')
    else:
        flash(_('Backup file not found.'), 'error')
    return redirect(url_for('settings_bp.settings'))


@settings_bp.route('/backups/upload-chunk', methods=['POST'])
def backup_upload_chunk() -> tuple[Response, int] | Response:
    upload_id   = request.form.get('uploadId', '')
    chunk_file  = request.files.get('chunk')

    if not UPLOAD_ID_RE.match(upload_id):
        return jsonify({'error': _('Invalid upload ID')}), 400
    try:
        chunk_index  = int(request.form.get('chunkIndex', ''))
        total_chunks = int(request.form.get('totalChunks', ''))
    except (TypeError, ValueError):
        return jsonify({'error': _('Invalid chunk parameters')}), 400
    if not 0 < total_chunks <= MAX_UPLOAD_CHUNKS or not 0 <= chunk_index < total_chunks:
        return jsonify({'error': _('Invalid chunk parameters')}), 400
    if not chunk_file:
        return jsonify({'error': _('No chunk data')}), 400

    if chunk_index == 0:
        sweep_stale_uploads()
    tmp_dir = os.path.join(BACKUP_DIR, '.tmp', upload_id)
    os.makedirs(tmp_dir, exist_ok=True)
    chunk_file.save(os.path.join(tmp_dir, f'{chunk_index:05d}'))

    received = len([f for f in os.listdir(tmp_dir) if f.isdigit()])
    if received < total_chunks:
        return jsonify({'done': False, 'received': received, 'total': total_chunks})

    ok, result = assemble_upload(tmp_dir, total_chunks)
    if not ok:
        return jsonify({'error': result}), 400
    logger.info('Backup uploaded: %s', result)
    return jsonify({'done': True, 'filename': result})


def _migrate_after_restore() -> None:
    """Bring a restored (possibly older) schema up to the current migration head."""
    from flask_migrate import upgrade
    upgrade()


@settings_bp.route('/backups/restore/<filename>', methods=['POST'])
@limiter.limit("3/minute")
def backup_restore(filename: str) -> Response:
    if not BACKUP_FILENAME_RE.match(filename):
        flash(_('Invalid filename.'), 'error')
        return redirect(url_for('settings_bp.settings'))

    if not os.path.exists(os.path.join(BACKUP_DIR, filename)):
        flash(_('Backup file not found.'), 'error')
        return redirect(url_for('settings_bp.settings'))

    try:
        ok, result = run_restore(filename)
        if not ok:
            flash(result, 'error')
            return redirect(url_for('settings_bp.settings'))
        db.session.remove()
        _migrate_after_restore()
        reschedule_all(current_app._get_current_object())
        flash(_('Restore from %(filename)s completed successfully. The previous state was saved as %(safety)s.',
                filename=filename, safety=result), 'success')
    except Exception as e:
        logger.error('Backup restore failed: %s', str(e)[:200])
        flash(_('Restore failed: %(error)s', error=str(e)[:200]), 'error')

    return redirect(url_for('settings_bp.settings'))
