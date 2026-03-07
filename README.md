# 🏦 Bank of Tina

A self-hosted web application for tracking shared expenses and balances within a small office or group. Features include expense recording with receipts, per-user weekly email reports, an admin summary email, charts and statistics, automated backups, and a fully configurable UI with themes and email templates. Built with Flask and MariaDB, runs entirely in Docker — no external services required.

---

## ✨ Features

### Users & Balances
- Add team members with name and email
- Real-time balance tracking for every user
- Deactivate users (hidden from dashboard, manageable from Settings)
- Dashboard shows Name and Balance; email column optional (Settings → General, default off)
- User detail page shows paginated transaction history (20 per page); click a user's name on the dashboard to open it
- **Per-user email preferences** — opt in/out of the weekly balance email individually; choose how much transaction history to include (`Last 3`, `This week`, `This month`, or `None`)

### Transactions
- **Expense** — record who paid and assign items to individuals
- **Deposit** — add money to a user's balance
- **Withdrawal** — deduct money from a user's balance
- **Edit** any saved transaction: description, notes, amount, date, from/to user, expense items, and receipt
- **Notes field** — optional free-text notes on any transaction for longer context or justification; shown inline on all transaction lists and included in search
- **Delete** any transaction (balances are automatically reversed)
- **Month-by-month view** — transactions grouped by day with ◀ ▶ navigation and a month/year jump picker; defaults to the current month
- **Search** — free-text search across descriptions and expense items; advanced filters for type, user, date range, amount range, and a "Has attachment / receipt" toggle; paginated results (25 per page); only active users appear in the user filter

### Expense Items
- Add line items per expense (name + price)
- Edit, add, or remove items on saved transactions
- Configurable number of pre-filled blank rows when opening the Add Transaction form

### Common Autocomplete
- **Item names** — save frequently used expense item names; get autocomplete suggestions when adding items
- **Descriptions** — save frequently used transaction descriptions; autocomplete appears on all description fields (expense, deposit, withdrawal)
- **Prices** — save frequently used prices; autocomplete appears on expense item price fields
- **Global toggle** — enable or disable all autocomplete with a single switch
- **Blacklist** — per-type blacklists prevent specific values from ever being auto-collected
- **Auto-collect** — optional scheduled job that scans the transaction history and promotes values that appear at or above a configurable threshold; separate on/off switches and thresholds for item names, descriptions, and prices
- **Debug log** — when debug mode is on, every auto-collect decision (added / skipped / summary) is written to the database and shown in the Settings UI; log is capped at 500 entries

### Receipts
- Upload JPG, PNG, or PDF receipts when recording a transaction
- Upload, replace, or remove a receipt on any existing transaction — the old file is deleted from disk automatically
- Files are saved in an organised directory tree:
  `uploads/YYYY/MM/DD/BuyerName_filename.ext`
- Filenames are sanitised (special characters removed) before saving

### Backup & Restore
- **Create backup** on demand or on a recurring schedule (same day/time picker as email and auto-collect)
- Each backup is a single `bot_backup_YYYY_MM_DD_HH-mm-ss.tar.gz` containing:
  - `dump.sql` — full MariaDB dump with `DROP TABLE IF EXISTS` (streamed to disk, no memory limit)
  - `receipts/` — complete copy of all uploaded receipt images
  - `.env` — credentials reconstructed from the container's environment variables
- **Download** any backup directly from the browser
- **Restore** from any listed backup with one click — receipts are restored first so the database is never touched if the file copy fails
- **Upload** a backup from another instance — large files are sent in 5 MB chunks with a progress bar, so there is no effective size limit
- **Auto-prune** — configure how many backups to keep; older ones are deleted automatically after each scheduled run
- **Backup status email** — when a site admin is configured, an optional email is sent after each *scheduled* backup with the result (success or failure), filename, backups kept, and number pruned; manual backups never trigger this email
- **Debug log** — when debug mode is on, every backup step is written to the database and shown in the Settings UI

### PWA — Install to Home Screen
- **Web App Manifest** — served dynamically at `/manifest.json`; `theme_color` tracks the configured navbar color
- **Service worker** — network-first strategy; always fetches fresh data; shows a self-contained offline page when the network is down or the server returns an HTTP error (e.g. 503); served from `/sw.js` via a Flask route so it can control the entire app scope
- **Icons** — 32×32, 192×192, and 512×512 PNG icons; persisted on the host via bind mount (`./icons/`) so they survive container rebuilds; auto-generated with the default theme color on first run; `/favicon.ico` route serves the 32px icon; manageable from Settings → Templates → App Icon:
  - **Regenerate from navbar color** — one-click regeneration using the current theme color as background (white bank silhouette)
  - **Upload custom icon** — upload any PNG or JPG; automatically resized to 32×32, 192×192, and 512×512
  - **Reset to default** — restores the original Bootstrap blue icon
  - Cache-busting ensures browsers and PWA pick up new icons immediately
