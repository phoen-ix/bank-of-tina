# Bank of Tina

Self-hosted Flask/MariaDB web app for tracking shared expenses and balances within a small office or group. Runs entirely in Docker with no external dependencies. All configuration is done through the web UI.

- **Repo:** `https://github.com/phoen-ix/bank-of-tina`
- **Branch:** `main`
- **Runtime URL:** `http://<server>:5000`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.0, Flask-SQLAlchemy 3.1, Flask-Babel 4.0 |
| Database | MariaDB 11 (via PyMySQL) |
| ORM | SQLAlchemy with Flask-Migrate (Alembic) for schema migrations |
| Monetary types | `Decimal` / `db.Numeric(12, 2)` everywhere (no floats) |
| Rate limiting | Flask-Limiter 3.5 (in-memory, per-route limits, no global default) |
| Scheduler | APScheduler `BackgroundScheduler` |
| Timezone | pytz |
| Logging | Python `logging` to stdout, structured format |
| Type hints | `from __future__ import annotations` on all modules |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11, Chart.js 4.4, vanilla JS (all self-hosted under `static/vendor/`, no CDN) |
| Container | Docker + docker-compose, gunicorn (1 worker, 300 s timeout), non-root user via gosu entrypoint |
| i18n | Flask-Babel, gettext `.po`/`.mo` files, ~427 translated strings (German + English) |
| Testing | pytest with SQLite in-memory (`FLASK_TESTING=1`), 85 tests |
| DB tools | `mariadb-client` installed in image for `mysqldump`/`mysql` CLI |

---

## File Structure

The backend was split from a single 2300-line `app.py` into a modular Flask Blueprint architecture. The extensions pattern (`extensions.py` holds unbound instances; `app.py` binds them) prevents circular imports.

```
bank-of-tina/
├── app/
│   ├── app.py                    # Thin entry point: create app, init extensions, register blueprints, start scheduler
│   ├── extensions.py             # Shared instances: db, csrf, migrate, limiter, scheduler, babel
│   ├── config.py                 # Constants: THEMES, TEMPLATE_DEFAULTS, TEMPLATE_DEFAULTS_DE, ALLOWED_EXTENSIONS, BACKUP_DIR, DEFAULT_ICON_BG
│   ├── models.py                 # All 11 SQLAlchemy model classes (fully type-annotated)
│   ├── helpers.py                # Utility functions (parse_amount, fmt_amount, save_receipt, update_balance, etc.)
│   ├── email_service.py          # build_email_html, build_admin_summary_email, send_single_email, send_all_emails
│   ├── backup_service.py         # run_backup, _backup_log, _prune_old_backups, _list_backups, build_backup_status_email
│   ├── scheduler_jobs.py         # _add_email_job, _add_common_job, _add_backup_job, auto_collect_common, _restore_schedule
│   ├── babel.cfg                 # Babel extraction config
│   ├── translations/             # Gettext i18n files (Flask-Babel)
│   │   ├── messages.pot          # Extracted translation template
│   │   ├── de/LC_MESSAGES/       # German translations (.po + .mo)
│   │   └── en/LC_MESSAGES/       # English translations (.po + .mo, msgstr empty — falls back to msgid)
│   ├── migrations/               # Alembic migrations (Flask-Migrate)
│   │   └── versions/             # Migration scripts
│   ├── routes/
│   │   ├── __init__.py           # register_blueprints(app) — registers all 3 blueprints
│   │   ├── main.py               # main_bp: health, dashboard, users, transactions, search, receipts, PWA
│   │   ├── settings.py           # settings_bp: all settings, common items, backup, templates, icons, user management
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
│   │   └── settings.html         # All settings tabs (General/Email/Common/Backup/Templates/Users)
│   └── static/
│       ├── sw.js                 # Service worker (network-first, offline fallback)
│       ├── offline.html          # Self-contained offline fallback page
│       ├── vendor/               # Self-hosted frontend dependencies (no CDN)
│       │   ├── css/              # bootstrap.min.css, bootstrap-icons.css
│       │   ├── js/               # bootstrap.bundle.min.js, chart.umd.min.js
│       │   └── fonts/            # bootstrap-icons.woff2, bootstrap-icons.woff
│       └── icons/
│           ├── icon-32.png       # Favicon 32x32
│           ├── icon-192.png      # PWA icon 192x192
│           └── icon-512.png      # PWA icon 512x512
├── tests/
│   ├── conftest.py               # pytest fixtures: app, client, clean_db, make_user factory
│   ├── test_helpers.py           # parse_amount, fmt_amount, hex_to_rgb, apply_template (14 tests)
│   ├── test_models.py            # User, Transaction, ExpenseItem, Setting, CommonItem (12 tests)
│   ├── test_routes.py            # Dashboard, transactions, search, edit, API (26 tests)
│   ├── test_settings.py          # Settings CRUD, common items, templates, schedule (15 tests)
│   ├── test_analytics.py         # Analytics page and data endpoint (5 tests)
│   ├── test_health.py            # Health endpoint (2 tests)
│   ├── test_email_service.py     # Email building and sending (4 tests)
│   └── test_i18n.py              # i18n: locale switching, translations, tx_type filter (7 tests)
├── uploads/                      # Receipts — bind-mounted; YYYY/MM/DD/Buyer_file.ext
├── backups/                      # Backup archives — bind-mounted; bot_backup_*.tar.gz
├── icons/                        # PWA icons — bind-mounted; persists across rebuilds
├── mariadb-data/                 # MariaDB data — bind-mounted
├── docker/
│   ├── requirements.txt          # Python dependencies
│   └── entrypoint.sh             # Docker entrypoint: fixes bind-mount ownership, drops to appuser via gosu
├── scripts/
│   └── create_icons.py           # One-time stdlib icon generator (already run; output committed)
├── Dockerfile
├── docker-compose.yml
├── .env                          # Not committed (gitignored)
├── .env.example                  # Committed template
├── .gitignore
└── .dockerignore
```

