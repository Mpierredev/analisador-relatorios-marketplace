"""Altair chart builders for financial breakdown and temporal demand patterns."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final, cast

import altair as alt
import pandas as pd

from analisador.analytics import (
    FinancialBreakdown,
    HourlySalesRow,
    WeekdaySalesRow,
)
from analisador.ui.formatting import format_brl, format_percent

_FINANCIAL_COLORS: Final[dict[str, str]] = {
    "Faturamento bruto": "#1D4ED8",
    "Taxas e comissões": "#D97706",
    "Custos de envio": "#0284C7",
    "Receita líquida": "#16A34A",
    "Cancelado + devolvido": "#DC2626",
}


def _financial_entries(
    breakdown: FinancialBreakdown,
) -> list[tuple[str, Decimal, Decimal | None]]:
    losses = breakdown.cancelled_revenue + breakdown.returned_revenue
    gross = breakdown.gross_revenue
    zero = Decimal("0")
    return [
        ("Faturamento bruto", gross, Decimal("1") if gross > 0 else None),
        ("Taxas e comissões", breakdown.fees_total or zero, breakdown.fees_pct),
        ("Custos de envio", breakdown.shipping_total or zero, breakdown.shipping_pct),
        ("Receita líquida", breakdown.net_revenue or zero, breakdown.net_margin_pct),
        ("Cancelado + devolvido", losses, None),
    ]


def _build_financial_records(
    breakdown: FinancialBreakdown,
) -> tuple[list[dict[str, float | str]], list[str]]:
    visible: list[dict[str, float | str]] = []
    labels: list[str] = []
    for label, amount, pct in _financial_entries(breakdown):
        if amount > 0 or label in ("Faturamento bruto", "Receita líquida"):
            labels.append(label)
            visible.append(
                {
                    "Componente": label,
                    "Valor (R$)": float(amount),
                    "Valor": format_brl(amount),
                    "Percentual": format_percent(pct),
                }
            )
    return visible, labels


def build_financial_composition_chart(breakdown: FinancialBreakdown) -> alt.Chart:
    """Build a horizontal bar chart summarizing revenue, deductions, and losses."""
    visible, labels = _build_financial_records(breakdown)
    scale = alt.Scale(
        domain=labels, range=[_FINANCIAL_COLORS[label] for label in labels]
    )
    chart = (
        alt.Chart(pd.DataFrame(visible))
        .mark_bar()
        .encode(
            x=alt.X("Valor (R$):Q", title="Valor (R$)"),
            y=alt.Y("Componente:N", sort=labels, title="Componente"),
            color=alt.Color("Componente:N", scale=scale, legend=None),
            tooltip=["Componente:N", "Valor:N", "Percentual:N"],
        )
        .properties(height=250)
    )
    return cast(alt.Chart, chart)


def _build_time_bucket_chart(
    records: list[dict[str, float | int | str]],
    bucket_col: str,
    bucket_title: str,
    sort_order: list[str],
    color: str,
) -> alt.Chart:
    tips = [
        f"{bucket_col}:N",
        "Pedidos:Q",
        "Itens:Q",
        "Faturamento:N",
        "Participação (%):Q",
    ]
    chart = (
        alt.Chart(pd.DataFrame(records))
        .mark_bar(color=color)
        .encode(
            x=alt.X(f"{bucket_col}:N", sort=sort_order, title=bucket_title),
            y=alt.Y("Faturamento (R$):Q", title="Faturamento bruto (R$)"),
            tooltip=tips,
        )
        .properties(height=280)
    )
    return cast(alt.Chart, chart)


def build_weekday_chart(rows: Sequence[WeekdaySalesRow]) -> alt.Chart:
    """Build a Mon-Sun bar chart of gross revenue by day of the week."""
    order = [row.weekday_label for row in rows]
    records: list[dict[str, float | int | str]] = [
        {
            "Dia": row.weekday_label,
            "Faturamento (R$)": float(row.gross_revenue),
            "Faturamento": format_brl(row.gross_revenue),
            "Pedidos": row.order_count,
            "Itens": row.item_count,
            "Participação (%)": round(float(row.revenue_share) * 100, 1),
        }
        for row in rows
    ]
    return _build_time_bucket_chart(records, "Dia", "Dia da semana", order, "#1D4ED8")


def build_hourly_chart(rows: Sequence[HourlySalesRow]) -> alt.Chart:
    """Build a 24-hour bar chart of gross revenue by hour of day."""
    order = [row.hour_label for row in rows]
    records: list[dict[str, float | int | str]] = [
        {
            "Horário": row.hour_label,
            "Faturamento (R$)": float(row.gross_revenue),
            "Faturamento": format_brl(row.gross_revenue),
            "Pedidos": row.order_count,
            "Itens": row.item_count,
            "Participação (%)": round(float(row.revenue_share) * 100, 1),
        }
        for row in rows
    ]
    return _build_time_bucket_chart(records, "Horário", "Hora do dia", order, "#0284C7")


__all__ = [
    "build_financial_composition_chart",
    "build_hourly_chart",
    "build_weekday_chart",
]