- **Android Chrome**: three-dot menu → "Add to home screen" (or automatic install banner)
- **iOS Safari**: Share sheet → "Add to Home Screen" → correct icon, name, and standalone launch
- No App Store required; no native build tools required

### UI
- **Toast notifications** — success/error messages appear as Bootstrap 5 toasts in the top-right corner, auto-hide after 4 seconds, and stack when multiple messages fire simultaneously; includes a global `showToast(message, type)` JS helper for programmatic use
- **Skeleton loading** — the Charts page shows pulsing skeleton placeholders (horizontal bars for Balances/Top Items, full-width rectangles for History/Volume) while data loads, replacing the previous spinner

### Templates & Theming
- **Color palette** — navbar color, email header gradient (start + end), positive and negative balance colors; each has a color picker paired with a hex text field
- **Preset themes** — choose from Default, Ocean, Forest, Sunset, or Slate via a dropdown; selecting a preset fills all pickers instantly; manually changing any picker switches to "Custom"
- **Email subjects** — editable subject line for each of the three email types
- **Email body templates** — edit the greeting, intro, footer line 1, and footer line 2 of the weekly balance email; set the intro and footer of the admin summary email; set the footer of the backup status email; leave any field blank to omit that line
- **Include email addresses toggle** — admin summary email card has an "Include email addresses in summary table" switch (default off); when off, only names and balances are shown
- **Placeholders** — substituted at send time:

  | Placeholder | Available in |
  |-------------|--------------|
  | `[Name]` | Weekly email subject & body |
  | `[Balance]` | Weekly email body |
  | `[BalanceStatus]` | Weekly email body |
  | `[Date]` | All three email subjects & bodies |
  | `[UserCount]` | Admin summary subject & body |
  | `[BackupStatus]` | Backup status email subject |

- **Live preview** — each email template card has a **Preview** button that opens the rendered HTML in a new tab using real data (or sample data when no users exist)
- All theme and template settings are stored in the database and applied immediately with no restart

### Settings (web UI — no `.env` editing needed)
The Settings page is split into six tabs:

| Tab | What you configure |
|-----|--------------------|
| **General** | Default number of blank item rows in the Add Transaction form; number of recent transactions shown on the dashboard (0 hides the section); timezone (applied to all displayed dates, email subjects, and backup filenames); **decimal separator** (period `1.99` or comma `1,99`) applied to all monetary display and input throughout the app; **currency symbol** (€, $, £, ¥, and more) shown before all monetary amounts throughout the UI, charts, and emails; toggle to show/hide the email column on the dashboard; site admin (used for admin summary emails) |
| **Email** | SMTP credentials; enable/disable email sending; debug mode (logs runs to DB, surfaces SMTP errors in the UI); admin summary email toggle; send balance emails on demand; set a recurring auto-schedule |
| **Common** | Global autocomplete toggle; manually manage item names, descriptions, and prices (each with its own blacklist); configure the auto-collect scheduled job and view its debug log |
| **Backup** | Create/download/delete backups; restore from any backup or an uploaded file; configure an automatic backup schedule with auto-prune; backup status email to site admin (scheduled runs only); debug log |
| **Templates** | Color palette + preset themes; editable subjects and body text for all three email types (balance, admin summary, backup status); preview buttons for each email; **App Icon** card — regenerate icons from navbar color, upload a custom icon, or reset to default |
| **Users** | Add new users (including email opt-in and transaction scope preferences); active users and deactivated users are shown in separate lists (the deactivated list is hidden when empty); deactivate or reactivate any user |

### Email Notifications
- SMTP credentials are stored securely in the database (configured via Settings → Email)
- **Send Now** button to immediately email all active users their current balance
- **Auto-schedule** — pick a day and time (24 h clock); the schedule survives container restarts
- **Per-user opt-in** — users can be set to opt out of the weekly email; opted-out users are skipped on every send (manual and scheduled)
- **Per-user transaction scope** — each user's email includes their choice of: last 3 transactions, all transactions this week, all transactions this month, or no transaction history at all
- **Admin summary email** — when a site admin is configured (Settings → General), an optional extra email is sent to them after each run with a colour-coded balance overview of *all* active users (regardless of individual opt-in status)

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose (plugin `docker compose` or standalone `docker-compose`)

