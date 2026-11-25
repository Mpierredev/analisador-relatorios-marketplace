"""Interactive date, status, product, granularity, and metric filter controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from analisador.analytics import ProductRankingMetric, TimeGranularity
from analisador.core.enums import CanonicalField, OrderStatus
from analisador.ui.formatting import (
    GRANULARITY_LABELS,
    RANKING_METRIC_LABELS,
    STATUS_LABELS,
)


@dataclass(frozen=True, slots=True)
class DashboardFilters:
    """Selected filter state driving dashboard queries."""

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
        else (fallback_start, fallback_end)
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


def render_dashboard_filters(canonical_df: pd.DataFrame) -> DashboardFilters:
    """Render top dashboard filter controls and return active selections."""
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
    return DashboardFilters(
        start_bound, end_bound, chosen, query, granularity, ranking_metric
    )


__all__ = ["DashboardFilters", "render_dashboard_filters"]
