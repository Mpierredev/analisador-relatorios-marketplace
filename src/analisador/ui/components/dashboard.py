"""Interactive sales dashboard with quality diagnostics, filters, KPIs, and charts."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from analisador.analytics import PeriodComparison, ProductRankingMetric
from analisador.core.enums import NetRevenueSource
from analisador.normalization import NormalizationResult
from analisador.ui.components.charts import (
    build_abc_chart,
    build_status_chart,
    build_timeseries_chart,
    build_top_products_chart,
)
from analisador.ui.components.dashboard_diagnostics import (
    render_financial_and_timing_tab,
    render_product_diagnostics_section,
)
from analisador.ui.components.errors import render_quality_summary, render_ui_error
from analisador.ui.components.exports import render_export_section
from analisador.ui.components.filters import render_dashboard_filters
from analisador.ui.formatting import (
    NET_REVENUE_SOURCE_HELP,
    format_brl,
    format_int_br,
    format_metric_delta,
    format_percent,
)
from analisador.ui.services import (
    DashboardBundle,
    compute_dashboard_bundle_cached,
    translate_exception,
)
from analisador.ui.state import (
    STATE_DASHBOARD_ENABLED,
    STATE_NORMALIZED_RESULT,
    build_dashboard_cache_key,
)


def _active_comparison(bundle: DashboardBundle) -> PeriodComparison | None:
    cmp = bundle.comparison
    if cmp is None or cmp.previous.order_count <= 0:
        return None
    return cmp


def _render_primary_kpis(
    bundle: DashboardBundle,
    cmp: PeriodComparison | None,
) -> None:
    kpis = bundle.kpis
    row1 = st.columns(3)
    row1[0].metric(
        "Faturamento bruto",
        format_brl(kpis.gross_revenue),
        delta=format_metric_delta(cmp.gross_revenue, kind="brl") if cmp else None,
    )
    row1[1].metric(
        "Pedidos",
        format_int_br(kpis.order_count),
        delta=format_metric_delta(cmp.order_count, kind="int") if cmp else None,
    )
    row1[2].metric(
        "Itens vendidos",
        format_int_br(kpis.item_count),
        delta=format_metric_delta(cmp.item_count, kind="int") if cmp else None,
    )


def _render_secondary_kpis(
    bundle: DashboardBundle,
    net_source: NetRevenueSource,
    cmp: PeriodComparison | None,
) -> None:
    kpis = bundle.kpis
    row2 = st.columns(3)
    row2[0].metric(
        "Ticket médio",
        format_brl(kpis.average_ticket),
        delta=format_metric_delta(cmp.average_ticket, kind="brl") if cmp else None,
    )
    row2[1].metric(
        "Taxa de cancelamento",
        format_percent(kpis.cancellation_rate),
        delta=format_metric_delta(cmp.cancellation_rate, kind="pct") if cmp else None,
        delta_color="inverse",
    )
    row2[2].metric(
        "Receita líquida",
        format_brl(kpis.net_revenue),
        delta=format_metric_delta(cmp.net_revenue, kind="brl") if cmp else None,
        help=NET_REVENUE_SOURCE_HELP[net_source],
    )
    if cmp is None:
        st.caption(
            "Ajuste o filtro de período para comparar com o intervalo "
            "anterior equivalente."
        )


def _render_abc_section(bundle: DashboardBundle) -> None:
    st.markdown("#### Curva ABC de produtos")
    if not bundle.abc_curve:
        st.info("Sem faturamento positivo suficiente para calcular a Curva ABC.")
        return
    st.altair_chart(build_abc_chart(bundle.abc_curve[:20]), width="stretch")
    abc_table = pd.DataFrame(
        [
            {
                "Posição": row.rank,
                "Produto": row.product_name,
                "SKU": row.sku or "—",
                "Quantidade": row.quantity,
                "Faturamento": format_brl(row.gross_revenue),
                "Participação": format_percent(row.revenue_share),
                "Acumulado": format_percent(row.cumulative_share),
                "Classe": row.abc_class.value,
            }
            for row in bundle.abc_curve
        ]
    )
    st.dataframe(abc_table, width="stretch", hide_index=True)


def _render_overview_tab(
    bundle: DashboardBundle,
    net_source: NetRevenueSource,
) -> None:
    cmp = _active_comparison(bundle)
    _render_primary_kpis(bundle, cmp)
    _render_secondary_kpis(bundle, net_source, cmp)
    col_ts, col_status = st.columns([3, 2])
    with col_ts:
        st.markdown("#### Evolução de vendas")
        if bundle.time_series:
            st.altair_chart(build_timeseries_chart(bundle.time_series), width="stretch")
        else:
            st.info(
                "Sem vendas ativas para exibir na série temporal com os filtros atuais."
            )
    with col_status:
        st.markdown("#### Distribuição de status")
        if bundle.status_distribution:
            st.altair_chart(
                build_status_chart(bundle.status_distribution), width="stretch"
            )
        else:
            st.info("Sem pedidos para distribuição de status no recorte atual.")


def _render_products_tab(
    bundle: DashboardBundle,
    ranking_metric: ProductRankingMetric,
) -> None:
    st.markdown("#### Top produtos")
    if bundle.top_products:
        st.altair_chart(
            build_top_products_chart(bundle.top_products, ranking_metric),
            width="stretch",
        )
    else:
        st.info("Nenhum produto encontrado para o recorte atual.")
    _render_abc_section(bundle)
    render_product_diagnostics_section(bundle)


def _render_dashboard_tabs(
    bundle: DashboardBundle,
    result: NormalizationResult,
    ranking_metric: ProductRankingMetric,
    date_bounds: tuple[date | None, date | None],
) -> None:
    tabs = st.tabs(
        [
            "Visão geral",
            "Financeiro e horários",
            "Produtos e Curva ABC",
            "Qualidade e exportação",
        ]
    )
    with tabs[0]:
        _render_overview_tab(bundle, result.net_revenue_source)
    with tabs[1]:
        render_financial_and_timing_tab(bundle, result.net_revenue_source)
    with tabs[2]:
        _render_products_tab(bundle, ranking_metric)
    with tabs[3]:
        render_quality_summary(result.quality_report)
        render_export_section(
            result, start_date=date_bounds[0], end_date=date_bounds[1]
        )


def _render_filtered_dashboard(result: NormalizationResult) -> None:
    filters = render_dashboard_filters(result.dataframe)
    try:
        bundle = compute_dashboard_bundle_cached(
            result.dataframe,
            build_dashboard_cache_key(),
            filters.start_date,
            filters.end_date,
            filters.statuses,
            filters.product_query,
            filters.granularity.value,
            filters.ranking_metric.value,
        )
    except Exception as exc:
        render_ui_error(translate_exception(exc))
        return
    _render_dashboard_tabs(
        bundle, result, filters.ranking_metric, (filters.start_date, filters.end_date)
    )


def render_dashboard_section() -> None:
    """Render interactive filters, tabbed KPIs, charts, quality, and exports."""
    if not st.session_state.get(STATE_DASHBOARD_ENABLED, False):
        return
    result = st.session_state.get(STATE_NORMALIZED_RESULT)
    if not isinstance(result, NormalizationResult):
        return
    st.subheader("Painel de vendas")
    if result.dataframe.empty:
        st.warning("Nenhuma linha válida restou após a normalização.")
        return
    _render_filtered_dashboard(result)


__all__ = ["render_dashboard_section"]