### 1. Clone the repository
```bash
git clone https://github.com/phoen-ix/bank-of-tina.git
cd bank-of-tina
```

### 2. Create your environment file
```bash
cp .env.example .env
```
Open `.env` and set a strong `SECRET_KEY` and your desired database credentials:
```bash
# Generate a secret key with:
python3 -c "import secrets; print(secrets.token_hex(32))"
```
The `DB_*` defaults (`tina`/`tina`) are fine for a private deployment — change them for anything internet-facing.

### 3. Start the application
```bash
docker compose up -d
```

### 4. Open the web interface
```
http://your-server-ip:5000
```

That's it. SMTP credentials and the email schedule are configured from the **Settings** page inside the app — no restart required.

---

## 📱 Usage Guide

### Adding Users
1. **Settings** → **Users** tab → fill in name and email
2. Set **Weekly email report** (toggle on/off) and **Include in email** (transaction scope)
3. **Add**

### Recording an Expense
1. **Add Transaction** → **Expense** tab
2. Select who paid
3. Enter a description (optional: upload a receipt)
4. Fill in item rows (pre-filled based on your General setting)
5. **Record Expense**

### Browsing Transactions by Month
1. **All Transactions** in the nav → defaults to the current month
2. Use ◀ / ▶ to move one month at a time (▶ is disabled on the current month)
3. Use the **Month** and **Year** dropdowns to jump directly to any past period

### Searching Transactions
1. Use the search bar in the navbar (any page) for a quick keyword search
2. Or navigate to `/search` directly for more control
3. Click **Advanced filters** to filter by type, user, date range, amount range, and/or the **Has attachment / receipt** toggle — filters can be combined
4. Results span all months and show the full date (`YYYY-MM-DD HH:MM`)

