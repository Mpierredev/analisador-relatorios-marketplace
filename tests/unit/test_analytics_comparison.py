"""Unit and end-to-end integration tests for period comparison and pipeline."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from analisador.analytics import (
    AbcClass,
    TimeGranularity,
    build_time_series,
    compare_periods,
    compute_abc_curve,
    compute_kpis,
    compute_status_distribution,
    rank_products,
)
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import Marketplace, OrderStatus
from analisador.ingestion import read_report
from analisador.normalization import normalize_report
from analisador.validation import validate_report

_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def _sample_comparison_df() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        # Previous window: Jan 1..Jan 7 -> 2 completed orders (R$ 200.00), 3 items
        {
            "order_id": "ORD-1",
            "order_date": pd.Timestamp("2025-01-01 10:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto A",
            "quantity": 2,
            "gross_revenue": 12_000,
            "net_revenue": 10_000,
        },
        {
            "order_id": "ORD-2",
            "order_date": pd.Timestamp("2025-01-06 16:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto B",
            "quantity": 1,
            "gross_revenue": 8_000,
            "net_revenue": 7_000,
        },
        # Current window: Jan 8..Jan 14 -> 4 orders (3 active=R$ 300.00, 1 cancelled)
        {
            "order_id": "ORD-3",
            "order_date": pd.Timestamp("2025-01-08 09:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto A",
            "quantity": 2,
            "gross_revenue": 15_000,
            "net_revenue": 12_750,
        },
        {
            "order_id": "ORD-4",
            "order_date": pd.Timestamp("2025-01-10 11:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto B",
            "quantity": 1,
            "gross_revenue": 9_000,
            "net_revenue": 7_650,
        },
        {
            "order_id": "ORD-5",
            "order_date": pd.Timestamp("2025-01-12 14:00:00", tz=_TZ),
            "status": OrderStatus.COMPLETED.value,
            "product_name": "Produto C",
            "quantity": 3,
            "gross_revenue": 6_000,
            "net_revenue": 5_100,
        },
        {
            "order_id": "ORD-6",
            "order_date": pd.Timestamp("2025-01-14 20:00:00", tz=_TZ),
            "status": OrderStatus.CANCELLED.value,
            "product_name": "Produto C",
            "quantity": 1,
            "gross_revenue": 5_000,
            "net_revenue": 5_000,
        },
    ]
    df = pd.DataFrame(rows)
    df["net_revenue"] = df["net_revenue"].astype("Int64")
    return df


def test_compare_periods_explicit_contiguous_windows() -> None:
    dataframe = _sample_comparison_df()

    comparison = compare_periods(
        dataframe,
        start_date=date(2025, 1, 8),
        end_date=date(2025, 1, 14),
    )

    assert comparison.previous.gross_revenue == Decimal("200.00")
    assert comparison.previous.order_count == 2
    assert comparison.previous.average_ticket == Decimal("100.00")
    assert comparison.previous.cancellation_rate == 0.0

    assert comparison.current.gross_revenue == Decimal("300.00")
    assert comparison.current.order_count == 4
    assert comparison.current.cancelled_order_count == 1
    assert comparison.current.cancellation_rate == pytest.approx(0.25)

    assert comparison.gross_revenue.absolute_delta == Decimal("100.00")
    assert comparison.gross_revenue.percentage_delta == pytest.approx(0.5)
    assert comparison.order_count.absolute_delta == 2
    assert comparison.order_count.percentage_delta == pytest.approx(1.0)
    assert comparison.item_count.absolute_delta == 3
    assert comparison.average_ticket.absolute_delta == Decimal("0.00")
    assert comparison.average_ticket.percentage_delta == pytest.approx(0.0)
    # Previous cancellation_rate is 0.0 -> percentage_delta must be None
    assert comparison.cancellation_rate.absolute_delta == pytest.approx(0.25)
    assert comparison.cancellation_rate.percentage_delta is None
    assert comparison.net_revenue.absolute_delta == Decimal("85.00")
    assert comparison.net_revenue.percentage_delta == pytest.approx(0.5)


def test_compare_periods_auto_split_and_datetime_windows() -> None:
    dataframe = _sample_comparison_df()

    # Auto split over Jan 1..Jan 14 (14 days -> current Jan 8..14, previous Jan 1..7)
    auto_comparison = compare_periods(dataframe)
    assert auto_comparison.current.gross_revenue == Decimal("300.00")
    assert auto_comparison.previous.gross_revenue == Decimal("200.00")

    dt_comparison = compare_periods(
        dataframe,
        start_date=datetime(2025, 1, 8, 0, 0, tzinfo=_TZ),
        end_date=datetime(2025, 1, 14, 23, 59, 59, 999999, tzinfo=_TZ),
    )
    assert dt_comparison.previous.gross_revenue == Decimal("200.00")
    assert dt_comparison.current.gross_revenue == Decimal("300.00")

    single_day = dataframe.iloc[[0]]
    single_day_cmp = compare_periods(single_day)
    assert single_day_cmp.current.gross_revenue == Decimal("120.00")
    assert single_day_cmp.previous.gross_revenue == Decimal("0.00")
    assert single_day_cmp.gross_revenue.percentage_delta is None


def test_compare_periods_validation_errors() -> None:
    dataframe = _sample_comparison_df()

    with pytest.raises(ValueError, match="ambas as datas"):
        compare_periods(dataframe, start_date=date(2025, 1, 8))

    with pytest.raises(ValueError, match="posterior"):
        compare_periods(
            dataframe,
            start_date=date(2025, 1, 10),
            end_date=date(2025, 1, 8),
        )

    with pytest.raises(ValueError, match="datas válidas"):
        compare_periods(dataframe.iloc[0:0])


def test_end_to_end_mercado_livre_xlsx_to_analytics_pipeline() -> None:
    raw_rows = [
        {
            "N.º de venda": "200001",
            "Data da venda": "01/03/2025 10:00",
            "Estado": "Entregue",
            "Título do anúncio": "Cadeira Gamer",
            "SKU": "CAD-1",
            "Unidades": 2,
            "Receita por produtos": "R$ 800,00",
            "Tarifa de venda e impostos": "R$ 80,00",
            "Custos de envio": "R$ 40,00",
            "Total (BRL)": "R$ 680,00",
        },
        {
            "N.º de venda": "200002",
            "Data da venda": "05/03/2025 14:30",
            "Estado": "Entregue",
            "Título do anúncio": "Mouse Sem Fio",
            "SKU": "MOU-2",
            "Unidades": 2,
            "Receita por produtos": "R$ 200,00",
            "Tarifa de venda e impostos": "R$ 20,00",
            "Custos de envio": "R$ 10,00",
            "Total (BRL)": "R$ 170,00",
        },
        {
            "N.º de venda": "200003",
            "Data da venda": "06/03/2025 18:00",
            "Estado": "Cancelada pelo comprador",
            "Título do anúncio": "Teclado Compacto",
            "SKU": "TEC-3",
            "Unidades": 1,
            "Receita por produtos": "R$ 150,00",
            "Tarifa de venda e impostos": "R$ 0,00",
            "Custos de envio": "R$ 0,00",
            "Total (BRL)": "R$ 150,00",
        },
    ]
    buffer = BytesIO()
    pd.DataFrame(raw_rows).to_excel(buffer, index=False)

    raw_df = read_report(buffer.getvalue(), "vendas_ml.xlsx")
    validation = validate_report(raw_df, Marketplace.MERCADO_LIVRE)
    normalized = normalize_report(raw_df, validation)

    canonical_df = normalized.dataframe
    kpis = compute_kpis(canonical_df)
    series = build_time_series(canonical_df, TimeGranularity.DAILY)
    ranking = rank_products(canonical_df)
    abc = compute_abc_curve(canonical_df)
    distribution = compute_status_distribution(canonical_df)

    assert kpis.gross_revenue == Decimal("1000.00")
    assert kpis.total_fees == Decimal("100.00")
    assert kpis.total_shipping == Decimal("50.00")
    assert kpis.net_revenue == Decimal("850.00")
    assert kpis.order_count == 3
    assert kpis.cancelled_order_count == 1
    assert kpis.cancellation_rate == pytest.approx(1 / 3)
    assert len(series) == 5  # Mar 1 .. Mar 5 (Mar 6 cancelled leaves no active sales)
    assert [row.product_name for row in ranking] == ["Cadeira Gamer", "Mouse Sem Fio"]
    assert [(row.product_name, row.abc_class) for row in abc] == [
        ("Cadeira Gamer", AbcClass.A),
        ("Mouse Sem Fio", AbcClass.C),
    ]
    assert len(distribution) == 2
