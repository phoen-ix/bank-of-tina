from __future__ import annotations

import html as html_mod
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import UTC, datetime

from flask import current_app

from flask_babel import gettext as _

from extensions import db
from models import BackupLog
from helpers import get_setting, get_tpl, apply_template, now_local, prune_log
from config import BACKUP_DIR, db_env

logger = logging.getLogger(__name__)

# Archive members restore extracts; everything else (e.g. the .env copy) is ignored.
_RESTORABLE = ('dump.sql', 'receipts')
# Upload chunks are 5 MB (settings.html); 400 chunks = 2 GB.
MAX_UPLOAD_CHUNKS = 400
_STALE_UPLOAD_SECONDS = 24 * 3600
BACKUP_FILENAME_RE: re.Pattern[str] = re.compile(r'^bot_backup_[\d_-]+\.tar\.gz$')


def _backup_log(level: str, message: str) -> None:
    db.session.add(BackupLog(level=level, message=message))
    db.session.flush()
    prune_log(BackupLog)
    db.session.commit()


def _db_command(binary: str, *extra: str) -> tuple[list[str], dict[str, str]]:
    """Build a mariadb/mariadb-dump command line. The password goes through the
    environment (MYSQL_PWD) so it never shows up in the process list."""
    cfg = db_env()
    cmd = [binary, '-h', cfg['host'], '-P', cfg['port'], '-u', cfg['user'], *extra, cfg['name']]
    env = {**os.environ, 'MYSQL_PWD': cfg['password']}
    return cmd, env


def _new_backup_path() -> tuple[str, str]:
    """Return (filename, path) for a new archive; never reuses an existing name."""
    ts = now_local().strftime('%Y_%m_%d_%H-%M-%S')
    filename = f'bot_backup_{ts}.tar.gz'
    n = 1
    while os.path.exists(os.path.join(BACKUP_DIR, filename)):
        filename = f'bot_backup_{ts}-{n}.tar.gz'
        n += 1
    return filename, os.path.join(BACKUP_DIR, filename)


def run_backup() -> tuple[bool, str]:
    """Create a full backup tar.gz in BACKUP_DIR. Returns (True, filename) or (False, error_msg)."""
    debug = get_setting('backup_debug', '0') == '1'

    def log(level: str, msg: str) -> None:
        if debug:
            _backup_log(level, msg)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename, dest = _new_backup_path()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            dump_path = os.path.join(tmp, 'dump.sql')
            cmd, env = _db_command('mariadb-dump', '--single-transaction', '--add-drop-table')
            with open(dump_path, 'wb') as dump_file:
                result = subprocess.run(cmd, stdout=dump_file, stderr=subprocess.PIPE,
                                        env=env, timeout=300)
            if result.returncode != 0:
                err = result.stderr.decode(errors='replace')[:300]
                log('ERROR', f'mariadb-dump failed: {err}')
                return False, f'mariadb-dump failed: {err}'
            log('INFO', 'SQL dump created')

            receipts_dest = os.path.join(tmp, 'receipts')
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if os.path.exists(upload_folder):
                shutil.copytree(upload_folder, receipts_dest)
            else:
                os.makedirs(receipts_dest)
            log('INFO', 'Receipts copied')

            env_keys = ['DB_ROOT_PASSWORD', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'SECRET_KEY']
            env_lines = [f'{k}={os.environ.get(k, "")}' for k in env_keys if os.environ.get(k)]
            with open(os.path.join(tmp, '.env'), 'w') as f:
                f.write('\n'.join(env_lines) + '\n')
            log('INFO', '.env reconstructed')

            # The archive holds credentials: create it owner-only from the start.
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as raw, tarfile.open(fileobj=raw, mode='w:gz') as tar:
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


def _restorable(name: str) -> bool:
    name = os.path.normpath(name)
    return name in _RESTORABLE or name.startswith('receipts' + os.sep)


def _replace_dir_contents(target: str, source: str) -> None:
    """Empty `target` (a bind mount, so it can't be removed itself) and copy `source` into it."""
    for item in os.listdir(target):
        item_path = os.path.join(target, item)
        if os.path.isdir(item_path) and not os.path.islink(item_path):
            shutil.rmtree(item_path)
        else:
            os.remove(item_path)
    shutil.copytree(source, target, dirs_exist_ok=True)


