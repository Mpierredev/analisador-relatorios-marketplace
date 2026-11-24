"""Altair chart builders for time series, product ranking, status, and ABC curve."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import altair as alt
import pandas as pd

from analisador.analytics import (
    AbcCurveRow,
    ProductRankingMetric,
    ProductRankingRow,
    StatusDistributionRow,
    TimeSeriesPoint,
)
from analisador.ui.formatting import STATUS_LABELS


def build_timeseries_chart(points: Sequence[TimeSeriesPoint]) -> alt.Chart:
    """Build an interactive Altair line chart of gross revenue over time."""
    records = [
        {
            "Periodo": pd.Timestamp(point.period_start),
            "Faturamento (R$)": float(point.gross_revenue),
            "Pedidos": point.order_count,
            "Itens": point.item_count,
        }
        for point in points
    ]
    frame = pd.DataFrame(records)
    chart = (
        alt.Chart(frame)
        .mark_line(point=True, color="#1D4ED8")
        .encode(
            x=alt.X("Periodo:T", title="Período"),
            y=alt.Y("Faturamento (R$):Q", title="Faturamento bruto (R$)"),
            tooltip=["Periodo:T", "Faturamento (R$):Q", "Pedidos:Q", "Itens:Q"],
        )
        .properties(height=320)
    )
    return cast(alt.Chart, chart)


def build_top_products_chart(
    rows: Sequence[ProductRankingRow],
    metric: ProductRankingMetric,
) -> alt.Chart:
    """Build a horizontal bar chart ranking products by revenue or quantity."""
    value_field = (
        "Faturamento (R$)" if metric is ProductRankingMetric.REVENUE else "Quantidade"
    )
    records = [
        {
            "Produto": row.product_name,
            "Faturamento (R$)": float(row.gross_revenue),
            "Quantidade": row.quantity,
            "Pedidos": row.order_count,
        }
        for row in rows
    ]
    frame = pd.DataFrame(records)
    chart = (
        alt.Chart(frame)
        .mark_bar(color="#2563EB")
        .encode(
            x=alt.X(f"{value_field}:Q", title=value_field),
            y=alt.Y("Produto:N", sort="-x", title="Produto"),
            tooltip=["Produto:N", "Faturamento (R$):Q", "Quantidade:Q", "Pedidos:Q"],
        )
        .properties(height=320)
    )
    return cast(alt.Chart, chart)


def build_status_chart(rows: Sequence[StatusDistributionRow]) -> alt.Chart:
    """Build a bar chart showing order counts grouped by canonical status."""
    records = [
        {
            "Status": STATUS_LABELS.get(row.status, row.status.value),
            "Pedidos": row.order_count,
            "Participação (%)": round(row.order_share * 100, 1),
            "Faturamento (R$)": float(row.gross_revenue),
        }
        for row in rows
    ]
    frame = pd.DataFrame(records)
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X("Status:N", sort="-y", title="Status"),
            y=alt.Y("Pedidos:Q", title="Pedidos"),
            color=alt.Color("Status:N", legend=None),
            tooltip=[
                "Status:N",
                "Pedidos:Q",
                "Participação (%):Q",
                "Faturamento (R$):Q",
            ],
        )
        .properties(height=300)
    )
    return cast(alt.Chart, chart)


_ABC_COLOR_SCALE = alt.Scale(
    domain=["Classe A", "Classe B", "Classe C"],
    range=["#1D4ED8", "#0EA5E9", "#64748B"],
)


def build_abc_chart(rows: Sequence[AbcCurveRow]) -> alt.Chart:
    """Build a bar chart colored and labeled by Pareto ABC class."""
    frame = pd.DataFrame(
        [
            {
                "Produto": row.product_name,
                "Faturamento (R$)": float(row.gross_revenue),
                "Acumulado (%)": round(float(row.cumulative_share) * 100, 1),
                "Classe ABC": f"Classe {row.abc_class.value}",
            }
            for row in rows
        ]
    )
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X("Produto:N", sort="-y", title="Produto"),
            y=alt.Y("Faturamento (R$):Q", title="Faturamento bruto (R$)"),
            color=alt.Color("Classe ABC:N", scale=_ABC_COLOR_SCALE),
            tooltip=[
                "Produto:N",
                "Classe ABC:N",
                "Faturamento (R$):Q",
                "Acumulado (%):Q",
            ],
        )
        .properties(height=320)
    )
    return cast(alt.Chart, chart)


__all__ = [
    "build_abc_chart",
    "build_status_chart",
    "build_timeseries_chart",
    "build_top_products_chart",
]
