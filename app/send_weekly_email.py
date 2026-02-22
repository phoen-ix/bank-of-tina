#!/usr/bin/env python3
"""
Weekly email notification script for Bank of Tina
Sends balance updates to all users
"""

import os
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, User, Transaction

# Email configuration (set these via environment variables)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', SMTP_USERNAME)
FROM_NAME = os.environ.get('FROM_NAME', 'Bank of Tina')

def create_balance_email(user):
    """Create HTML email with user's balance and recent transactions"""
    
    # Get user's recent transactions
    recent_transactions = Transaction.query.filter(
        (Transaction.from_user_id == user.id) | (Transaction.to_user_id == user.id)
    ).order_by(Transaction.date.desc()).limit(10).all()
    
    # Determine balance status
    if user.balance < 0:
        balance_class = "color: #dc3545;"
        balance_status = f"You owe €{abs(user.balance):.2f}"
    elif user.balance > 0:
        balance_class = "color: #28a745;"
        balance_status = f"You are owed €{user.balance:.2f}"
    else:
        balance_class = "color: #6c757d;"
        balance_status = "Your balance is settled"
    
    # Build transaction list HTML
    transactions_html = ""
    if recent_transactions:
        for trans in recent_transactions:
            if trans.from_user_id == user.id:
                direction = "→"
                other_user = trans.to_user.name if trans.to_user else "System"
                amount_class = "color: #dc3545;"
                amount_sign = "-"
            else:
                direction = "←"
                other_user = trans.from_user.name if trans.from_user else "System"
                amount_class = "color: #28a745;"
                amount_sign = "+"
            
            transactions_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                    {trans.date.strftime('%Y-%m-%d')}
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                    {trans.description}
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                    {direction} {other_user}
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; {amount_class}">
                    {amount_sign}€{trans.amount:.2f}
                </td>
            </tr>
            """
    else:
        transactions_html = """
        <tr>
            <td colspan="4" style="padding: 16px; text-align: center; color: #6c757d;">
                No recent transactions
            </td>
        </tr>
        """
    
    # Create HTML email
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">🏦 Bank of Tina</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Weekly Balance Update</p>
        </div>
        
        <div style="background: white; padding: 30px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 10px 10px;">
            <p style="font-size: 16px; margin-bottom: 20px;">Hi {user.name},</p>
            
            <p>Here's your weekly update from the Bank of Tina:</p>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <p style="margin: 0 0 10px 0; color: #6c757d; text-transform: uppercase; font-size: 12px; font-weight: bold;">Current Balance</p>
                <h2 style="margin: 0; font-size: 36px; {balance_class}">€{user.balance:.2f}</h2>
                <p style="margin: 10px 0 0 0; {balance_class}">{balance_status}</p>
            </div>
            
            <h3 style="color: #495057; margin-top: 30px;">Recent Transactions</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;">Date</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;">Description</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;">With</th>
                        <th style="padding: 10px; text-align: right; border-bottom: 2px solid #dee2e6;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {transactions_html}
                </tbody>
            </table>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 14px;">
                <p>This is an automated weekly update from the Bank of Tina system.</p>
                <p style="margin-top: 10px;">Making office lunches easier! 🥗</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def send_email(to_email, to_name, subject, html_content):
    """Send an email via SMTP"""
    
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("Error: SMTP credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD environment variables.")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{FROM_NAME} <{FROM_EMAIL}>'
    msg['To'] = f'{to_name} <{to_email}>'
    
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email to {to_email}: {e}")
        return False

def send_weekly_updates():
    """Send weekly balance updates to all users"""
    
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("No users found in database.")
            return
        
        print(f"Sending weekly updates to {len(users)} users...")
        
        success_count = 0
        for user in users:
            print(f"Sending to {user.name} ({user.email})...")
            
            html_content = create_balance_email(user)
            subject = f"Bank of Tina - Weekly Balance Update ({datetime.now().strftime('%Y-%m-%d')})"
            
            if send_email(user.email, user.name, subject, html_content):
                success_count += 1
                print(f"  ✓ Sent successfully")
            else:
                print(f"  ✗ Failed to send")
        
        print(f"\nCompleted: {success_count}/{len(users)} emails sent successfully")

if __name__ == '__main__':
    send_weekly_updates()
