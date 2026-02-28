# Bank of Tina — Handover Document

This document gives a new Claude instance full context to continue development without reading the entire codebase from scratch.

---

## Project Overview

**Bank of Tina** is a self-hosted Flask/MariaDB web app for tracking shared expenses and balances within a small office or group. It runs entirely in Docker with no external dependencies. All configuration is done through the web UI — no `.env` editing needed after initial setup.

- **Repo:** `https://github.com/phoen-ix/bank-of-tina`
- **Branch:** `main`
- **Working directory:** `/home/mk/claude/bank-of-tina`
- **Runtime URL:** `http://<server>:5000`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.0, Flask-SQLAlchemy 3.1 |
| Database | MariaDB 11 (via PyMySQL) |
| ORM | SQLAlchemy with Flask-Migrate (Alembic) for schema migrations |
| Monetary types | `Decimal` / `db.Numeric(12, 2)` everywhere (no floats) |
| Rate limiting | Flask-Limiter 3.5 (in-memory, per-route limits, no global default) |
| Scheduler | APScheduler `BackgroundScheduler` |
| Timezone | pytz |
| Logging | Python `logging` to stdout, structured format |
| Type hints | `from __future__ import annotations` on all modules |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11, vanilla JS |
| Container | Docker + docker-compose, gunicorn (1 worker, 300 s timeout), non-root user |
| Testing | pytest with SQLite in-memory (`FLASK_TESTING=1`), 76 tests |
| DB tools | `mariadb-client` installed in image for `mysqldump`/`mysql` CLI |

---

## File Structure

The backend was split from a single 2300-line `app.py` into a modular Flask Blueprint architecture. The extensions pattern (`extensions.py` holds unbound instances; `app.py` binds them) prevents circular imports.

