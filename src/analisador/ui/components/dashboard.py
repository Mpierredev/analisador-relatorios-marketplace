"""Interactive sales dashboard with quality diagnostics, filters, KPIs, and charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from analisador.analytics import ProductRankingMetric, TimeGranularity
from analisador.core.enums import CanonicalField, NetRevenueSource, OrderStatus
from analisador.normalization import NormalizationResult
from analisador.ui.components.charts import (
    build_abc_chart,
    build_status_chart,
    build_timeseries_chart,
    build_top_products_chart,
)
from analisador.ui.components.errors import render_quality_summary, render_ui_error
from analisador.ui.components.exports import render_export_section
from analisador.ui.formatting import (
    GRANULARITY_LABELS,
    NET_REVENUE_SOURCE_HELP,
    RANKING_METRIC_LABELS,
    STATUS_LABELS,
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


@dataclass(frozen=True, slots=True)
class _DashboardFilters:
    start_date: date | None
    end_date: date | None
    statuses: tuple[str, ...]
    product_query: str
    granularity: TimeGranularity
    ranking_metric: ProductRankingMetric


def _unpack_date_selection(
    selection: Any,
    fallback_start: date,
    fallback_end: date,
) -> tuple[date, date]:
    if isinstance(selection, tuple | list):
        if len(selection) >= 2:
            return selection[0], selection[1]
        if len(selection) == 1:
            return selection[0], selection[0]
        return fallback_start, fallback_end
    return (
        (selection, selection)
        if isinstance(selection, date)
        else (
            fallback_start,
            fallback_end,
        )
    )


def _render_date_filter(canonical_df: pd.DataFrame) -> tuple[date | None, date | None]:
    valid_dates = pd.to_datetime(
        canonical_df[CanonicalField.ORDER_DATE.value], errors="coerce"
    ).dropna()
    if valid_dates.empty:
        return None, None
    min_d, max_d = valid_dates.min().date(), valid_dates.max().date()
    selected = st.date_input(
        "Período",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        key="dash_date_range",
    )
    return _unpack_date_selection(selected, min_d, max_d)


def _render_status_and_product_filters(
    canonical_df: pd.DataFrame,
) -> tuple[tuple[str, ...], str]:
    col_status, col_prod = st.columns(2)
    statuses = sorted(
        {
            str(val)
            for val in canonical_df[CanonicalField.STATUS.value].dropna().unique()
        }
    )
    chosen = col_status.multiselect(
        "Status dos pedidos",
        options=statuses,
        default=statuses,
        format_func=lambda val: STATUS_LABELS.get(OrderStatus(val), val),
        key="dash_statuses",
    )
    query = col_prod.text_input(
        "Filtrar por produto",
        placeholder="Digite parte do nome do produto...",
        key="dash_product_query",
    )
    return tuple(chosen), query


def _render_filters(canonical_df: pd.DataFrame) -> _DashboardFilters:
    col_period, col_gran, col_metric = st.columns([2, 1, 1])
    with col_period:
        start_bound, end_bound = _render_date_filter(canonical_df)
    granularity = (
        col_gran.selectbox(
            "Granularidade",
            options=list(TimeGranularity),
            format_func=lambda item: GRANULARITY_LABELS[item],
            key="dash_granularity",
        )
        or TimeGranularity.DAILY
    )
    ranking_metric = (
        col_metric.selectbox(
            "Ranking de produtos",
            options=list(ProductRankingMetric),
            format_func=lambda item: RANKING_METRIC_LABELS[item],
            key="dash_ranking_metric",
        )
        or ProductRankingMetric.REVENUE
    )
    chosen, query = _render_status_and_product_filters(canonical_df)
    return _DashboardFilters(
        start_bound, end_bound, chosen, query, granularity, ranking_metric
    )


def _render_primary_kpis(bundle: DashboardBundle) -> None:
    kpis, cmp = bundle.kpis, bundle.comparison
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
) -> None:
    kpis, cmp = bundle.kpis, bundle.comparison
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


def _render_charts_and_tables(
    bundle: DashboardBundle,
    ranking_metric: ProductRankingMetric,
) -> None:
    st.markdown("#### Evolução de vendas")
    if bundle.time_series:
        st.altair_chart(build_timeseries_chart(bundle.time_series), width="stretch")
    else:
        st.info(
            "Sem vendas ativas para exibir na série temporal com os filtros atuais."
        )
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### Top produtos")
        if bundle.top_products:
            st.altair_chart(
                build_top_products_chart(bundle.top_products, ranking_metric),
                width="stretch",
            )
        else:
            st.info("Nenhum produto encontrado para o recorte atual.")
    with col_right:
        st.markdown("#### Distribuição de status")
        if bundle.status_distribution:
            st.altair_chart(
                build_status_chart(bundle.status_distribution), width="stretch"
            )
        else:
            st.info("Sem pedidos para distribuição de status no recorte atual.")
    _render_abc_section(bundle)


def _render_filtered_dashboard(result: NormalizationResult) -> None:
    filters = _render_filters(result.dataframe)
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
    _render_primary_kpis(bundle)
    _render_secondary_kpis(bundle, result.net_revenue_source)
    _render_charts_and_tables(bundle, filters.ranking_metric)
    render_export_section(
        result, start_date=filters.start_date, end_date=filters.end_date
    )


def render_dashboard_section() -> None:
    """Render quality summary, interactive filters, KPIs, charts, and tables."""
    if not st.session_state.get(STATE_DASHBOARD_ENABLED, False):
        return
    result = st.session_state.get(STATE_NORMALIZED_RESULT)
    if not isinstance(result, NormalizationResult):
        return
    st.divider()
    st.subheader("4. Dashboard de vendas")
    render_quality_summary(result.quality_report)
    if result.dataframe.empty:
        st.warning("Nenhuma linha válida restou após a normalização.")
        return
    _render_filtered_dashboard(result)


__all__ = ["render_dashboard_section"]
