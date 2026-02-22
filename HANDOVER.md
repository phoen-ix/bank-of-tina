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
| ORM | SQLAlchemy (no migrations — `db.create_all()` on startup) |
| Scheduler | APScheduler `BackgroundScheduler` |
| Timezone | pytz |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11, vanilla JS |
| Container | Docker + docker-compose, gunicorn (1 worker, 300 s timeout) |
| DB tools | `mariadb-client` installed in image for `mysqldump`/`mysql` CLI |

---

## File Structure

```
bank-of-tina/
├── app/
│   ├── app.py                    # Entire backend: models, routes, helpers, scheduler
│   ├── send_weekly_email.py      # Standalone script (env-var driven, legacy)
│   └── templates/
│       ├── base.html             # Shared layout; injects dynamic theme CSS
│       ├── index.html            # Dashboard (active users only)
│       ├── add_transaction.html
│       ├── edit_transaction.html # Edit transaction + receipt upload/remove
│       ├── transactions.html     # Month-by-month view
│       ├── search.html           # Cross-month search with advanced filters
│       ├── user_detail.html
│       └── settings.html         # All settings tabs (General/Email/Common/Backup/Templates/Users)
├── uploads/                      # Receipts — bind-mounted; YYYY/MM/DD/Buyer_file.ext
├── backups/                      # Backup archives — bind-mounted; bot_backup_*.tar.gz
├── mariadb-data/                 # MariaDB data — bind-mounted
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                          # Not committed (gitignored)
├── .env.example                  # Committed template
├── .gitignore
└── .dockerignore
```

---

## Database Models (`app/app.py`)

| Model | Key fields | Notes |
|-------|-----------|-------|
| `User` | `id`, `name`, `email`, `balance` (Float), `is_active`, `email_opt_in` (Bool, default `True`), `email_transactions` (String, default `'last3'`) | Deactivated users are hidden from dashboard/search filter; `email_opt_in` controls whether the weekly email is sent; `email_transactions` values: `'none'` \| `'last3'` \| `'this_week'` \| `'this_month'` |
| `Transaction` | `id`, `date`, `description`, `amount`, `from_user_id`, `to_user_id`, `transaction_type`, `receipt_path` | Types: `expense`, `deposit`, `withdrawal`, `transfer` |
| `ExpenseItem` | `id`, `transaction_id`, `item_name`, `price`, `buyer_id` | Child rows of an expense transaction |
| `Setting` | `key` (PK), `value` | Key/value store for all configuration |
| `CommonItem` | `id`, `name` | Autocomplete item names |
| `CommonDescription` | `id`, `value` | Autocomplete descriptions |
| `CommonPrice` | `id`, `value` | Autocomplete prices |
| `CommonBlacklist` | `id`, `type`, `value` | Prevents auto-collection of specific values |
| `AutoCollectLog` | `id`, `ran_at`, `level`, `category`, `message` | Capped at 500 rows |
| `EmailLog` | `id`, `sent_at`, `level`, `recipient`, `message` | Capped at 500 rows |
| `BackupLog` | `id`, `ran_at`, `level`, `message` | Capped at 500 rows |

Schema is created by `db.create_all()` at startup. A lightweight `_migrate_db()` function (called immediately after `db.create_all()`) issues `ALTER TABLE … ADD COLUMN` for any columns added since initial install, swallowing duplicate-column errors. New columns must be registered there for existing installs to pick them up automatically.

---

## Settings System

All runtime config is stored in the `Setting` table as key/value strings. Two helpers manage it:

```python
get_setting(key, default=None)   # Returns value or default
set_setting(key, value)          # Upserts
```

The `settings()` view builds a `cfg` dict from all keys and passes it to `settings.html`. Each settings sub-route (e.g. `settings_general`, `settings_email`) POSTs and redirects back. Tab state is preserved in `sessionStorage` client-side.

### Known Setting Keys

