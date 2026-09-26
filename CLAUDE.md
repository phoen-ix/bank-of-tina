# Bank of Tina

Self-hosted Flask/MariaDB web app for tracking shared expenses and balances within a small office or group. Runs entirely in Docker with no external dependencies. All configuration is done through the web UI.

- **Repo:** `https://github.com/phoen-ix/bank-of-tina`
- **Branch:** `main`
- **Runtime URL:** `http://<server>:5000`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14, Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Babel 4.0 |
| Database | MariaDB 12.3 (via PyMySQL) |
| ORM | SQLAlchemy with Flask-Migrate (Alembic) for schema migrations |
| Monetary types | `Decimal` / `db.Numeric(12, 2)` everywhere (no floats) |
| Rate limiting | Flask-Limiter 3.5 (in-memory, per-route limits, no global default) |
| Scheduler | APScheduler `BackgroundScheduler` |
| Timezone | pytz |
| Logging | Python `logging` to stdout, structured format |
| Type hints | `from __future__ import annotations` on all modules |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.10, Chart.js 4.4, vanilla JS (all self-hosted under `static/vendor/`, no CDN) |
| Container | Docker + docker-compose, gunicorn (1 worker, 4 threads, 300 s timeout), non-root user via gosu entrypoint, app code root-owned |
| i18n | Flask-Babel, gettext `.po`/`.mo` files, ~500 translated strings (German + English) |
| Testing | pytest with SQLite in-memory (`FLASK_TESTING=1`), 172 tests |
| DB tools | `mariadb-client` installed in image for the `mariadb-dump`/`mariadb` CLI (the `mysql*` names are not installed on trixie) |

---

## File Structure

The backend was split from a single 2300-line `app.py` into a modular Flask Blueprint architecture. The extensions pattern (`extensions.py` holds unbound instances; `app.py` binds them) prevents circular imports.

