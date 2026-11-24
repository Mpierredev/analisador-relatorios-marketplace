"""Vectorized Pandas Series parsing for Brazilian and international currencies."""

from __future__ import annotations

import re
from typing import Any, Final

import numpy as np
import pandas as pd

from analisador.core.config import CENTS_PER_UNIT, MAX_MONETARY_INTEGER_DIGITS
from analisador.core.enums import DecimalStyle

BRL_TOKENS: Final[frozenset[str]] = frozenset({"r$", "brl"})

_CURRENCY_TOKEN_PATTERN: Final[str] = r"(?:r\$|us\$|brl|usd|\$|€)"
PARENS_WRAPPED_RE: Final[re.Pattern[str]] = re.compile(
    rf"^\(\s*(?P<cur1>{_CURRENCY_TOKEN_PATTERN})?\s*"
    rf"(?P<body>[0-9.,]+)\s*(?P<cur2>{_CURRENCY_TOKEN_PATTERN})?\s*\)$",
    re.IGNORECASE,
)
PREFIX_PARENS_RE: Final[re.Pattern[str]] = re.compile(
    rf"^(?P<cur1>{_CURRENCY_TOKEN_PATTERN})\s*\(\s*(?P<body>[0-9.,]+)\s*\)$",
    re.IGNORECASE,
)
SIGNED_RE: Final[re.Pattern[str]] = re.compile(
    rf"^(?P<s1>[+-])?\s*(?P<cur1>{_CURRENCY_TOKEN_PATTERN})?\s*"
    rf"(?P<s2>[+-])?\s*(?P<body>[0-9.,]+)\s*(?P<cur2>{_CURRENCY_TOKEN_PATTERN})?$",
    re.IGNORECASE,
)

DIGITS_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\d+$")
BR_BOTH_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d+$")
US_BOTH_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d+$")
COMMA_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:,\d{3})+$")
COMMA_MULTI_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{1,3}(?:,\d{3}){2,}$"
)
COMMA_SINGLE_DEC_RE: Final[re.Pattern[str]] = re.compile(r"^\d+,\d+$")
DOT_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
DOT_MULTI_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:\.\d{3}){2,}$")
DOT_BRL_SINGLE_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}\.\d{3}$")
DOT_SINGLE_DEC_RE: Final[re.Pattern[str]] = re.compile(r"^\d+\.\d+$")


def _extract_series_components(
    cleaned: pd.Series[Any],
) -> tuple[pd.Series[Any], pd.Series[Any], pd.Series[Any], pd.Series[Any]]:
    wrapped = cleaned.str.extract(PARENS_WRAPPED_RE)
    pref_parens = cleaned.str.extract(PREFIX_PARENS_RE)
    signed = cleaned.str.extract(SIGNED_RE)

    has_wrapped = wrapped["body"].notna()
    has_pref = (~has_wrapped) & pref_parens["body"].notna()
    single_sign = ~(signed["s1"].notna() & signed["s2"].notna())
    has_signed = (~has_wrapped) & (~has_pref) & signed["body"].notna() & single_sign

    body = wrapped["body"].where(has_wrapped, pref_parens["body"])
    body = body.where(has_wrapped | has_pref, signed["body"])
    valid_token = has_wrapped | has_pref | has_signed

    is_negative = (
        has_wrapped
        | has_pref
        | (has_signed & ((signed["s1"] == "-") | (signed["s2"] == "-")))
    )
    c1 = wrapped["cur1"].fillna(pref_parens["cur1"]).fillna(signed["cur1"])
    c2 = wrapped["cur2"].fillna(signed["cur2"])
    is_brl = c1.fillna("").str.lower().isin(BRL_TOKENS) | c2.fillna(
        ""
    ).str.lower().isin(BRL_TOKENS)
    return valid_token, is_negative, is_brl, body.fillna("")


def _classify_comma_only(
    comma_only: pd.Series[Any],
    body: pd.Series[Any],
    decimal_style: DecimalStyle,
) -> tuple[pd.Series[Any], pd.Series[Any]]:
    empty_mask = pd.Series(False, index=body.index)
    if decimal_style is DecimalStyle.US:
        return comma_only & body.str.fullmatch(COMMA_THOUSANDS_RE.pattern), empty_mask
    if decimal_style is DecimalStyle.BR:
        return empty_mask, comma_only & body.str.fullmatch(COMMA_SINGLE_DEC_RE.pattern)
    th_mask = comma_only & body.str.fullmatch(COMMA_MULTI_THOUSANDS_RE.pattern)
    dec_mask = comma_only & (~th_mask) & body.str.fullmatch(COMMA_SINGLE_DEC_RE.pattern)
    return th_mask, dec_mask


def _classify_dot_only(
    dot_only: pd.Series[Any],
    body: pd.Series[Any],
    is_brl: pd.Series[Any],
    decimal_style: DecimalStyle,
) -> tuple[pd.Series[Any], pd.Series[Any]]:
    empty_mask = pd.Series(False, index=body.index)
    if decimal_style is DecimalStyle.BR:
        return dot_only & body.str.fullmatch(DOT_THOUSANDS_RE.pattern), empty_mask
    if decimal_style is DecimalStyle.US:
        return empty_mask, dot_only & body.str.fullmatch(DOT_SINGLE_DEC_RE.pattern)
    th_mask = dot_only & (
        body.str.fullmatch(DOT_MULTI_THOUSANDS_RE.pattern)
        | (is_brl & body.str.fullmatch(DOT_BRL_SINGLE_THOUSANDS_RE.pattern))
    )
    dec_mask = dot_only & (~th_mask) & body.str.fullmatch(DOT_SINGLE_DEC_RE.pattern)
    return th_mask, dec_mask


