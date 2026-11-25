"""Temporal demand patterns grouped by weekday and hour of day."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

import pandas as pd

from analisador.analytics.filters import (
    DEFAULT_EXCLUDED_STATUSES,
    build_order_key_series,
    cents_to_brl_decimal,
    filter_by_period,
    filter_sales,
    validate_canonical_dataframe,
)
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import CanonicalField, OrderStatus

_SHARE_QUANTIZER: Final[Decimal] = Decimal("0.0001")
_ZERO_SHARE: Final[Decimal] = Decimal("0.0000")
_WEEKDAY_LABELS: Final[tuple[str, ...]] = (
    "Seg",
    "Ter",
    "Qua",
    "Qui",
    "Sex",
    "Sáb",
    "Dom",
)
_PATTERN_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)


@dataclass(frozen=True, slots=True)
class WeekdaySalesRow:
    """Sales volume and revenue share for a single day of the week (Mon-Sun)."""

    weekday: int
    weekday_label: str
    order_count: int
    item_count: int
    gross_revenue: Decimal
    revenue_share: Decimal


@dataclass(frozen=True, slots=True)
class HourlySalesRow:
    """Sales volume and revenue share for a single hour of the day (00h-23h)."""

    hour: int
    hour_label: str
    order_count: int
    item_count: int
    gross_revenue: Decimal
    revenue_share: Decimal


def _localize_order_dates(series: pd.Series[Any]) -> pd.Series[Any]:
    parsed = pd.to_datetime(series, errors="coerce")
    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        return parsed.dt.tz_convert(DEFAULT_TIMEZONE)
    if parsed.isna().all() and not series.dropna().empty:
        return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(
            DEFAULT_TIMEZONE
        )
    return parsed


def _build_bucket_frame(
    sales_df: pd.DataFrame,
    buckets: pd.Series[Any],
    valid_mask: pd.Series[Any],
) -> pd.DataFrame:
    scoped = sales_df.loc[valid_mask]
    return pd.DataFrame(
        {
            "_bucket": buckets.loc[valid_mask].astype("int64"),
            "_order_key": build_order_key_series(scoped),
            "_qty": scoped[CanonicalField.QUANTITY.value],
            "_gross": scoped[CanonicalField.GROSS_REVENUE.value],
        },
        index=scoped.index,
    )


def _group_by_time_bucket(
    sales_df: pd.DataFrame,
    buckets: pd.Series[Any],
) -> tuple[dict[int, tuple[int, int, int]], int]:
    valid_mask = buckets.notna()
    if not valid_mask.any():
        return {}, 0
    working = _build_bucket_frame(sales_df, buckets, valid_mask)
    agg_df = working.groupby("_bucket", observed=True, sort=False).agg(
        orders=("_order_key", "nunique"),
        items=("_qty", "sum"),
        gross_cents=("_gross", "sum"),
    )
    totals = {
        int(bucket): (int(o), int(i), int(g))
        for bucket, o, i, g in zip(
            agg_df.index.tolist(),
            agg_df["orders"].tolist(),
            agg_df["items"].tolist(),
            agg_df["gross_cents"].tolist(),
            strict=True,
        )
    }
    return totals, sum(entry[2] for entry in totals.values())


def _compute_share(cents: int, total_cents: int) -> Decimal:
    if total_cents <= 0 or cents == 0:
        return _ZERO_SHARE
    return (Decimal(cents) / Decimal(total_cents)).quantize(
        _SHARE_QUANTIZER, rounding=ROUND_HALF_UP
    )


def _extract_time_buckets(
    dataframe: pd.DataFrame,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    exclude_statuses: Sequence[OrderStatus | str],
    attr_name: str,
) -> tuple[dict[int, tuple[int, int, int]], int]:
    validate_canonical_dataframe(dataframe, required_fields=_PATTERN_REQUIRED_FIELDS)
    sales_df = filter_sales(
        filter_by_period(dataframe, start_date, end_date),
        exclude_statuses=exclude_statuses,
    )
    if sales_df.empty:
        return {}, 0
    localized = _localize_order_dates(sales_df[CanonicalField.ORDER_DATE.value])
    bucket_series = getattr(localized.dt, attr_name)
    return _group_by_time_bucket(sales_df, bucket_series)


def compute_weekday_sales(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> list[WeekdaySalesRow]:
    """Compute sales distribution across all 7 weekdays (Monday=0 to Sunday=6)."""
    buckets, total_cents = _extract_time_buckets(
        dataframe, start_date, end_date, exclude_statuses, "day_of_week"
    )
    if not buckets:
        return []
    rows: list[WeekdaySalesRow] = []
    for day_idx, label in enumerate(_WEEKDAY_LABELS):
        orders, items, gross = buckets.get(day_idx, (0, 0, 0))
        rows.append(
            WeekdaySalesRow(
                weekday=day_idx,
                weekday_label=label,
                order_count=orders,
                item_count=items,
                gross_revenue=cents_to_brl_decimal(gross),
                revenue_share=_compute_share(gross, total_cents),
            )
        )
    return rows


def compute_hourly_sales(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> list[HourlySalesRow]:
    """Compute sales distribution across all 24 hours of day (00h-23h)."""
    buckets, total_cents = _extract_time_buckets(
        dataframe, start_date, end_date, exclude_statuses, "hour"
    )
    if not buckets:
        return []
    rows: list[HourlySalesRow] = []
    for hour_idx in range(24):
        orders, items, gross = buckets.get(hour_idx, (0, 0, 0))
        rows.append(
            HourlySalesRow(
                hour=hour_idx,
                hour_label=f"{hour_idx:02d}h",
                order_count=orders,
                item_count=items,
                gross_revenue=cents_to_brl_decimal(gross),
                revenue_share=_compute_share(gross, total_cents),
            )
        )
    return rows


__all__ = [
    "HourlySalesRow",
    "WeekdaySalesRow",
    "compute_hourly_sales",
    "compute_weekday_sales",
]
