# Quick Start Guide for Tina 🥗

Hey Tina! This is your personal guide to using Bank of Tina. Don't worry - it's super easy!

## Your Daily Workflow

### 1. Someone Buys Lunch (e.g., Alex gets sandwiches)

**Steps:**
1. Open the app: `http://your-server:5000`
2. Click "Add Transaction" (top menu)
3. Stay on the "Expense" tab (it's the first one)
4. Fill out the form:
   - **Who paid?** → Select "Alex"
   - **Description** → Type "Lunch at Subway" or whatever
   - **Receipt** → Click "Choose File" and upload the photo Alex sent you
5. Click "Add Item" and fill in each sandwich:
   - **Item name**: "Turkey Sandwich"
   - **Price**: €6.50
   - **Who owes?**: Select "Walter" (or whoever ordered it)
6. Keep clicking "Add Item" for each person's food
7. Click "Record Expense" at the bottom
8. Done! ✅

**What happens:**
- Walter's balance goes down by €6.50 (he owes)
- Alex's balance goes up by €6.50 (he's owed)
- The receipt is saved for reference

### 2. Someone Adds Money to Their Account

**When someone gives you cash or does a bank transfer:**

1. Click "Add Transaction"
2. Click the "Deposit" tab
3. Fill in:
   - **User** → Select the person (e.g., Walter)
   - **Amount** → Type how much (e.g., 20.00)
   - **Description** → Optional, like "Cash deposit"
4. Click "Add Money"
5. Done! Their balance goes up ✅

### 3. Someone Withdraws Money

**When someone takes money out:**

1. Click "Add Transaction"
2. Click the "Withdrawal" tab
3. Fill in:
   - **User** → Select the person
   - **Amount** → How much they're taking out
4. Click "Withdraw Money"
5. Done! Their balance goes down ✅

## Viewing Balances

The **Dashboard** (home page) shows everyone's current balance:
- **Green numbers** 💚 = They are OWED money (someone owes them)
- **Red numbers** ❤️ = They OWE money (they need to pay)

Click on anyone's name to see their full transaction history!

## Weekly Emails 📧

Every Monday at 9 AM, everyone automatically gets an email showing:
- Their current balance
- Recent transactions
- Who they owe or who owes them

**To send emails manually right now:**
```bash
./send_emails.sh
```

Just run this command on your server anytime you want to send the weekly update.

## Common Scenarios

### Scenario: Lunch Run
**Alex goes to the store, buys lunch for Walter and Sarah**

1. Add transaction → Expense
2. Who paid: Alex
3. Description: "Store lunch run"
4. Upload receipt (the store receipt photo)
5. Add items:
   - Item: "Caesar Salad", Price: €5.50, Who owes: Walter
   - Item: "Chicken Wrap", Price: €6.00, Who owes: Sarah
   - Item: "Chips", Price: €2.00, Who owes: Alex (yes, Alex can owe himself!)
6. Record expense

**Result:**
- Walter: -€5.50
- Sarah: -€6.00
- Alex: +€11.50 (he paid €13.50 but owes himself €2)

### Scenario: Monthly Top-Up
**Walter deposits €50 to cover his expenses**

1. Add transaction → Deposit
2. User: Walter
3. Amount: 50
4. Add Money

**Result:**
- If Walter was at -€12.30, he's now at +€37.70

## Tips to Make Your Life Easier

### 1. Batch Entry
If you get 5 receipts during lunch, enter them all at once while you have the receipts handy.

### 2. Clear Descriptions
Instead of "Food" write "Pizza Palace - Friday lunch" so people remember what it was.

### 3. Upload Receipts
Always upload the receipt image - it prevents disputes and keeps records clean.

### 4. Check Balances Weekly
Look at the dashboard on Mondays before sending emails. If someone's balance is getting too negative, maybe give them a friendly reminder!

### 5. Encourage Settlement
When someone hits +€50 or -€50, suggest they settle up (deposit or withdraw) to keep balances manageable.

## Troubleshooting

### "I can't log in!"
This app doesn't have login - just open the URL in your browser! It's designed for internal use.

### "Upload failed"
- Check if the file is too big (max 16MB)
- Make sure it's a JPG, PNG, or PDF
- Try a smaller image

### "Emails aren't sending"
1. Check if your email settings are correct in the `.env` file
2. Try sending manually: `./send_emails.sh`
3. Check the error messages that appear

### "I made a mistake!"
Unfortunately, there's no "undo" button yet. But you can:
- Add a reverse transaction to correct it
- Or ask your IT person to help with the database

## Quick Reference Card

```
🏠 Dashboard          → See everyone's balance
➕ Add Transaction   → Record expenses, deposits, withdrawals
📋 All Transactions  → See complete history
📧 Send Emails       → Run: ./send_emails.sh
📊 Check Status      → Run: ./status.sh
```

## You're All Set! 🎉

You're doing a great thing managing money for everyone. This tool will make it so much easier!

**Remember:**
- The app saves everything automatically
- Receipts are stored safely
- Everyone gets weekly updates
- You can see everything at a glance on the dashboard

Questions? The full README.md has more details, or ask your IT colleague who set this up!

Happy tracking! 🥗💰