| Key | Default | Notes |
|-----|---------|-------|
| `default_item_rows` | `3` | Pre-filled rows in Add Transaction |
| `recent_transactions_count` | `10` | Dashboard recent transactions (0 = hide) |
| `timezone` | `UTC` | pytz name; applied to all display dates, email subjects, backup filenames |
| `site_admin_id` | — | User ID (string) of the admin; used for summary/backup emails |
| `smtp_server/port/username/password` | — | SMTP credentials |
| `from_email`, `from_name` | — | Sender identity |
| `email_enabled` | `0` | Master email on/off switch |
| `email_debug` | `0` | Logs every send to `EmailLog` |
| `admin_summary_email` | `0` | Send admin summary after each email run |
| `schedule_enabled` | `0` | Email auto-schedule on/off |
| `schedule_day/hour/minute` | `*, 9, 0` | APScheduler cron values |
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

## Key Helpers (`app/app.py`)

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
# parse_amount("1,99") → 1.99.  Used everywhere a monetary value is read from a form.

fmt_amount(value)
# Formats a float to 2 decimal places using the configured decimal_separator setting.
# fmt_amount(1.99) → "1,99" when separator is comma.

@app.template_filter('money')
# Jinja filter: {{ value|money }} — calls fmt_amount(float(value)).
# Used in all templates instead of "%.2f"|format(value).

hex_to_rgb(hex_color)
# "#0d6efd" → "13, 110, 253"  (for Bootstrap CSS custom property --bs-primary-rgb)

detect_theme()
# Compares current color settings against THEMES dict; returns theme key or 'custom'.

save_receipt(file, buyer_name)
# Saves an uploaded FileStorage to /uploads/YYYY/MM/DD/BuyerName_filename.ext
# Returns relative path for DB storage, or None if file invalid.

@app.context_processor inject_theme()
# Injects theme_navbar, theme_navbar_rgb, theme_balance_positive, theme_balance_negative,
# and decimal_sep into every template. base.html uses the theme values in an inline
# <style> block; decimal_sep is used by JS (const DECIMAL_SEP) for input/display formatting.
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

A single `BackgroundScheduler` instance is created at module level. Three job slots (each replaced when settings are saved):

| Job ID | Trigger | What it does |
|--------|---------|-------------|
| `weekly_email` | cron (day/hour/minute) | `send_all_emails()` |
| `auto_collect` | cron | scans transactions, promotes common values |
| `backup_job` | cron | `run_backup()`, prunes old backups, emails admin if configured |

Jobs are restored from the DB on startup via `_restore_schedule()`. The scheduler is shut down on process exit via `atexit`.

---

## Email System

Three email types, each with editable subject + body via the Templates tab:

| Function | Recipient | Triggered by |
|----------|-----------|-------------|
| `build_email_html(user)` | Individual opted-in active users | Manual "Send Now" or auto-schedule |
| `build_admin_summary_email(users)` | Site admin | After each email run, if `admin_summary_email=1` |
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

`THEMES` dict (5 presets) and `TEMPLATE_DEFAULTS` dict live near the top of `app.py`. Colors are stored in `Setting` and injected into every page via the `inject_theme` context processor. `base.html` applies them with an inline `<style>` block overriding Bootstrap CSS custom properties (`--bs-primary`, `--bs-primary-rgb`, button colors, nav tab active color, `.balance-positive`, `.balance-negative`).

---

## Receipts

- Stored under `/uploads` (bind-mount), path relative to that root stored in `Transaction.receipt_path`
- Served via `view_receipt(filepath)` using `send_from_directory`
- On edit transaction: upload replaces old file (old deleted from disk); "Remove receipt" checkbox deletes file from disk and clears `receipt_path`

---

## Search

Route: `GET /search` — parameters: `q`, `type`, `user`, `date_from`, `date_to`, `amount_min`, `amount_max`, `has_receipt`. User dropdown only shows active users. Advanced filters panel auto-opens if any filter param is present in the URL (JS checks on load).