```
bank-of-tina/
├── app/
│   ├── app.py                    # Thin entry point: create app, init extensions, register blueprints, start scheduler
│   ├── extensions.py             # Shared instances: db, csrf, migrate, limiter, scheduler, babel
│   ├── config.py                 # Constants: THEMES, TEMPLATE_DEFAULTS(_DE), ALLOWED_EXTENSIONS, BACKUP_DIR, DEFAULT_ICON_BG, CURRENCIES, CRON_DAYS, LOG_KEEP; db_env()
│   ├── models.py                 # All 11 SQLAlchemy model classes (fully type-annotated)
│   ├── helpers.py                # Utility functions (parse_amount, fmt_amount, adjust_balance, tz helpers, save_receipt, etc.)
│   ├── email_service.py          # build_email_html, build_admin_summary_email, Mailer, send_single_email, send_all_emails
│   ├── backup_service.py         # run_backup, run_restore, assemble_upload, sweep_stale_uploads, _prune_old_backups, _list_backups, build_backup_status_email
│   ├── scheduler_jobs.py         # _add_email_job, _add_common_job, _add_backup_job, auto_collect_common, _restore_schedule, reschedule_all
│   ├── babel.cfg                 # Babel extraction config
│   ├── translations/             # Gettext i18n files (Flask-Babel)
│   │   ├── messages.pot          # Extracted translation template
│   │   ├── de/LC_MESSAGES/       # German translations (.po + .mo)
│   │   └── en/LC_MESSAGES/       # English translations (.po + .mo, msgstr empty — falls back to msgid)
│   ├── migrations/               # Alembic migrations (Flask-Migrate)
│   │   └── versions/             # Migration scripts
│   ├── routes/
│   │   ├── __init__.py           # register_blueprints(app) — registers all 3 blueprints
│   │   ├── main.py               # main_bp: health, dashboard, users (add/edit/toggle), transactions, search, receipts, PWA, /offline
│   │   ├── settings.py           # settings_bp: all settings, common items, backup/upload/restore, templates, icons
│   │   └── analytics.py          # analytics_bp: charts page + JSON data endpoint
│   ├── templates/
│   │   ├── base.html             # Shared layout; injects dynamic theme CSS + PWA tags
│   │   ├── index.html            # Dashboard (active users only)
│   │   ├── add_transaction.html
│   │   ├── edit_transaction.html # Edit transaction + receipt upload/remove
│   │   ├── transactions.html     # Month-by-month view
│   │   ├── search.html           # Cross-month search with advanced filters and pagination
│   │   ├── user_detail.html      # User profile with paginated transaction history
│   │   ├── _pagination.html      # Reusable Bootstrap 5 pagination partial
│   │   ├── analytics.html        # Charts & Statistics page (4-tab Chart.js dashboard)
│   │   ├── settings.html         # All settings tabs (General/Email/Common/Backup/Templates/Users)
│   │   └── offline.html          # Standalone offline page (served at /offline, cached by the service worker)
│   └── static/
│       ├── sw.js                 # Service worker (navigations only; offline page on network failure)
│       ├── js/money.js           # parseCents/fmtCents for the expense forms (mirrors helpers.parse_amount)
│       ├── vendor/               # Self-hosted frontend dependencies (no CDN)
│       │   ├── css/              # bootstrap.min.css, bootstrap-icons.css
│       │   ├── js/               # bootstrap.bundle.min.js, chart.umd.min.js
│       │   └── fonts/            # bootstrap-icons.woff2, bootstrap-icons.woff
│       └── icons/                # icon-32/192/512.png — generated at startup if missing (not in git; bind-mounted)
├── tests/
│   ├── conftest.py               # pytest fixtures: app, client, clean_db, make_user factory, backup_dir
│   ├── test_helpers.py           # parse_amount, fmt_amount, hex_to_rgb, apply_template
│   ├── test_models.py            # User, Transaction, ExpenseItem, Setting, CommonItem
│   ├── test_routes.py            # Dashboard, transactions, search, edit
│   ├── test_settings.py          # Settings CRUD, common items, templates, schedule
│   ├── test_analytics.py         # Analytics page and data endpoint
│   ├── test_health.py            # Health endpoint, security headers, safe redirects
│   ├── test_email_service.py     # Email building
│   ├── test_email_sending.py     # SMTP: TLS modes, cert verification, headers, batching, escaping
│   ├── test_backup.py            # Backup/restore/upload (subprocess mocked), migration logging
│   ├── test_money_time.py        # Balance integrity, amount parsing, timezone bounds, receipts, themes
│   ├── test_validation.py        # Input validation, schedule robustness, log clipping/pruning
│   ├── test_frontend.py          # Rendered pages: no user data in JS, offline page, tabs, locale labels
│   └── test_i18n.py              # i18n: locale switching, translations, tx_type filter
├── uploads/                      # Receipts — bind-mounted; YYYY/MM/DD/Buyer_file.ext
├── backups/                      # Backup archives — bind-mounted; bot_backup_*.tar.gz
├── icons/                        # PWA icons — bind-mounted; persists across rebuilds
├── mariadb-data/                 # MariaDB data — bind-mounted
├── docker/
│   ├── requirements.txt          # Runtime Python dependencies
│   ├── requirements-dev.txt      # + pytest (CI / local tests; not installed in the image)
│   └── entrypoint.sh             # Docker entrypoint: fixes bind-mount ownership, drops to appuser via gosu
├── Dockerfile
├── docker-compose.yml
├── .env                          # Not committed (gitignored)
├── .env.example                  # Committed template
├── .gitignore
└── .dockerignore
```

### Module Dependency Graph (no cycles)

```
extensions.py  → flask_babel, flask_sqlalchemy, flask_wtf, flask_migrate, flask_limiter, apscheduler
config.py      → flask_babel (lazy_gettext only)
models.py      → extensions
helpers.py     → extensions, models, config
email_service  → extensions, models, helpers
backup_service → extensions, models, helpers, config
scheduler_jobs → extensions, models, helpers, email_service, backup_service
routes/*       → extensions, models, helpers, config, services, scheduler_jobs
app.py         → everything (assembly point)
```

---

## Database Models (`app/models.py`)

