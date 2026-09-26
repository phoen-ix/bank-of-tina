from decimal import Decimal

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
        from helpers import set_setting
        assert fmt_amount(Decimal('12.50')) == '12.50'
        set_setting('decimal_separator', ',')
        assert fmt_amount(Decimal('12.5')) == '12,50'


def test_fmt_amount_zero(app):
    with app.app_context():
        from helpers import fmt_amount
        assert fmt_amount(Decimal('0')) == '0.00'
        assert fmt_amount(Decimal('-3.1')) == '-3.10'


def test_parse_amount_negative(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount('-5.25') == Decimal('-5.25')


def test_parse_amount_empty_string(app):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount('') == Decimal('0')


def test_parse_amount_invalid_letters(app):
    with app.app_context():
        from helpers import parse_amount, AmountError
        with pytest.raises(AmountError):
            parse_amount('abc')
        # Callers catch ValueError; decimal.InvalidOperation is not one.
        assert issubclass(AmountError, ValueError)


@pytest.mark.parametrize('raw', ['NaN', 'Infinity', '-inf', '1e5', '1.2.3', '12,34,56', '--1', '.'])
def test_parse_amount_rejects_non_plain_numbers(app, raw):
    with app.app_context():
        from helpers import parse_amount, AmountError
        with pytest.raises(AmountError):
            parse_amount(raw)


@pytest.mark.parametrize('raw, expected', [
    ('1.005', '1.01'), ('2.004', '2.00'), ('7', '7.00'), ('.5', '0.50'),
    ('1.234,56', '1234.56'), ('1,234.56', '1234.56'), ('1 234,5', '1234.50'),
])
def test_parse_amount_normalizes_to_cents(app, raw, expected):
    with app.app_context():
        from helpers import parse_amount
        assert parse_amount(raw) == Decimal(expected)
        assert parse_amount(raw).as_tuple().exponent == -2


def test_parse_amount_positive_and_range(app):
    with app.app_context():
        from helpers import parse_amount, AmountError
        with pytest.raises(AmountError):
            parse_amount('0', positive=True)
        with pytest.raises(AmountError):
            parse_amount('-3', positive=True)
        with pytest.raises(AmountError):
            parse_amount('10000000000')
        assert parse_amount('9999999999.99') == Decimal('9999999999.99')


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
