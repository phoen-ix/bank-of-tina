import io
import logging
import os
import stat
import subprocess
import tarfile

import pytest


def _make_archive(path, members):
    """Write a tar.gz at `path` with {name: bytes} members."""
    with tarfile.open(path, 'w:gz') as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


class FakeDb:
    """Stands in for subprocess.run: records calls, 'dumps' and 'restores'."""

    def __init__(self, restore_rc=0):
        self.calls = []
        self.restore_rc = restore_rc

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if cmd[0] == 'mariadb-dump':
            kwargs['stdout'].write(b'-- dump\n')
            return subprocess.CompletedProcess(cmd, 0, stderr=b'')
        return subprocess.CompletedProcess(cmd, self.restore_rc, stderr=b'restore broke')


def test_backup_keeps_password_out_of_argv(app, backup_dir, monkeypatch):
    import backup_service

    fake = FakeDb()
    monkeypatch.setattr(backup_service.subprocess, 'run', fake)
    monkeypatch.setenv('DB_PASSWORD', 's3cret')

    with app.app_context():
        ok, filename = backup_service.run_backup()

    assert ok, filename
    cmd, kwargs = fake.calls[0]
    assert cmd[0] == 'mariadb-dump'
    assert '--single-transaction' in cmd
    assert not any('s3cret' in part for part in cmd)
    assert kwargs['env']['MYSQL_PWD'] == 's3cret'

    path = backup_dir / filename
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    with tarfile.open(path) as tar:
        names = tar.getnames()
    assert {'dump.sql', 'receipts', '.env'} <= set(names)


def test_backup_names_never_collide(app, backup_dir, monkeypatch):
    import backup_service

    monkeypatch.setattr(backup_service.subprocess, 'run', FakeDb())
    with app.app_context():
        first = backup_service.run_backup()[1]
        second = backup_service.run_backup()[1]
    assert first != second
    assert backup_service.BACKUP_FILENAME_RE.match(second)


def test_restore_order_and_sandbox(app, backup_dir, monkeypatch):
    import backup_service

    fake = FakeDb()
    monkeypatch.setattr(backup_service.subprocess, 'run', fake)
    uploads = app.config['UPLOAD_FOLDER']
    with open(os.path.join(uploads, 'old.txt'), 'w') as f:
        f.write('old')
    _make_archive(
        backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz',
        {
            'dump.sql': b'SELECT 1;',
            'receipts/2026/01/01/new.txt': b'new',
            '.env': b'SECRET_KEY=x',
        },
    )

    with app.app_context():
        ok, safety = backup_service.run_restore('bot_backup_2026_01_01_00-00-00.tar.gz')

    assert ok, safety
    # Safety backup first, then the sandboxed restore.
    assert [c[0][0] for c in fake.calls] == ['mariadb-dump', 'mariadb']
    assert '--sandbox' in fake.calls[1][0]
    assert (backup_dir / safety).exists()
    assert os.path.exists(os.path.join(uploads, '2026/01/01/new.txt'))
    assert not os.path.exists(os.path.join(uploads, 'old.txt'))