```
bank-of-tina/
├── app/
│   ├── app.py                    # Thin entry point: create app, init extensions, register blueprints, start scheduler
│   ├── extensions.py             # Shared instances: db, csrf, migrate, limiter, scheduler
│   ├── config.py                 # Constants: THEMES, TEMPLATE_DEFAULTS, ALLOWED_EXTENSIONS, BACKUP_DIR, DEFAULT_ICON_BG
│   ├── models.py                 # All 11 SQLAlchemy model classes (fully type-annotated)
│   ├── helpers.py                # Utility functions (parse_amount, fmt_amount, save_receipt, update_balance, etc.)
│   ├── email_service.py          # build_email_html, build_admin_summary_email, send_single_email, send_all_emails
│   ├── backup_service.py         # run_backup, _backup_log, _prune_old_backups, _list_backups, build_backup_status_email
│   ├── scheduler_jobs.py         # _add_email_job, _add_common_job, _add_backup_job, auto_collect_common, _restore_schedule
│   ├── migrations/               # Alembic migrations (Flask-Migrate)
│   │   ├── env.py
│   │   ├── alembic.ini
│   │   ├── script.py.mako
│   │   └── versions/             # Migration scripts (initial schema + future)
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
│   │   ├── search.html           # Cross-month search with advanced filters
│   │   ├── user_detail.html
│   │   ├── analytics.html        # Charts & Statistics page (4-tab Chart.js dashboard)
│   │   └── settings.html         # All settings tabs (General/Email/Common/Backup/Templates/Users)
│   └── static/
│       ├── sw.js                 # Service worker (network-first, offline fallback)
│       ├── offline.html          # Self-contained offline fallback page (no CDN deps)
│       └── icons/
│           ├── icon-192.png      # PWA icon 192×192
│           └── icon-512.png      # PWA icon 512×512
├── tests/
│   ├── conftest.py               # pytest fixtures: app, client, clean_db, make_user factory
│   ├── test_helpers.py           # parse_amount, fmt_amount, hex_to_rgb, apply_template (14 tests)
│   ├── test_models.py            # User, Transaction, ExpenseItem, Setting, CommonItem (12 tests)
│   ├── test_routes.py            # Dashboard, transactions, search, edit, API (26 tests)
│   ├── test_settings.py          # Settings CRUD, common items, templates, schedule (15 tests)
│   ├── test_analytics.py         # Analytics page and data endpoint (5 tests)
│   ├── test_health.py            # Health endpoint (2 tests)
│   └── test_email_service.py     # Email building and sending (4 tests)
├── uploads/                      # Receipts — bind-mounted; YYYY/MM/DD/Buyer_file.ext
├── backups/                      # Backup archives — bind-mounted; bot_backup_*.tar.gz
├── icons/                        # PWA icons — bind-mounted; persists across rebuilds
├── mariadb-data/                 # MariaDB data — bind-mounted
├── create_icons.py               # One-time stdlib icon generator (already run; output committed)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
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
- **Existing DB without Alembic** — stamps at head (no migration needed, just marks the current version)
- **New empty DB** — runs `upgrade()` to create all tables from the migration scripts
- **DB with Alembic version** — runs `upgrade()` to apply any pending migrations

To add a new column or change the schema:
1. Edit `models.py`
2. Run `flask db migrate -m "description"` to auto-generate a migration script
3. Review the generated script in `app/migrations/versions/`
4. The migration will run automatically on next app start

The `env.py` uses `render_as_batch=True` for SQLite compatibility (important for tests).

---

## Settings System

All runtime config is stored in the `Setting` table as key/value strings. Two helpers manage it:

```python
get_setting(key, default=None)   # Returns value or default
set_setting(key, value)          # Upserts
```

The `settings()` view (in `routes/settings.py`) builds a `cfg` dict from all keys and passes it to `settings.html`. Each settings sub-route (e.g. `settings_general`, `settings_email`) POSTs and redirects back. Tab state is preserved in `sessionStorage` client-side. A `?tab=<name>` URL parameter (e.g. `?tab=users`) overrides `sessionStorage` on load, allowing external links to open a specific tab directly.

### Known Setting Keys

| Key | Default | Notes |
|-----|---------|-------|
| `default_item_rows` | `3` | Pre-filled rows in Add Transaction |
| `recent_transactions_count` | `5` | Dashboard recent transactions (0 = hide) |
| `timezone` | `UTC` | pytz name; applied to all display dates, email subjects, backup filenames |
| `site_admin_id` | — | User ID (string) of the admin; used for summary/backup emails |
| `smtp_server/port/username/password` | — | SMTP credentials |
| `from_email`, `from_name` | — | Sender identity |
| `email_enabled` | `1` | Master email on/off switch |
| `email_debug` | `0` | Logs every send to `EmailLog` |
| `admin_summary_email` | `0` | Send admin summary after each email run |
| `admin_summary_include_emails` | `0` | Include email addresses in the admin summary table; `'1'` shows the Email column |
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
| `decimal_separator` | `.` | `'.'` or `','`; applied to all monetary display and input |
| `currency_symbol` | `€` | Symbol prepended to all monetary amounts in UI, charts, and emails; configurable via Settings → General dropdown (12 common currencies) |
| `show_email_on_dashboard` | `0` | `'1'` shows the Email column in the dashboard user table |
| `icon_version` | `0` | Unix timestamp; cache-busting param appended to icon URLs |
| `icon_mode` | `generated` | `'generated'` or `'custom'`; tracks whether the icon was regenerated or uploaded |
| `color_navbar` | `#0d6efd` | Theme: navbar background |
| `color_email_grad_start/end` | `#667eea / #764ba2` | Theme: email header gradient |
| `color_balance_positive/negative` | `#28a745 / #dc3545` | Theme: balance colors |
| `tpl_email_subject` | `Bank of Tina - Weekly Balance Update ([Date])` | |
| `tpl_email_greeting` | `Hi [Name],` | |
| `tpl_email_intro` | `Here's your weekly update…` | |
| `tpl_email_footer1/2` | see code | |
| `tpl_admin_subject` | `Bank of Tina - Admin Summary ([Date])` | |
| `tpl_admin_intro` | `` | Empty = omit |
| `tpl_admin_footer` | `This is an automated admin summary…` | |
| `tpl_backup_subject` | `Bank of Tina - Backup [BackupStatus] ([Date])` | |
| `tpl_backup_footer` | `This is an automated backup report…` | |