### Module Dependency Graph (no cycles)

```
extensions.py  → flask_sqlalchemy, flask_wtf, flask_migrate, flask_limiter, apscheduler
config.py      → (nothing)
models.py      → extensions
helpers.py     → extensions, models, config
email_service  → extensions, models, helpers
backup_service → extensions, models, helpers, config
scheduler_jobs → extensions, helpers, email_service, backup_service
routes/*       → extensions, models, helpers, config, services, scheduler_jobs
app.py         → everything (assembly point)
```

---

## Database Models (`app/models.py`)

| Model | Key fields | Notes |
|-------|-----------|-------|
| `User` | `id`, `name`, `email`, `balance` (Numeric(12,2)), `is_active`, `email_opt_in` (Bool, default `True`), `email_transactions` (String, default `'last3'`) | Deactivated users are hidden from dashboard/search filter; `email_opt_in` controls whether the weekly email is sent; `email_transactions` values: `'none'` \| `'last3'` \| `'this_week'` \| `'this_month'` |
| `Transaction` | `id`, `date`, `description`, `amount` (Numeric(12,2)), `from_user_id`, `to_user_id`, `transaction_type`, `receipt_path`, `notes` (Text, nullable) | Types: `expense`, `deposit`, `withdrawal`, `transfer` |
| `ExpenseItem` | `id`, `transaction_id`, `item_name`, `price` (Numeric(12,2)), `buyer_id` | Child rows of an expense transaction |
| `Setting` | `key` (PK), `value` | Key/value store for all configuration |
| `CommonItem` | `id`, `name` | Autocomplete item names |
| `CommonDescription` | `id`, `value` | Autocomplete descriptions |
| `CommonPrice` | `id`, `value` (Numeric(12,2)) | Autocomplete prices |
| `CommonBlacklist` | `id`, `type`, `value` | Prevents auto-collection of specific values |
| `AutoCollectLog` | `id`, `ran_at`, `level`, `category`, `message` | Capped at 500 rows |
| `EmailLog` | `id`, `sent_at`, `level`, `recipient`, `message` | Capped at 500 rows |
| `BackupLog` | `id`, `ran_at`, `level`, `message` | Capped at 500 rows |

