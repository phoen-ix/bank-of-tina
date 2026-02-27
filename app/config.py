from __future__ import annotations

ALLOWED_EXTENSIONS: set[str] = {'png', 'jpg', 'jpeg', 'pdf'}

BACKUP_DIR: str = '/backups'

THEMES: dict[str, dict[str, str]] = {
    'default': {
        'label': 'Default',
        'color_navbar': '#0d6efd',
        'color_email_grad_start': '#667eea',
        'color_email_grad_end': '#764ba2',
        'color_balance_positive': '#28a745',
        'color_balance_negative': '#dc3545',
    },
    'ocean': {
        'label': 'Ocean',
        'color_navbar': '#0077b6',
        'color_email_grad_start': '#0077b6',
        'color_email_grad_end': '#00b4d8',
        'color_balance_positive': '#2ec4b6',
        'color_balance_negative': '#e76f51',
    },
    'forest': {
        'label': 'Forest',
        'color_navbar': '#2d6a4f',
        'color_email_grad_start': '#2d6a4f',
        'color_email_grad_end': '#52b788',
        'color_balance_positive': '#52b788',
        'color_balance_negative': '#e63946',
    },
    'sunset': {
        'label': 'Sunset',
        'color_navbar': '#c94b4b',
        'color_email_grad_start': '#c94b4b',
        'color_email_grad_end': '#4b134f',
        'color_balance_positive': '#28a745',
        'color_balance_negative': '#dc3545',
    },
    'slate': {
        'label': 'Slate',
        'color_navbar': '#343a40',
        'color_email_grad_start': '#343a40',
        'color_email_grad_end': '#6c757d',
        'color_balance_positive': '#28a745',
        'color_balance_negative': '#dc3545',
    },
}

TEMPLATE_DEFAULTS: dict[str, str] = {
    'color_navbar':             '#0d6efd',
    'color_email_grad_start':   '#667eea',
    'color_email_grad_end':     '#764ba2',
    'color_balance_positive':   '#28a745',
    'color_balance_negative':   '#dc3545',
    'tpl_email_subject':   'Bank of Tina - Weekly Balance Update ([Date])',
    'tpl_email_greeting':  'Hi [Name],',
    'tpl_email_intro':     "Here's your weekly update from the Bank of Tina:",
    'tpl_email_footer1':   'This is an automated weekly update from the Bank of Tina system.',
    'tpl_email_footer2':   'Making office lunches easier! \U0001f957',
    'tpl_admin_subject':   'Bank of Tina - Admin Summary ([Date])',
    'tpl_admin_intro':     '',
    'tpl_admin_footer':    'This is an automated admin summary from the Bank of Tina system.',
    'tpl_backup_subject':  'Bank of Tina - Backup [BackupStatus] ([Date])',
    'tpl_backup_footer':   'This is an automated backup report from the Bank of Tina system.',
}

DEFAULT_ICON_BG: str = '#0d6efd'
