from decimal import Decimal


def test_parse_amount_dot(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount('12.50') == Decimal('12.50')


def test_parse_amount_comma(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount('12,50') == Decimal('12.50')


def test_parse_amount_none(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount(None) == Decimal('0')


def test_parse_amount_whitespace(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount('  3.14  ') == Decimal('3.14')


def test_fmt_amount_default_separator(app):
    with app.app_context():
        from helpers import fmt_amount
        result = fmt_amount(Decimal('12.50'))
        assert result == '12.50' or result == '12,50'  # depends on db setting


def test_fmt_amount_zero(app):
    with app.app_context():
        from helpers import fmt_amount
        result = fmt_amount(Decimal('0'))
        assert '0' in result and '00' in result
