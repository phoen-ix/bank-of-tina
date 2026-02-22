╔══════════════════════════════════════════════════════════════╗
║                  BANK OF TINA - READ ME FIRST                ║
╚══════════════════════════════════════════════════════════════╝

Welcome! You've extracted the Bank of Tina application.

QUICK START (3 steps):
═══════════════════════

1. CONFIGURE EMAIL
   ─────────────────
   There are TWO copies of the env file for your convenience:
   
   Hidden:  .env.example  (use: ls -la to see it)
   Visible: env.example   (regular ls shows it)
   
   Copy either one to .env and edit it:
   
   $ cp env.example .env
   $ nano .env
   
   Required: Add your email SMTP settings


2. RUN SETUP
   ──────────
   $ ./setup.sh
   
   This will:
   - Check Docker/Docker Compose
   - Create directories
   - Build containers
   - Start the application


3. ACCESS THE APP
   ───────────────
   Open in browser: http://localhost:5000
   
   Or: http://YOUR_SERVER_IP:5000


TROUBLESHOOTING:
════════════════

"Where is .env.example?"
  → It's hidden! Use: ls -la
  → Or use the visible copy: env.example

"Docker Compose not found"
  → Scripts auto-detect docker compose vs docker-compose
  → Both versions work!

"Emails not sending"
  → Check your .env file
  → For Gmail: Use App Password, not regular password
  → Test with: ./send_emails.sh


HELPFUL COMMANDS:
═════════════════

Check status:       ./status.sh
View logs:          docker compose logs -f web
Restart:            docker compose restart
Stop:               docker compose down
Send emails:        ./send_emails.sh


DOCUMENTATION:
══════════════

README.md                  → Full technical documentation
QUICK_START_FOR_TINA.md    → Daily usage guide (for Tina)
PROJECT_SUMMARY.md         → Feature overview


GMAIL SETUP (most common):
═══════════════════════════

1. Go to: https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Generate App Password for "Bank of Tina"
4. Use that password in .env file:

   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  (app password)
   FROM_EMAIL=your-email@gmail.com


Questions? Check README.md for detailed help!

════════════════════════════════════════════════════════════════
