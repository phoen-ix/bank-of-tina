from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime

from flask import current_app

from extensions import db
from models import BackupLog
from helpers import get_setting, get_tpl, apply_template, now_local, fmt_amount
from config import BACKUP_DIR

logger = logging.getLogger(__name__)

_db_user = os.environ.get('DB_USER', 'tina')
_db_pass = os.environ.get('DB_PASSWORD', 'tina')
_db_host = os.environ.get('DB_HOST', 'localhost')
_db_port = os.environ.get('DB_PORT', '3306')
_db_name = os.environ.get('DB_NAME', 'bank_of_tina')


def _backup_log(level: str, message: str) -> None:
    db.session.add(BackupLog(level=level, message=message))
    db.session.commit()


def run_backup() -> tuple[bool, str]:
    """Create a full backup tar.gz in BACKUP_DIR. Returns (True, filename) or (False, error_msg)."""
    debug = get_setting('backup_debug', '0') == '1'

    def log(level: str, msg: str) -> None:
        if debug:
            _backup_log(level, msg)

    ts = now_local().strftime('%Y_%m_%d_%H-%M-%S')
    filename = f'bot_backup_{ts}.tar.gz'
    dest = os.path.join(BACKUP_DIR, filename)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory() as tmp:
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

            receipts_dest = os.path.join(tmp, 'receipts')
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if os.path.exists(upload_folder):
                shutil.copytree(upload_folder, receipts_dest)
            else:
                os.makedirs(receipts_dest)
            log('INFO', 'Receipts copied')

            env_keys = ['DB_ROOT_PASSWORD', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
                        'SECRET_KEY', 'SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME',
                        'SMTP_PASSWORD', 'FROM_EMAIL', 'FROM_NAME']
            env_lines = [f'{k}={os.environ.get(k, "")}' for k in env_keys if os.environ.get(k)]
            with open(os.path.join(tmp, '.env'), 'w') as f:
                f.write('\n'.join(env_lines) + '\n')
            log('INFO', '.env reconstructed')

            with tarfile.open(dest, 'w:gz') as tar:
                tar.add(dump_path, arcname='dump.sql')
                tar.add(receipts_dest, arcname='receipts')
                tar.add(os.path.join(tmp, '.env'), arcname='.env')

        log('SUCCESS', f'Backup created: {filename}')
        logger.info('Backup created: %s', filename)
        return True, filename

    except Exception as e:
        err = str(e)[:300]
        log('ERROR', err)
        logger.error('Backup failed: %s', err)
        if os.path.exists(dest):
            os.remove(dest)
        return False, err


def _prune_old_backups(keep: int) -> None:
    """Delete oldest backups keeping only the most recent `keep` files."""
    if keep <= 0:
        return
    files = sorted([
        f for f in os.listdir(BACKUP_DIR)
        if re.match(r'^bot_backup_[\d_-]+\.tar\.gz$', f)
    ])
    while len(files) > keep:
        os.remove(os.path.join(BACKUP_DIR, files.pop(0)))


def _list_backups() -> list[dict[str, str | int | datetime]]:
    """Return list of dicts with backup file info, newest first."""
    backups: list[dict[str, str | int | datetime]] = []
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


def build_backup_status_email(ok: bool, result: str, kept: int, pruned: int) -> str:
    date_str   = now_local().strftime('%Y-%m-%d %H:%M')
    grad_start = get_tpl('color_email_grad_start')
    grad_end   = get_tpl('color_email_grad_end')
    footer     = apply_template(get_tpl('tpl_backup_footer'), Date=date_str)
    footer_html = f'<p>{footer}</p>' if footer.strip() else ''

    if ok:
        status_color = '#28a745'
        status_icon  = '\u2714'
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
        status_icon  = '\u2718'
        status_text  = 'Backup failed'
        detail_rows  = f"""
            <tr><td style="padding:8px;color:#6c757d;width:140px;">Error</td>
                <td style="padding:8px;color:#dc3545;">{result}</td></tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height:1.6; color:#333; max-width:600px; margin:0 auto; padding:20px;">
    <div style="background:linear-gradient(135deg,{grad_start} 0%,{grad_end} 100%); color:white; padding:30px; border-radius:10px 10px 0 0; text-align:center;">
        <h1 style="margin:0; font-size:28px;">\U0001f3e6 Bank of Tina</h1>
        <p style="margin:10px 0 0 0; opacity:0.9;">Scheduled Backup Report \u2014 {date_str}</p>
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
