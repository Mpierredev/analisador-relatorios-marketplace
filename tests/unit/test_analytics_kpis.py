"""Unit tests with hand-calculated expectations for KPIs and filters."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from analisador.analytics import (
    cents_to_brl_decimal,
    compute_kpis,
    compute_status_distribution,
    filter_by_period,
    filter_sales,
)
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import OrderStatus
from analisador.core.errors import MissingRequiredColumnsError

_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def _sample_canonical_df() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "order_id": "ORD-1",
            "order_date": pd.Timestamp("2025-01-01 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Fone Bluetooth",
            "sku": "FON-1",
            "quantity": 2,
            "unit_price": 10_000,
            "gross_revenue": 20_000,
            "fees": 2_000,
            "shipping_cost": 1_500,
            "net_revenue": 16_500,
            "marketplace": "mercado_livre",
        },
        {
            "order_id": "ORD-1",
            "order_date": pd.Timestamp("2025-01-01 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Cabo USB-C",
            "sku": "CAB-1",
            "quantity": 1,
            "unit_price": 5_000,
            "gross_revenue": 5_000,
            "fees": 500,
            "shipping_cost": 0,
            "net_revenue": 4_500,
            "marketplace": "mercado_livre",
        },
        {
            "order_id": "ORD-2",
            "order_date": pd.Timestamp("2025-01-03 15:30:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Fone Bluetooth",
            "sku": "FON-1",
            "quantity": 1,
            "unit_price": 15_000,
            "gross_revenue": 15_000,
            "fees": 1_500,
            "shipping_cost": 1_000,
            "net_revenue": 12_500,
            "marketplace": "mercado_livre",
        },
        {
            "order_id": "ORD-3",
            "order_date": pd.Timestamp("2025-01-04 09:00:00", tz=_TZ),
            "status": OrderStatus.CANCELLED.value,
            "product_name": "Capa Silicone",
            "sku": "CAP-1",
            "quantity": 1,
            "unit_price": 8_000,
            "gross_revenue": 8_000,
            "fees": 0,
            "shipping_cost": 0,
            "net_revenue": 8_000,
            "marketplace": "mercado_livre",
        },
        {
            "order_id": "ORD-4",
            "order_date": pd.Timestamp("2025-01-05 18:00:00", tz=_TZ),
            "status": OrderStatus.RETURNED.value,
            "product_name": "Película Vidro",
            "sku": pd.NA,
            "quantity": 3,
            "unit_price": 2_000,
            "gross_revenue": 6_000,
            "fees": pd.NA,
            "shipping_cost": pd.NA,
            "net_revenue": pd.NA,
            "marketplace": "mercado_livre",
        },
    ]
    dataframe = pd.DataFrame(rows)
    dataframe["fees"] = dataframe["fees"].astype("Int64")
    dataframe["shipping_cost"] = dataframe["shipping_cost"].astype("Int64")
    dataframe["net_revenue"] = dataframe["net_revenue"].astype("Int64")
    return dataframe


def test_cents_to_brl_decimal_rounding() -> None:
    assert cents_to_brl_decimal(12_345) == Decimal("123.45")
    assert cents_to_brl_decimal(0) == Decimal("0.00")
    assert cents_to_brl_decimal(-505) == Decimal("-5.05")


def test_compute_kpis_hand_calculated_general_and_multi_item_order() -> None:
    dataframe = _sample_canonical_df()

    kpis = compute_kpis(dataframe)

    # Active orders: ORD-1 (200.00 + 50.00 = 250.00, 3 items) + ORD-2 (150.00, 1 item)
    assert kpis.gross_revenue == Decimal("400.00")
    assert kpis.order_count == 4
    assert kpis.cancelled_order_count == 1
    assert kpis.cancellation_rate == pytest.approx(0.25)
    assert kpis.item_count == 4
    assert kpis.average_ticket == Decimal("200.00")
    assert kpis.total_fees == Decimal("40.00")
    assert kpis.total_shipping == Decimal("25.00")
    assert kpis.net_revenue == Decimal("335.00")
    assert kpis.has_net_revenue is True
    assert kpis.period_start == datetime(2025, 1, 1, 10, 0, 0, tzinfo=_TZ)
    assert kpis.period_end == datetime(2025, 1, 5, 18, 0, 0, tzinfo=_TZ)


def test_compute_kpis_period_filter_and_all_cancelled_slice() -> None:
    dataframe = _sample_canonical_df()

    jan_1_to_3 = compute_kpis(
        dataframe,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 3),
    )
    assert jan_1_to_3.order_count == 2
    assert jan_1_to_3.cancelled_order_count == 0
    assert jan_1_to_3.cancellation_rate == 0.0
    assert jan_1_to_3.gross_revenue == Decimal("400.00")
    assert jan_1_to_3.average_ticket == Decimal("200.00")

    cancelled_only = compute_kpis(
        dataframe,
        start_date=date(2025, 1, 4),
        end_date=date(2025, 1, 4),
    )
    assert cancelled_only.order_count == 1
    assert cancelled_only.cancelled_order_count == 1
    assert cancelled_only.cancellation_rate == 1.0
    assert cancelled_only.gross_revenue == Decimal("0.00")
    assert cancelled_only.item_count == 0
    assert cancelled_only.average_ticket == Decimal("0.00")
    assert cancelled_only.total_fees is None
    assert cancelled_only.net_revenue is None


def test_compute_kpis_when_optional_monetary_columns_all_na_and_empty_df() -> None:
    dataframe = _sample_canonical_df().copy()
    dataframe["fees"] = pd.Series([pd.NA] * len(dataframe), dtype="Int64")
    dataframe["shipping_cost"] = pd.Series([pd.NA] * len(dataframe), dtype="Int64")
    dataframe["net_revenue"] = pd.Series([pd.NA] * len(dataframe), dtype="Int64")

    kpis = compute_kpis(dataframe)
    assert kpis.total_fees is None
    assert kpis.total_shipping is None
    assert kpis.net_revenue is None
    assert kpis.has_net_revenue is False

    empty_kpis = compute_kpis(dataframe.iloc[0:0])
    assert empty_kpis.order_count == 0
    assert empty_kpis.cancelled_order_count == 0
    assert empty_kpis.cancellation_rate is None
    assert empty_kpis.gross_revenue == Decimal("0.00")
    assert empty_kpis.average_ticket == Decimal("0.00")
    assert empty_kpis.period_start is None
    assert empty_kpis.period_end is None


def test_compute_status_distribution_hand_calculated_shares() -> None:
    dataframe = _sample_canonical_df()

    distribution = compute_status_distribution(dataframe)

    # ORD-1 counts once as COMPLETED; ORD-2 is COMPLETED -> 2 completed orders out of 4
    assert [row.status for row in distribution] == [
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
        OrderStatus.RETURNED,
    ]
    completed = distribution[0]
    assert completed.order_count == 2
    assert completed.item_count == 4
    assert completed.gross_revenue == Decimal("400.00")
    assert completed.order_share == pytest.approx(0.5)
    assert completed.revenue_share == Decimal("0.7407")

    cancelled = distribution[1]
    assert cancelled.order_count == 1
    assert cancelled.order_share == pytest.approx(0.25)
    assert cancelled.revenue_share == Decimal("0.1481")

    returned = distribution[2]
    assert returned.order_count == 1
    assert returned.order_share == pytest.approx(0.25)
    assert returned.revenue_share == Decimal("0.1111")

    assert compute_status_distribution(dataframe.iloc[0:0]) == []


def test_filter_helpers_and_validation_errors() -> None:
    dataframe = _sample_canonical_df()

    filtered_sales = filter_sales(dataframe)
    assert len(filtered_sales) == 3
    assert set(filtered_sales["order_id"]) == {"ORD-1", "ORD-2"}

    no_exclusion = filter_sales(dataframe, exclude_statuses=())
    assert len(no_exclusion) == 5

    jan_4 = filter_by_period(
        dataframe,
        start_date=date(2025, 1, 4),
        end_date=date(2025, 1, 4),
    )
    assert list(jan_4["order_id"]) == ["ORD-3"]

    with pytest.raises(MissingRequiredColumnsError) as missing_exc:
        compute_kpis(dataframe.drop(columns=["gross_revenue"]))
    assert missing_exc.value.missing_columns == ("gross_revenue",)

    with pytest.raises(TypeError, match="DataFrame"):
        compute_kpis([{"order_date": "2025-01-01"}])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="posterior"):
        filter_by_period(
            dataframe,
            start_date=date(2025, 1, 5),
            end_date=date(2025, 1, 1),
        )

    with pytest.raises(ValueError, match="Status de pedido inválido"):
        filter_sales(dataframe, exclude_statuses=("desconhecido",))
