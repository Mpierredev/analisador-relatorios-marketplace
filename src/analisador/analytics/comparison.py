"""Contiguous equivalent previous-period KPI comparisons."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final

import pandas as pd

from analisador.analytics.filters import (
    DEFAULT_EXCLUDED_STATUSES,
    validate_canonical_dataframe,
)
from analisador.analytics.kpis import compute_kpis
from analisador.core.enums import CanonicalField, OrderStatus
from analisador.core.models import KpiSummary

_COMPARISON_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)
_ONE_MICROSECOND: Final[timedelta] = timedelta(microseconds=1)


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """Comparison between current and previous values of a single KPI metric."""

    current: Decimal | int | float | None
    previous: Decimal | int | float | None
    absolute_delta: Decimal | int | float | None
    percentage_delta: float | None


@dataclass(frozen=True, slots=True)
class PeriodComparison:
    """Full comparison between the target period KPIs and its preceding window."""

    current: KpiSummary
    previous: KpiSummary
    gross_revenue: MetricDelta
    order_count: MetricDelta
    item_count: MetricDelta
    average_ticket: MetricDelta
    cancellation_rate: MetricDelta
    net_revenue: MetricDelta


def _delta_decimal(current: Decimal | None, previous: Decimal | None) -> MetricDelta:
    if current is None or previous is None:
        return MetricDelta(
            current=current,
            previous=previous,
            absolute_delta=None,
            percentage_delta=None,
        )
    absolute = current - previous
    pct = float(absolute / previous) if previous != Decimal("0") else None
    return MetricDelta(
        current=current,
        previous=previous,
        absolute_delta=absolute,
        percentage_delta=pct,
    )


def _delta_int(current: int, previous: int) -> MetricDelta:
    absolute = current - previous
    pct = (absolute / previous) if previous != 0 else None
    return MetricDelta(
        current=current,
        previous=previous,
        absolute_delta=absolute,
        percentage_delta=pct,
    )


def _delta_float(current: float | None, previous: float | None) -> MetricDelta:
    if current is None or previous is None:
        return MetricDelta(
            current=current,
            previous=previous,
            absolute_delta=None,
            percentage_delta=None,
        )
    absolute = current - previous
    pct = (absolute / previous) if previous != 0.0 else None
    return MetricDelta(
        current=current,
        previous=previous,
        absolute_delta=absolute,
        percentage_delta=pct,
    )


def _resolve_date_windows(
    start_date: date,
    end_date: date,
) -> tuple[tuple[date, date], tuple[date, date]]:
    if start_date > end_date:
        raise ValueError(
            "A data inicial do período não pode ser posterior à data final."
        )
    span_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span_days - 1)
    return (start_date, end_date), (prev_start, prev_end)


def _resolve_datetime_windows(
    start_date: date | datetime,
    end_date: date | datetime,
) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    start_ts = (
        pd.Timestamp(start_date).to_pydatetime()
        if isinstance(start_date, datetime)
        else datetime.combine(start_date, datetime.min.time())
    )
    end_ts = (
        pd.Timestamp(end_date).to_pydatetime()
        if isinstance(end_date, datetime)
        else datetime.combine(end_date, datetime.max.time())
    )
    if start_ts > end_ts:
        raise ValueError(
            "A data inicial do período não pode ser posterior à data final."
        )
    duration = end_ts - start_ts
    prev_end_dt = start_ts - _ONE_MICROSECOND
    return (start_ts, end_ts), (prev_end_dt - duration, prev_end_dt)


def _resolve_explicit_windows(
    start_date: date | datetime,
    end_date: date | datetime,
) -> tuple[
    tuple[date | datetime, date | datetime], tuple[date | datetime, date | datetime]
]:
    """Resolve explicit [start, end] and contiguous equal-duration previous window."""
    if not isinstance(start_date, datetime) and not isinstance(end_date, datetime):
        return _resolve_date_windows(start_date, end_date)
    return _resolve_datetime_windows(start_date, end_date)


def _resolve_auto_windows(
    dataframe: pd.DataFrame,
) -> tuple[tuple[date, date], tuple[date, date]]:
    """Split dataset calendar span into equal current and previous day windows."""
    valid_dates = pd.to_datetime(
        dataframe[CanonicalField.ORDER_DATE.value],
        errors="coerce",
    ).dropna()
    if valid_dates.empty:
        raise ValueError(
            "Informe o período de referência ou forneça datas válidas para comparação."
        )
    min_day = valid_dates.min().date()
    max_day = valid_dates.max().date()
    total_days = (max_day - min_day).days + 1
    if total_days < 2:
        prev_day = min_day - timedelta(days=1)
        return (min_day, max_day), (prev_day, prev_day)

    half_days = total_days // 2
    cur_end = max_day
    cur_start = max_day - timedelta(days=half_days - 1)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=half_days - 1)
    return (cur_start, cur_end), (prev_start, prev_end)


def _build_period_comparison(
    current: KpiSummary,
    previous: KpiSummary,
) -> PeriodComparison:
    return PeriodComparison(
        current=current,
        previous=previous,
        gross_revenue=_delta_decimal(current.gross_revenue, previous.gross_revenue),
        order_count=_delta_int(current.order_count, previous.order_count),
        item_count=_delta_int(current.item_count, previous.item_count),
        average_ticket=_delta_decimal(current.average_ticket, previous.average_ticket),
        cancellation_rate=_delta_float(
            current.cancellation_rate,
            previous.cancellation_rate,
        ),
        net_revenue=_delta_decimal(current.net_revenue, previous.net_revenue),
    )


def compare_periods(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> PeriodComparison:
    """Compare target period KPIs against the contiguous previous period."""
    validate_canonical_dataframe(dataframe, required_fields=_COMPARISON_REQUIRED_FIELDS)
    msg = "Informe ambas as datas inicial e final do período para comparação."
    if (start_date is None) != (end_date is None):
        raise ValueError(msg)
    cur_window, prev_window = (
        _resolve_explicit_windows(start_date, end_date)
        if start_date is not None and end_date is not None
        else _resolve_auto_windows(dataframe)
    )
    cur_kpis = compute_kpis(
        dataframe,
        start_date=cur_window[0],
        end_date=cur_window[1],
        exclude_statuses=exclude_statuses,
    )
    prev_kpis = compute_kpis(
        dataframe,
        start_date=prev_window[0],
        end_date=prev_window[1],
        exclude_statuses=exclude_statuses,
    )
    return _build_period_comparison(cur_kpis, prev_kpis)


__all__ = [
    "MetricDelta",
    "PeriodComparison",
    "compare_periods",
]
