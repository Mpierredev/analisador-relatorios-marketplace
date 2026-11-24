from decimal import Decimal

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analisador.core.config import MAX_MONETARY_INTEGER_DIGITS
from analisador.core.enums import DecimalStyle
from analisador.normalization.currency import (
    cents_to_decimal,
    decimal_to_cents,
    parse_currency_cents,
    parse_currency_series_to_cents,
    parse_currency_value,
)


def _format_br(cents: int, *, include_symbol: bool = True) -> str:
    abs_cents = abs(cents)
    int_str = f"{abs_cents // 100:,}".replace(",", ".")
    body = f"{int_str},{abs_cents % 100:02d}"
    prefixed = f"R$ {body}" if include_symbol else body
    return f"-{prefixed}" if cents < 0 else prefixed


def _format_us(cents: int, *, include_symbol: bool = False) -> str:
    abs_cents = abs(cents)
    body = f"{abs_cents // 100:,}.{abs_cents % 100:02d}"
    prefixed = f"${body}" if include_symbol else body
    return f"-{prefixed}" if cents < 0 else prefixed


@pytest.mark.parametrize(
    ("raw", "style", "expected_cents"),
    [
        ("R$ 1.234,56", DecimalStyle.AUTO, 123_456),
        ("1.234,56", DecimalStyle.AUTO, 123_456),
        ("1234.56", DecimalStyle.AUTO, 123_456),
        ("1,234.56", DecimalStyle.AUTO, 123_456),
        ("$1,234.56", DecimalStyle.AUTO, 123_456),
        ("(123,45)", DecimalStyle.AUTO, -12_345),
        ("(R$ 1.234,56)", DecimalStyle.AUTO, -123_456),
        ("R$ (1.234,56)", DecimalStyle.AUTO, -123_456),
        ("(123,45 BRL)", DecimalStyle.AUTO, -12_345),
        ("-31.2", DecimalStyle.AUTO, -3_120),
        ("-121.69", DecimalStyle.AUTO, -12_169),
        ("-R$ 31,20", DecimalStyle.AUTO, -3_120),
        ("R$ -31,20", DecimalStyle.AUTO, -3_120),
        ("R$\u00a01.200", DecimalStyle.AUTO, 120_000),
        ("1.234.567", DecimalStyle.AUTO, 123_456_700),
        ("1.234", DecimalStyle.BR, 123_400),
        ("1.234", DecimalStyle.US, 123),
        ("1,234", DecimalStyle.US, 123_400),
        ("1,234", DecimalStyle.BR, 123),
        ("1.995", DecimalStyle.US, 200),
        ("-1.995", DecimalStyle.US, -200),
        ("-0.00", DecimalStyle.AUTO, 0),
        ("0,00", DecimalStyle.BR, 0),
    ],
)
def test_parse_currency_cents_valid_formats(
    raw: str,
    style: DecimalStyle,
    expected_cents: int,
) -> None:
    assert parse_currency_cents(raw, decimal_style=style) == expected_cents
    series_result = parse_currency_series_to_cents(
        pd.Series([raw]), decimal_style=style
    )
    assert int(series_result.iloc[0]) == expected_cents


@pytest.mark.parametrize(
    ("raw", "style"),
    [
        ("", DecimalStyle.AUTO),
        ("   ", DecimalStyle.AUTO),
        ("abc", DecimalStyle.AUTO),
        ("--10,00", DecimalStyle.AUTO),
        ("-R$ -10,00", DecimalStyle.AUTO),
        ("+-10.00", DecimalStyle.AUTO),
        ("(-10,00)", DecimalStyle.AUTO),
        ("1.23,45", DecimalStyle.AUTO),
        ("12,34", DecimalStyle.US),
        ("12.34", DecimalStyle.BR),
        ("10-", DecimalStyle.AUTO),
        ("9" * (MAX_MONETARY_INTEGER_DIGITS + 1), DecimalStyle.AUTO),
    ],
)
def test_parse_currency_rejects_invalid_inputs(raw: str, style: DecimalStyle) -> None:
    assert parse_currency_cents(raw, decimal_style=style) is None
    assert parse_currency_value(raw, decimal_style=style) is None
    series_result = parse_currency_series_to_cents(
        pd.Series([raw]), decimal_style=style
    )
    assert pd.isna(series_result.iloc[0])


def test_cents_decimal_conversions_and_guards() -> None:
    assert cents_to_decimal(123_456) == Decimal("1234.56")
    assert cents_to_decimal(-50) == Decimal("-0.50")
    assert parse_currency_value("R$ 1.234,56") == Decimal("1234.56")
    assert decimal_to_cents(Decimal("12.345")) == 1_235
    assert decimal_to_cents(Decimal("-12.345")) == -1_235

    with pytest.raises(ValueError, match="not bool"):
        cents_to_decimal(True)
    with pytest.raises(ValueError, match="finite Decimal"):
        decimal_to_cents(Decimal("NaN"))
    with pytest.raises(ValueError, match="maximum supported digits"):
        decimal_to_cents(Decimal("9" * (MAX_MONETARY_INTEGER_DIGITS + 1)))


def test_parse_currency_series_handles_empty_and_all_blank() -> None:
    empty_res = parse_currency_series_to_cents(pd.Series([], dtype="object"))
    assert empty_res.empty
    assert str(empty_res.dtype) == "Int64"

    blank_res = parse_currency_series_to_cents(pd.Series(["", None, pd.NA]))
    assert blank_res.isna().all()


@settings(max_examples=100, deadline=None)
@given(cents=st.integers(min_value=-(10**11), max_value=10**11))
def test_currency_roundtrip_br_us_and_parentheses(cents: int) -> None:
    br_text = _format_br(cents)
    us_text = _format_us(cents)
    assert parse_currency_cents(br_text) == cents
    assert parse_currency_cents(us_text, decimal_style=DecimalStyle.US) == cents
    if cents < 0:
        parens = f"({br_text.removeprefix('-')})"
        assert parse_currency_cents(parens) == cents


@settings(max_examples=100, deadline=None)
@given(
    values=st.lists(
        st.one_of(
            st.integers(min_value=-(10**9), max_value=10**9).map(_format_br),
            st.integers(min_value=-(10**9), max_value=10**9).map(_format_us),
            st.integers(min_value=1, max_value=10**9).map(
                lambda c: f"({_format_br(c)})"
            ),
            st.text(max_size=12),
            st.just(""),
        ),
        max_size=25,
    ),
    style=st.sampled_from(list(DecimalStyle)),
)
def test_currency_series_matches_scalar_parser(
    values: list[str],
    style: DecimalStyle,
) -> None:
    series_out = parse_currency_series_to_cents(pd.Series(values), decimal_style=style)
    scalar_out = [parse_currency_cents(item, decimal_style=style) for item in values]
    actual = [None if pd.isna(v) else int(v) for v in series_out.tolist()]
    assert actual == scalar_out
