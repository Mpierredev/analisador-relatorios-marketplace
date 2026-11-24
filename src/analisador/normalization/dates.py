"""Vectorized date parsing supporting Brazilian, ISO, and textual PT/ES dates."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from analisador.core.config import DEFAULT_TIMEZONE, PREVIEW_ROW_COUNT

_TEXTUAL_MONTHS: Final[dict[str, str]] = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "marco": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "septiembre": "09",
    "setiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}

_TEXTUAL_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<day>\d{1,2})\s+de\s+(?P<month>[A-Za-zÀ-ÿ]+)\s+de\s+(?P<year>\d{4})"
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
    r"\s*(?:hs?\.?)?)?$",
    re.IGNORECASE,
)
_ISO_TZ_AWARE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})$"
)
_ISO_NAIVE_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
)
_BR_STANDARD_FORMATS: Final[tuple[str, ...]] = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
)
_US_STANDARD_FORMATS: Final[tuple[str, ...]] = (
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%m-%d-%Y %H:%M:%S",
    "%m-%d-%Y %H:%M",
    "%m-%d-%Y",
)


@dataclass(frozen=True, slots=True)
class DateParseResult:
    """Result of parsing a raw date Series along with failure diagnostics."""

    series: pd.Series[Any]
    total_count: int
    parsed_count: int
    empty_count: int
    invalid_count: int
    sample_invalid_rows: tuple[int, ...] = ()


def _build_format_cascade(
    *,
    dayfirst: bool,
    date_formats: Sequence[str],
) -> tuple[str, ...]:
    locale_formats = _BR_STANDARD_FORMATS if dayfirst else _US_STANDARD_FORMATS
    ordered = (*_ISO_NAIVE_FORMATS, *date_formats, *locale_formats)
    return tuple(dict.fromkeys(ordered))


def _localize_naive_timestamp(naive: datetime, timezone: str) -> datetime:
    localized = pd.Timestamp(naive).tz_localize(
        timezone, nonexistent="shift_forward", ambiguous=True
    )
    result: datetime = localized.to_pydatetime()
    return result


def _rewrite_textual_scalar(text: str) -> str:
    match = _TEXTUAL_DATE_RE.match(text)
    if match is None:
        return text
    month_num = _TEXTUAL_MONTHS.get(match.group("month").lower())
    if month_num is None:
        return text
    base = f"{match.group('year')}-{month_num}-{match.group('day').zfill(2)}"
    hour = match.group("hour")
    if hour is None:
        return base
    second = match.group("second") or "00"
    return f"{base} {hour.zfill(2)}:{match.group('minute')}:{second}"


def parse_date_value(
    raw: str,
    *,
    dayfirst: bool = True,
    timezone: str = DEFAULT_TIMEZONE,
    date_formats: Sequence[str] = (),
) -> datetime | None:
    """Parse a single date string into a timezone-aware datetime, or None."""
    target_tz = ZoneInfo(timezone)
    text = raw.strip()
    if not text:
        return None
    normalized = _rewrite_textual_scalar(text)
    if _ISO_TZ_AWARE_RE.match(normalized):
        try:
            iso_dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
        return iso_dt.astimezone(target_tz)

    for fmt in _build_format_cascade(dayfirst=dayfirst, date_formats=date_formats):
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        return _localize_naive_timestamp(parsed, timezone)
    return None


def _rewrite_textual_series(non_empty: pd.Series[Any]) -> pd.Series[Any]:
    extracted = non_empty.str.extract(_TEXTUAL_DATE_RE)
    months = extracted["month"].fillna("").str.lower().map(_TEXTUAL_MONTHS)
    valid = months.notna()
    if not valid.any():
        return non_empty

    sub = extracted.loc[valid]
    base = sub["year"] + "-" + months.loc[valid] + "-" + sub["day"].str.zfill(2)
    has_time = sub["hour"].notna()
    if has_time.any():
        base.loc[has_time] = (
            base.loc[has_time]
            + " "
            + sub.loc[has_time, "hour"].str.zfill(2)
            + ":"
            + sub.loc[has_time, "minute"]
            + ":"
            + sub.loc[has_time, "second"].fillna("00")
        )
    rewritten = non_empty.copy()
    rewritten.loc[valid] = base
    return rewritten


def _parse_aware_iso_slice(
    aware_strings: pd.Series[Any],
    timezone: str,
) -> pd.Series[Any]:
    parsed = pd.to_datetime(aware_strings, format="ISO8601", utc=True, errors="coerce")
    converted: pd.Series[Any] = parsed.dt.tz_convert(timezone).dt.as_unit("us")
    return converted


def _parse_naive_cascade_slice(
    naive_strings: pd.Series[Any],
    *,
    dayfirst: bool,
    timezone: str,
    date_formats: Sequence[str],
) -> pd.Series[Any]:
    naive_result = pd.Series(pd.NaT, index=naive_strings.index, dtype="datetime64[us]")
    remaining = naive_strings
    for fmt in _build_format_cascade(dayfirst=dayfirst, date_formats=date_formats):
        if remaining.empty:
            break
        attempt = pd.to_datetime(remaining, format=fmt, errors="coerce")
        matched = attempt.notna()
        if matched.any():
            naive_result.loc[attempt.index[matched]] = attempt.loc[matched].dt.as_unit(
                "us"
            )
            remaining = remaining.loc[~matched]
    localized: pd.Series[Any] = naive_result.dt.tz_localize(
        timezone, nonexistent="shift_forward", ambiguous=True
    ).dt.as_unit("us")
    return localized


def _parse_non_empty_dates(
    non_empty: pd.Series[Any],
    *,
    dayfirst: bool,
    timezone: str,
    date_formats: Sequence[str],
) -> pd.Series[Any]:
    rewritten = _rewrite_textual_series(non_empty)
    aware_mask = rewritten.str.match(_ISO_TZ_AWARE_RE)
    tz_dtype = pd.DatetimeTZDtype(unit="us", tz=timezone)
    parsed = pd.Series(pd.NaT, index=non_empty.index, dtype=tz_dtype)
    if aware_mask.any():
        aware_idx = rewritten.index[aware_mask]
        parsed.loc[aware_idx] = _parse_aware_iso_slice(
            rewritten.loc[aware_idx], timezone
        )
    if (~aware_mask).any():
        naive_idx = rewritten.index[~aware_mask]
        parsed.loc[naive_idx] = _parse_naive_cascade_slice(
            rewritten.loc[naive_idx],
            dayfirst=dayfirst,
            timezone=timezone,
            date_formats=date_formats,
        )
    return parsed


def _build_date_parse_result(
    result: pd.Series[Any],
    non_empty_mask: pd.Series[Any],
    total_count: int,
    empty_count: int,
) -> DateParseResult:
    invalid_mask = non_empty_mask & result.isna()
    invalid_positions = np.flatnonzero(invalid_mask.to_numpy(dtype=bool))
    sample_invalid = tuple(int(pos) for pos in invalid_positions[:PREVIEW_ROW_COUNT])
    return DateParseResult(
        series=result,
        total_count=total_count,
        parsed_count=int(result.notna().sum()),
        empty_count=empty_count,
        invalid_count=len(invalid_positions),
        sample_invalid_rows=sample_invalid,
    )


def parse_date_series(
    series: pd.Series[Any],
    *,
    dayfirst: bool = True,
    timezone: str = DEFAULT_TIMEZONE,
    date_formats: Sequence[str] = (),
) -> DateParseResult:
    """Vectorized date parsing for a Pandas Series with failure tracking."""
    ZoneInfo(timezone)
    tz_dtype = pd.DatetimeTZDtype(unit="us", tz=timezone)
    result = pd.Series(pd.NaT, index=series.index, dtype=tz_dtype)
    total_count = len(series)
    if total_count == 0:
        return DateParseResult(
            series=result, total_count=0, parsed_count=0, empty_count=0, invalid_count=0
        )

    cleaned = series.fillna("").astype(str).str.strip()
    non_empty_mask = cleaned != ""
    empty_count = int((~non_empty_mask).sum())
    if non_empty_mask.any():
        result.loc[non_empty_mask] = _parse_non_empty_dates(
            cleaned.loc[non_empty_mask],
            dayfirst=dayfirst,
            timezone=timezone,
            date_formats=date_formats,
        )
    return _build_date_parse_result(result, non_empty_mask, total_count, empty_count)


__all__ = [
    "DateParseResult",
    "parse_date_series",
    "parse_date_value",
]