| Model | Key fields | Notes |
|-------|-----------|-------|
| `User` | `id`, `name`, `email`, `balance` (Numeric(12,2)), `is_active`, `email_opt_in` (Bool, default `True`), `email_transactions` (String, default `'last3'`) | Deactivated users are hidden from dashboard/search filter; `email_opt_in` controls whether the weekly email is sent; `email_transactions` values: `'none'` \| `'last3'` \| `'this_week'` \| `'this_month'` |
| `Transaction` | `id`, `date` (naive UTC), `description`, `amount` (Numeric(12,2)), `from_user_id`, `to_user_id`, `transaction_type`, `receipt_path`, `notes` (Text, nullable) | Types: `expense`, `deposit`, `withdrawal`. An expense creates one transaction per debtor, all sharing the receipt |
| `ExpenseItem` | `id`, `transaction_id`, `item_name`, `price` (Numeric(12,2)), `buyer_id` | Child rows of an expense transaction |
| `Setting` | `key` (PK), `value` | Key/value store for all configuration |
| `CommonItem` | `id`, `name` | Autocomplete item names |
| `CommonDescription` | `id`, `value` | Autocomplete descriptions |
| `CommonPrice` | `id`, `value` (Numeric(12,2)) | Autocomplete prices |
| `CommonBlacklist` | `id`, `type`, `value` | Prevents auto-collection of specific values |
| `AutoCollectLog` | `id`, `ran_at`, `level`, `category`, `message` | Capped at 500 rows (`prune_log`) |
| `EmailLog` | `id`, `sent_at`, `level`, `recipient`, `message` | Capped at 500 rows; failures always logged, successes only with `email_debug` |
| `BackupLog` | `id`, `ran_at`, `level`, `message` | Capped at 500 rows |

Log models clip `message`/`recipient` to the column length (`@validates`), because MariaDB strict mode rejects over-long strings.

Schema is managed by **Flask-Migrate (Alembic)**. On startup, `app.py` checks the database state:
- **Existing DB without Alembic** — stamps at head
- **New empty DB** — runs `upgrade()` to create all tables
- **DB with Alembic version** — runs `upgrade()` to apply pending migrations

To add a new column or change the schema:
1. Edit `models.py`
2. Run `flask db migrate -m "description"` to auto-generate a migration script
3. Review the generated script in `app/migrations/versions/`
4. The migration will run automatically on next app start

The `env.py` uses `render_as_batch=True` for SQLite compatibility. It only applies `alembic.ini`'s logging config when nothing configured logging yet — otherwise `fileConfig()` would disable every app logger after the startup `upgrade()`.

---

## Settings System

All runtime config is stored in the `Setting` table as key/value strings:

```python
get_setting(key, default=None)           # Returns value or default; uses db.session.get()
set_setting(key, value, commit=True)     # Upserts; pass commit=False when batching multiple settings
```

The `settings()` view builds a `cfg` dict from all keys and passes it to `settings.html`. Tab state is preserved in `sessionStorage` client-side. A `?tab=<name>` URL parameter overrides `sessionStorage` on load.

### Known Setting Keys