def test_restore_runs_outside_a_db_transaction(app, backup_dir, monkeypatch):
    """The restore client drops every table: an open transaction of this request
    (metadata locks of earlier reads) would make it wait forever."""
    import backup_service
    from extensions import db

    fake = FakeDb()
    open_tx = []

    def run(cmd, **kwargs):
        if cmd[0] == 'mariadb':
            open_tx.append(db.session().in_transaction())
        return fake(cmd, **kwargs)

    monkeypatch.setattr(backup_service.subprocess, 'run', run)
    _make_archive(backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz', {'dump.sql': b'SELECT 1;'})
    with app.app_context():
        ok, safety = backup_service.run_restore('bot_backup_2026_01_01_00-00-00.tar.gz')
    assert ok, safety
    assert open_tx == [False]


def test_restore_db_failure_keeps_receipts(app, backup_dir, monkeypatch):
    import backup_service

    monkeypatch.setattr(backup_service.subprocess, 'run', FakeDb(restore_rc=1))
    uploads = app.config['UPLOAD_FOLDER']
    with open(os.path.join(uploads, 'old.txt'), 'w') as f:
        f.write('old')
    _make_archive(
        backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz',
        {
            'dump.sql': b'SELECT 1;',
            'receipts/new.txt': b'new',
        },
    )

    with app.app_context():
        ok, err = backup_service.run_restore('bot_backup_2026_01_01_00-00-00.tar.gz')

    assert not ok
    assert 'restore broke' in err
    assert os.path.exists(os.path.join(uploads, 'old.txt'))
    assert not os.path.exists(os.path.join(uploads, 'new.txt'))


def test_restore_requires_dump(app, backup_dir, monkeypatch):
    import backup_service

    fake = FakeDb()
    monkeypatch.setattr(backup_service.subprocess, 'run', fake)
    _make_archive(backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz', {'receipts/a.txt': b'a'})

    with app.app_context():
        ok, _ = backup_service.run_restore('bot_backup_2026_01_01_00-00-00.tar.gz')

    assert not ok
    assert fake.calls == []


def test_restore_ignores_unexpected_members(app, backup_dir, monkeypatch, tmp_path):
    import backup_service

    monkeypatch.setattr(backup_service.subprocess, 'run', FakeDb())
    _make_archive(
        backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz',
        {
            'dump.sql': b'SELECT 1;',
            '../escaped.txt': b'x',
            'receipts/../../escaped2.txt': b'x',
        },
    )

    with app.app_context():
        ok, _ = backup_service.run_restore('bot_backup_2026_01_01_00-00-00.tar.gz')

    assert ok
    assert not (tmp_path / 'escaped.txt').exists()
    assert not (tmp_path / 'escaped2.txt').exists()


def test_restore_route_migrates_and_reschedules(client, app, backup_dir, monkeypatch):
    import routes.settings as settings_routes

    calls = []
    monkeypatch.setattr(settings_routes, 'run_restore', lambda f: (True, 'bot_backup_safety.tar.gz'))
    monkeypatch.setattr(settings_routes, '_migrate_after_restore', lambda: calls.append('migrate'))
    monkeypatch.setattr(settings_routes, 'reschedule_all', lambda a: calls.append('reschedule'))
    (backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz').write_bytes(b'x')

    response = client.post('/backups/restore/bot_backup_2026_01_01_00-00-00.tar.gz', follow_redirects=True)

    assert response.status_code == 200
    assert calls == ['migrate', 'reschedule']
    assert b'bot_backup_safety.tar.gz' in response.data


def _upload(client, data, chunk=b'x'):
    form = {'uploadId': '12345678-1234-1234-1234-123456789abc', **data, 'chunk': (io.BytesIO(chunk), 'chunk')}
    return client.post('/backups/upload-chunk', data=form, content_type='multipart/form-data')


def test_upload_rejects_bad_chunk_parameters(client, app, backup_dir):
    from backup_service import MAX_UPLOAD_CHUNKS

    for data in (
        {'chunkIndex': '0', 'totalChunks': '0'},
        {'chunkIndex': '3', 'totalChunks': '2'},
        {'chunkIndex': '-1', 'totalChunks': '2'},
        {'chunkIndex': '0', 'totalChunks': str(MAX_UPLOAD_CHUNKS + 1)},
    ):
        assert _upload(client, data).status_code == 400
    assert not [f for f in os.listdir(backup_dir) if f.endswith('.tar.gz')]


def test_upload_assembles_archive(client, app, backup_dir, tmp_path):
    archive = tmp_path / 'upload.tar.gz'
    _make_archive(archive, {'dump.sql': b'SELECT 1;'})
    raw = archive.read_bytes()
    half = len(raw) // 2

    r1 = _upload(client, {'chunkIndex': '0', 'totalChunks': '2'}, raw[:half])
    assert r1.get_json()['done'] is False
    r2 = _upload(client, {'chunkIndex': '1', 'totalChunks': '2'}, raw[half:])
    data = r2.get_json()
    assert data['done'] is True
    assert (backup_dir / data['filename']).read_bytes() == raw
    assert not os.listdir(backup_dir / '.tmp')


def test_upload_rejects_non_archive(client, app, backup_dir):
    response = _upload(client, {'chunkIndex': '0', 'totalChunks': '1'}, b'not a tarball')
    assert response.status_code == 400
    assert not [f for f in os.listdir(backup_dir) if f.endswith('.tar.gz')]


def test_upload_failure_does_not_leak_the_os_error(client, app, backup_dir, tmp_path, monkeypatch):
    import backup_service

    monkeypatch.setattr(
        backup_service, '_new_backup_path', lambda: ('x.tar.gz', str(tmp_path / 'no-such-dir' / 'x.tar.gz'))
    )
    response = _upload(client, {'chunkIndex': '0', 'totalChunks': '1'})
    assert response.status_code == 400
    assert response.get_json()['error'] == 'The uploaded backup could not be saved.'
    assert 'no-such-dir' not in response.get_data(as_text=True)


def test_names_with_a_trailing_newline_are_refused(client, app, backup_dir):
    """'$' in the old patterns matched before a final newline."""
    (backup_dir / 'bot_backup_2026_01_01_00-00-00.tar.gz').write_bytes(b'x')
    name = 'bot_backup_2026_01_01_00-00-00.tar.gz%0A'
    assert client.get(f'/backups/download/{name}').status_code == 404
    for action in ('delete', 'restore'):
        response = client.post(f'/backups/{action}/{name}', follow_redirects=True)
        assert 'Invalid filename.' in response.get_data(as_text=True)
    form = {
        'uploadId': '12345678-1234-1234-1234-123456789abc\n',
        'chunkIndex': '0',
        'totalChunks': '2',
        'chunk': (io.BytesIO(b'x'), 'chunk'),
    }
    response = client.post('/backups/upload-chunk', data=form, content_type='multipart/form-data')
    assert response.status_code == 400
    assert not (backup_dir / '.tmp').exists()


def test_path_inside_refuses_to_leave_the_root(tmp_path):
    from helpers import path_inside

    assert path_inside(str(tmp_path), 'a', 'b.txt') == str(tmp_path / 'a' / 'b.txt')
    for parts in (('..', 'x'), ('/etc/passwd',), ('a', '../../x'), ('.',)):
        with pytest.raises(ValueError):
            path_inside(str(tmp_path), *parts)


def test_migrations_keep_app_logging(app):
    """Running Alembic must not disable the app's loggers (fileConfig default)."""
    from flask_migrate import upgrade

    root_handlers = list(logging.getLogger().handlers)
    with app.app_context():
        upgrade(sql=True)
    assert logging.getLogger().handlers == root_handlers
    for name in ('email_service', 'backup_service', 'routes.main'):
        assert logging.getLogger(name).disabled is False


def test_backup_job_prunes_to_keep_and_mails_admin(app, backup_dir, make_user, monkeypatch):
    import scheduler_jobs
    from extensions import scheduler

    names = [f'bot_backup_2026_01_0{d}_03-00-00.tar.gz' for d in range(1, 5)]

    def fake_backup():
        for name in names:
            (backup_dir / name).write_bytes(b'x')
        return True, names[-1]

    sent = []
    monkeypatch.setattr(scheduler_jobs, 'run_backup', fake_backup)
    monkeypatch.setattr(scheduler_jobs, 'send_single_email', lambda *a: sent.append(a) or (True, None))
    with app.app_context():
        from helpers import set_setting

        admin = make_user(email='admin@example.com')
        set_setting('site_admin_id', str(admin.id))
        set_setting('backup_admin_email', '1')
        set_setting('backup_keep', '2')
        scheduler_jobs._add_backup_job(app)
        try:
            scheduler.get_job('backup_job').func()
        finally:
            scheduler.remove_all_jobs()

    assert sorted(p.name for p in backup_dir.iterdir()) == names[-2:]
    assert len(sent) == 1
    to_email, _name, subject, html = sent[0]
    assert to_email == 'admin@example.com'
    assert subject.startswith('Bank of Tina - Backup Success (')
    assert '2 old backup(s) deleted' in html