Schema is managed by **Flask-Migrate (Alembic)**. On startup, `app.py` checks the database state:
- **Existing DB without Alembic** — stamps at head
- **New empty DB** — runs `upgrade()` to create all tables
- **DB with Alembic version** — runs `upgrade()` to apply pending migrations

To add a new column or change the schema:
1. Edit `models.py`
2. Run `flask db migrate -m "description"` to auto-generate a migration script
3. Review the generated script in `app/migrations/versions/`
4. The migration will run automatically on next app start

The `env.py` uses `render_as_batch=True` for SQLite compatibility (important for tests).

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
| `smtp_server/port/username/password` | — | SMTP credentials |
| `from_email`, `from_name` | — | Sender identity |
| `email_enabled` | `1` | Master email on/off switch |
| `email_debug` | `0` | Logs every send to `EmailLog` |
| `admin_summary_email` | `0` | Send admin summary after each email run |
| `admin_summary_include_emails` | `0` | Include email addresses in admin summary |
| `schedule_enabled` | `0` | Email auto-schedule on/off |
| `schedule_day/hour/minute` | `mon, 9, 0` | APScheduler cron values |
| `common_enabled` | `1` | Global autocomplete toggle |
| `common_auto_enabled` | `0` | Auto-collect scheduled job |
| `common_auto_debug` | `0` | Log auto-collect decisions |
| `common_auto_day/hour/minute` | `*, 2, 0` | Auto-collect cron |
| `common_items/descriptions/prices_auto` | `0` | Per-type auto-collect switches |
| `common_items/descriptions/prices_threshold` | `5` | Minimum occurrences to promote |
| `backup_enabled` | `0` | Backup auto-schedule on/off |
| `backup_debug` | `0` | Log backup steps to `BackupLog` |
| `backup_admin_email` | `0` | Email admin after scheduled backup |
| `backup_day/hour/minute` | `*, 3, 0` | Backup cron |
| `backup_keep` | `7` | How many backups to keep (auto-prune) |
| `decimal_separator` | `.` | `'.'` or `','` |
| `currency_symbol` | `EUR` | 12-option dropdown |
| `show_email_on_dashboard` | `0` | Show Email column in dashboard |
| `language` | `de` | `'de'` or `'en'` |
| `icon_version` | `0` | Unix timestamp for cache-busting |
| `icon_mode` | `generated` | `'generated'` or `'custom'` |
| `color_navbar` | `#7f8dbb` | Theme: navbar background |
| `color_email_grad_start/end` | `#7f8dbb / #ffffff` | Theme: email header gradient |
| `color_balance_positive/negative` | `#5a9a7a / #c9534a` | Theme: balance colors |
| `tpl_email_subject_{lang}` | see `TEMPLATE_DEFAULTS` / `TEMPLATE_DEFAULTS_DE` | Stored per-language (e.g. `_de`, `_en`); accessed via `get_tpl('tpl_email_subject')` which auto-appends current language |
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
now_local()              # datetime.now() in configured timezone. Works in both request and APScheduler contexts.
get_tpl(key)             # For tpl_* keys: reads language-suffixed DB key (e.g. tpl_email_subject_de), falls back to TEMPLATE_DEFAULTS_DE/TEMPLATE_DEFAULTS. Color keys are language-independent.
apply_template(text, **kwargs)  # Replaces [Key] placeholders: apply_template("Hi [Name]", Name="Alice") -> "Hi Alice"
parse_amount(s)          # Parses decimal string, normalises '.' and ',' separators. Returns Decimal.
fmt_amount(value)        # Formats Decimal to 2 places using configured decimal_separator.
hex_to_rgb(hex_color)    # "#0d6efd" -> "13, 110, 253"
detect_theme()           # Compares current colors against THEMES dict; returns theme key or 'custom'.
save_receipt(file, buyer_name)         # Saves upload to /uploads/YYYY/MM/DD/BuyerName_filename.ext
delete_receipt_file(receipt_path, exclude_transaction_id)  # Deletes receipt if no other transaction references it
parse_submitted_date(date_str)  # Parses datetime-local string (app tz) -> naive UTC datetime
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