| Key | Default | Notes |
|-----|---------|-------|
| `default_item_rows` | `3` | Pre-filled rows in Add Transaction |
| `recent_transactions_count` | `5` | Dashboard recent transactions (0 = hide) |
| `timezone` | `UTC` | pytz name; applied to all display dates, email subjects, backup filenames |
| `site_admin_id` | — | User ID (string) of the admin |
| `smtp_server/port/username/password` | — | SMTP credentials; port validated 1–65535 |
| `smtp_security` | `starttls` | `'starttls'` \| `'ssl'` (implicit TLS, `SMTP_SSL`) \| `'none'`; certificates are always verified |
| `from_email`, `from_name` | — | Sender identity |
| `email_enabled` | `1` | Master email on/off switch |
| `email_debug` | `0` | Logs every send to `EmailLog` |
| `admin_summary_email` | `0` | Send admin summary after each email run |
| `admin_summary_include_emails` | `0` | Include email addresses in admin summary |
| `schedule_enabled` | `0` | Email auto-schedule on/off |
| `schedule_day/hour/minute` | `mon, 9, 0` | APScheduler cron values; day must be in `config.CRON_DAYS` |
| `common_enabled` | `1` | Global autocomplete toggle |
| `common_auto_enabled` | `0` | Auto-collect scheduled job |
| `common_auto_debug` | `0` | Log auto-collect decisions |
| `common_auto_day/hour/minute` | `*, 2, 0` | Auto-collect cron |
| `common_items/descriptions/prices_auto` | `0` | Per-type auto-collect switches |
| `common_items/descriptions/prices_threshold` | `5` | Minimum occurrences to promote |
| (`CommonBlacklist` price values) | | Stored normalized (`'3.50'`); auto-collect also normalizes older entries |
| `backup_enabled` | `0` | Backup auto-schedule on/off |
| `backup_debug` | `0` | Log backup steps to `BackupLog` |
| `backup_admin_email` | `0` | Email admin after scheduled backup |
| `backup_day/hour/minute` | `*, 3, 0` | Backup cron |
| `backup_keep` | `7` | How many backups to keep (auto-prune) |
| `decimal_separator` | `.` | `'.'` or `','` |
| `currency_symbol` | `€` | Must be one of `config.CURRENCIES` (inserted into HTML/emails) |
| `show_email_on_dashboard` | `0` | Show Email column in dashboard |
| `language` | `de` | `'de'` or `'en'` |
| `icon_version` | `0` | Unix timestamp for cache-busting |
| `color_navbar` | `#7f8dbb` | Theme: navbar background |
| `color_email_grad_start/end` | `#7f8dbb / #ffffff` | Theme: email header gradient |
| `color_balance_positive/negative` | `#5a9a7a / #c9534a` | Theme: balance colors |
| `tpl_email_subject_{lang}` | see `TEMPLATE_DEFAULTS` / `TEMPLATE_DEFAULTS_DE` | Stored per-language (e.g. `_de`, `_en`); accessed via `get_tpl('tpl_email_subject')` which auto-appends current language. Only customizations are stored: saving a value equal to the default (or resetting) deletes the row |
| `tpl_email_greeting_{lang}` | | |
| `tpl_email_intro_{lang}` | | |
| `tpl_email_footer1_{lang}` / `tpl_email_footer2_{lang}` | | |
| `tpl_admin_subject_{lang}` | | |
| `tpl_admin_intro_{lang}` | | Empty = omit |
| `tpl_admin_footer_{lang}` | | |
| `tpl_backup_subject_{lang}` | | |
| `tpl_backup_footer_{lang}` | | |

---

## Key Helpers (`app/helpers.py`)

```python
parse_amount(s, positive=False)  # -> Decimal rounded to cents; raises AmountError (an InputError/ValueError) for garbage/NaN/exponents
adjust_balance(user_id, delta)   # Atomic SQL `balance = balance + delta`; no commit
apply_balance_effect(tx, reverse=False)  # from_user -= amount, to_user += amount (or the reverse)
local_to_utc(naive_local) / local_day_start_utc(date)
local_days_utc(first, last) / local_month_utc(y, m)  # Half-open UTC [start, end) for local calendar ranges
parse_local_datetime(s)  # datetime-local string (app tz) -> naive UTC, or None
prune_log(Model, keep=500)       # Keep the newest rows of a log table; no commit
delete_setting(key, commit=True)
redirect_back(default)   # Redirect to the referrer only if it is on this host
now_local()              # datetime.now() in configured timezone. Works in both request and APScheduler contexts.
get_tpl(key)             # For tpl_* keys: reads language-suffixed DB key (e.g. tpl_email_subject_de), falls back to TEMPLATE_DEFAULTS_DE/TEMPLATE_DEFAULTS. Color keys are language-independent.
apply_template(text, **kwargs)  # Replaces [Key] placeholders: apply_template("Hi [Name]", Name="Alice") -> "Hi Alice"
fmt_amount(value)        # Formats Decimal to 2 places using configured decimal_separator.
hex_to_rgb(hex_color)    # "#0d6efd" -> "13, 110, 253"
detect_theme()           # Compares current colors against THEMES dict; returns theme key or 'custom'.
save_receipt(file, buyer_name)         # Saves upload to /uploads/YYYY/MM/DD/BuyerName_stem_<6 hex>.ext
delete_receipt_file(receipt_path, exclude_transaction_id)  # Deletes receipt if no other transaction references it
parse_submitted_date(date_str)  # Like parse_local_datetime(), falls back to now (UTC)
get_app_tz()             # Configured pytz timezone, cached on Flask g. Use now_local() in scheduler jobs.
to_local(dt)             # Converts naive UTC datetime to configured local timezone.
make_icon_png(size, bg_color, fg_color)  # Generates PNG with bank silhouette. Stdlib only.
generate_and_save_icons(bg_hex)          # Generates 32, 192, 512 PNGs, saves to static/icons/
```

