"""Targeted unit tests closing remaining branch and defensive coverage gaps."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from analisador.analytics import (
    TimeGranularity,
    build_time_series,
    compare_periods,
    compute_status_distribution,
    filter_by_period,
    rank_products,
)
from analisador.analytics.comparison import _resolve_datetime_windows
from analisador.analytics.filters import build_order_key_series, count_unique_orders
from analisador.analytics.timeseries import _compute_avg_ticket
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import DecimalStyle, OrderStatus
from analisador.normalization.currency import parse_currency_cents
from analisador.normalization.dtypes import (
    compact_categorical_text,
    compact_quantity_series,
)
from analisador.normalization.quality import count_duplicate_rows
from analisador.validation.types import InferredColumnType, infer_column_type

_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def test_dtype_compaction_edges() -> None:
    empty_qty = compact_quantity_series(pd.Series([], dtype="Int64"))
    assert str(empty_qty.dtype) == "int32"

    large_qty = compact_quantity_series(pd.Series([3_000_000_000], dtype="Int64"))
    assert str(large_qty.dtype) == "int64"

    empty_txt = compact_categorical_text(pd.Series([], dtype="string"))
    assert len(empty_txt) == 0


def test_currency_quality_and_validation_type_edge_cases() -> None:
    # Single-separator invalid BR precision vs multi-thousands AUTO formatting
    assert parse_currency_cents("1,23,45", decimal_style=DecimalStyle.BR) is None
    assert (
        parse_currency_cents("1,234,567", decimal_style=DecimalStyle.AUTO)
        == 123_456_700
    )

    assert count_duplicate_rows(pd.DataFrame(), has_mapped_order_id=True) == 0

    # Leading-zero codes are identifiers, not integer quantities
    assert infer_column_type(["007", "008", "009"]) == InferredColumnType.IDENTIFIER


def test_analytics_grouping_timeseries_and_comparison_edges() -> None:
    # DataFrame without order_id/sku columns, naive datetimes, and mixed null order_ids
    naive_df = pd.DataFrame(
        {
            "order_date": [
                pd.Timestamp("2025-01-06 10:00:00"),
                pd.Timestamp("2025-02-10 12:00:00"),
            ],
            "status": [OrderStatus.COMPLETED.value, "status_nao_mapeado"],
            "product_name": ["Item Zero", "Item Outro"],
            "quantity": pd.Series([1, 2], dtype="int32"),
            "gross_revenue": pd.Series([0, 0], dtype="int64"),
        }
    )
    assert count_unique_orders(naive_df) == 2
    assert list(build_order_key_series(naive_df)) == [0, 1]

    ranked = rank_products(naive_df)
    assert len(ranked) == 2
    assert all(row.sku is None for row in ranked)
    assert all(row.net_revenue is None for row in ranked)
    assert all(row.revenue_share == Decimal("0.0000") for row in ranked)

    dist = compute_status_distribution(naive_df)
    assert {row.status for row in dist} == {OrderStatus.COMPLETED, OrderStatus.OTHER}

    aware_bound_filtered = filter_by_period(
        naive_df,
        start_date=datetime(2025, 1, 1, tzinfo=_TZ),
        end_date=datetime(2025, 1, 31, tzinfo=_TZ),
    )
    assert len(aware_bound_filtered) == 1

    weekly = build_time_series(
        naive_df,
        TimeGranularity.WEEKLY,
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 20),
    )
    assert len(weekly) >= 3
    monthly = build_time_series(
        naive_df,
        TimeGranularity.MONTHLY,
        start_date=date(2025, 1, 15),
        end_date=date(2025, 3, 5),
    )
    assert len(monthly) == 3

    assert _compute_avg_ticket(Decimal("100.00"), 0) == Decimal("0.00")

    # Partial null order_id key preserves nulls as distinct orders
    aware_df = naive_df.copy()
    aware_df["order_date"] = aware_df["order_date"].dt.tz_localize(_TZ)
    aware_df["order_id"] = pd.Series(["ORD-A", pd.NA], dtype="string")
    keys = build_order_key_series(aware_df)
    assert keys.nunique() == 2

    with pytest.raises(ValueError, match="posterior"):
        _resolve_datetime_windows(date(2025, 2, 10), datetime(2025, 2, 1, 12, 0))
    with pytest.raises(ValueError, match="posterior"):
        compare_periods(
            aware_df,
            start_date=date(2025, 2, 10),
            end_date=datetime(2025, 2, 1, 12, 0, tzinfo=_TZ),
        )