---

## Key Helpers (`app/helpers.py`)

```python
now_local()
# Returns datetime.now() in the configured timezone.
# Uses get_setting() directly — works in both request and APScheduler contexts.
# (get_app_tz() exists too but uses Flask g, so scheduler-only code uses now_local().)

get_tpl(key)
# Like get_setting() but falls back to TEMPLATE_DEFAULTS dict.

apply_template(text, **kwargs)
# Replaces [Key] placeholders: apply_template("Hi [Name]", Name="Alice") → "Hi Alice"

parse_amount(s)
# Parses a user-supplied decimal string, normalising both '.' and ',' as separators.
# Returns a Decimal: parse_amount("1,99") → Decimal('1.99').
# Used everywhere a monetary value is read from a form.

fmt_amount(value)
# Formats a Decimal to 2 decimal places using the configured decimal_separator setting.
# fmt_amount(Decimal('1.99')) → "1,99" when separator is comma.

@app.template_filter('money')
# Jinja filter: {{ value|money }} — calls fmt_amount(Decimal(str(value))).
# Used in all templates instead of "%.2f"|format(value).

hex_to_rgb(hex_color)
# "#0d6efd" → "13, 110, 253"  (for Bootstrap CSS custom property --bs-primary-rgb)

detect_theme()
# Compares current color settings against THEMES dict; returns theme key or 'custom'.

save_receipt(file, buyer_name)
# Saves an uploaded FileStorage to /uploads/YYYY/MM/DD/BuyerName_filename.ext
# Returns relative path for DB storage, or None if file invalid.

delete_receipt_file(receipt_path, exclude_transaction_id)
# Deletes a receipt file from disk only when no other transaction still references the same
# path (shared-receipt safety check). Silently ignores missing files.

parse_submitted_date(date_str)
# Parses a datetime-local string (from a form input in the app timezone) and returns a
# naive UTC datetime. Accepts '%Y-%m-%dT%H:%M' and '%Y-%m-%d'; falls back to utcnow().

get_app_tz()
# Returns the configured pytz timezone, cached on Flask g for the duration of the request.
# Use now_local() in scheduler/background jobs instead (g is not available there).

to_local(dt)
# Converts a naive UTC datetime to the configured local timezone (using get_app_tz()).

@app.template_filter('localdt')
# Jinja filter: {{ dt|localdt }} — calls to_local(dt).strftime('%Y-%m-%d %H:%M').
# Used in all templates to display stored UTC datetimes in the configured timezone.

### In `app.py` (template filters and context processor)

@app.template_filter('money')        # {{ value|money }} → fmt_amount(Decimal(str(value)))
@app.template_filter('localdt')      # {{ dt|localdt }} → to_local(dt).strftime(...)
@app.context_processor inject_theme() # Injects theme_navbar, theme_navbar_rgb, etc. into every template

### In `helpers.py`

make_icon_png(size, bg_color, fg_color=(0xff, 0xff, 0xff))
# Generates a square PNG with a bank silhouette. Ported from create_icons.py — stdlib only.

generate_and_save_icons(bg_hex)
# Parses a hex color, generates 192 and 512 PNGs, saves to static/icons/, updates
# icon_version and icon_mode settings.
```

---

## Balance Logic

Balances are maintained directly on `User.balance`. Every transaction mutates balances immediately:

- **Expense/Withdrawal**: `from_user.balance -= amount`
- **Deposit/Transfer**: `to_user.balance += amount`
- **Delete**: effects are fully reversed
- **Edit**: old effects reversed first, new effects applied after

There is no derived-balance recalculation — the stored balance is the source of truth. Be careful when modifying transaction logic.

---

## APScheduler

A single `BackgroundScheduler` instance lives in `extensions.py`. Three job slots (each replaced when settings are saved):

