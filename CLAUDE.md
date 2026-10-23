# Bank of Tina

Self-hosted Flask/MariaDB web app for tracking shared expenses and balances in a small office.
No login; all configuration happens in the web UI (Settings). Runs in Docker on port 5000.
Repo `https://github.com/phoen-ix/bank-of-tina`, branch `main`. README.md is bilingual (German first,
then English) and carries the user manual.

## Commands

```bash
pip install -r docker/requirements-dev.txt
FLASK_TESTING=1 python -m pytest tests/ -v          # SQLite in-memory, no services needed
python -m pytest --collect-only -q | tail -1         # how many tests there are

flask db migrate -m "description"   # from app/, against a DB at the current head; runs on next start

# i18n, from the repo root so the #: references keep their app/ prefix
pybabel extract -F app/babel.cfg -k _ -k gettext -k lazy_gettext -o app/translations/messages.pot app
pybabel update -i app/translations/messages.pot -d app/translations
# edit app/translations/de/LC_MESSAGES/messages.po (new "fuzzy" guesses are usually wrong)
pybabel compile -d app/translations

# Docs screenshots (both languages) against throwaway stacks; Node 26 + Docker
cd e2e && npm ci && npx playwright install chromium && cd ..
PORT_BASE=24100 scripts/docs-screenshots.sh            # -> docs/screenshots/*.png, then oxipng them
```

On the fleet VM, Docker runs go through the fleet's `slot` gate (`slot heavy bank-of-tina -- …`);
`fleet check bank-of-tina` runs install/test/audit.

## Invariants

**Money**
- Every amount is `Decimal` / `db.Numeric(12, 4)` (4 decimals so split items like 0.3975 stay exact); the
  frontend mirrors it in `static/js/money.js` (integer units of 1/10000). Never floats.
- Read form amounts with `parse_amount()` (catch `InputError`), display with `fmt_amount()` / `|money`.
  Wrap a balance in `Decimal(str(...))` before arithmetic (PyMySQL may hand back floats).
- Change balances only via `adjust_balance()` / `apply_balance_effect()` (one atomic SQL
  `balance = balance + :delta`, safe across gunicorn threads). The stored `User.balance` is the source of
  truth - never recalculate it from transactions.
- Each route commits exactly once (rollback on `InputError`); edit/delete POSTs lock the transaction row
  (`with_for_update`) so a double submit can't reverse it twice. Validate before touching balances.

**Dates and time**
- Stored dates are naive UTC; form dates are local (the `timezone` setting). Convert input with
  `parse_local_datetime()` / `local_to_utc()`, filter with `local_days_utc()` / `local_month_utc()`
  (half-open `[start, end)`), display with `|localdt`.
- `datetime.now()` is UTC in Docker: use `now_local()` for display and filenames,
  `datetime.now(UTC).replace(tzinfo=None)` for stored values. `get_app_tz()` caches on `g`.

**Templates and frontend**
- No user data inside `<script>`: pass values with `|tojson`, or render HTML in a `<template>` element
  and clone it (see `add_transaction.html`). Translated JS strings: `{{ _('...')|tojson }}`, never
  `'{{ _('...') }}'` (gettext output is not escaped).
- CSP is nonce-based (`script-src 'self' 'nonce-…'`): no inline event handlers; scripts carry
  `nonce="{{ csp_nonce }}"`. All frontend libraries are self-hosted under `static/vendor/` - no CDN.
- `sw.js` cache constant is `'bot-v3'`; bump it when `offline.html` changes.

**Code structure**
- Never import from `app.py`; import `db`, `csrf`, `scheduler`, `limiter`, `babel` from `extensions.py`.
- SQLAlchemy 2.0 style only: `db.session.get()`, `db.session.execute(db.select(...))`, `db.paginate()`.
  Never `Model.query`.
- Blueprint `url_for` is prefixed: `main.index`, `settings_bp.settings`, `analytics_bp.analytics`.
- `email_service.py` imports stdlib `html`; never name a local variable `html` in a function that calls
  `html.escape()` (it becomes an unbound local - this crashed scheduled emails once).
- Log models clip `message`/`recipient` to the column length (`@validates`): MariaDB strict mode rejects
  over-long strings.
- `migrations/env.py` applies `alembic.ini` logging only when nothing configured logging yet - otherwise
  `fileConfig()` disables every app logger after the startup `upgrade()`.

**Scheduler and process model**
- Exactly one gunicorn worker (APScheduler must exist once); it runs 4 threads, so request code must be
  thread-safe.
- Scheduler jobs receive `app` and use `with app.app_context():`; wrap `_()` in
  `with force_locale(get_setting('language', 'de')):`. Never import `app` in service modules.
- `FLASK_TESTING=1` skips DB init, migrations and scheduler start at import time.

**i18n**
- Wrap every UI string: `_()` in Python, `{{ _('...') }}` in Jinja, `lazy_gettext` for module-level
  constants. Then extract/update/compile; commit both `.po` and `.mo`.
- Transaction types are stored in English (`expense`, `deposit`, `withdrawal`); translate at display
  time with `|tx_type`.
- Email templates (`tpl_*`) are stored per language (`tpl_email_subject_de`) and only when customized:
  saving a value equal to the default (or resetting) deletes the row; `get_tpl()` falls back to
  `TEMPLATE_DEFAULTS_DE` / `TEMPLATE_DEFAULTS`. Colour keys are language-independent.

**Docker, config, security**
- The app has no defaults for `DB_USER`/`DB_PASSWORD` and refuses the example `SECRET_KEY`; compose
  requires `SECRET_KEY`, `DB_PASSWORD`, `DB_ROOT_PASSWORD` (`:?`).