def run_restore(filename: str) -> tuple[bool, str]:
    """Restore database and receipts from BACKUP_DIR/filename.

    Order matters: a safety backup of the current state is taken first, then
    the database is restored, and only if that succeeded are the receipts
    replaced. Returns (True, safety_backup_filename) or (False, error_msg).
    """
    path = os.path.join(BACKUP_DIR, filename)
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(path, 'r:gz') as tar:
            members = [m for m in tar.getmembers() if _restorable(m.name)]
            # filter='data' rejects links pointing outside, device files,
            # absolute paths and '..' traversal.
            tar.extractall(tmp, members=members, filter='data')

        dump_path = os.path.join(tmp, 'dump.sql')
        if not os.path.isfile(dump_path):
            return False, _('The archive does not contain a database dump.')

        ok, safety = run_backup()
        if not ok:
            return False, _('Could not create a safety backup of the current data: %(err)s', err=safety)

        # --sandbox makes the client refuse shell escapes (\!) and other
        # client-side commands embedded in a crafted dump.
        cmd, env = _db_command('mariadb', '--sandbox')
        with open(dump_path, 'rb') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, env=env, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode(errors='replace')[:300]
            return False, _('Database restore failed: %(err)s', err=err)

        receipts_src = os.path.join(tmp, 'receipts')
        if os.path.isdir(receipts_src):
            _replace_dir_contents(current_app.config['UPLOAD_FOLDER'], receipts_src)

    logger.info('Backup restored: %s (safety backup %s)', filename, safety)
    return True, safety


def sweep_stale_uploads() -> None:
    """Remove chunk directories of uploads abandoned more than a day ago."""
    tmp_root = os.path.join(BACKUP_DIR, '.tmp')
    if not os.path.isdir(tmp_root):
        return
    cutoff = time.time() - _STALE_UPLOAD_SECONDS
    for entry in os.listdir(tmp_root):
        entry_path = os.path.join(tmp_root, entry)
        try:
            if os.path.getmtime(entry_path) < cutoff:
                shutil.rmtree(entry_path, ignore_errors=True)
        except OSError:
            pass


def assemble_upload(chunk_dir: str, total_chunks: int) -> tuple[bool, str]:
    """Join uploaded chunks into a new backup archive.

    Returns (True, filename) or (False, error_msg). The chunk directory is
    always removed.
    """
    filename, dest = _new_backup_path()
    try:
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as out:
            for i in range(total_chunks):
                with open(os.path.join(chunk_dir, f'{i:05d}'), 'rb') as c:
                    shutil.copyfileobj(c, out)
        if not tarfile.is_tarfile(dest):
            os.remove(dest)
            return False, _('The uploaded file is not a backup archive.')
        return True, filename
    except OSError as e:
        if os.path.exists(dest):
            os.remove(dest)
        return False, str(e)[:300]
    finally:
        shutil.rmtree(chunk_dir, ignore_errors=True)


def _prune_old_backups(keep: int) -> None:
    """Delete oldest backups keeping only the most recent `keep` files."""
    if keep <= 0:
        return
    files = sorted(f for f in os.listdir(BACKUP_DIR) if BACKUP_FILENAME_RE.match(f))
    while len(files) > keep:
        os.remove(os.path.join(BACKUP_DIR, files.pop(0)))


def _list_backups() -> list[dict[str, str | int | datetime]]:
    """Return list of dicts with backup file info, newest first."""
    backups: list[dict[str, str | int | datetime]] = []
    if os.path.exists(BACKUP_DIR):
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if BACKUP_FILENAME_RE.match(f):
                fpath = os.path.join(BACKUP_DIR, f)
                stat = os.stat(fpath)
                backups.append({
                    'filename': f,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime, tz=UTC),
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
        status_text  = _('Backup completed successfully')
        detail_rows  = f"""
            <tr><td style="padding:8px;color:#6c757d;width:140px;">{_('File')}</td>
                <td style="padding:8px;font-family:monospace;">{html_mod.escape(result)}</td></tr>
            <tr><td style="padding:8px;color:#6c757d;">{_('Backups kept')}</td>
                <td style="padding:8px;">{kept}</td></tr>"""
        if pruned:
            detail_rows += f"""
            <tr><td style="padding:8px;color:#6c757d;">{_('Pruned')}</td>
                <td style="padding:8px;">{_('%(count)d old backup(s) deleted', count=pruned)}</td></tr>"""
    else:
        status_color = '#dc3545'
        status_icon  = '\u2718'
        status_text  = _('Backup failed')
        detail_rows  = f"""
            <tr><td style="padding:8px;color:#6c757d;width:140px;">{_('Error')}</td>
                <td style="padding:8px;color:#dc3545;">{html_mod.escape(result)}</td></tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height:1.6; color:#333; max-width:600px; margin:0 auto; padding:20px;">
    <div style="background:linear-gradient(135deg,{grad_start} 0%,{grad_end} 100%); color:white; padding:30px; border-radius:10px 10px 0 0; text-align:center;">
        <h1 style="margin:0; font-size:28px;">\U0001f3e6 Bank of Tina</h1>
        <p style="margin:10px 0 0 0; opacity:0.9;">{_('Scheduled Backup Report')} \u2014 {date_str}</p>
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