### Template filters (defined in `app.py`)

```python
@app.template_filter('money')        # {{ value|money }} -> fmt_amount(Decimal(str(value)))
@app.template_filter('localdt')      # {{ dt|localdt }} -> to_local(dt).strftime(...)
@app.template_filter('tx_type')      # Translates DB transaction types at display time
@app.template_filter('format_date_babel')  # Localized date formatting via Babel
@app.context_processor inject_theme()  # Injects theme_navbar, theme_navbar_rgb, etc.
```

---

## Balance Logic

Balances are maintained directly on `User.balance`. Every transaction mutates balances immediately, always through `adjust_balance()` / `apply_balance_effect()` (a single SQL `UPDATE … SET balance = balance + :delta`, so concurrent gunicorn threads can't lose updates):

- **from_user** pays the amount (expense debtor, withdrawal), **to_user** receives it (expense buyer, deposit)
- **Delete**: effects are fully reversed
- **Edit**: input is validated first; then old effects are reversed and new effects applied
- Each route commits exactly once (rollback on `InputError`); edit/delete POSTs lock the transaction row (`with_for_update`) so a double submit can't reverse it twice

There is no derived-balance recalculation — the stored balance is the source of truth.

**Admin hidden from dashboard** — The site admin (`site_admin_id`) is excluded from the dashboard balance table. The admin acts as the "bank" — her balance is always the negative sum of all other users, so displaying it is redundant. She still appears in all transaction dropdowns, search, analytics, and other views because she actively participates in transactions.

---

## APScheduler

A single `BackgroundScheduler` instance lives in `extensions.py`. Three job slots:

| Job ID | Trigger | What it does |
|--------|---------|-------------|
| `email_job` | cron (day/hour/minute) | `send_all_emails()` |
| `common_job` | cron | scans transactions, promotes common values |
| `backup_job` | cron | `run_backup()`, prunes old backups, emails admin if configured |

Jobs are restored from the DB on startup via `_restore_schedule(app)`, which logs and skips a job with broken settings instead of failing the boot. `reschedule_all(app)` re-creates all jobs (timezone change, after a restore). Job defaults: `misfire_grace_time=3600`, `coalesce=True`. Each job uses `with app.app_context():` since background threads have no Flask request context. Scheduler is shut down on process exit via `atexit`.

---

## Email System

Three email types, each with editable subject + body via the Templates tab:

| Function | Recipient | Triggered by |
|----------|-----------|-------------|
| `build_email_html(user)` | Individual opted-in active users | Manual "Send Now" or auto-schedule |
| `build_admin_summary_email(users, include_emails=False)` | Site admin | After each email run, if `admin_summary_email=1` |
| `build_backup_status_email(ok, result, kept, pruned)` | Site admin | After each **scheduled** backup only |

**Sending** goes through `Mailer` (one SMTP connection per run, reconnects once on disconnect, fails the rest of the run fast on a connection/TLS/login error). TLS mode from `smtp_security`, always with `ssl.create_default_context()`. Headers via `formataddr`/`formatdate`/`make_msgid`. Placeholder values and the currency symbol are HTML-escaped; template text itself is admin-authored HTML.

**Per-user email preferences** (stored on `User`):
- `email_opt_in` — if `False`, user is skipped during `send_all_emails()`
- `email_transactions` — controls "Recent Transactions" section: `'none'`, `'last3'`, `'this_week'`, `'this_month'`

**Placeholders by email type:**

| Placeholder | Weekly | Admin summary | Backup |
|-------------|--------|---------------|--------|
| `[Name]` | yes | — | — |
| `[Balance]` | yes | — | — |
| `[BalanceStatus]` | yes | — | — |
| `[Date]` | yes | yes | yes |
| `[UserCount]` | — | yes | — |
| `[BackupStatus]` | — | — | yes (`Success` / `Failed`) |

---

## Backup / Restore

`run_backup()` creates `/backups/bot_backup_YYYY_MM_DD_HH-mm-ss.tar.gz` (mode `0600`, never overwrites — a `-N` suffix is added) containing:
- `dump.sql` — streamed `mariadb-dump --single-transaction` output
- `receipts/` — full copy of `/uploads`
- `.env` — `SECRET_KEY` and DB credentials from container env vars

The DB password is passed via `MYSQL_PWD`, never on the command line (`_db_command()`).

`run_restore(filename)` (called by the `backup_restore` route after `BACKUP_FILENAME_RE` validation):
1. Extracts only `dump.sql` and `receipts/` with `tarfile`'s `filter='data'`
2. Requires `dump.sql`; creates a safety backup of the current state
3. Restores the DB with `mariadb --sandbox` (refuses `\!` shell escapes in a crafted dump)
4. Only if that succeeded, replaces the `/uploads` contents
The route then runs `flask_migrate.upgrade()` and `reschedule_all()`.

Chunked upload: JS sends 5 MB chunks (max 400 = 2 GB, index/count validated); `assemble_upload()` checks the result is a tar archive; stale chunk dirs older than 24 h are swept. `MAX_CONTENT_LENGTH` is 10 MB (per chunk).

---

## Analytics / Charts (`app/routes/analytics.py`)

| Route | Purpose |
|-------|---------|
| `GET /analytics` | Renders page; passes user list and default date range (last 90 days) |
| `GET /analytics/data` | JSON API; accepts `date_from`, `date_to`, `users` (comma-separated IDs) |

Balance history is computed by starting from `User.balance` and reversing every transaction after the end of local day T. Sample granularity: weekly if range <= 90 days, monthly otherwise. `date_from`/`date_to` are local calendar days (converted with `local_days_utc`); volume buckets use local dates and Babel-formatted labels.

---

## PWA Support

Installable as a Progressive Web App. `/manifest.json` is a dynamic Flask route with live `theme_color`. The service worker only handles navigations and shows the cached `/offline` page on network failure (server responses pass through). Icons auto-generated on first startup if missing. Cache constant in `sw.js` is `'bot-v3'` — bump it when `offline.html` changes.

---

## Internationalization (i18n)

Fully bilingual (German + English) using Flask-Babel with standard gettext.

| Context | Pattern |
|---------|---------|
| Python code | `from flask_babel import gettext as _` then `_('...')` |
| Python with params | `_('User %(name)s added!', name=name)` |
| Jinja2 templates | `{{ _('...') }}` |
| JS strings in templates | `{{ _('...')\|tojson }}` — never `'{{ _('...') }}'` (gettext output is not escaped) |
| Module-level constants | `lazy_gettext('...')` (see `config.CURRENCIES`) |
| Transaction types | `\|tx_type` filter |
| Localized dates | `\|format_date_babel` filter |
| Scheduler jobs | `with force_locale(get_setting('language', 'de')): ...` |

### Translation workflow

```bash
# From the repo root, so the #: references keep their app/ prefix
pybabel extract -F app/babel.cfg -k _ -k gettext -k lazy_gettext -o app/translations/messages.pot app
pybabel update -i app/translations/messages.pot -d app/translations
# Edit app/translations/de/LC_MESSAGES/messages.po (check for new "fuzzy" guesses -- they are usually wrong)
pybabel compile -d app/translations
```

Both `.po` and `.mo` files are committed.

---

## Common Gotchas

- **Adding a new column** — edit `models.py`, run `flask db migrate -m "description"`. Migration runs automatically on next start.
- **Monetary values use `Decimal`** — all columns use `db.Numeric(12, 2)`. Always use `parse_amount()` to read form values (catch `InputError`) and `fmt_amount()` / `|money` to display them. Change balances only via `adjust_balance()` / `apply_balance_effect()`. When reading a balance for arithmetic, wrap it in `Decimal(str(...))`.
- **Stored dates are naive UTC, form dates are local** — convert input with `parse_local_datetime()`/`local_to_utc()`, filter by local days/months with `local_days_utc()`/`local_month_utc()`, display with `|localdt`.
- **No user data inside `<script>`** — pass values with `|tojson`, or render HTML in a `<template>` element and clone it (see `add_transaction.html`).
- **`datetime.now()` is UTC in Docker** — use `now_local()` for display/filenames. For UTC: `datetime.now(UTC).replace(tzinfo=None)`.
- **Balance is stored, not derived** — never recalculate from transactions; mutate `user.balance` carefully.
- **`/uploads` and `/app/static/icons` are bind-mounts** — cannot `rmtree` the directories; clear contents only.
- **Scheduler jobs receive `app` parameter** — use `with app.app_context():`. Never import `app` directly in service modules.
- **SQLAlchemy 2.0 style only** — use `db.session.get()`, `db.session.execute(db.select(...))`, `db.paginate()`. Never use `Model.query`.
- **Circular imports** — never import from `app.py`. Import `db`, `csrf`, `scheduler` from `extensions.py`.
- **Blueprint url_for** — must be prefixed: `url_for('main.index')`, `url_for('settings_bp.settings')`, `url_for('analytics_bp.analytics')`.
- **Single gunicorn worker** — APScheduler only works with 1 worker (it runs 4 threads, so request code must be thread-safe).
- **i18n strings** — wrap with `_()` (Python) or `{{ _('...') }}` (Jinja2). Run extract/update/compile after adding strings.
- **Transaction types are English in DB** — use `|tx_type` filter to translate at display time.
- **Scheduler jobs need `force_locale()`** — wrap `_()` calls in `with force_locale(...)`.
- **`FLASK_TESTING=1`** — skips DB init, scheduler start, and migration at import time.
- **DB credentials are required** — the app has no defaults for `DB_USER`/`DB_PASSWORD`; compose requires `SECRET_KEY`, `DB_PASSWORD` and `DB_ROOT_PASSWORD` (`:?`), `DB_USER` defaults to `tina`.
- **Port binding** — compose publishes `${BIND_ADDRESS:-127.0.0.1}:5000` (the app has no login). `BEHIND_PROXY=1` enables `ProxyFix` for one reverse proxy.
- **`import html` shadowing** — `email_service.py` imports the stdlib `html` module for `html.escape()`. Never use `html` as a local variable name in functions that call `html.escape()`, or Python will treat the module reference as an unbound local.

---

## Test Suite

```bash
pip install -r docker/requirements-dev.txt
FLASK_TESTING=1 python -m pytest tests/ -v
```

- Sets `FLASK_TESTING=1` and `SQLALCHEMY_DATABASE_URI=sqlite://` before importing `app`
- `WTF_CSRF_ENABLED=False`; the limiter is switched off with `limiter.enabled = False` (`RATELIMIT_ENABLED` is only read in `init_app`, which already ran at import)
- Session-scoped `app` fixture (uploads in a tmp dir); autouse `clean_db` empties all tables and removes scheduler jobs after each test
- `backup_dir` fixture points `BACKUP_DIR` and `UPLOAD_FOLDER` at tmp dirs; tests mock `subprocess.run` / `smtplib` — nothing talks to a real DB server or SMTP server
- `clean_db` sets `language='en'` so tests see English msgids
- Test requests share the test's app context (and `g`, session): Flask-Babel caches locale on `g._flask_babel.babel_locale` — clear when switching languages mid-test; set `timezone` before the first request (`get_app_tz` caches on `g`)

| File | Tests | Coverage |
|------|-------|----------|
| `test_helpers.py` | 30 | `parse_amount`, `fmt_amount`, `hex_to_rgb`, `apply_template` |
| `test_models.py` | 12 | User, Transaction, ExpenseItem, Setting, CommonItem |
| `test_routes.py` | 24 | Dashboard, transactions, search, edit |
| `test_settings.py` | 15 | Settings CRUD, common items, templates, schedule |
| `test_analytics.py` | 5 | Analytics page and data endpoint |
| `test_health.py` | 6 | Health, CSP/security headers, safe redirects |
| `test_email_service.py` | 4 | Email building |
| `test_email_sending.py` | 13 | SMTP modes, cert verification, headers, batching, escaping |
| `test_backup.py` | 11 | Backup/restore/upload, migration logging |
| `test_money_time.py` | 19 | Balance integrity, amounts, timezones, receipts, themes |
| `test_validation.py` | 18 | Input validation, schedules, logs |
| `test_frontend.py` | 8 | No user data in JS, offline page, tabs, localized labels |
| `test_i18n.py` | 7 | Locale switching, translations, tx_type filter |

---

## Structured Logging

Configured in `app.py` via `setup_logging()`. All output goes to stdout:

```
2025-01-15 09:30:00,123 INFO [app] Database tables created / verified
```

- `LOG_LEVEL` env var controls verbosity (default `INFO`)
- APScheduler and Werkzeug loggers quieted to `WARNING`
