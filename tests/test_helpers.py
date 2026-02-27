from decimal import Decimal, InvalidOperation

import pytest


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


def test_parse_amount_negative(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount('-5.25') == Decimal('-5.25')


def test_parse_amount_empty_string(app):
    with app.app_context():
        from helpers import parse_amount
        with pytest.raises(InvalidOperation):
            parse_amount('')


def test_parse_amount_invalid_letters(app):
    with app.app_context():
        from helpers import parse_amount
        with pytest.raises(InvalidOperation):
            parse_amount('abc')


def test_fmt_amount_comma_separator(app):
    with app.app_context():
        from helpers import set_setting, fmt_amount
        set_setting('decimal_separator', ',')
        result = fmt_amount(Decimal('1234.56'))
        assert result == '1234,56'


def test_hex_to_rgb_standard(app):
    with app.app_context():
        from helpers import hex_to_rgb
        assert hex_to_rgb('#ff0000') == '255, 0, 0'
        assert hex_to_rgb('#00ff00') == '0, 255, 0'
        assert hex_to_rgb('#0000ff') == '0, 0, 255'


def test_hex_to_rgb_invalid(app):
    with app.app_context():
        from helpers import hex_to_rgb
        assert hex_to_rgb('invalid') == '0, 0, 0'
        assert hex_to_rgb('') == '0, 0, 0'


def test_apply_template_multiple_placeholders(app):
    with app.app_context():
        from helpers import apply_template
        result = apply_template('Hello [Name], your balance is [Balance].',
                                Name='Alice', Balance='€50.00')
        assert result == 'Hello Alice, your balance is €50.00.'


def test_apply_template_missing_placeholder(app):
    with app.app_context():
        from helpers import apply_template
        result = apply_template('Hello [Name], status: [Status]', Name='Bob')
        assert result == 'Hello Bob, status: [Status]'
