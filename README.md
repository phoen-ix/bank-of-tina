# 🏦 Bank of Tina

A lightweight, self-hosted web application for managing shared expenses and balances within an office or group. Built with Flask and MariaDB, runs entirely in Docker — no external services required.

---

## ✨ Features

### Users & Balances
- Add team members with name and email
- Real-time balance tracking for every user
- Deactivate users (hidden from dashboard, manageable from Settings)
- Full transaction history per user

### Transactions
- **Expense** — record who paid and assign items to individuals
- **Deposit** — add money to a user's balance
- **Withdrawal** — deduct money from a user's balance
- **Edit** any saved transaction: description, amount, date, from/to user, expense items, and receipt
- **Delete** any transaction (balances are automatically reversed)
- **Month-by-month view** — transactions grouped by day with ◀ ▶ navigation and a month/year jump picker; defaults to the current month
- **Search** — free-text search across descriptions and expense items; advanced filters for type, user, date range, amount range, and a "Has attachment / receipt" toggle; only active users appear in the user filter

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

### UI
- Flash notifications (success/error banners) auto-dismiss after 4 seconds; can still be closed manually at any time

### Templates & Theming
- **Color palette** — navbar color, email header gradient (start + end), positive and negative balance colors; each has a color picker paired with a hex text field
- **Preset themes** — choose from Default, Ocean, Forest, Sunset, or Slate via a dropdown; selecting a preset fills all pickers instantly; manually changing any picker switches to "Custom"
- **Email subjects** — editable subject line for each of the three email types
- **Email body templates** — edit the greeting, intro, footer line 1, and footer line 2 of the weekly balance email; set the intro and footer of the admin summary email; set the footer of the backup status email; leave any field blank to omit that line
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
| **General** | Default number of blank item rows in the Add Transaction form; number of recent transactions shown on the dashboard (0 hides the section); timezone (applied to all displayed dates, email subjects, and backup filenames); site admin (used for admin summary emails) |
| **Email** | SMTP credentials; enable/disable email sending; debug mode (logs runs to DB, surfaces SMTP errors in the UI); admin summary email toggle; send balance emails on demand; set a recurring auto-schedule |
| **Common** | Global autocomplete toggle; manually manage item names, descriptions, and prices (each with its own blacklist); configure the auto-collect scheduled job and view its debug log |
| **Backup** | Create/download/delete backups; restore from any backup or an uploaded file; configure an automatic backup schedule with auto-prune; backup status email to site admin (scheduled runs only); debug log |
| **Templates** | Color palette + preset themes; editable subjects and body text for all three email types (balance, admin summary, backup status); preview buttons for each email |
| **Users** | Add new users; view all users with their status and balance; deactivate or reactivate any user |

### Email Notifications
- SMTP credentials are stored securely in the database (configured via Settings → Email)
- **Send Now** button to immediately email all active users their current balance
- **Auto-schedule** — pick a day and time (24 h clock); the schedule survives container restarts
- **Admin summary email** — when a site admin is configured (Settings → General), an optional extra email is sent to them after each run with a colour-coded balance overview of all active users
- Standalone `send_weekly_email.py` script still works via environment variables if needed

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose (plugin `docker compose` or standalone `docker-compose`)

### 1. Clone the repository
```bash
git clone https://github.com/your-username/bank-of-tina.git
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
1. **Settings** → **Users** tab → fill in name and email → **Add**

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
2. All users are listed with their status (Active / Inactive) and current balance
3. Click **Deactivate** to hide a user from the dashboard, or **Reactivate** to restore them

---

## 🗂️ File Structure

```
bank-of-tina/
├── app/
│   ├── app.py                    # Flask application (routes, models, scheduler)
│   ├── send_weekly_email.py      # Standalone email script (uses env vars)
│   ├── templates/
│   │   ├── base.html             # Shared layout with dynamic theme CSS
│   │   ├── index.html            # Dashboard (active users only)
│   │   ├── add_transaction.html
│   │   ├── edit_transaction.html # Edit transactions, items, and receipts
│   │   ├── transactions.html     # Month-by-month transactions list
│   │   ├── search.html           # Cross-month search with advanced filters
│   │   ├── user_detail.html
│   │   └── settings.html         # Settings (General / Email / Common / Backup / Templates / Users)
│   └── static/
├── uploads/                      # Receipts — organised as YYYY/MM/DD/
├── backups/                      # Backup archives (bot_backup_*.tar.gz)
├── mariadb-data/                 # MariaDB data directory (created on first run)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🔒 Security Notes

- Set a strong, random `SECRET_KEY` in your `.env` file
- Never commit your `.env` file (it is in `.gitignore`)
- Use an **App Password** for Gmail rather than your main account password
- Restrict network access to port 5000 — place behind a reverse proxy (nginx, Caddy) with authentication if the app is internet-facing
- Back up the `mariadb-data/` directory regularly, or use the built-in **Backup** feature (Settings → Backup tab)

---

## 🔧 Maintenance

### View logs
```bash
docker compose logs -f web
docker compose logs -f db
```

### Backup & restore
Use the built-in **Settings → Backup** tab for creating, downloading, uploading, and restoring backups.

For a manual database-only dump:
```bash
docker compose exec db mysqldump -u tina -ptina bank_of_tina > backup_$(date +%Y%m%d).sql
```

### Update after code changes
```bash
docker compose build && docker compose up -d
```

### Reset everything ⚠️ (deletes all data)
```bash
docker compose down
rm -rf mariadb-data/ uploads/*/
docker compose up -d
```

---

## 🐛 Troubleshooting

| Problem | Steps |
|---------|-------|
| Emails not sending | Check Settings → Email; verify SMTP credentials; check logs |
| Receipt upload fails | Check `chmod 755 uploads/`; verify file is JPG/PNG/PDF |
| Port 5000 in use | Change the host port in `docker-compose.yml` (`"8080:5000"`) |
| Web container won't start | `docker compose logs db` — db may still be initialising; it will retry automatically |
| DB connection refused | Ensure `mariadb-data/` is writable; `docker compose restart db` |

---

## 💡 Future Ideas

- [ ] CSV / Excel export of transactions
- [ ] User authentication and login system
- [ ] Charts and analytics dashboard
- [ ] Support for multiple currencies
- [ ] OCR for automatic receipt parsing
- [ ] Saved/pinned searches

---

Made with ❤️ to make office lunches easier! 🥗