Balances are maintained directly on `User.balance`. Every transaction mutates balances immediately:

- **Expense/Withdrawal**: `from_user.balance -= amount`
- **Deposit/Transfer**: `to_user.balance += amount`
- **Delete**: effects are fully reversed
- **Edit**: old effects reversed first, new effects applied after

There is no derived-balance recalculation — the stored balance is the source of truth.

---

## APScheduler

A single `BackgroundScheduler` instance lives in `extensions.py`. Three job slots:

| Job ID | Trigger | What it does |
|--------|---------|-------------|
| `email_job` | cron (day/hour/minute) | `send_all_emails()` |
| `common_job` | cron | scans transactions, promotes common values |
| `backup_job` | cron | `run_backup()`, prunes old backups, emails admin if configured |

Jobs are restored from the DB on startup via `_restore_schedule(app)`. Each job uses `with app.app_context():` since background threads have no Flask request context. Scheduler is shut down on process exit via `atexit`.

---

## Email System

Three email types, each with editable subject + body via the Templates tab:

| Function | Recipient | Triggered by |
|----------|-----------|-------------|
| `build_email_html(user)` | Individual opted-in active users | Manual "Send Now" or auto-schedule |
| `build_admin_summary_email(users, include_emails=False)` | Site admin | After each email run, if `admin_summary_email=1` |
| `build_backup_status_email(ok, result, kept, pruned)` | Site admin | After each **scheduled** backup only |

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

`run_backup()` creates `/backups/bot_backup_YYYY_MM_DD_HH-mm-ss.tar.gz` containing:
- `dump.sql` — streamed `mysqldump` output
- `receipts/` — full copy of `/uploads`
- `.env` — reconstructed from container env vars

`backup_restore(filename)`:
1. Validates filename against `BACKUP_FILENAME_RE`
2. Extracts to temp dir (rejects symlinks, hardlinks, absolute paths, `..` traversal)
3. Restores files first (clears `/uploads` contents, copies receipts in)
4. Then restores DB — file failure doesn't touch DB

Chunked upload: JS sends 5 MB chunks. `MAX_CONTENT_LENGTH` is 10 MB (per chunk).

---

## Analytics / Charts (`app/routes/analytics.py`)

| Route | Purpose |
|-------|---------|
| `GET /analytics` | Renders page; passes user list and default date range (last 90 days) |
| `GET /analytics/data` | JSON API; accepts `date_from`, `date_to`, `users` (comma-separated IDs) |

Balance history is computed by starting from `User.balance` and reversing every transaction after date T. Sample granularity: weekly if range <= 90 days, monthly otherwise.

---

## PWA Support

Installable as a Progressive Web App. `/manifest.json` is a dynamic Flask route with live `theme_color`. Service worker uses network-first strategy with offline fallback. Icons auto-generated on first startup if missing. Cache constant in `sw.js` is `'bot-v2'`.

---

## Internationalization (i18n)

Fully bilingual (German + English) using Flask-Babel with standard gettext.

| Context | Pattern |
|---------|---------|
| Python code | `from flask_babel import gettext as _` then `_('...')` |
| Python with params | `_('User %(name)s added!', name=name)` |
| Jinja2 templates | `{{ _('...') }}` |
| JS strings in templates | `{{ _('...')\|tojson }}` |
| Transaction types | `\|tx_type` filter |
| Localized dates | `\|format_date_babel` filter |
| Scheduler jobs | `with force_locale(get_setting('language', 'de')): ...` |

