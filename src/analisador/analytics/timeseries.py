"""Time series aggregations at daily, weekly, and monthly granularities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Final

import pandas as pd

from analisador.analytics._grouping import extract_optional_brl_sums
from analisador.analytics.filters import (
    DEFAULT_EXCLUDED_STATUSES,
    build_order_key_series,
    cents_to_brl_decimal,
    filter_by_period,
    filter_sales,
    resolve_period_bounds,
    validate_canonical_dataframe,
)
from analisador.core.enums import CanonicalField, OrderStatus

_ZERO_BRL: Final[Decimal] = Decimal("0.00")
_TIMESERIES_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)


class TimeGranularity(StrEnum):
    """Supported aggregation granularities for sales time series."""

    DAILY = "diario"
    WEEKLY = "semanal"
    MONTHLY = "mensal"


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    """Single time bucket aggregation returned by build_time_series."""

    period_start: date
    granularity: TimeGranularity
    gross_revenue: Decimal
    net_revenue: Decimal | None
    order_count: int
    item_count: int
    average_ticket: Decimal


_GRANULARITY_FREQS: Final[dict[TimeGranularity, str]] = {
    TimeGranularity.DAILY: "D",
    TimeGranularity.WEEKLY: "W-MON",
    TimeGranularity.MONTHLY: "MS",
}


def _coerce_granularity(granularity: TimeGranularity | str) -> TimeGranularity:
    if isinstance(granularity, TimeGranularity):
        return granularity
    try:
        return TimeGranularity(str(granularity).strip())
    except ValueError as exc:
        raise ValueError(f"Granularidade temporal inválida: {granularity!r}.") from exc


def _compute_bucket_dates(
    timestamps: pd.Series[Any],
    granularity: TimeGranularity,
) -> pd.Series[Any]:
    """Compute naive normalized bucket start Timestamps without .to_period()."""
    local_ts = pd.to_datetime(timestamps, errors="coerce")
    if getattr(local_ts.dt, "tz", None) is not None:
        local_ts = local_ts.dt.tz_localize(None)
    normalized = local_ts.dt.normalize()
    if granularity is TimeGranularity.DAILY:
        return normalized
    if granularity is TimeGranularity.WEEKLY:
        return normalized - pd.to_timedelta(normalized.dt.day_of_week, unit="D")
    return normalized - pd.to_timedelta(normalized.dt.day - 1, unit="D")


def _single_bucket_timestamp(
    bound: pd.Timestamp,
    granularity: TimeGranularity,
) -> pd.Timestamp:
    """Map a boundary timestamp onto its corresponding period-start bucket."""
    naive = bound.tz_localize(None) if bound.tzinfo is not None else bound
    normalized = naive.normalize()
    if granularity is TimeGranularity.DAILY:
        return normalized
    if granularity is TimeGranularity.WEEKLY:
        return normalized - pd.Timedelta(days=int(normalized.weekday()))
    return normalized.replace(day=1)


def _compute_avg_ticket(gross_brl: Decimal, orders: int) -> Decimal:
    if orders <= 0:
        return _ZERO_BRL
    return (gross_brl / Decimal(orders)).quantize(_ZERO_BRL, rounding=ROUND_HALF_UP)


def _to_bucket_date(bucket_ts: object) -> date:
    if isinstance(bucket_ts, pd.Timestamp):
        return bucket_ts.date()
    return pd.Timestamp(str(bucket_ts)).date()


def _empty_point(
    bucket_date: date,
    granularity: TimeGranularity,
    *,
    has_net_data: bool,
) -> TimeSeriesPoint:
    return TimeSeriesPoint(
        period_start=bucket_date,
        granularity=granularity,
        gross_revenue=_ZERO_BRL,
        net_revenue=_ZERO_BRL if has_net_data else None,
        order_count=0,
        item_count=0,
        average_ticket=_ZERO_BRL,
    )


def _build_full_bucket_index(
    points_by_bucket: dict[date, TimeSeriesPoint],
    granularity: TimeGranularity,
    start_bound: pd.Timestamp | None,
    end_bound: pd.Timestamp | None,
) -> list[date]:
    """Build contiguous sorted bucket start dates between span endpoints."""
    observed = sorted(points_by_bucket)
    min_bucket = pd.Timestamp(observed[0])
    max_bucket = pd.Timestamp(observed[-1])
    if start_bound is not None:
        start_bucket = _single_bucket_timestamp(start_bound, granularity)
        min_bucket = min(min_bucket, start_bucket)
    if end_bound is not None:
        end_bucket = _single_bucket_timestamp(end_bound, granularity)
        max_bucket = max(max_bucket, end_bucket)

    freq = _GRANULARITY_FREQS[granularity]
    return [ts.date() for ts in pd.date_range(min_bucket, max_bucket, freq=freq)]


def _build_bucket_frame(
    sales_df: pd.DataFrame,
    granularity: TimeGranularity,
) -> pd.DataFrame:
    cols: dict[str, pd.Series[Any]] = {
        "_bucket": _compute_bucket_dates(
            sales_df[CanonicalField.ORDER_DATE.value], granularity
        ),
        "_order_key": build_order_key_series(sales_df),
        "_qty": sales_df[CanonicalField.QUANTITY.value],
        "_gross": sales_df[CanonicalField.GROSS_REVENUE.value],
    }
    net_col = CanonicalField.NET_REVENUE.value
    if net_col in sales_df.columns:
        cols["_net"] = sales_df[net_col]
    return pd.DataFrame(cols, index=sales_df.index)


def _points_from_agg(
    agg_df: pd.DataFrame,
    net_vals: list[Decimal | None],
    granularity: TimeGranularity,
) -> dict[date, TimeSeriesPoint]:
    points: dict[date, TimeSeriesPoint] = {}
    for bucket_ts, orders, items, gross_cents, net_brl in zip(
        agg_df.index.tolist(),
        agg_df["orders"].tolist(),
        agg_df["items"].tolist(),
        agg_df["gross_cents"].tolist(),
        net_vals,
        strict=True,
    ):
        bucket_date = _to_bucket_date(bucket_ts)
        gross_brl = cents_to_brl_decimal(int(gross_cents))
        order_cnt = int(orders)
        points[bucket_date] = TimeSeriesPoint(
            period_start=bucket_date,
            granularity=granularity,
            gross_revenue=gross_brl,
            net_revenue=net_brl,
            order_count=order_cnt,
            item_count=int(items),
            average_ticket=_compute_avg_ticket(gross_brl, order_cnt),
        )
    return points


def _group_sales_by_bucket(
    sales_df: pd.DataFrame,
    granularity: TimeGranularity,
) -> dict[date, TimeSeriesPoint]:
    """Group active sales rows into bucket-keyed TimeSeriesPoint records."""
    working = _build_bucket_frame(sales_df, granularity)
    grouped = working.groupby("_bucket", sort=True)
    agg_df = grouped.agg(
        orders=("_order_key", "nunique"),
        items=("_qty", "sum"),
        gross_cents=("_gross", "sum"),
    )
    net_vals = extract_optional_brl_sums(
        grouped, "_net", len(agg_df), enabled="_net" in working.columns
    )
    return _points_from_agg(agg_df, net_vals, granularity)


def _fill_series_gaps(
    sales_df: pd.DataFrame,
    points: dict[date, TimeSeriesPoint],
    granularity: TimeGranularity,
    start_bound: pd.Timestamp | None,
    end_bound: pd.Timestamp | None,
) -> list[TimeSeriesPoint]:
    net_col = CanonicalField.NET_REVENUE.value
    has_net = net_col in sales_df.columns and not sales_df[net_col].dropna().empty
    full_dates = _build_full_bucket_index(points, granularity, start_bound, end_bound)
    return [
        points.get(day, _empty_point(day, granularity, has_net_data=has_net))
        for day in full_dates
    ]


def build_time_series(
    dataframe: pd.DataFrame,
    granularity: TimeGranularity | str = TimeGranularity.DAILY,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
    fill_missing_periods: bool = True,
) -> list[TimeSeriesPoint]:
    """Aggregate sales metrics into daily, weekly, or monthly points."""
    validate_canonical_dataframe(dataframe, required_fields=_TIMESERIES_REQUIRED_FIELDS)
    resolved_granularity = _coerce_granularity(granularity)
    start_bound, end_bound = resolve_period_bounds(dataframe, start_date, end_date)
    sales_df = filter_sales(
        filter_by_period(dataframe, start_date, end_date),
        exclude_statuses=exclude_statuses,
    )
    sales_df = sales_df.loc[sales_df[CanonicalField.ORDER_DATE.value].notna()]
    if sales_df.empty:
        return []

    points = _group_sales_by_bucket(sales_df, resolved_granularity)
    if not fill_missing_periods:
        return [points[key] for key in sorted(points)]
    return _fill_series_gaps(
        sales_df, points, resolved_granularity, start_bound, end_bound
    )


__all__ = [
    "TimeGranularity",
    "TimeSeriesPoint",
    "build_time_series",
]
