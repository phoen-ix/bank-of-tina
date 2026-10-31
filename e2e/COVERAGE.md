# E2E coverage inventory

Generated 2026-10-31 from two extraction commands, run from the repo root:

```bash
# 1. Every route (52 rules + /static): 
(cd app && FLASK_TESTING=1 SECRET_KEY=x SQLALCHEMY_DATABASE_URI=sqlite:// flask routes)
# 2. Every form, confirm/alert dialog and tab/modal/collapse/dropdown toggle in the templates (90 lines):
grep -nE '<form|data-confirm=|confirm\(|alert\(|data-bs-toggle="(tab|modal|collapse|dropdown)"' app/templates/*.html
```

**Roles:** the app has no login, so there is one role, the *visitor*. Every row is that role.
Register, verify, login, logout, password reset and 2FA do not exist. The cross-cutting flows
that do exist are the language switch, the theme colours, the PWA/offline mode and the
per-client rate limit.

**Items: 138 · ✅ 136 · ❌ 2** (both (c), covered by pytest).
Tests: `npx playwright test --list` (101 tests in 15 files, including the setup step). File names below are relative to
`e2e/tests/`. "sweep" = `sweep.spec.ts › visitor (no login) › …`.

## 1. Routes (`flask routes`) × visitor

| # | Route | Methods | Test |
|---|---|---|---|
| 1 | `/` | GET | ✅ sweep › page: dashboard |
| 2 | `/transaction/add` | GET | ✅ sweep › page: add transaction |
| 3 | `/transaction/add` | POST (expense) | ✅ add-transaction.spec.ts › expense › split between two debtors, the buyer's own item is not recorded |
| 4 | `/transaction/add` | POST (deposit/withdrawal) | ✅ add-transaction.spec.ts › deposit and withdrawal › deposit then withdrawal move the balance |
| 5 | `/transactions` | GET | ✅ sweep › page: all transactions; transactions.spec.ts › month view: day groups, details, totals per type, user links |
| 6 | `/search` | GET | ✅ sweep › page: search, page: search results |
| 7 | `/user/<id>` | GET | ✅ sweep › page: user detail |
| 8 | `/user/add` | POST | ✅ users.spec.ts › add a user from Settings → Users |
| 9 | `/user/<id>/edit` | POST | ✅ users.spec.ts › edit dialog: change everything, validation, cancel |
| 10 | `/user/<id>/toggle-active` | POST | ✅ users.spec.ts › deactivate and reactivate on the detail page |
| 11 | `/transaction/<id>/edit` | GET | ✅ sweep › page: edit transaction |
| 12 | `/transaction/<id>/edit` | POST | ✅ transactions.spec.ts › edit › expense items: the amount follows the items, balances follow the amount |
| 13 | `/transaction/<id>/delete` | POST | ✅ transactions.spec.ts › delete: cancelled confirm keeps it, confirmed delete reverses balances |
| 14 | `/receipt/<path>` | GET | ✅ sweep › JSON and asset routes; add-transaction.spec.ts › expense › receipt: a PDF is stored and linked, other file types are refused |
| 15 | `/analytics` | GET | ✅ sweep › page: charts |
| 16 | `/analytics/data` | GET | ✅ analytics.spec.ts › filters: users and dates drive every chart |
| 17 | `/settings` | GET | ✅ sweep › page: settings, page: settings tab general/email/common-items/backup/templates/users |
| 18 | `/settings/general` | POST | ✅ global/general.spec.ts › language: the whole UI switches to German and back |
| 19 | `/settings/email` | POST | ✅ global/email.spec.ts › credentials form: saved, password kept when left blank, port suggestion |
| 20 | `/settings/send-now` | POST | ✅ global/email.spec.ts › Send Now: every opted-in user gets their balance, the admin a summary |
| 21 | `/settings/email/clear-log` | POST | ✅ global/email.spec.ts › Send Now: every opted-in user gets their balance, the admin a summary |
| 22 | `/settings/schedule` | POST | ✅ global/email.spec.ts › auto-schedule: enable, the summary line, disable |
| 23 | `/settings/common` | POST | ✅ global/autocollect.spec.ts › switching autocomplete off empties every suggestion list |
| 24 | `/settings/common-items/add` | POST | ✅ common.spec.ts › item names: add, no duplicates, autocomplete, remove |
| 25 | `/settings/common-items/<id>/delete` | POST | ✅ common.spec.ts › item names: add, no duplicates, autocomplete, remove |
| 26 | `/settings/common-descriptions/add` | POST | ✅ common.spec.ts › descriptions: add and remove |
| 27 | `/settings/common-descriptions/<id>/delete` | POST | ✅ common.spec.ts › descriptions: add and remove |
| 28 | `/settings/common-prices/add` | POST | ✅ common.spec.ts › prices: comma input, display, invalid input, remove |
| 29 | `/settings/common-prices/<id>/delete` | POST | ✅ common.spec.ts › prices: comma input, display, invalid input, remove |
| 30 | `/settings/common-blacklist/add` | POST | ✅ common.spec.ts › blacklists: item, description and price (normalised) |
| 31 | `/settings/common-blacklist/<id>/delete` | POST | ✅ common.spec.ts › blacklists: item, description and price (normalised) |
| 32 | `/settings/common-auto` | POST | ✅ global/autocollect.spec.ts › auto-collect: schedule, Run Now promotes frequent values, blacklist wins, debug log |
| 33 | `/settings/common-auto/run` | POST | ✅ global/autocollect.spec.ts › auto-collect: schedule, Run Now promotes frequent values, blacklist wins, debug log |
| 34 | `/settings/common-auto/clear-log` | POST | ✅ global/autocollect.spec.ts › auto-collect: schedule, Run Now promotes frequent values, blacklist wins, debug log |
| 35 | `/api/common-items` | GET | ✅ sweep › JSON and asset routes; common.spec.ts › item names: add, no duplicates, autocomplete, remove |
| 36 | `/api/common-descriptions` | GET | ✅ sweep › JSON and asset routes; common.spec.ts › descriptions: add and remove |
| 37 | `/api/common-prices` | GET | ✅ sweep › JSON and asset routes; add-transaction.spec.ts › expense › autocomplete suggestions come from the common lists |
| 38 | `/settings/templates` | POST | ✅ global/templates.spec.ts › weekly email text: placeholders, blank lines, preview, reset with confirm |
| 39 | `/settings/templates/reset` | POST | ✅ global/templates.spec.ts › weekly email text: placeholders, blank lines, preview, reset with confirm |
| 40 | `/settings/templates/preview/email` | GET | ✅ sweep › email preview /settings/templates/preview/email |
| 41 | `/settings/templates/preview/admin-summary` | GET | ✅ sweep › email preview /settings/templates/preview/admin-summary |
| 42 | `/settings/templates/preview/backup` | GET | ✅ sweep › email preview /settings/templates/preview/backup |
| 43 | `/settings/icon` | POST | ✅ global/templates.spec.ts › app icon: regenerate, upload, refuse bad files, reset |
| 44 | `/settings/backup` | POST | ✅ global/backup.spec.ts › schedule: enable with retention, summary line, debug log, disable |
| 45 | `/settings/backup/create` | POST | ✅ global/backup.spec.ts › create, download and delete a backup |
| 46 | `/settings/backup/clear-log` | POST | ✅ global/backup.spec.ts › schedule: enable with retention, summary line, debug log, disable |
| 47 | `/backups/download/<file>` | GET | ✅ global/backup.spec.ts › create, download and delete a backup |
| 48 | `/backups/delete/<file>` | POST | ✅ global/backup.spec.ts › create, download and delete a backup |
| 49 | `/backups/upload-chunk` | POST | ✅ global/backup.spec.ts › upload a downloaded backup and restore it: later changes are undone |
| 50 | `/backups/restore/<file>` | POST | ✅ global/backup.spec.ts › upload a downloaded backup and restore it: later changes are undone |
| 51 | `/health` | GET | ✅ sweep › JSON and asset routes |
| 52 | `/manifest.json` | GET | ✅ sweep › JSON and asset routes; pwa.spec.ts › manifest, theme colour and icons are linked |
| 53 | `/sw.js` | GET | ✅ sweep › JSON and asset routes; pwa.spec.ts › service worker › installs, and shows the offline page when the network is gone |
| 54 | `/offline` | GET | ✅ sweep › page: offline page |
| 55 | `/favicon.ico` | GET | ✅ sweep › JSON and asset routes |
| 56 | `/static/<path>` | GET | ✅ sweep › JSON and asset routes (money.js); pwa.spec.ts › manifest, theme colour and icons are linked (icons) |

