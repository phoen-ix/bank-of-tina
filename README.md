# 🏦 Bank of Tina

A simple, dockerized web application to manage shared expenses and balances within your office or group. Perfect for tracking lunch expenses, shared purchases, and keeping everyone's account balanced!

## ✨ Features

- **User Management**: Add team members with email addresses
- **Expense Tracking**: Record who paid for what and who owes whom
- **Receipt Upload**: Upload and store receipt images (JPG, PNG, PDF)
- **Manual Item Entry**: Easily add items with prices and assign to the right person
- **Balance Tracking**: Real-time balance updates for all users
- **Deposit/Withdrawal**: Users can add or withdraw money from their accounts
- **Transaction History**: Complete audit trail of all transactions
- **Weekly Email Reports**: Automated balance updates sent every Monday
- **Mobile Responsive**: Works great on phones, tablets, and desktops

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed on your server
  - For newer Docker installations, Compose is a plugin (use `docker compose`)
  - For older installations, use standalone `docker-compose`
  - The scripts auto-detect which version you have
- An email account for sending notifications (Gmail, Outlook, etc.)

### Installation

1. **Clone or copy this project to your server**:
```bash
cd /path/to/your/server
# Copy the bank-of-tina directory here
```

2. **Create the required directories** (if they don't exist):
```bash
cd bank-of-tina
mkdir -p uploads database
```

3. **Configure email settings**:
```bash
cp .env.example .env
nano .env  # Edit with your email credentials
```

**Note**: `.env.example` is a hidden file (starts with a dot). To see it:
```bash
ls -la    # Shows hidden files
# OR use the visible copy:
cp env.example .env
```

For Gmail:
- Go to Google Account → Security → 2-Step Verification → App Passwords
- Generate an app password for "Bank of Tina"
- Use this password in your `.env` file

4. **Start the application**:
```bash
# The script auto-detects your Docker Compose version
docker-compose up -d
# OR if using the Docker Compose plugin:
docker compose up -d
```

5. **Access the web interface**:
```
http://your-server-ip:5000
```

## 📧 Email Configuration

### Supported Email Providers

**Gmail** (recommended for simplicity):
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

**Outlook/Office365**:
```env
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

**Yahoo**:
```env
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-password
```

**Custom SMTP Server**:
```env
SMTP_SERVER=mail.yourdomain.com
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
```

### Setting Up Automated Weekly Emails

#### Option 1: Using Cron on Host Server (Recommended)

Add to your server's crontab:
```bash
crontab -e
```

Add this line (adjust path):
```cron
# Send weekly emails every Monday at 9:00 AM
0 9 * * 1 /path/to/bank-of-tina/send_emails.sh
```

#### Option 2: Using Docker Cron Container

Uncomment the `cron` service in `docker-compose.yml` and restart:
```bash
docker-compose down
docker-compose up -d
```

#### Manual Email Sending

To send emails manually at any time:
```bash
./send_emails.sh
```

Or directly:
```bash
docker exec bank-of-tina python send_weekly_email.py
```

## 📱 Usage Guide

### Adding Users

1. Go to the dashboard
2. Click "Add User"
3. Enter name and email address
4. User is created with €0.00 balance

### Recording an Expense

**Example: Alex buys lunch, Walter owes for a salad**

1. Click "Add Transaction" → "Expense" tab
2. Select who paid (Alex)
3. Add description (e.g., "Supermarket lunch")
4. Upload receipt (optional)
5. Click "Add Item" for each item:
   - Item: "Caesar Salad"
   - Price: €5.50
   - Who owes: Walter
6. Click "Record Expense"

Result: Walter's balance: -€5.50, Alex's balance: +€5.50

### Adding Money (Deposit)

When someone wants to add money to their account:
1. Click "Add Transaction" → "Deposit" tab
2. Select the user
3. Enter amount
4. Click "Add Money"

### Withdrawing Money

When someone wants to withdraw from their balance:
1. Click "Add Transaction" → "Withdrawal" tab
2. Select the user
3. Enter amount
4. Click "Withdraw Money"

## 🗂️ File Structure

```
bank-of-tina/
├── app/
│   ├── app.py                 # Main Flask application
│   ├── send_weekly_email.py   # Email notification script
│   ├── templates/             # HTML templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── add_transaction.html
│   │   ├── transactions.html
│   │   └── user_detail.html
│   └── static/                # Static files (CSS, JS)
├── uploads/                   # Receipt images (mounted volume)
├── database/                  # SQLite database (mounted volume)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .env                       # Your configuration (create from .env.example)
├── crontab                    # Cron schedule for emails
├── send_emails.sh            # Script to manually send emails
└── README.md
```

## 🔒 Security Notes

- **Change the SECRET_KEY** in `.env` to a random string
- **Never commit** your `.env` file to version control
- **Use app passwords** for Gmail instead of your main password
- **Restrict access** to the web interface (use a reverse proxy with authentication if exposed to internet)
- **Backup** your database regularly (it's in the `database/` folder)

## 🔧 Maintenance

### Backup Database

```bash
cp database/bank_of_tina.db database/bank_of_tina_backup_$(date +%Y%m%d).db
```

### View Logs

```bash
docker compose logs -f web
# OR
docker-compose logs -f web
```

### Update the Application

```bash
docker compose down
docker compose build
docker compose up -d
# OR use docker-compose if you have the standalone version
```

### Reset Everything (⚠️ WARNING: Deletes all data)

```bash
docker compose down  # or docker-compose down
rm -rf database/* uploads/*
docker compose up -d  # or docker-compose up -d
```

## 🐛 Troubleshooting

### Emails not sending?

1. Check your SMTP credentials in `.env`
2. For Gmail, ensure you're using an App Password
3. Check the logs: `docker-compose logs web`
4. Test manually: `./send_emails.sh`

### Can't upload receipts?

1. Check file permissions: `chmod 777 uploads/`
2. Ensure the uploads volume is mounted correctly
3. Check file size (max 16MB)

### Database locked?

1. Restart the container: `docker compose restart web` (or `docker-compose restart web`)
2. Check file permissions: `chmod 666 database/bank_of_tina.db`

### Port 5000 already in use?

Edit `docker-compose.yml` and change the port:
```yaml
ports:
  - "8000:5000"  # Use port 8000 instead
```

## 🎨 Customization

### Change the Port

Edit `docker-compose.yml`:
```yaml
ports:
  - "YOUR_PORT:5000"
```

### Change Email Schedule

Edit `crontab` file:
```
# Every Friday at 5 PM
0 17 * * 5 cd /app && /usr/local/bin/python send_weekly_email.py >> /var/log/cron.log 2>&1
```

### Customize Email Template

Edit `app/send_weekly_email.py` and modify the `create_balance_email()` function.

## 💡 Tips for Tina

### Workflow for Recording Expenses

1. **During the day**: Collect receipts from teammates
2. **End of day**: Log into the app and record each expense
3. **Upload receipts**: Keep digital copies for reference
4. **Review**: Check the dashboard to see everyone's balance

### Best Practices

- Enter transactions on the same day they occur
- Always upload receipts for larger expenses
- Use clear descriptions (e.g., "Lunch - Italian Restaurant" instead of just "Food")
- Encourage users to settle up when balances get high
- Run the weekly email on Monday mornings to start the week fresh

### Encouraging Adoption

- Show teammates the dashboard - it's satisfying to see balances!
- The email notifications keep everyone informed without manual work
- Receipt photos make expense tracking transparent
- It's much easier than manual spreadsheets or cash handling

## 📊 Improvements & Future Ideas

Potential enhancements you could add:

- [ ] OCR for automatic receipt parsing
- [ ] Split expenses among multiple people (percentage-based)
- [ ] Export transactions to CSV/Excel
- [ ] User authentication and login system
- [ ] Mobile app
- [ ] Integration with Slack/Teams for notifications
- [ ] Charts and analytics
- [ ] Support for multiple currencies
- [ ] Recurring expenses (monthly lunch subscription, etc.)

## 🤝 Support

Need help? Things to try:

1. Check this README thoroughly
2. Look at the example workflows above
3. Check Docker logs: `docker-compose logs -f`
4. Ensure all environment variables are set correctly

## 📄 License

This is a personal tool created to help Tina manage office expenses. Feel free to modify and adapt it to your needs!

---

Made with ❤️ to make office lunches easier! 🥗
