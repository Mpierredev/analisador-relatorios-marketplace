"""Unit tests for daily, weekly, and monthly time series aggregations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from analisador.analytics import TimeGranularity, build_time_series
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import OrderStatus

_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def _sample_timeseries_df() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "order_id": "ORD-1",
            "order_date": pd.Timestamp("2025-01-01 23:10:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto A",
            "sku": "A1",
            "quantity": 2,
            "gross_revenue": 10_000,
            "net_revenue": 8_500,
        },
        {
            "order_id": "ORD-2",
            "order_date": pd.Timestamp("2025-01-03 11:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto B",
            "sku": "B1",
            "quantity": 1,
            "gross_revenue": 5_000,
            "net_revenue": 4_200,
        },
        {
            "order_id": "ORD-3",
            "order_date": pd.Timestamp("2025-01-04 12:00:00", tz=_TZ),
            "status": OrderStatus.CANCELLED.value,
            "product_name": "Produto C",
            "sku": "C1",
            "quantity": 5,
            "gross_revenue": 25_000,
            "net_revenue": 25_000,
        },
        {
            "order_id": "ORD-4",
            "order_date": pd.Timestamp("2025-01-08 09:00:00", tz=_TZ),
            "status": OrderStatus.IN_PROGRESS.value,
            "product_name": "Produto A",
            "sku": "A1",
            "quantity": 3,
            "gross_revenue": 15_000,
            "net_revenue": 12_000,
        },
        {
            "order_id": "ORD-5",
            "order_date": pd.Timestamp("2025-02-02 14:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto B",
            "sku": "B1",
            "quantity": 4,
            "gross_revenue": 20_000,
            "net_revenue": 17_000,
        },
    ]
    df = pd.DataFrame(rows)
    df["net_revenue"] = df["net_revenue"].astype("Int64")
    return df


def test_build_time_series_daily_with_gap_filling() -> None:
    dataframe = _sample_timeseries_df()

    points = build_time_series(
        dataframe,
        TimeGranularity.DAILY,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 4),
    )

    assert [point.period_start for point in points] == [
        date(2025, 1, 1),
        date(2025, 1, 2),
        date(2025, 1, 3),
        date(2025, 1, 4),
    ]
    assert points[0].gross_revenue == Decimal("100.00")
    assert points[0].net_revenue == Decimal("85.00")
    assert points[0].item_count == 2
    assert points[0].average_ticket == Decimal("100.00")

    # Jan 2 gap-filled with zeros; Jan 4 had only a cancelled order so zeros
    assert points[1].order_count == 0
    assert points[1].gross_revenue == Decimal("0.00")
    assert points[1].net_revenue == Decimal("0.00")
    assert points[2].gross_revenue == Decimal("50.00")
    assert points[3].gross_revenue == Decimal("0.00")
    assert points[3].order_count == 0


def test_build_time_series_weekly_monday_buckets_without_gaps() -> None:
    dataframe = _sample_timeseries_df()

    points = build_time_series(
        dataframe,
        TimeGranularity.WEEKLY,
        fill_missing_periods=False,
    )

    # 2025-01-01 (Wed) & 2025-01-03 (Fri) -> Monday 2024-12-30
    # 2025-01-08 (Wed) -> Monday 2025-01-06
    # 2025-02-02 (Sun) -> Monday 2025-01-27
    assert [point.period_start for point in points] == [
        date(2024, 12, 30),
        date(2025, 1, 6),
        date(2025, 1, 27),
    ]
    assert points[0].order_count == 2
    assert points[0].item_count == 3
    assert points[0].gross_revenue == Decimal("150.00")
    assert points[0].average_ticket == Decimal("75.00")
    assert points[1].gross_revenue == Decimal("150.00")
    assert points[2].gross_revenue == Decimal("200.00")


def test_build_time_series_monthly_with_and_without_net_revenue() -> None:
    dataframe = _sample_timeseries_df()

    monthly = build_time_series(dataframe, "mensal")
    assert [point.period_start for point in monthly] == [
        date(2025, 1, 1),
        date(2025, 2, 1),
    ]
    assert monthly[0].order_count == 3
    assert monthly[0].item_count == 6
    assert monthly[0].gross_revenue == Decimal("300.00")
    assert monthly[0].net_revenue == Decimal("247.00")
    assert monthly[0].average_ticket == Decimal("100.00")

    no_net_df = dataframe.drop(columns=["net_revenue"])
    monthly_no_net = build_time_series(no_net_df, TimeGranularity.MONTHLY)
    assert all(point.net_revenue is None for point in monthly_no_net)


def test_build_time_series_empty_and_invalid_granularity() -> None:
    dataframe = _sample_timeseries_df()
    assert build_time_series(dataframe.iloc[0:0], TimeGranularity.DAILY) == []

    with pytest.raises(ValueError, match="Granularidade temporal inválida"):
        build_time_series(dataframe, "hora")