## 2. Features, forms, dialogs (template extraction)

| # | Item | Test |
|---|---|---|
| 57 | Navbar links, brand, search box (base.html) | ✅ pwa.spec.ts › navbar links and brand; search.spec.ts › text matches description, notes and item names; % and _ are literal |
| 58 | Navbar collapse toggler (phone) | ✅ pwa.spec.ts › phone: the menu collapses behind the toggler |
| 59 | Flash toasts | ✅ transactions.spec.ts › delete: cancelled confirm keeps it, confirmed delete reverses balances |
| 60 | Dashboard: balances table, links, positive/negative colours | ✅ users.spec.ts › user detail: details, history with paid/received, items and notes; global/templates.spec.ts › custom colours: hex box and picker stay in sync, the preset turns Custom |
| 61 | Dashboard: recent transactions, "View All Transactions" | ✅ global/general.spec.ts › dashboard options: email column and recent transactions |
| 62 | Dashboard: quick actions (Record Expense / Add Money / Withdraw Money) | ✅ add-transaction.spec.ts › deposit and withdrawal › quick actions open the matching tab |
| 63 | Dashboard: empty state ("No users yet.", "No transactions yet.") | ❌ (c) needs a database without active users, which the shared stack never is; `tests/test_routes.py::test_index_page` checks both texts |
| 64 | Add Transaction tabs Expense / Deposit / Withdrawal | ✅ add-transaction.spec.ts › deposit and withdrawal › quick actions open the matching tab |
| 65 | Expense: Add Item / remove item, live total, "owed to the buyer" note | ✅ add-transaction.spec.ts › expense › Add Item and remove buttons change the rows and the total |
| 66 | Expense: alert "Please add at least one item!" / incomplete row / bad price | ✅ add-transaction.spec.ts › expense › client-side checks: no items, incomplete row, bad price |
| 67 | Expense: required fields (browser validation) | ✅ add-transaction.spec.ts › expense › required fields block the submit |
| 68 | Expense: only the buyer's own items (server error) | ✅ add-transaction.spec.ts › expense › server-side: an expense of only the buyer's own items is rejected |
| 69 | Expense: receipt upload (PDF ok, .txt refused), receipt link | ✅ add-transaction.spec.ts › expense › receipt: a PDF is stored and linked, other file types are refused |
| 70 | Autocomplete datalists (items, descriptions, prices) | ✅ add-transaction.spec.ts › expense › autocomplete suggestions come from the common lists |
| 71 | Deposit / withdrawal forms, overdraw, notes | ✅ add-transaction.spec.ts › deposit and withdrawal › deposit then withdrawal move the balance |
| 72 | Amount validation (not a number, zero, negative, exponent) | ✅ add-transaction.spec.ts › deposit and withdrawal › invalid amounts are refused and change nothing |
| 73 | Tampered forms (unknown user, unknown type, no buyer) | ✅ add-transaction.spec.ts › deposit and withdrawal › tampered forms: unknown user and unknown type |
| 74 | Month view: day headers, items/notes row, receipt button, totals per type | ✅ transactions.spec.ts › month view: day groups, details, totals per type, user links |
| 75 | Month view: previous/next, jump month/year selects, next disabled on current month | ✅ transactions.spec.ts › month navigation: previous/next, jump selects, current month |
| 76 | Month view: empty month | ✅ transactions.spec.ts › empty month |
| 77 | Delete transaction: confirm dialog (cancel and accept), balances reversed — month view | ✅ transactions.spec.ts › delete: cancelled confirm keeps it, confirmed delete reverses balances |
| 78 | Delete transaction — search results | ✅ search.spec.ts › edit and delete from the results |
| 79 | Delete transaction — user detail (and its Edit link) | ✅ users.spec.ts › edit and delete a transaction from the user page |
| 80 | Edit expense: items, read-only amount, add/remove rows | ✅ transactions.spec.ts › edit › expense items: the amount follows the items, balances follow the amount |
| 81 | Edit expense: remove every item → amount editable | ✅ transactions.spec.ts › edit › removing every item makes the amount editable again |
| 82 | Edit: alert on a bad item price | ✅ transactions.spec.ts › edit › a bad item price is caught before saving |
| 83 | Edit: amount, to-user, date (moves month), new receipt, remove receipt | ✅ transactions.spec.ts › edit › deposit: amount, user, date and receipt |
| 84 | Edit: invalid amount / unknown user | ✅ transactions.spec.ts › edit › invalid amount and unknown user are refused, nothing changes |
| 85 | Edit: Cancel | ✅ transactions.spec.ts › edit › cancel goes back to the month without saving |
| 86 | Search: hint before searching, no results | ✅ search.spec.ts › before searching, and no results |
| 87 | Search: text in description / notes / item names, literal % and _ | ✅ search.spec.ts › text matches description, notes and item names; % and _ are literal |
| 88 | Search: advanced filters collapse, type, user, dates, amounts, receipt | ✅ search.spec.ts › advanced filters: type, user, dates, amounts, receipt |
| 89 | Search: pagination keeps the filters | ✅ search.spec.ts › pagination keeps the query and filters |
| 90 | Add user form (options), Users tab table | ✅ users.spec.ts › add a user from Settings → Users |
| 91 | Add user: duplicate name/email (case-insensitive), bad email, too long, blank | ✅ users.spec.ts › add user: validation messages |
| 92 | User detail: email, balance, member since, paid/received history, items, notes, back link | ✅ users.spec.ts › user detail: details, history with paid/received, items and notes |
| 93 | User detail: empty history, pagination | ✅ users.spec.ts › user detail: empty history and pagination |
| 94 | Edit user dialog (modal): cancel, close, save, duplicate email, bad date | ✅ users.spec.ts › edit dialog: change everything, validation, cancel |
| 95 | Deactivate/reactivate on the detail page; hidden everywhere else | ✅ users.spec.ts › deactivate and reactivate on the detail page |
| 96 | Deactivate (confirm) / reactivate on the Users tab | ✅ users.spec.ts › deactivate (with confirm) and reactivate on the Users tab |
| 97 | Charts: first load (last 90 days, all users) | ✅ analytics.spec.ts › first load: the last 90 days of every active user |
| 98 | Charts: users dropdown (clear/select all, n of m), dates, Apply, 4 tabs, By Amount/By Count | ✅ analytics.spec.ts › filters: users and dates drive every chart |
| 99 | Charts: empty states (no users, no transactions, no items) | ✅ analytics.spec.ts › empty states: no users ticked, and a period without transactions |
| 100 | Charts: quick ranges 30/90/365/All | ✅ analytics.spec.ts › quick ranges count back from today |
| 101 | Charts: error box when the data request fails | ✅ analytics.spec.ts › a failing data request shows the error box |
| 102 | Charts: Print / PDF button, print layout, before/afterprint | ✅ analytics.spec.ts › print: the button prints, print media shows only the header and the active chart |
| 103 | Settings tabs, remembered tab after a save | ✅ sweep › page: settings tab …; common.spec.ts › item names: add, no duplicates, autocomplete, remove |
| 104 | General: language (whole UI, html lang, flashes, offline page) | ✅ global/general.spec.ts › language: the whole UI switches to German and back |
| 105 | General: timezone | ✅ global/general.spec.ts › timezone: stored times are shown in the chosen zone |
| 106 | General: decimal separator, currency symbol | ✅ global/general.spec.ts › decimal comma and currency symbol everywhere amounts appear |
| 107 | General: email column on the dashboard, recent transactions count (incl. 0) | ✅ global/general.spec.ts › dashboard options: email column and recent transactions |
| 108 | General: default empty item rows (incl. 0) | ✅ global/general.spec.ts › default empty item rows on the expense form |
| 109 | General: site admin (hidden on dashboard, enables admin emails, inactive admin stays) | ✅ global/general.spec.ts › site admin: hidden from the dashboard, enables the admin emails |
| 110 | Email: credentials, password kept, encryption → port suggestion | ✅ global/email.spec.ts › credentials form: saved, password kept when left blank, port suggestion |
| 111 | Email: invalid port | ✅ global/email.spec.ts › invalid port is refused by the server |
| 112 | Email: Send Now (Mailpit), opt-out, admin summary, debug log, Clear Log confirm | ✅ global/email.spec.ts › Send Now: every opted-in user gets their balance, the admin a summary |
| 113 | Email: SMTP failure | ✅ global/email.spec.ts › a broken SMTP server: every send fails, and the failures are logged |
| 114 | Email: sending switched off | ✅ global/email.spec.ts › sending switched off: Send Now does nothing |
| 115 | Email: auto-schedule switch shows/hides fields, summary line | ✅ global/email.spec.ts › auto-schedule: enable, the summary line, disable |
| 116 | Scheduled runs firing (email, auto-collect, backup + status email to the admin) | ❌ (c) the jobs run in the app's own clock; `tests/test_backup.py::test_backup_job_prunes_to_keep_and_mails_admin` runs the backup job (retention pruning, status mail to the admin), `tests/test_email_sending.py::test_backup_status_mail_failure_is_logged` its mail failure, `tests/test_validation.py::test_timezone_change_reschedules_backup_job` / `test_broken_schedule_settings_do_not_block_startup` the scheduling; the e2e suite drives the same code through Send Now / Run Now / Create Backup Now |
| 117 | Common: global autocomplete switch | ✅ global/autocollect.spec.ts › switching autocomplete off empties every suggestion list |
| 118 | Common: item names add (no duplicates) / remove confirm | ✅ common.spec.ts › item names: add, no duplicates, autocomplete, remove |
| 119 | Common: descriptions add / remove confirm | ✅ common.spec.ts › descriptions: add and remove |
| 120 | Common: prices (comma input) add / invalid / remove confirm | ✅ common.spec.ts › prices: comma input, display, invalid input, remove |
| 121 | Common: three blacklists add / remove, price normalised, invalid | ✅ common.spec.ts › blacklists: item, description and price (normalised) |
| 122 | Common: server checks (blank, invalid type, unknown ids → 404) | ✅ common.spec.ts › server-side checks: blank values and unknown ids |
| 123 | Auto-collect: switch, thresholds, schedule, summary line, Run Now, blacklist, debug log, Clear Log | ✅ global/autocollect.spec.ts › auto-collect: schedule, Run Now promotes frequent values, blacklist wins, debug log |
| 124 | Backup: Create Backup Now, list, Download, Delete confirm | ✅ global/backup.spec.ts › create, download and delete a backup |
| 125 | Backup: delete/restore unknown or invalid file name | ✅ global/backup.spec.ts › delete: unknown and invalid file names |
| 126 | Backup: chunked upload with progress, page reload, Restore confirm (cancel, accept), safety backup | ✅ global/backup.spec.ts › upload a downloaded backup and restore it: later changes are undone |
| 127 | Backup upload: alerts (no file, empty file, over 2 GB), not an archive | ✅ global/backup.spec.ts › upload: no file, an empty file, a too large file, not an archive |
| 128 | Backup: schedule, retention, admin-email switch disabled without admin, debug log | ✅ global/backup.spec.ts › schedule: enable with retention, summary line, debug log, disable |
| 129 | Templates: preset theme → pickers, navbar/theme-color/manifest recoloured | ✅ global/templates.spec.ts › preset theme fills the pickers and recolours the app |
| 130 | Templates: hex box ↔ picker, preset turns Custom, balance colours | ✅ global/templates.spec.ts › custom colours: hex box and picker stay in sync, the preset turns Custom |
| 131 | Templates: weekly email texts, placeholders, blank line omitted, Preview (new tab), Reset confirm | ✅ global/templates.spec.ts › weekly email text: placeholders, blank lines, preview, reset with confirm |
| 132 | Templates: stored per language | ✅ global/templates.spec.ts › templates are kept per language |
| 133 | Templates: admin summary (include emails), backup preview | ✅ global/templates.spec.ts › admin summary and backup previews; email addresses in the summary |
| 134 | App icon: regenerate, upload (none / gif / broken / png), reset | ✅ global/templates.spec.ts › app icon: regenerate, upload, refuse bad files, reset |
| 135 | PWA: service worker, offline page, Retry | ✅ pwa.spec.ts › service worker › installs, and shows the offline page when the network is gone |

## 3. Error states and cross-cutting

| # | Item | Test |
|---|---|---|
| 136 | 404: unknown user / transaction / receipt / backup file / route; POST actions on unknown ids | ✅ sweep › error states: 404 for unknown ids, files and routes; users.spec.ts › unknown user ids answer 404 on every user action |
| 137 | 400: form without CSRF token | ✅ errors.spec.ts › a form posted without its CSRF token is refused |
| 138 | 429: per-client rate limit, message, other clients unaffected | ✅ errors.spec.ts › rate limit: the 11th new user within a minute is refused with a message; errors.spec.ts › rate limit is per client: another client can still add users |

Not counted as items: the docs tour (`e2e/docs/`, its own render check) and the German
translation of every string (covered by `pybabel` catalogs and `tests/test_i18n.py`; the
e2e suite switches the language once, #104, plus the German blacklist messages,
`global/general.spec.ts › German blacklist messages name the list in German`).