def _classify_series_formats(
    body: pd.Series[Any],
    valid_token: pd.Series[Any],
    is_brl: pd.Series[Any],
    decimal_style: DecimalStyle,
) -> tuple[pd.Series[Any], pd.Series[Any], pd.Series[Any]]:
    has_dot = body.str.contains(".", regex=False)
    has_comma = body.str.contains(",", regex=False)

    pure_int = valid_token & (~has_dot) & (~has_comma) & body.str.fullmatch(r"\d+")
    both_mask = valid_token & has_dot & has_comma
    br_both = both_mask & body.str.fullmatch(BR_BOTH_RE.pattern)
    us_both = both_mask & body.str.fullmatch(US_BOTH_RE.pattern)

    comma_th, comma_dec = _classify_comma_only(
        valid_token & (~has_dot) & has_comma, body, decimal_style
    )
    dot_th, dot_dec = _classify_dot_only(
        valid_token & has_dot & (~has_comma), body, is_brl, decimal_style
    )
    return pure_int | comma_th | dot_th, br_both | comma_dec, us_both | dot_dec


def _extract_int_and_frac(
    body: pd.Series[Any],
    thousands_only: pd.Series[Any],
    br_dec: pd.Series[Any],
    us_dec: pd.Series[Any],
) -> tuple[pd.Series[Any], pd.Series[Any]]:
    int_part = pd.Series("", index=body.index, dtype="object")
    frac_part = pd.Series("", index=body.index, dtype="object")
    if thousands_only.any():
        cleaned_th = body.loc[thousands_only].str.replace(".", "", regex=False)
        int_part.loc[thousands_only] = cleaned_th.str.replace(",", "", regex=False)
    if br_dec.any():
        br_clean = body.loc[br_dec].str.replace(".", "", regex=False)
        split_br = br_clean.str.split(",", n=1)
        int_part.loc[br_dec] = split_br.str[0]
        frac_part.loc[br_dec] = split_br.str[1]
    if us_dec.any():
        us_clean = body.loc[us_dec].str.replace(",", "", regex=False)
        split_us = us_clean.str.split(".", n=1)
        int_part.loc[us_dec] = split_us.str[0]
        frac_part.loc[us_dec] = split_us.str[1]
    return int_part, frac_part


def _compute_cents_array(
    significant_int: pd.Series[Any],
    frac_part: pd.Series[Any],
    is_negative: pd.Series[Any],
    valid_len: pd.Series[Any],
) -> np.ndarray[Any, np.dtype[np.int64]]:
    int_vals = significant_int.loc[valid_len].replace("", "0").to_numpy(dtype=np.int64)
    padded = (
        frac_part.loc[valid_len]
        .astype(str)
        .str.pad(width=3, side="right", fillchar="0")
        .str.slice(0, 3)
    )
    first2 = padded.str.slice(0, 2).to_numpy(dtype=np.int64)
    carry = (padded.str.slice(2, 3) >= "5").to_numpy(dtype=np.int64)
    unsigned_cents = int_vals * CENTS_PER_UNIT + first2 + carry
    signs = np.where(is_negative.loc[valid_len].to_numpy(dtype=bool), -1, 1)
    cents: np.ndarray[Any, np.dtype[np.int64]] = (unsigned_cents * signs).astype(
        np.int64
    )
    return cents


def _parse_non_empty_currency(
    cleaned: pd.Series[Any],
    decimal_style: DecimalStyle,
    result: pd.Series[Any],
) -> pd.Series[Any]:
    valid_token, is_negative, is_brl, body = _extract_series_components(cleaned)
    thousands_only, br_dec, us_dec = _classify_series_formats(
        body, valid_token, is_brl, decimal_style
    )
    valid_format = thousands_only | br_dec | us_dec
    if not valid_format.any():
        return result
    int_part, frac_part = _extract_int_and_frac(body, thousands_only, br_dec, us_dec)
    significant_int = int_part.astype(str).str.lstrip("0")
    valid_len = valid_format & (
        significant_int.str.len() <= MAX_MONETARY_INTEGER_DIGITS
    )
    if not valid_len.any():
        return result
    cents_array = _compute_cents_array(
        significant_int, frac_part, is_negative, valid_len
    )
    result.iloc[np.flatnonzero(valid_len.to_numpy(dtype=bool))] = cents_array
    return result


def parse_currency_series_to_cents(
    series: pd.Series[Any],
    *,
    decimal_style: DecimalStyle = DecimalStyle.AUTO,
) -> pd.Series[Any]:
    """Vectorized currency parsing for a Pandas Series into nullable Int64 cents."""
    result = pd.Series(pd.NA, index=series.index, dtype="Int64")
    if series.empty:
        return result
    cleaned = (
        series.fillna("")
        .astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
    )
    if not (cleaned != "").any():
        return result
    return _parse_non_empty_currency(cleaned, decimal_style, result)


__all__ = ["parse_currency_series_to_cents"]
