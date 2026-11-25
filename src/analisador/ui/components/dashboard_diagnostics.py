"""Financial breakdown, timing patterns, and product diagnostic UI sections."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analisador.analytics import FinancialBreakdown, ProductDiagnosticRow
from analisador.core.enums import NetRevenueSource
from analisador.ui.components.charts_diagnostics import (
    build_financial_composition_chart,
    build_hourly_chart,
    build_weekday_chart,
)
from analisador.ui.formatting import (
    NET_REVENUE_SOURCE_HELP,
    format_brl,
    format_percent,
)
from analisador.ui.services import DashboardBundle

_HIGH_CANCELLATION_THRESHOLD = 0.25


def _render_financial_kpis(
    breakdown: FinancialBreakdown,
    net_source: NetRevenueSource,
) -> None:
    cols = st.columns(4)
    cols[0].metric(
        "Receita líquida",
        format_brl(breakdown.net_revenue),
        help=NET_REVENUE_SOURCE_HELP[net_source],
    )
    cols[0].caption(f"Margem líquida: {format_percent(breakdown.net_margin_pct)}")

    cols[1].metric("Taxas e comissões", format_brl(breakdown.fees_total))
    cols[1].caption(f"Peso no bruto: {format_percent(breakdown.fees_pct)}")

    cols[2].metric("Custos de envio", format_brl(breakdown.shipping_total))
    cols[2].caption(f"Peso no bruto: {format_percent(breakdown.shipping_pct)}")

    losses = breakdown.cancelled_revenue + breakdown.returned_revenue
    cols[3].metric("Perdas (canc. + dev.)", format_brl(losses))
    cols[3].caption(
        f"Canc.: {format_brl(breakdown.cancelled_revenue)} | "
        f"Dev.: {format_brl(breakdown.returned_revenue)}"
    )


def _render_timing_patterns(bundle: DashboardBundle) -> None:
    st.markdown("#### Padrões por dia da semana e horário")
    if not bundle.weekday_sales or not bundle.hourly_sales:
        st.info("Sem vendas válidas no período para exibir distribuição temporal.")
        return
    col_week, col_hour = st.columns(2)
    peak_day = max(bundle.weekday_sales, key=lambda row: row.gross_revenue)
    peak_hour = max(bundle.hourly_sales, key=lambda row: row.gross_revenue)
    with col_week:
        st.altair_chart(build_weekday_chart(bundle.weekday_sales), width="stretch")
        st.caption(
            f"Maior faturamento em {peak_day.weekday_label}: "
            f"{format_brl(peak_day.gross_revenue)} ({peak_day.order_count} pedidos)."
        )
    with col_hour:
        st.altair_chart(build_hourly_chart(bundle.hourly_sales), width="stretch")
        st.caption(
            f"Horário de pico às {peak_hour.hour_label}: "
            f"{format_brl(peak_hour.gross_revenue)} ({peak_hour.order_count} pedidos)."
        )


def render_financial_and_timing_tab(
    bundle: DashboardBundle,
    net_source: NetRevenueSource,
) -> None:
    """Render the financial breakdown and temporal demand patterns tab."""
    st.markdown("#### Raio-X financeiro")
    _render_financial_kpis(bundle.financial, net_source)
    st.altair_chart(
        build_financial_composition_chart(bundle.financial),
        width="stretch",
    )
    _render_timing_patterns(bundle)


def _build_diagnostic_table(rows: list[ProductDiagnosticRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Produto": row.product_name,
                "SKU": row.sku or "—",
                "Pedidos": row.total_orders,
                "Cancelados": row.cancelled_orders,
                "Taxa cancel.": format_percent(row.cancellation_rate),
                "Faturamento": format_brl(row.gross_revenue),
                "Receita líquida": format_brl(row.net_revenue),
                "Margem líq.": format_percent(row.net_margin_pct),
            }
            for row in rows
        ]
    )


def render_product_diagnostics_section(bundle: DashboardBundle) -> None:
    """Render per-product margin and cancellation risk diagnostics."""
    st.markdown("#### Radar de margem e cancelamentos por produto")
    if not bundle.product_diagnostics:
        st.info("Nenhum produto encontrado para diagnóstico no recorte atual.")
        return
    risky = [
        row
        for row in bundle.product_diagnostics
        if row.cancelled_orders > 0
        and row.cancellation_rate >= _HIGH_CANCELLATION_THRESHOLD
    ]
    if risky:
        st.caption(
            f"{len(risky)} produto(s) com taxa de cancelamento igual ou superior a "
            f"25,0% no período (maior incidência: {risky[0].product_name})."
        )
    table = _build_diagnostic_table(bundle.product_diagnostics)
    st.dataframe(table, width="stretch", hide_index=True)


__all__ = [
    "render_financial_and_timing_tab",
    "render_product_diagnostics_section",
]
