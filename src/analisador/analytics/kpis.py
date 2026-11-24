"""KPI summary and order status distribution calculations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

import pandas as pd

from analisador.analytics.filters import (
    DEFAULT_EXCLUDED_STATUSES,
    cents_to_brl_decimal,
    count_unique_orders,
    filter_by_period,
    filter_sales,
    resolve_period_bounds,
    validate_canonical_dataframe,
)
from analisador.core.enums import CanonicalField, OrderStatus
from analisador.core.models import KpiSummary

_ZERO_BRL: Final[Decimal] = Decimal("0.00")
_SHARE_QUANTIZER: Final[Decimal] = Decimal("0.0001")
_ZERO_SHARE: Final[Decimal] = Decimal("0.0000")
_KPI_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)
_STATUS_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)


@dataclass(frozen=True, slots=True)
class StatusDistributionRow:
    """Aggregated order, item, and revenue breakdown for a single OrderStatus."""

    status: OrderStatus
    order_count: int
    item_count: int
    gross_revenue: Decimal
    order_share: float
    revenue_share: Decimal


def _sum_optional_cents(
    dataframe: pd.DataFrame, field: CanonicalField
) -> Decimal | None:
    """Sum an optional cents column in BRL, returning None when absent or all-NA."""
    column = field.value
    if dataframe.empty or column not in dataframe.columns:
        return None
    series: pd.Series[Any] = dataframe[column].dropna()
    if series.empty:
        return None
    return cents_to_brl_decimal(int(series.sum()))


def _resolve_summary_period(
    period_df: pd.DataFrame,
    start_bound: pd.Timestamp | None,
    end_bound: pd.Timestamp | None,
) -> tuple[datetime | None, datetime | None]:
    """Resolve period_start and period_end timestamps for KpiSummary."""
    valid_dates = pd.to_datetime(
        period_df[CanonicalField.ORDER_DATE.value],
        errors="coerce",
    ).dropna()
    resolved_start = (
        start_bound.to_pydatetime()
        if start_bound is not None
        else (valid_dates.min().to_pydatetime() if not valid_dates.empty else None)
    )
    resolved_end = (
        end_bound.to_pydatetime()
        if end_bound is not None
        else (valid_dates.max().to_pydatetime() if not valid_dates.empty else None)
    )
    if resolved_start is None or resolved_end is None:
        return resolved_start, resolved_end
    if resolved_start > resolved_end:
        return resolved_start, resolved_start
    return resolved_start, resolved_end


def _compute_cancelled_order_count(dataframe: pd.DataFrame) -> int:
    """Count distinct orders whose canonical status equals OrderStatus.CANCELLED."""
    if dataframe.empty:
        return 0
    status_series = dataframe[CanonicalField.STATUS.value].astype("string").str.strip()
    cancelled_df = dataframe.loc[status_series == OrderStatus.CANCELLED.value]
    return count_unique_orders(cancelled_df)


def _compute_average_ticket(gross_revenue: Decimal, order_count: int) -> Decimal:
    """Compute 2-decimal average ticket per order, returning 0.00 when empty."""
    if order_count <= 0:
        return _ZERO_BRL
    return (gross_revenue / Decimal(order_count)).quantize(
        _ZERO_BRL,
        rounding=ROUND_HALF_UP,
    )


def _sum_required_int(dataframe: pd.DataFrame, field: CanonicalField) -> int:
    return 0 if dataframe.empty else int(dataframe[field.value].sum())


def _build_kpi_summary(
    period_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    period_start: datetime | None,
    period_end: datetime | None,
) -> KpiSummary:
    total_orders = count_unique_orders(period_df)
    cancelled = min(_compute_cancelled_order_count(period_df), total_orders)
    gross_brl = cents_to_brl_decimal(
        _sum_required_int(sales_df, CanonicalField.GROSS_REVENUE)
    )
    items = _sum_required_int(sales_df, CanonicalField.QUANTITY)
    avg_ticket = _compute_average_ticket(gross_brl, count_unique_orders(sales_df))
    return KpiSummary(
        gross_revenue=gross_brl,
        order_count=total_orders,
        item_count=items,
        average_ticket=avg_ticket,
        cancellation_rate=(cancelled / total_orders) if total_orders > 0 else None,
        cancelled_order_count=cancelled,
        total_fees=_sum_optional_cents(sales_df, CanonicalField.FEES),
        total_shipping=_sum_optional_cents(sales_df, CanonicalField.SHIPPING_COST),
        net_revenue=_sum_optional_cents(sales_df, CanonicalField.NET_REVENUE),
        period_start=period_start,
        period_end=period_end,
    )


def compute_kpis(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> KpiSummary:
    """Compute general or period-filtered sales KPIs from a canonical DataFrame."""
    validate_canonical_dataframe(dataframe, required_fields=_KPI_REQUIRED_FIELDS)
    start_bound, end_bound = resolve_period_bounds(dataframe, start_date, end_date)
    period_df = filter_by_period(dataframe, start_date, end_date)
    period_start, period_end = _resolve_summary_period(
        period_df, start_bound, end_bound
    )
    sales_df = filter_sales(period_df, exclude_statuses=exclude_statuses)
    return _build_kpi_summary(period_df, sales_df, period_start, period_end)


def _coerce_status(raw_status: object) -> OrderStatus:
    """Coerce a grouped status string into OrderStatus, falling back to OTHER."""
    text = "" if raw_status is None else str(raw_status).strip()
    try:
        return OrderStatus(text)
    except ValueError:
        return OrderStatus.OTHER


def _group_status_entries(
    period_df: pd.DataFrame,
) -> list[tuple[OrderStatus, int, int, int]]:
    working = period_df.copy()
    working["_status_key"] = (
        working[CanonicalField.STATUS.value].astype("string").fillna("").str.strip()
    )
    entries: list[tuple[OrderStatus, int, int, int]] = []
    for raw_status, group in working.groupby("_status_key", observed=True, sort=False):
        entries.append(
            (
                _coerce_status(raw_status),
                count_unique_orders(group),
                int(group[CanonicalField.QUANTITY.value].sum()),
                int(group[CanonicalField.GROSS_REVENUE.value].sum()),
            )
        )
    return entries


def _build_status_row(
    entry: tuple[OrderStatus, int, int, int],
    total_orders: int,
    total_cents: int,
) -> StatusDistributionRow:
    status, orders, items, cents = entry
    rev_share = (
        (Decimal(cents) / Decimal(total_cents)).quantize(
            _SHARE_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )
        if total_cents > 0
        else _ZERO_SHARE
    )
    return StatusDistributionRow(
        status=status,
        order_count=orders,
        item_count=items,
        gross_revenue=cents_to_brl_decimal(cents),
        order_share=(orders / total_orders) if total_orders > 0 else 0.0,
        revenue_share=rev_share,
    )


def compute_status_distribution(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
) -> list[StatusDistributionRow]:
    """Compute order counts, items, revenue, and shares grouped by OrderStatus."""
    validate_canonical_dataframe(dataframe, required_fields=_STATUS_REQUIRED_FIELDS)
    period_df = filter_by_period(dataframe, start_date, end_date)
    if period_df.empty:
        return []
    entries = _group_status_entries(period_df)
    total_orders = sum(entry[1] for entry in entries)
    total_cents = sum(entry[3] for entry in entries)
    rows = [_build_status_row(e, total_orders, total_cents) for e in entries]
    rows.sort(key=lambda r: (-r.order_count, -r.gross_revenue, r.status.value))
    return rows


__all__ = [
    "StatusDistributionRow",
    "compute_kpis",
    "compute_status_distribution",
]
