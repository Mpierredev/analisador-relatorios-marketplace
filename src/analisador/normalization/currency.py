"""Brazilian and international currency parsing into exact cents and Decimals."""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from analisador.core.config import CENTS_PER_UNIT, MAX_MONETARY_INTEGER_DIGITS
from analisador.core.enums import DecimalStyle
from analisador.normalization.currency_series import (
    BR_BOTH_RE,
    BRL_TOKENS,
    COMMA_MULTI_THOUSANDS_RE,
    COMMA_SINGLE_DEC_RE,
    COMMA_THOUSANDS_RE,
    DIGITS_ONLY_RE,
    DOT_BRL_SINGLE_THOUSANDS_RE,
    DOT_MULTI_THOUSANDS_RE,
    DOT_SINGLE_DEC_RE,
    DOT_THOUSANDS_RE,
    PARENS_WRAPPED_RE,
    PREFIX_PARENS_RE,
    SIGNED_RE,
    US_BOTH_RE,
    parse_currency_series_to_cents,
)

_CENTS_DECIMAL: Final[Decimal] = Decimal(CENTS_PER_UNIT)
_TWO_DECIMALS: Final[Decimal] = Decimal("0.01")


def cents_to_decimal(cents: int) -> Decimal:
    """Convert an integer cent amount to a 2-decimal-place Decimal."""
    if isinstance(cents, bool):
        raise ValueError("cents must be an integer, not bool.")
    return (Decimal(cents) / _CENTS_DECIMAL).quantize(_TWO_DECIMALS)


def decimal_to_cents(value: Decimal) -> int:
    """Convert a finite Decimal to exact integer cents using ROUND_HALF_UP."""
    if not value.is_finite():
        raise ValueError("value must be a finite Decimal.")
    quantized = value.quantize(_TWO_DECIMALS, rounding=ROUND_HALF_UP)
    int_digits = str(abs(quantized)).split(".", 1)[0].lstrip("0")
    if len(int_digits) > MAX_MONETARY_INTEGER_DIGITS:
        raise ValueError("Monetary value exceeds maximum supported digits.")
    return int((quantized * _CENTS_DECIMAL).to_integral_exact())


def _is_brl_token(cur1: str | None, cur2: str | None) -> bool:
    tokens = {tok.lower() for tok in (cur1, cur2) if tok}
    return bool(tokens & BRL_TOKENS)


def _extract_scalar_parts(raw: str) -> tuple[bool, bool, str] | None:
    text = raw.replace("\u00a0", " ").strip()
    if not text:
        return None
    for pattern in (PARENS_WRAPPED_RE, PREFIX_PARENS_RE):
        match = pattern.match(text)
        if match is not None:
            cur1 = match.group("cur1")
            cur2 = match.groupdict().get("cur2")
            return True, _is_brl_token(cur1, cur2), match.group("body")
    signed_match = SIGNED_RE.match(text)
    if signed_match is None:
        return None
    s1, s2 = signed_match.group("s1"), signed_match.group("s2")
    if s1 and s2:
        return None
    is_negative = s1 == "-" or s2 == "-"
    is_brl = _is_brl_token(signed_match.group("cur1"), signed_match.group("cur2"))
    return is_negative, is_brl, signed_match.group("body")


def _split_single(
    body: str,
    pattern: re.Pattern[str],
    separator: str,
) -> tuple[str, str] | None:
    if not pattern.match(body):
        return None
    int_part, frac_part = body.split(separator, 1)
    return int_part, frac_part


def _split_comma_only(body: str, decimal_style: DecimalStyle) -> tuple[str, str] | None:
    if decimal_style is DecimalStyle.US:
        return (body.replace(",", ""), "") if COMMA_THOUSANDS_RE.match(body) else None
    if decimal_style is DecimalStyle.BR:
        return _split_single(body, COMMA_SINGLE_DEC_RE, ",")
    if COMMA_MULTI_THOUSANDS_RE.match(body):
        return body.replace(",", ""), ""
    return _split_single(body, COMMA_SINGLE_DEC_RE, ",")


def _split_dot_only(
    body: str,
    *,
    decimal_style: DecimalStyle,
    is_brl_currency: bool,
) -> tuple[str, str] | None:
    if decimal_style is DecimalStyle.BR:
        return (body.replace(".", ""), "") if DOT_THOUSANDS_RE.match(body) else None
    if decimal_style is DecimalStyle.US:
        return _split_single(body, DOT_SINGLE_DEC_RE, ".")
    if DOT_MULTI_THOUSANDS_RE.match(body):
        return body.replace(".", ""), ""
    if is_brl_currency and DOT_BRL_SINGLE_THOUSANDS_RE.match(body):
        return body.replace(".", ""), ""
    return _split_single(body, DOT_SINGLE_DEC_RE, ".")


def _split_numeric_body(
    body: str,
    *,
    decimal_style: DecimalStyle,
    is_brl_currency: bool,
) -> tuple[str, str] | None:
    if DIGITS_ONLY_RE.match(body):
        return body, ""
    if "." in body and "," in body:
        if BR_BOTH_RE.match(body):
            int_part, frac_part = body.replace(".", "").split(",", 1)
            return int_part, frac_part
        if US_BOTH_RE.match(body):
            int_part, frac_part = body.replace(",", "").split(".", 1)
            return int_part, frac_part
        return None
    if "," in body:
        return _split_comma_only(body, decimal_style)
    return _split_dot_only(
        body, decimal_style=decimal_style, is_brl_currency=is_brl_currency
    )


def parse_currency_cents(
    raw: str,
    *,
    decimal_style: DecimalStyle = DecimalStyle.AUTO,
) -> int | None:
    """Parse a currency string directly into integer cents, or None if invalid."""
    extracted = _extract_scalar_parts(raw)
    if extracted is None:
        return None
    is_negative, is_brl, body = extracted
    parts = _split_numeric_body(
        body, decimal_style=decimal_style, is_brl_currency=is_brl
    )
    if parts is None:
        return None
    int_part, frac_part = parts
    significant_int = int_part.lstrip("0")
    if len(significant_int) > MAX_MONETARY_INTEGER_DIGITS:
        return None
    padded = (frac_part + "000")[:3]
    carry = 1 if padded[2] >= "5" else 0
    int_value = int(significant_int) if significant_int else 0
    unsigned_cents = int_value * CENTS_PER_UNIT + int(padded[:2]) + carry
    return -unsigned_cents if is_negative and unsigned_cents > 0 else unsigned_cents


def parse_currency_value(
    raw: str,
    *,
    decimal_style: DecimalStyle = DecimalStyle.AUTO,
) -> Decimal | None:
    """Parse a currency string into a 2-decimal-place Decimal, or None if invalid."""
    cents = parse_currency_cents(raw, decimal_style=decimal_style)
    if cents is None:
        return None
    return cents_to_decimal(cents)


__all__ = [
    "cents_to_decimal",
    "decimal_to_cents",
    "parse_currency_cents",
    "parse_currency_series_to_cents",
    "parse_currency_value",
]