| Job ID | Trigger | What it does |
|--------|---------|-------------|
| `email_job` | cron (day/hour/minute) | `send_all_emails()` |
| `common_job` | cron | scans transactions, promotes common values |
| `backup_job` | cron | `run_backup()`, prunes old backups, emails admin if configured |

Jobs are restored from the DB on startup via `_restore_schedule(app)` in `scheduler_jobs.py`. Each job setup function receives `app` as a parameter and uses `with app.app_context():` since background threads have no Flask request context. The scheduler is shut down on process exit via `atexit`.

---

## Email System

Three email types, each with editable subject + body via the Templates tab:

| Function | Recipient | Triggered by |
|----------|-----------|-------------|
| `build_email_html(user)` | Individual opted-in active users | Manual "Send Now" or auto-schedule |
| `build_admin_summary_email(users, include_emails=False)` | Site admin | After each email run, if `admin_summary_email=1` |
| `build_backup_status_email(ok, result, kept, pruned)` | Site admin | After each **scheduled** backup only |

`send_single_email(to_email, to_name, subject, html)` handles the SMTP connection. All subjects and body fields go through `apply_template()` with the appropriate placeholder dict.

**Per-user email preferences** (stored on `User`):
- `email_opt_in` — if `False`, the user is skipped entirely during `send_all_emails()`. The admin summary always uses *all* active users regardless of opt-in.
- `email_transactions` — controls what `build_email_html()` includes in the "Recent Transactions" section:
  - `'none'` — section is omitted entirely from the HTML
  - `'last3'` — last 3 transactions (`.limit(3)`)
  - `'this_week'` — all transactions since Monday 00:00 in the configured timezone (converted to UTC for the DB query)
  - `'this_month'` — all transactions since the 1st of the current month 00:00 (same UTC conversion)

The constant `VALID_EMAIL_TX = {'none', 'last3', 'this_week', 'this_month'}` is defined at module level; both `add_user` and `edit_user` validate the submitted value against it and fall back to `'last3'` if invalid.

**Placeholders by email type:**

| Placeholder | Weekly | Admin summary | Backup |
|-------------|--------|---------------|--------|
| `[Name]` | ✓ | — | — |
| `[Balance]` | ✓ | — | — |
| `[BalanceStatus]` | ✓ | — | — |
| `[Date]` | ✓ | ✓ | ✓ |
| `[UserCount]` | — | ✓ | — |
| `[BackupStatus]` | — | — | ✓ (`Success` / `Failed`) |

---

## Backup / Restore

`run_backup()` creates `/backups/bot_backup_YYYY_MM_DD_HH-mm-ss.tar.gz` containing:
- `dump.sql` — streamed `mysqldump` output (no memory limit)
- `receipts/` — full copy of `/uploads`
- `.env` — reconstructed from container env vars

`backup_restore(filename)`:
1. Validates filename against `BACKUP_FILENAME_RE = r'^bot_backup_[\d_-]+\.tar\.gz$'`
2. Extracts to a temp dir (safe members only — no absolute paths, no `..`)
3. **Restores files first** (clears `/uploads` contents, copies receipts in)
4. **Then restores DB** — this ordering means a file failure doesn't touch the DB

`/uploads` is a bind-mount so its directory cannot be deleted with `rmtree` — only its contents are cleared.

Chunked upload: JS sends 5 MB chunks to `/backups/upload-chunk` with a shared `uploadId`. Server reassembles with `tempfile` then moves the completed file into `BACKUP_DIR`. `MAX_CONTENT_LENGTH` is 10 MB (per chunk).

---

## Theming

`THEMES` dict (5 presets) and `TEMPLATE_DEFAULTS` dict live in `config.py`. Colors are stored in `Setting` and injected into every page via the `inject_theme` context processor. `base.html` applies them with an inline `<style>` block overriding Bootstrap CSS custom properties (`--bs-primary`, `--bs-primary-rgb`, button colors, nav tab active color, `.balance-positive`, `.balance-negative`).

