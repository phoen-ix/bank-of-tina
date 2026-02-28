from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pytz

from extensions import db
from models import User, Transaction, EmailLog
from helpers import get_setting, get_tpl, apply_template, fmt_amount, now_local

logger = logging.getLogger(__name__)


def build_email_html(user: User) -> str:
    tx_pref = user.email_transactions

    if tx_pref == 'none':
        recent_transactions: list[Transaction] = []
        show_tx_section = False
    else:
        show_tx_section = True
        base_stmt = db.select(Transaction).where(
            (Transaction.from_user_id == user.id) | (Transaction.to_user_id == user.id)
        ).order_by(Transaction.date.desc())

        if tx_pref == 'last3':
            recent_transactions = db.session.execute(base_stmt.limit(3)).scalars().all()
        elif tx_pref == 'this_week':
            local_tz = pytz.timezone(get_setting('timezone', 'UTC'))
            now_lt = datetime.now(local_tz)
            week_start = (now_lt - timedelta(days=now_lt.weekday())).replace(
                            hour=0, minute=0, second=0, microsecond=0)
            week_start_utc = week_start.astimezone(pytz.UTC).replace(tzinfo=None)
            recent_transactions = db.session.execute(base_stmt.where(Transaction.date >= week_start_utc)).scalars().all()
        elif tx_pref == 'this_month':
            local_tz = pytz.timezone(get_setting('timezone', 'UTC'))
            now_lt = datetime.now(local_tz)
            month_start = now_lt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_start_utc = month_start.astimezone(pytz.UTC).replace(tzinfo=None)
            recent_transactions = db.session.execute(base_stmt.where(Transaction.date >= month_start_utc)).scalars().all()
        else:
            recent_transactions = db.session.execute(base_stmt.limit(3)).scalars().all()

    sym = get_setting('currency_symbol', '\u20ac')
    if user.balance < 0:
        balance_class = "color: #dc3545;"
        balance_status = f"You owe {sym}{fmt_amount(abs(user.balance))}"
    elif user.balance > 0:
        balance_class = "color: #28a745;"
        balance_status = f"You are owed {sym}{fmt_amount(user.balance)}"
    else:
        balance_class = "color: #6c757d;"
        balance_status = "Your balance is settled"

    transactions_section_html = ""
    if show_tx_section:
        transactions_html = ""
        if recent_transactions:
            for trans in recent_transactions:
                if trans.from_user_id == user.id:
                    direction = "\u2192"
                    other_user = trans.to_user.name if trans.to_user else "System"
                    amount_class = "color: #dc3545;"
                    amount_sign = "-"
                else:
                    direction = "\u2190"
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
                        {amount_sign}{sym}{fmt_amount(trans.amount)}
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

        transactions_section_html = f"""
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
            </table>"""

    grad_start = get_tpl('color_email_grad_start')
    grad_end   = get_tpl('color_email_grad_end')
    tpl_vars   = dict(Name=user.name, Balance=f'{sym}{fmt_amount(user.balance)}',
                      BalanceStatus=balance_status, Date=now_local().strftime('%Y-%m-%d'))

    greeting = apply_template(get_tpl('tpl_email_greeting'), **tpl_vars)
    intro    = apply_template(get_tpl('tpl_email_intro'),    **tpl_vars)
    footer1  = apply_template(get_tpl('tpl_email_footer1'),  **tpl_vars)
    footer2  = apply_template(get_tpl('tpl_email_footer2'),  **tpl_vars)

    greeting_html = f'<p style="font-size: 16px; margin-bottom: 20px;">{greeting}</p>' if greeting.strip() else ''
    intro_html    = f'<p>{intro}</p>' if intro.strip() else ''
    footer1_html  = f'<p>{footer1}</p>' if footer1.strip() else ''
    footer2_html  = f'<p style="margin-top: 10px;">{footer2}</p>' if footer2.strip() else ''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, {grad_start} 0%, {grad_end} 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">\U0001f3e6 Bank of Tina</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Weekly Balance Update</p>
        </div>

        <div style="background: white; padding: 30px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 10px 10px;">
            {greeting_html}
            {intro_html}

            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <p style="margin: 0 0 10px 0; color: #6c757d; text-transform: uppercase; font-size: 12px; font-weight: bold;">Current Balance</p>
                <h2 style="margin: 0; font-size: 36px; {balance_class}">{sym}{fmt_amount(user.balance)}</h2>
            </div>

            {transactions_section_html}

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 14px;">
                {footer1_html}
                {footer2_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html


def build_admin_summary_email(users: list[User], include_emails: bool = False) -> str:
    sym        = get_setting('currency_symbol', '\u20ac')
    date_str   = now_local().strftime('%Y-%m-%d')
    grad_start = get_tpl('color_email_grad_start')
    grad_end   = get_tpl('color_email_grad_end')
    tpl_vars   = dict(Date=date_str, UserCount=len(users))

    intro  = apply_template(get_tpl('tpl_admin_intro'),  **tpl_vars)
    footer = apply_template(get_tpl('tpl_admin_footer'), **tpl_vars)

    intro_html  = f'<p style="margin-bottom:20px;">{intro}</p>' if intro.strip() else ''
    footer_html = f'<p>{footer}</p>' if footer.strip() else ''

    pos_color = get_tpl('color_balance_positive')
    neg_color = get_tpl('color_balance_negative')
    rows_html = ''
    for user in users:
        color = neg_color if user.balance < 0 else (pos_color if user.balance > 0 else '#6c757d')
        email_cell = f'<td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; color: #6c757d; font-size: 0.9em;">{user.email}</td>' if include_emails else ''
        rows_html += f"""
            <tr>
                <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6;">{user.name}</td>
                {email_cell}
                <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold; color: {color};">{sym}{fmt_amount(user.balance)}</td>
            </tr>"""

    email_header = '<th style="padding: 10px 8px; text-align: left; border-bottom: 2px solid #dee2e6;">Email</th>' if include_emails else ''

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, {grad_start} 0%, {grad_end} 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">\U0001f3e6 Bank of Tina</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Admin Summary \u2014 {date_str}</p>
    </div>
    <div style="background: white; padding: 30px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 10px 10px;">
        {intro_html}
        <h3 style="color: #495057; margin-top: 0;">All Active Users</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 10px 8px; text-align: left; border-bottom: 2px solid #dee2e6;">Name</th>
                    {email_header}
                    <th style="padding: 10px 8px; text-align: right; border-bottom: 2px solid #dee2e6;">Balance</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 13px;">
            {footer_html}
        </div>
    </div>
</body>
</html>"""


def send_single_email(to_email: str, to_name: str, subject: str, html: str) -> tuple[bool, str | None]:
    smtp_server   = get_setting('smtp_server', 'smtp.gmail.com')
    smtp_port     = int(get_setting('smtp_port', '587'))
    smtp_username = get_setting('smtp_username', '')
    smtp_password = get_setting('smtp_password', '')
    from_email    = get_setting('from_email', smtp_username)
    from_name     = get_setting('from_name', 'Bank of Tina')

    if not smtp_username or not smtp_password:
        return False, 'SMTP credentials not configured'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{from_name} <{from_email}>'
    msg['To'] = f'{to_name} <{to_email}>'
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        logger.info('Email sent to %s', to_email)
        return True, None
    except Exception as e:
        logger.error('Email failed to %s: %s', to_email, e)
        return False, str(e)


def send_all_emails() -> tuple[int, int, list[str]]:
    if get_setting('email_enabled', '1') != '1':
        return 0, 0, ['Email sending is disabled in General settings.']

    all_active_users = db.session.execute(db.select(User).filter_by(is_active=True)).scalars().all()
    opted_in_users   = [u for u in all_active_users if u.email_opt_in]
    success, fail = 0, 0
    errors: list[str] = []
    debug = get_setting('email_debug', '0') == '1'
    subject = apply_template(get_tpl('tpl_email_subject'), Date=now_local().strftime('%Y-%m-%d'))
    for user in opted_in_users:
        html = build_email_html(user)
        ok, err = send_single_email(user.email, user.name, subject, html)
        if ok:
            success += 1
            if debug:
                db.session.add(EmailLog(level='SUCCESS',
                                        recipient=f'{user.name} <{user.email}>',
                                        message='Email sent successfully'))
        else:
            fail += 1
            errors.append(f"{user.name} <{user.email}>: {err}")
            if debug:
                db.session.add(EmailLog(level='FAIL',
                                        recipient=f'{user.name} <{user.email}>',
                                        message=err or 'Unknown error'))

    admin_id = get_setting('site_admin_id', '')
    if get_setting('admin_summary_email', '0') == '1' and admin_id:
        admin = db.session.get(User, int(admin_id)) if admin_id.isdigit() else None
        if admin:
            summary_subject = apply_template(get_tpl('tpl_admin_subject'),
                                             Date=now_local().strftime('%Y-%m-%d'),
                                             UserCount=len(all_active_users))
            summary_html = build_admin_summary_email(all_active_users, include_emails=get_setting('admin_summary_include_emails', '0') == '1')
            ok, err = send_single_email(admin.email, admin.name, summary_subject, summary_html)
            if debug:
                if ok:
                    db.session.add(EmailLog(level='INFO', recipient=None,
                                            message=f'Admin summary sent to {admin.name} <{admin.email}>'))
                else:
                    db.session.add(EmailLog(level='FAIL', recipient=f'{admin.name} <{admin.email}>',
                                            message=f'Admin summary failed: {err}'))

    if debug:
        db.session.add(EmailLog(level='INFO', recipient=None,
                                message=f'Run complete: {success} sent, {fail} failed'))
        db.session.commit()
        oldest_kept = db.session.execute(
            db.select(EmailLog).order_by(EmailLog.id.desc()).offset(500)
        ).scalar()
        if oldest_kept:
            db.session.execute(db.delete(EmailLog).where(EmailLog.id <= oldest_kept.id))
        db.session.commit()

    logger.info('Email batch complete: %d sent, %d failed', success, fail)
    return success, fail, errors