---

## Common Gotchas

- **Adding a new column** — add it to the model *and* register an `ALTER TABLE` entry in `_migrate_db()` so existing installs pick it up automatically on the next container start.
- **Monetary input/display** — always use `parse_amount()` (not `float()`) to read form values and `fmt_amount()` / `|money` filter to display them, so the configured decimal separator is respected everywhere.
- **`datetime.now()` is UTC in Docker** — always use `now_local()` for display or filenames, never `datetime.now()` directly.
- **Balance is stored, not derived** — never recalculate from transactions; mutate `user.balance` carefully.
- **`/uploads` is a bind-mount** — cannot `rmtree` the directory itself; clear its contents only.
- **Scheduler jobs need `with app.app_context()`** — background jobs have no Flask request context.
- **Single gunicorn worker** — the in-process APScheduler only works correctly with 1 worker. Scaling requires moving to a proper task queue.
- **`db.create_all()` is idempotent** but won't add columns to existing tables — that's what `_migrate_db()` is for.

---

## Analytics / Charts (`app/app.py` + `app/templates/analytics.html`)

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
  "type_breakdown":     {"expense": {"count": 30, "amount": 150.0}, ...},
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

### Print / PDF

- `window.print()` → browser "Save as PDF"
- `@page { size: A4 landscape; margin: 10mm 12mm; }` sets the page geometry
- `@media print` hides nav, filter bar, tab strip, buttons, and description text; only the active tab pane is shown (inactive panes remain `display:none` via Bootstrap's `.active` class — we do **not** force-show all panes)
- Chart wrapper heights are overridden to `155mm` (`138mm` for the breakdown donuts) so Chart.js fills the landscape page
- `beforeprint` event calls `chart.resize()` so Chart.js redraws at the print dimensions before the browser captures the canvas; also appends the active tab label to the print-header meta line
- `afterprint` restores the meta line text

---

## Current State (as of last commit)

All features are fully implemented and committed. Recent work in order:

1. Backup/Restore (chunked upload, auto-prune, scheduled runs)
2. Site admin + admin summary email
3. Backup status email to admin (scheduled only)
4. Timezone fix (`now_local()`)
5. Auto-dismiss flash alerts (4 s)
6. Templates tab: color palette, preset themes, editable email subjects + body, live preview
7. Search: active-users-only filter, has-receipt toggle
8. Edit transaction: receipt upload / replace / remove
9. `.dockerignore` updated (excludes `backups/`, `mariadb-data/`, `*.tar.gz`)
10. **Per-user email preferences** — `email_opt_in` and `email_transactions` fields on `User`; `_migrate_db()` for existing installs; opt-in filtering in `send_all_emails()`; preference-driven transaction query in `build_email_html()`; controls in Add User form (settings.html) and Edit User modal (user_detail.html)
11. **Charts & Statistics page** — `/analytics` + `/analytics/data` JSON endpoint; 5-tab Chart.js dashboard (Balances, History, Volume, Top Items, Breakdown); shared filter bar (date range + user multi-select + quick presets); A4 landscape print/PDF with per-tab canvas resize via `beforeprint`
12. **Decimal separator setting** — `decimal_separator` key in `Setting` (`.` or `,`); configured in Settings → General; `parse_amount()` helper normalises all user input; `fmt_amount()` / `|money` Jinja filter applied to all monetary display; `DECIMAL_SEP` JS constant injected via `inject_theme` context processor and used in `add_transaction.html` and `edit_transaction.html` for live total display and item serialisation; all monetary inputs changed from `type="number"` to `type="text" inputmode="decimal"`; Charts page uses the same `DECIMAL_SEP` constant via a `fmtMoney()` JS helper applied to all tooltip labels and axis ticks

---

## Future Ideas (from README)

- CSV / Excel export of transactions
- User authentication / login system
- Multiple currency support
- OCR for automatic receipt parsing
- Saved/pinned searches