---

## Receipts

- Stored under `/uploads` (bind-mount), path relative to that root stored in `Transaction.receipt_path`
- Served via `view_receipt(filepath)` using `send_from_directory`
- On edit transaction: upload replaces old file (old deleted from disk); "Remove receipt" checkbox deletes file from disk and clears `receipt_path`

---

## Search

Route: `GET /search` (in `routes/main.py`) — parameters: `q`, `type`, `user`, `date_from`, `date_to`, `amount_min`, `amount_max`, `has_receipt`. User dropdown only shows active users. Advanced filters panel auto-opens if any filter param is present in the URL (JS checks on load).

---

## Common Gotchas

- **Adding a new column** — add it to the model in `models.py`, then run `flask db migrate -m "description"` to generate an Alembic migration script. The migration runs automatically on next app start.
- **Monetary values use `Decimal`** — all model columns use `db.Numeric(12, 2)`, all Python code uses `Decimal`. Always use `parse_amount()` (not `float()`) to read form values and `fmt_amount()` / `|money` filter to display them, so the configured decimal separator is respected and there is no float drift.
- **`datetime.now()` is UTC in Docker** — always use `now_local()` for display or filenames, never `datetime.now()` directly.
- **Balance is stored, not derived** — never recalculate from transactions; mutate `user.balance` carefully.
- **`/uploads` and `/app/static/icons` are bind-mounts** — cannot `rmtree` the directories themselves; clear their contents only. Icons are auto-generated on first startup if missing.
- **Scheduler jobs receive `app` parameter** — use `with app.app_context():` since background threads have no Flask request context. Never import `app` directly in service modules; use `current_app` in request handlers or pass `app` explicitly to scheduler jobs.
- **Circular imports** — never import from `app.py` in other modules. Import `db`, `csrf`, `scheduler` from `extensions.py`. Import models from `models.py`.
- **Blueprint url_for** — all `url_for()` calls in templates must be blueprint-prefixed: `url_for('main.index')`, `url_for('settings_bp.settings')`, `url_for('analytics_bp.analytics')`, etc.
- **Single gunicorn worker** — the in-process APScheduler only works correctly with 1 worker. Scaling requires moving to a proper task queue.
- **Alembic migrations** — `db.create_all()` is no longer used in production; Flask-Migrate handles schema creation and evolution. Always generate migration scripts for schema changes.
- **`FLASK_TESTING=1`** — set this env var to skip DB init, scheduler start, and migration at import time. The test suite sets it in `conftest.py` before importing `app`.
- **DB credentials are required** — `DB_USER` and `DB_PASSWORD` have no hardcoded defaults; the app raises `RuntimeError` at startup if they are missing (unless `SQLALCHEMY_DATABASE_URI` is set directly, as in tests).

---

## Analytics / Charts (`app/routes/analytics.py` + `app/templates/analytics.html`)

Two new routes, no new DB tables — all data is derived from existing `Transaction` and `ExpenseItem` rows.

### Routes

| Route | Purpose |
|-------|---------|
| `GET /analytics` | Renders `analytics.html`; passes user list and default date range (last 90 days) |
| `GET /analytics/data` | JSON API; accepts `date_from`, `date_to`, `users` (comma-separated IDs); returns all chart data in one response |

### `/analytics/data` response shape

```json
{
  "balances":           [{"name": "Alice", "balance": 12.50}, ...],
  "balance_history":    {"labels": ["2025-01-06", ...], "datasets": {"Alice": [0, 5.0, ...], ...}},
  "transaction_volume": {"labels": ["Jan 06", ...], "counts": [3, ...], "amounts": [45.0, ...]},
  "top_items":          {"names": ["Coffee", ...], "counts": [12, ...], "totals": [48.0, ...]},
  "meta":               {"date_from": "...", "date_to": "...", "transaction_count": 45, "user_count": 5}
}
```

### Balance history computation