### Editing a Transaction
1. **All Transactions** (or a user's detail page) → pencil icon
2. Adjust any field — description, amount, date, from/to user
3. Add, edit, or remove expense items (the total auto-updates the Amount field)
4. Upload a new receipt, replace an existing one, or tick **Remove receipt** to delete it
5. **Save Changes** — balances are recalculated automatically

### Deleting a Transaction
- Trash icon on any transaction row — balances are reversed automatically

### Setting Up Email
1. **Settings** → **Email** tab
2. Fill in SMTP credentials and click **Save Settings**
3. Use **Send Emails Now** to test, or configure a recurring schedule under **Auto-Schedule**
4. Optionally enable **Send admin summary email** — requires a site admin to be set in the General tab first

### Customising Email Templates
1. **Settings** → **Templates** tab
2. Pick a colour preset or adjust individual colour pickers
3. Edit the subject and body text for each email type; use placeholders like `[Name]`, `[Balance]`, `[Date]`
4. Click **Preview** to open the rendered email in a new tab before saving
5. **Save Templates** — changes take effect on the next send

### Creating a Backup
1. **Settings** → **Backup** tab → **Create Backup Now**
2. The backup appears in the list instantly — click **Download** to save it locally
3. To schedule automatic backups, enable **Auto-Backup Schedule**, pick a day/time and how many backups to keep, then **Save Schedule**

### Restoring a Backup
- **From the list**: click **Restore** next to any existing backup and confirm
- **From a file**: use the **Upload Backup** section — select a `bot_backup_*.tar.gz` file and click **Upload**; the file is uploaded in chunks (no size limit) and appears in the list when done, ready to restore

### Managing Users
1. **Settings** → **Users** tab
2. Active users are shown in an **Active Users** list; deactivated users appear in a separate **Deactivated Users** list (hidden when no deactivated users exist)
3. Click **Deactivate** to move a user to the deactivated list, or **Reactivate** to restore them to the active list
4. Click a user's name to open their detail page, then **Edit User** to change their name, email, member-since date, or email preferences

---

## 🗂️ File Structure

```
bank-of-tina/
├── app/
│   ├── app.py                    # Thin entry point: creates Flask app, inits extensions, starts scheduler
│   ├── extensions.py             # Shared instances: db, csrf, migrate, limiter, scheduler
│   ├── config.py                 # Constants: THEMES, TEMPLATE_DEFAULTS, ALLOWED_EXTENSIONS, BACKUP_DIR
│   ├── models.py                 # All 11 SQLAlchemy models (fully type-annotated)
│   ├── helpers.py                # Utility functions: parse_amount, fmt_amount, save_receipt, etc.
│   ├── email_service.py          # Email building and sending (balance, admin summary, backup status)
│   ├── backup_service.py         # Backup creation, restore, pruning, status email
│   ├── scheduler_jobs.py         # APScheduler job setup and restore
│   ├── migrations/               # Alembic migrations (managed by Flask-Migrate)
│   │   ├── env.py
│   │   ├── alembic.ini
│   │   ├── script.py.mako
│   │   └── versions/             # Migration scripts
│   ├── routes/
│   │   ├── __init__.py           # register_blueprints(app)
│   │   ├── main.py               # main_bp: health, dashboard, users, transactions, search, receipts, PWA
│   │   ├── settings.py           # settings_bp: all settings, common items, backup, templates, icons
│   │   └── analytics.py          # analytics_bp: charts page + data endpoint
│   ├── templates/
│   │   ├── base.html             # Shared layout with dynamic theme CSS
│   │   ├── index.html            # Dashboard (active users only)
│   │   ├── add_transaction.html
│   │   ├── edit_transaction.html # Edit transactions, items, and receipts
│   │   ├── transactions.html     # Month-by-month transactions list
│   │   ├── search.html           # Cross-month search with advanced filters and pagination
│   │   ├── user_detail.html      # User profile with paginated transaction history
│   │   ├── _pagination.html      # Reusable Bootstrap 5 pagination partial
│   │   ├── analytics.html        # Charts & Statistics page
│   │   └── settings.html         # Settings (General / Email / Common / Backup / Templates / Users)
│   └── static/
│       ├── sw.js                 # Service worker (network-first, offline fallback)
│       ├── offline.html          # Self-contained offline fallback page
│       ├── vendor/               # Self-hosted frontend dependencies (no CDN)
│       │   ├── css/
│       │   │   ├── bootstrap.min.css       # Bootstrap 5.3.0
│       │   │   └── bootstrap-icons.css     # Bootstrap Icons 1.11.0
│       │   ├── js/
│       │   │   ├── bootstrap.bundle.min.js # Bootstrap 5.3.0 (with Popper)
│       │   │   └── chart.umd.min.js        # Chart.js 4.4.0
│       │   └── fonts/
│       │       ├── bootstrap-icons.woff2
│       │       └── bootstrap-icons.woff
│       └── icons/                # Bind-mounted from ./icons/ at runtime
│           ├── icon-32.png       # Favicon 32×32 (auto-generated on first run)
│           ├── icon-192.png      # PWA icon 192×192 (auto-generated on first run)
│           └── icon-512.png      # PWA icon 512×512 (auto-generated on first run)
├── tests/
│   ├── conftest.py               # pytest fixtures (SQLite in-memory, no CSRF, make_user factory)
│   ├── test_helpers.py           # Tests for parse_amount, fmt_amount, hex_to_rgb, apply_template
│   ├── test_models.py            # Tests for User, Transaction, ExpenseItem, Setting, CommonItem
│   ├── test_routes.py            # Tests for dashboard, transactions, search, edit, API
│   ├── test_settings.py          # Tests for settings CRUD, common items, templates, schedule
│   ├── test_analytics.py         # Tests for analytics page and data endpoint
│   ├── test_health.py            # Tests for /health endpoint
│   └── test_email_service.py     # Tests for email building and sending
├── uploads/                      # Receipts — organised as YYYY/MM/DD/ (bind-mounted)
├── backups/                      # Backup archives (bind-mounted)
├── icons/                        # PWA icons (bind-mounted; auto-generated on first run)
├── mariadb-data/                 # MariaDB data directory (bind-mounted)
├── create_icons.py               # One-time stdlib icon generator (run once, commit output)
├── entrypoint.sh                 # Docker entrypoint: fixes bind-mount ownership, drops to appuser
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🔒 Security Notes

- **Content Security Policy** — every HTML response includes a nonce-based CSP header (`script-src 'self' 'nonce-…'`; `style-src 'self' 'unsafe-inline'`; `frame-ancestors 'none'`; `object-src 'none'`). All inline event handlers have been converted to `addEventListener` / event delegation so no `'unsafe-inline'` is needed for scripts.
- **HTML injection prevention** — all user-controlled values (names, emails, descriptions, error messages) are escaped with `html.escape()` before insertion into HTML email templates
- **XSS-safe toast notifications** — the `showToast()` JS helper builds DOM nodes programmatically with `textContent`, never `innerHTML`
- **Safe tar extraction** — backup restore rejects symlinks, hardlinks, absolute paths, `..` traversal, and any member whose resolved path escapes the extraction directory
- **Safe search queries** — SQL wildcards (`%`, `_`) in user search input are escaped before building ILIKE patterns
- **SMTP timeout** — outbound email connections use a 30-second timeout to prevent indefinite hangs
- Set a strong, random `SECRET_KEY` in your `.env` file
- Never commit your `.env` file (it is in `.gitignore`)
- The Docker container starts as root only to fix bind-mount directory ownership, then immediately drops to a non-root user (`appuser`, UID 1000) via `gosu`
- Per-route rate limiting is enabled on write-heavy endpoints (user add, transaction add, send-now, backup create/restore)
- Use an **App Password** for Gmail rather than your main account password
- Restrict network access to port 5000 — place behind a reverse proxy (nginx, Caddy) with authentication if the app is internet-facing
- Back up the `mariadb-data/` directory regularly, or use the built-in **Backup** feature (Settings → Backup tab)

---

## 🔧 Maintenance

### Health check
```bash
curl http://localhost:5000/health
# Returns structured JSON with individual check results:
# {"status": "ok", "checks": {"database": "ok", "scheduler": "ok", "icons_writable": "ok"}}
# Returns 503 with "status": "error" when the database is unreachable
```

The Dockerfile includes a `HEALTHCHECK` instruction and the docker-compose web service uses `/health` for its healthcheck.

### View logs
```bash
docker compose logs -f web    # Structured log output (timestamp, level, module, message)
docker compose logs -f db
```

Set the `LOG_LEVEL` environment variable to control verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Default is `INFO`.

### Backup & restore
Use the built-in **Settings → Backup** tab for creating, downloading, uploading, and restoring backups.

For a manual database-only dump:
```bash
docker compose exec db mysqldump -u "$DB_USER" -p"$DB_PASSWORD" bank_of_tina > backup_$(date +%Y%m%d).sql
```

### Update after code changes
```bash
docker compose build && docker compose up -d
```

### Reset everything ⚠️ (deletes all data)
```bash
docker compose down
rm -rf mariadb-data/ uploads/*/ icons/
docker compose up -d
```

---

## 🐛 Troubleshooting

| Problem | Steps |
|---------|-------|
| Emails not sending | Check Settings → Email; verify SMTP credentials; check logs |
| Receipt upload fails | Check `chmod 755 uploads/`; verify file is JPG/PNG/PDF |
| Port 5000 in use | Change the host port in `docker-compose.yml` (`"8080:5000"`) |
| Web container won't start | `docker compose logs web` — the app retries DB connections up to 5 times with exponential backoff on startup; check db logs if all retries fail |
| DB connection refused | Ensure `mariadb-data/` is writable; `docker compose restart db` |

---

### Charts & Statistics
A dedicated **Charts** page (nav bar → Charts) with a shared filter bar and five tabs, each showing a different view of the data:

| Tab | Chart type | What it shows |
|-----|-----------|---------------|
| **Balances** | Horizontal bar | Current balance per user; green/red per sign; sorted highest → lowest |
| **History** | Multi-line | Each user's running balance over time, reconstructed from the transaction log; weekly or monthly sample points depending on the selected range |
| **Volume** | Bar + line combo | Transaction count (bars, left axis) and total amount (line, right axis) grouped by week or month |
| **Top Items** | Horizontal bar | Top 15 expense line items by total amount or count; toggle between the two modes |

**Filter bar** — date range pickers, quick presets (30 d / 90 d / 1 yr / All time), multi-select user dropdown, Apply button.

**Print / PDF** — prints only the currently active tab, formatted for A4 landscape; chart canvas is resized to fill the page before the browser captures it. Open browser print dialog → Save as PDF.

---

## 🧪 Running Tests

Tests use an in-memory SQLite database and require no running services:

```bash
FLASK_TESTING=1 python -m pytest tests/ -v
```

The test suite includes 78 tests across 7 test modules covering helpers, models, routes, settings, analytics, health check, and email service. All tests pass with zero warnings.

---

## 💡 Future Ideas

- [ ] CSV / Excel export of transactions
- [ ] User authentication and login system
- [ ] Exchange-rate-aware multi-currency support (currency symbol is already configurable)
- [ ] OCR for automatic receipt parsing
- [ ] Saved/pinned searches

---

Made with ❤️ to make office lunches easier! 🥗