### Translation workflow

```bash
cd app && pybabel extract -F babel.cfg -k _ -k gettext -k lazy_gettext -o translations/messages.pot .
pybabel update -i translations/messages.pot -d translations
# Edit app/translations/de/LC_MESSAGES/messages.po
pybabel compile -d translations
```

Both `.po` and `.mo` files are committed.

---

## Common Gotchas

- **Adding a new column** — edit `models.py`, run `flask db migrate -m "description"`. Migration runs automatically on next start.
- **Monetary values use `Decimal`** — all columns use `db.Numeric(12, 2)`. Always use `parse_amount()` to read form values and `fmt_amount()` / `|money` to display them.
- **`datetime.now()` is UTC in Docker** — use `now_local()` for display/filenames. For UTC: `datetime.now(UTC).replace(tzinfo=None)`.
- **Balance is stored, not derived** — never recalculate from transactions; mutate `user.balance` carefully.
- **`/uploads` and `/app/static/icons` are bind-mounts** — cannot `rmtree` the directories; clear contents only.
- **Scheduler jobs receive `app` parameter** — use `with app.app_context():`. Never import `app` directly in service modules.
- **SQLAlchemy 2.0 style only** — use `db.session.get()`, `db.session.execute(db.select(...))`, `db.paginate()`. Never use `Model.query`.
- **Circular imports** — never import from `app.py`. Import `db`, `csrf`, `scheduler` from `extensions.py`.
- **Blueprint url_for** — must be prefixed: `url_for('main.index')`, `url_for('settings_bp.settings')`, `url_for('analytics_bp.analytics')`.
- **Single gunicorn worker** — APScheduler only works with 1 worker.
- **i18n strings** — wrap with `_()` (Python) or `{{ _('...') }}` (Jinja2). Run extract/update/compile after adding strings.
- **Transaction types are English in DB** — use `|tx_type` filter to translate at display time.
- **Scheduler jobs need `force_locale()`** — wrap `_()` calls in `with force_locale(...)`.
- **`FLASK_TESTING=1`** — skips DB init, scheduler start, and migration at import time.
- **DB credentials are required** — `DB_USER` and `DB_PASSWORD` have no hardcoded defaults.

---

## Test Suite

```bash
FLASK_TESTING=1 python -m pytest tests/ -v
```

- Sets `FLASK_TESTING=1` and `SQLALCHEMY_DATABASE_URI=sqlite://` before importing `app`
- `WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`
- Session-scoped `app` fixture; autouse `clean_db` fixture rolls back after each test
- `clean_db` sets `language='en'` so tests see English msgids
- Flask-Babel caches locale on `g._flask_babel.babel_locale` — clear when switching languages mid-test

| File | Tests | Coverage |
|------|-------|----------|
| `test_helpers.py` | 14 | `parse_amount`, `fmt_amount`, `hex_to_rgb`, `apply_template` |
| `test_models.py` | 12 | User, Transaction, ExpenseItem, Setting, CommonItem |
| `test_routes.py` | 26 | Dashboard, transactions, search, edit, API |
| `test_settings.py` | 15 | Settings CRUD, common items, templates, schedule |
| `test_analytics.py` | 5 | Analytics page and data endpoint |
| `test_health.py` | 4 | Health, CSP headers |
| `test_email_service.py` | 4 | Email building and sending |
| `test_i18n.py` | 7 | Locale switching, translations, tx_type filter |

---

## Structured Logging

Configured in `app.py` via `setup_logging()`. All output goes to stdout:

```
2025-01-15 09:30:00,123 INFO [app] Database tables created / verified
```

- `LOG_LEVEL` env var controls verbosity (default `INFO`)
- APScheduler and Werkzeug loggers quieted to `WARNING`