- No login: compose publishes `${BIND_ADDRESS:-127.0.0.1}:5000`. `BEHIND_PROXY=1` enables `ProxyFix` for
  exactly one reverse proxy.
- `/uploads`, `/backups` and `/app/static/icons` are bind mounts: clear their contents, never `rmtree`
  the directories. App code in the image is root-owned; the entrypoint fixes mount ownership, then
  drops to `appuser` (UID 1000) via gosu.
- The image has `mariadb` / `mariadb-dump` (the `mysql*` names don't exist on trixie). The DB password
  goes via `MYSQL_PWD`, never the command line; restores run `mariadb --sandbox`; tar extraction uses
  `filter='data'` and only `dump.sql` + `receipts/`.

**Docs tour and fleet**
- Never test against a checkout's plain `docker compose up`: it uses `./mariadb-data` and the project
  name `bank-of-tina`. The tour uses `docker-compose.e2e.yml` (named volumes, own container names) under
  `COMPOSE_PROJECT_NAME=bank-of-tina_docs`; the script refuses live names. Port block on the fleet VM:
  24100 (`PORT_BASE=24100`).
- The tour seeds through the web forms (`e2e/docs/seed.ts`) with fixed dates; screenshot names are
  stable once committed. bank-of-tina keeps a FULL screenshot set in both languages (`x.png` and
  `x.de.png`), embedded in both halves of the README manual and in `docs/screenshots/README.md`.
  Budget: ≤400 KB per PNG and ≤6 MB for the folder after `oxipng -o 4 --strip safe` - that is why
  long tabs are clipped above a section and only the History chart tab is shot. Crop, never lower DPR.

## Architecture

```
extensions.py  → flask_babel, flask_sqlalchemy, flask_wtf, flask_migrate, flask_limiter, apscheduler
config.py      → THEMES, TEMPLATE_DEFAULTS(_DE), CURRENCIES, CRON_DAYS, BACKUP_DIR, db_env()
models.py      → extensions                                  (11 models)
helpers.py     → extensions, models, config                  (money, time, settings, receipts, icons)
email_service  → extensions, models, helpers                 (build_* emails, Mailer, send_all_emails)
backup_service → extensions, models, helpers, config         (run_backup/run_restore, chunked upload)
scheduler_jobs → extensions, models, helpers, email_service, backup_service
routes/        → main_bp (dashboard, users, transactions, search, receipts, PWA, /offline, /health),
                 settings_bp (all settings tabs, common items, templates, icons, backups),
                 analytics_bp (/analytics page + /analytics/data JSON)
app.py         → assembly point: config, extensions, blueprints, filters, CSP, startup migration, scheduler
```

**Schema**: Flask-Migrate. On startup `app.py` stamps an existing pre-Alembic DB at head, otherwise runs
`upgrade()`; it retries the DB connection 5 times with backoff. `env.py` uses `render_as_batch=True`.

**Settings**: key/value rows in `Setting` (`get_setting(key, default)`, `set_setting(key, value,
commit=True)`). Defaults live at the call sites; the full list with defaults is the `cfg` dict in
`routes/settings.py:settings()`. The page remembers its tab in `sessionStorage`; `?tab=<name>` wins.

**Balances**: `from_user` pays (expense debtor, withdrawal), `to_user` receives (expense buyer, deposit).
An expense creates one transaction per debtor (the buyer's own items are not recorded), all sharing the
receipt. The site admin (`site_admin_id`) is the "bank": hidden from the dashboard table and from the
admin summary, but present everywhere else.

**Scheduler**: one `BackgroundScheduler`, jobs `email_job`, `common_job` (auto-collect), `backup_job`;
`misfire_grace_time=3600`, `coalesce=True`. `_restore_schedule(app)` re-creates them at startup and
skips a job with broken settings; `reschedule_all(app)` after a timezone change or restore.

**Email**: `Mailer` keeps one SMTP connection per run (STARTTLS / SSL / none, certificates always
verified, 30 s timeout), reconnects once, fails the rest of the run fast on connect/TLS/login errors.
Failures always go to `EmailLog`, successes only with `email_debug`. Placeholder values are
HTML-escaped; template text is admin-authored HTML. The backup status email is sent after
*scheduled* backups only.

**Backup/restore**: `bot_backup_YYYY_MM_DD_HH-mm-ss.tar.gz` (mode 0600, `-N` suffix instead of
overwriting) with `dump.sql`, `receipts/`, `.env`. Restore makes a safety backup first, restores the DB,
only then replaces receipts; the route then runs `upgrade()` and `reschedule_all()`. Uploads come in
5 MB chunks (max 400 = 2 GB); `MAX_CONTENT_LENGTH` is 10 MB per request.

**Analytics**: balance history starts from the stored balances and reverses every transaction after
local day T; weekly samples up to 90 days, monthly beyond.

## Tests

`tests/conftest.py`: session-scoped `app` (SQLite in-memory, uploads in a tmp dir), autouse `clean_db`
empties all tables, removes scheduler jobs and sets `language='en'` (tests see English msgids).
`backup_dir` points `BACKUP_DIR`/`UPLOAD_FOLDER` at tmp dirs; tests mock `subprocess.run` / `smtplib`.
- CSRF is off; the limiter is switched off with `limiter.enabled = False` (`RATELIMIT_ENABLED` is only
  read in `init_app`, which already ran at import).
- Test requests share the test's app context (and `g`, session): Flask-Babel caches the locale on
  `g._flask_babel.babel_locale` - clear it when switching languages mid-test; set `timezone` before the
  first request.

## More

- `docs/history.md` - why things are the way they are (refactors, past bugs).
- `docs/screenshots/README.md` - screenshot gallery (doubles as the screen manual).
- `e2e/docs/` - the docs tour; `scripts/docs-screenshots.sh` - its single entry point.
