"""Unit tests for product rankings and ABC Pareto curve calculations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from analisador.analytics import (
    AbcClass,
    ProductRankingMetric,
    compute_abc_curve,
    rank_products,
)
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import OrderStatus

_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def _sample_products_df() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "order_id": "ORD-1",
            "order_date": pd.Timestamp("2025-01-01 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Notebook Pro",
            "sku": "NB-1",
            "quantity": 1,
            "gross_revenue": 30_000,
            "net_revenue": 27_000,
        },
        {
            "order_id": "ORD-2",
            "order_date": pd.Timestamp("2025-01-02 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Notebook Pro",
            "sku": "NB-1",
            "quantity": 1,
            "gross_revenue": 20_000,
            "net_revenue": 18_000,
        },
        {
            "order_id": "ORD-3",
            "order_date": pd.Timestamp("2025-01-03 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Monitor 27",
            "sku": "MON-27",
            "quantity": 2,
            "gross_revenue": 30_000,
            "net_revenue": 26_000,
        },
        {
            "order_id": "ORD-4",
            "order_date": pd.Timestamp("2025-01-04 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Teclado Mecânico",
            "sku": "TEC-1",
            "quantity": 3,
            "gross_revenue": 15_000,
            "net_revenue": 13_000,
        },
        {
            "order_id": "ORD-5",
            "order_date": pd.Timestamp("2025-01-05 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Mouse Pad",
            "sku": pd.NA,
            "quantity": 5,
            "gross_revenue": 5_000,
            "net_revenue": 4_500,
        },
        {
            "order_id": "ORD-6",
            "order_date": pd.Timestamp("2025-01-06 10:00:00", tz=_TZ),
            "status": OrderStatus.CANCELLED.value,
            "product_name": "Mouse Pad",
            "sku": "MP-1",
            "quantity": 10,
            "gross_revenue": 10_000,
            "net_revenue": 10_000,
        },
    ]
    df = pd.DataFrame(rows)
    df["net_revenue"] = df["net_revenue"].astype("Int64")
    return df


def test_rank_products_by_revenue_and_quantity_with_limit() -> None:
    dataframe = _sample_products_df()

    by_revenue = rank_products(dataframe, by=ProductRankingMetric.REVENUE, limit=2)
    assert [row.product_name for row in by_revenue] == ["Notebook Pro", "Monitor 27"]
    assert [row.rank for row in by_revenue] == [1, 2]
    assert by_revenue[0].gross_revenue == Decimal("500.00")
    assert by_revenue[0].net_revenue == Decimal("450.00")
    assert by_revenue[0].order_count == 2
    assert by_revenue[0].revenue_share == Decimal("0.5000")
    assert by_revenue[1].revenue_share == Decimal("0.3000")

    by_quantity = rank_products(dataframe, by="quantidade", limit=None)
    assert [row.product_name for row in by_quantity] == [
        "Mouse Pad",
        "Teclado Mecânico",
        "Notebook Pro",
        "Monitor 27",
    ]
    # Notebook Pro and Monitor 27 tie on quantity=2 -> tie-break by higher gross revenue
    assert by_quantity[0].quantity == 5
    assert by_quantity[0].sku is None
    assert by_quantity[0].revenue_share == Decimal("0.0500")


def test_compute_abc_curve_exact_pareto_boundaries() -> None:
    dataframe = _sample_products_df()

    curve = compute_abc_curve(dataframe)

    # Total valid revenue = 500 + 300 + 150 + 50 = 1000.00
    # Cumulative shares: 0.5000 (A), 0.8000 (A), 0.9500 (B), 1.0000 (C)
    assert [(row.product_name, row.abc_class) for row in curve] == [
        ("Notebook Pro", AbcClass.A),
        ("Monitor 27", AbcClass.A),
        ("Teclado Mecânico", AbcClass.B),
        ("Mouse Pad", AbcClass.C),
    ]
    assert [row.cumulative_share for row in curve] == [
        Decimal("0.5000"),
        Decimal("0.8000"),
        Decimal("0.9500"),
        Decimal("1.0000"),
    ]


def test_compute_abc_curve_single_dominant_product_and_zero_revenue_exclusion() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "order_id": "ORD-1",
                "order_date": pd.Timestamp("2025-01-01 10:00:00", tz=_TZ),
                "status": OrderStatus.COMPLETED.value,
                "product_name": "Produto Líder",
                "sku": "L1",
                "quantity": 1,
                "gross_revenue": 90_000,
            },
            {
                "order_id": "ORD-2",
                "order_date": pd.Timestamp("2025-01-02 10:00:00", tz=_TZ),
                "status": OrderStatus.COMPLETED.value,
                "product_name": "Brinde",
                "sku": "B0",
                "quantity": 2,
                "gross_revenue": 0,
            },
            {
                "order_id": "ORD-3",
                "order_date": pd.Timestamp("2025-01-03 10:00:00", tz=_TZ),
                "status": OrderStatus.COMPLETED.value,
                "product_name": "Acessório",
                "sku": "A1",
                "quantity": 1,
                "gross_revenue": 10_000,
            },
        ]
    )

    curve = compute_abc_curve(dataframe)
    # Brinde (0 revenue) is excluded; rank 1 with 90% remains Class A
    assert [(row.product_name, row.abc_class) for row in curve] == [
        ("Produto Líder", AbcClass.A),
        ("Acessório", AbcClass.C),
    ]


def test_product_analytics_empty_and_invalid_arguments() -> None:
    dataframe = _sample_products_df()
    assert rank_products(dataframe.iloc[0:0]) == []
    assert compute_abc_curve(dataframe.iloc[0:0]) == []

    with pytest.raises(ValueError, match="maior que zero"):
        rank_products(dataframe, limit=0)

    with pytest.raises(ValueError, match="Métrica de ranking inválida"):
        rank_products(dataframe, by="lucro")