`User.balance` is the *current* balance. Historical balance at date T is computed by starting from `user.balance` and reversing every transaction that occurred *after* T:
- `tx.to_user_id == user.id` and `tx.date > T` → subtract `tx.amount`
- `tx.from_user_id == user.id` and `tx.date > T` → add `tx.amount`

This requires fetching **all** of a user's transactions (not filtered by date range) for each user. One DB query per user — acceptable for the app's scale.

Sample-point granularity: weekly if date range ≤ 90 days, monthly otherwise.

### Chart.js notes

- Version 4.4.0 loaded from CDN (no npm/build step)
- All charts use `maintainAspectRatio: false` inside fixed-height wrapper `<div>`s
- Chart instances are stored in `_charts{}` map; `mkChart(id, cfg)` destroys the old instance before creating a new one
- Tab-switch resize: Bootstrap's `shown.bs.tab` event triggers `chart.resize()` on every canvas in the newly visible tab — fixes the zero-dimension bug that occurs when Chart.js initialises inside a hidden (`display:none`) tab pane
- **Decimal separator**: `DECIMAL_SEP` constant (from `inject_theme`) and a `fmtMoney(v)` helper (`toFixed(2).replace('.', DECIMAL_SEP)`) are used in all tooltip callbacks and axis tick formatters for monetary values
- **Currency symbol**: `CURRENCY_SYM` constant (from `inject_theme`) is used alongside `fmtMoney()` in all chart tooltip labels, axis tick formatters, and dataset/axis title strings; follows the same pattern as `DECIMAL_SEP`
- **Tabs**: Balances, History, Volume, Top Items (Breakdown tab was removed)

### Print / PDF

