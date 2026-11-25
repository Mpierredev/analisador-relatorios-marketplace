"""Unit tests for financial breakdown, product diagnostics, and temporal patterns."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from analisador.analytics import (
    FinancialBreakdown,
    analyze_product_diagnostics,
    compute_financial_breakdown,
    compute_hourly_sales,
    compute_weekday_sales,
)
from analisador.core.enums import CanonicalField, OrderStatus

_SP_TZ = ZoneInfo("America/Sao_Paulo")


def _sample_canonical_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            CanonicalField.ORDER_ID.value: ["O1", "O2", "O3", "O4"],
            CanonicalField.ORDER_DATE.value: [
                datetime(2026, 3, 2, 10, 15, tzinfo=_SP_TZ),  # Monday 10h
                datetime(2026, 3, 2, 10, 45, tzinfo=_SP_TZ),  # Monday 10h
                datetime(
                    2026, 3, 4, 19, 20, tzinfo=_SP_TZ
                ),  # Wednesday 19h (cancelled)
                datetime(2026, 3, 8, 22, 5, tzinfo=_SP_TZ),  # Sunday 22h (returned)
            ],
            CanonicalField.STATUS.value: [
                OrderStatus.COMPLETED.value,
                OrderStatus.COMPLETED.value,
                OrderStatus.CANCELLED.value,
                OrderStatus.RETURNED.value,
            ],
            CanonicalField.PRODUCT_NAME.value: [
                "Mouse Gamer",
                "Teclado RGB",
                "Mouse Gamer",
                "Headset USB",
            ],
            CanonicalField.SKU.value: ["SKU-M", "SKU-T", "SKU-M", "SKU-H"],
            CanonicalField.QUANTITY.value: [2, 1, 1, 1],
            CanonicalField.GROSS_REVENUE.value: [20000, 10000, 10000, 15000],
            CanonicalField.FEES.value: [3000, 1500, 1500, 2000],
            CanonicalField.SHIPPING_COST.value: [1000, 500, 500, 1000],
            CanonicalField.NET_REVENUE.value: [16000, 8000, 8000, 12000],
        }
    )


def test_financial_breakdown_decomposes_sales_and_losses() -> None:
    breakdown = compute_financial_breakdown(_sample_canonical_df())

    assert isinstance(breakdown, FinancialBreakdown)
    assert breakdown.gross_revenue == Decimal("300.00")
    assert breakdown.fees_total == Decimal("45.00")
    assert breakdown.shipping_total == Decimal("15.00")
    assert breakdown.net_revenue == Decimal("240.00")
    assert breakdown.cancelled_revenue == Decimal("100.00")
    assert breakdown.returned_revenue == Decimal("150.00")
    assert breakdown.fees_pct == Decimal("0.1500")
    assert breakdown.shipping_pct == Decimal("0.0500")
    assert breakdown.net_margin_pct == Decimal("0.8000")


def test_financial_breakdown_handles_missing_optional_columns_and_zero_gross() -> None:
    df = pd.DataFrame(
        {
            CanonicalField.ORDER_DATE.value: [
                datetime(2026, 3, 2, 9, 0, tzinfo=_SP_TZ)
            ],
            CanonicalField.STATUS.value: [OrderStatus.CANCELLED.value],
            CanonicalField.GROSS_REVENUE.value: [5000],
        }
    )
    breakdown = compute_financial_breakdown(df)

    assert breakdown.gross_revenue == Decimal("0.00")
    assert breakdown.fees_total is None
    assert breakdown.shipping_total is None
    assert breakdown.net_revenue is None
    assert breakdown.fees_pct is None
    assert breakdown.shipping_pct is None
    assert breakdown.net_margin_pct is None
    assert breakdown.cancelled_revenue == Decimal("50.00")


def test_product_diagnostics_tracks_margins_and_cancellation_rate() -> None:
    rows = analyze_product_diagnostics(_sample_canonical_df())
    by_name = {row.product_name: row for row in rows}

    assert [row.product_name for row in rows] == [
        "Mouse Gamer",
        "Teclado RGB",
        "Headset USB",
    ]
    mouse = by_name["Mouse Gamer"]
    assert mouse.sold_quantity == 2
    assert mouse.order_count == 1
    assert mouse.total_orders == 2
    assert mouse.cancelled_orders == 1
    assert mouse.returned_orders == 0
    assert mouse.cancellation_rate == pytest.approx(0.5)
    assert mouse.gross_revenue == Decimal("200.00")
    assert mouse.net_revenue == Decimal("160.00")
    assert mouse.net_margin_pct == Decimal("0.8000")

    headset = by_name["Headset USB"]
    assert headset.sold_quantity == 0
    assert headset.total_orders == 1
    assert headset.returned_orders == 1
    assert headset.gross_revenue == Decimal("0.00")
    assert headset.net_margin_pct is None


def test_product_diagnostics_validates_limit_and_empty_dataframe() -> None:
    df = _sample_canonical_df()
    assert len(analyze_product_diagnostics(df, limit=1)) == 1
    assert analyze_product_diagnostics(df.iloc[0:0]) == []
    with pytest.raises(ValueError, match="maior que zero"):
        analyze_product_diagnostics(df, limit=0)


def test_weekday_and_hourly_sales_patterns() -> None:
    df = _sample_canonical_df()
    weekdays = compute_weekday_sales(df)
    hourly = compute_hourly_sales(df)

    assert len(weekdays) == 7
    assert weekdays[0].weekday_label == "Seg"
    assert weekdays[0].order_count == 2
    assert weekdays[0].item_count == 3
    assert weekdays[0].gross_revenue == Decimal("300.00")
    assert weekdays[0].revenue_share == Decimal("1.0000")
    assert weekdays[6].order_count == 0

    assert len(hourly) == 24
    assert hourly[10].hour_label == "10h"
    assert hourly[10].order_count == 2
    assert hourly[10].gross_revenue == Decimal("300.00")
    assert hourly[10].revenue_share == Decimal("1.0000")
    assert hourly[0].order_count == 0


def test_patterns_convert_utc_timestamps_and_handle_empty() -> None:
    utc_df = pd.DataFrame(
        {
            CanonicalField.ORDER_ID.value: ["U1"],
            # 2026-03-02 03:00 UTC -> 2026-03-02 00:00 America/Sao_Paulo (Seg, 00h)
            CanonicalField.ORDER_DATE.value: [
                pd.Timestamp("2026-03-02 03:00:00+00:00")
            ],
            CanonicalField.STATUS.value: [OrderStatus.COMPLETED.value],
            CanonicalField.QUANTITY.value: [1],
            CanonicalField.GROSS_REVENUE.value: [1000],
        }
    )
    hourly = compute_hourly_sales(utc_df)
    assert hourly[0].order_count == 1
    assert compute_weekday_sales(utc_df.iloc[0:0]) == []
    assert compute_hourly_sales(utc_df.iloc[0:0]) == []