- `window.print()` → browser "Save as PDF"
- `@page { size: A4 landscape; margin: 10mm 12mm; }` sets the page geometry
- `@media print` hides nav, filter bar, tab strip, buttons, and description text; only the active tab pane is shown (inactive panes remain `display:none` via Bootstrap's `.active` class — we do **not** force-show all panes)
- Chart wrapper heights are overridden to `155mm` (`138mm` for the breakdown donuts) so Chart.js fills the landscape page
- `beforeprint` event calls `chart.resize()` so Chart.js redraws at the print dimensions before the browser captures the canvas; also appends the active tab label to the print-header meta line
- `afterprint` restores the meta line text

---

## PWA Support

The app is installable as a Progressive Web App on both Android and iOS with no App Store.

### Files
| File | Purpose |
|------|---------|
| `app/static/sw.js` | Service worker — network-first, caches only `offline.html` on install |
| `app/static/offline.html` | Self-contained offline fallback (no CDN, inline styles) |
| `app/static/icons/icon-192.png` | PWA icon 192×192 (bind-mounted from `./icons/`; auto-generated on first run) |
| `app/static/icons/icon-512.png` | PWA icon 512×512 (bind-mounted from `./icons/`; auto-generated on first run) |
| `create_icons.py` | One-time stdlib-only (no Pillow) icon generator; run once then commit output |

### `/manifest.json` route (`app/routes/main.py`)
Dynamic Flask route (`pwa_manifest()`). `theme_color` is fetched live via `get_tpl('color_navbar')` so it always reflects the user's configured navbar color. Icon URLs include a `?v=` cache-busting param from the `icon_version` setting. Uses `app.response_class(json.dumps(data), mimetype='application/manifest+json')` — same pattern as the analytics JSON endpoint.

### `base.html` additions
- **`<head>`** (after viewport meta): `<link rel="manifest">`, `<meta name="theme-color">`, Apple PWA meta tags, `<link rel="apple-touch-icon">`, favicon link. Icon `<link>` tags include `?v={{ icon_version }}` for cache-busting.
- **`<body>` footer** (before `{% block scripts %}`): SW registration script with `scope: '/'` (needed because `sw.js` lives under `/static/` but must cover all app paths). Uses `skipWaiting()` + `clients.claim()` for immediate activation.

### Icon management (Settings → Templates → App Icon card)
Icons can be managed from the web UI — no need to re-run `create_icons.py`:
- **Regenerate from navbar color** — re-generates the bank silhouette icons using the current `color_navbar` setting as the background color (stdlib-only, same algorithm as `create_icons.py`). The generation logic lives in `helpers.py` as `make_icon_png(size, bg_color, fg_color)` and `generate_and_save_icons(bg_hex)`.
- **Upload custom icon** — accepts a PNG/JPG upload, resizes to 192×192 and 512×512 using Pillow (`requirements.txt` includes `Pillow>=10.0`), saves to `static/icons/`.
- **Reset to default** — regenerates with the default Bootstrap blue `#0d6efd`.
- All three actions update the `icon_version` setting (unix timestamp) for cache-busting and set `icon_mode` to `generated` or `custom`.
- Route: `POST /settings/icon` in `routes/settings.py` with `action` field (`generate`, `upload`, `reset`).

### Cache versioning
The CACHE constant in `sw.js` is `'bot-v1'`. Bump to `'bot-v2'` etc. on future deploys to evict old caches (the activate handler deletes all cache keys that don't match the current name).

---

## Current State (as of last commit)

All features are fully implemented and committed. The codebase has been through two rounds of major refactoring:

### Round 3 improvements (most recent)
32. **Persistent PWA icons** — `./icons:/app/static/icons` bind mount added to `docker-compose.yml` so icons survive container rebuilds; `app.py` auto-generates default icons on first startup when the directory is empty; `icons/` added to `.gitignore` and `.dockerignore`
31. **Hardcoded credential removal** — `DB_USER` and `DB_PASSWORD` no longer fall back to `'tina'`; `app.py` raises `RuntimeError` at startup if they are missing (unless `SQLALCHEMY_DATABASE_URI` is set directly); `backup_service.py` and `routes/settings.py` default to empty string so `mysqldump`/`mysql` commands fail clearly; README backup example uses `$DB_USER`/`$DB_PASSWORD` variables instead of literal credentials

### Round 2 improvements
25. **Health check endpoint** — `GET /health` verifies database connectivity; Dockerfile `HEALTHCHECK` and docker-compose healthcheck point to `/health`
26. **Non-root Docker user** — container runs as `appuser` (UID/GID 1000) for reduced attack surface; bind-mounted volumes remain writable
27. **Flask-Migrate (Alembic)** — replaces the hand-rolled `_migrate_db()` ALTER TABLE approach; existing databases are auto-stamped on first run; new databases are created via migration scripts
28. **Rate limiting** — Flask-Limiter with in-memory storage; per-route limits on user add (10/min), transaction add (30/min POST), send-now (5/min), backup create (5/min), backup restore (3/min); 429 error handler with JSON and flash message support; disabled in tests via `RATELIMIT_ENABLED: False`
29. **Type hints** — `from __future__ import annotations` and full type annotations on all functions and module-level variables across every `.py` file; bug fix in `email_service.py` (bare `return False` → `return False, 'SMTP credentials not configured'`)
30. **Expanded test coverage** — 76 tests across 7 test modules (up from 16 in 3 modules); `make_user` factory fixture; new test files for settings, analytics, health, and email service

### Round 1 improvements
20. **Automated test suite** — pytest with SQLite in-memory; `FLASK_TESTING=1` init guard skips DB/scheduler setup
21. **Modular Blueprint architecture** — monolithic 2300-line `app.py` split into 11 modules with 3 blueprints
22. **Structured logging** — Python `logging` to stdout with structured format; `LOG_LEVEL` env var (default `INFO`)
23. **Decimal precision** — all monetary columns changed from `db.Float` to `db.Numeric(12, 2)`; all Python monetary code uses `Decimal`
24. **docker-compose cleanup** — removed deprecated `version: '3.8'` key

### Feature history
1. Backup/Restore (chunked upload, auto-prune, scheduled runs)
2. Site admin + admin summary email
3. Backup status email to admin (scheduled only)
4. Timezone fix (`now_local()`)
5. Auto-dismiss flash alerts (4 s)
6. Templates tab: color palette, preset themes, editable email subjects + body, live preview
7. Search: active-users-only filter, has-receipt toggle
8. Edit transaction: receipt upload / replace / remove
9. `.dockerignore` updated (excludes `backups/`, `mariadb-data/`, `*.tar.gz`)
10. **Per-user email preferences** — `email_opt_in` and `email_transactions` fields on `User`
11. **Charts & Statistics page** — `/analytics` + `/analytics/data` JSON endpoint; 4-tab Chart.js dashboard
12. **Decimal separator setting** — `decimal_separator` key in `Setting`; `parse_amount()` normalises input; `fmt_amount()` / `|money` for display
13. **Dashboard & user detail polish** — user name as link; email column hidden by default; user detail capped at 5 recent
14. **Transaction notes field** — optional `notes` (Text) column on `Transaction`
15. **Email template tweaks** — removed hardcoded balance status line; admin summary `include_emails` toggle
16. **Configurable currency symbol** — 12-option dropdown; applied to UI, charts, and emails
17. **PWA support** — Web App Manifest, service worker, installable on mobile
18. **PWA icon management** — regenerate/upload/reset icons from Settings
19. **Separated user lists** — active and deactivated users in separate lists

---

## Structured Logging

Configured in `app.py` via `setup_logging()`. All log output goes to stdout in the format:

```
2025-01-15 09:30:00,123 INFO [app] Database tables created / verified
2025-01-15 09:30:01,456 INFO [routes.main] Transaction created: deposit #42 amount=50.00
```

- `LOG_LEVEL` env var controls verbosity (default `INFO`)
- APScheduler and Werkzeug loggers are quieted to `WARNING`
- Key events logged: app lifecycle, transaction CRUD, user CRUD, email send/fail, backup create/restore, scheduler job registration
- DB log models (`EmailLog`, `AutoCollectLog`, `BackupLog`) are unchanged — they still power the in-app debug UI

---

## Test Suite

Located in `tests/`. Run with:

```bash
FLASK_TESTING=1 python -m pytest tests/ -v
```

### Setup (`conftest.py`)
- Sets `FLASK_TESTING=1` and `SQLALCHEMY_DATABASE_URI=sqlite://` *before* importing `app`
- `SECRET_KEY=test-key-not-for-production` (bypasses the strong-key check)
- `WTF_CSRF_ENABLED=False` (no CSRF tokens needed in tests)
- `RATELIMIT_ENABLED=False` (disables Flask-Limiter in tests)
- Session-scoped `app` fixture; autouse `clean_db` fixture rolls back after each test
- `make_user` factory fixture for quickly creating users with auto-incrementing names/emails

### Test files (76 tests total)
| File | Tests | Coverage |
|------|-------|----------|
| `test_helpers.py` | 14 | `parse_amount` (dot, comma, negative, empty, invalid), `fmt_amount` (default/comma separator), `hex_to_rgb`, `apply_template` |
| `test_models.py` | 12 | User CRUD, Transaction (all fields, types, relationships), ExpenseItem, Setting, CommonItem uniqueness, negative balance |
| `test_routes.py` | 26 | Dashboard, add user, deposit/withdrawal, expense with items, edit transaction, delete reversal, search (text/type/date/amount/receipt), user detail/edit/toggle, duplicate validation, PWA manifest, API |
| `test_settings.py` | 15 | Settings page, general/email update, common item/description/price/blacklist CRUD, template color/reset, schedule, send-now, common toggle, API endpoints, backup create |
| `test_analytics.py` | 5 | Analytics page loads, data endpoint (no transactions, with transactions, user filter, date range) |
| `test_health.py` | 2 | Health returns OK, correct JSON format |
| `test_email_service.py` | 4 | `build_email_html`, `build_admin_summary_email`, `send_single_email` without SMTP, `build_backup_status_email` |

---

## Future Ideas (from README)

- CSV / Excel export of transactions
- User authentication / login system
- Multiple currency support
- OCR for automatic receipt parsing
- Saved/pinned searches
