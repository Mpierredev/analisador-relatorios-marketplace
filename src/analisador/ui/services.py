"""In-memory UI pipeline orchestration, error translation, and bounded caching."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

from analisador.analytics import (
    AbcCurveRow,
    PeriodComparison,
    ProductRankingMetric,
    ProductRankingRow,
    StatusDistributionRow,
    TimeGranularity,
    TimeSeriesPoint,
    build_time_series,
    compare_periods,
    compute_abc_curve,
    compute_kpis,
    compute_status_distribution,
    filter_by_period,
    rank_products,
)
from analisador.core.config import (
    CACHE_MAX_ENTRIES,
    CACHE_TTL_SECONDS,
    DEFAULT_TOP_PRODUCTS_LIMIT,
)
from analisador.core.enums import CanonicalField
from analisador.core.errors import ReportError
from analisador.core.models import KpiSummary, ValidationReport
from analisador.ingestion import read_report
from analisador.normalization import NormalizationResult, normalize_report
from analisador.validation import ensure_can_generate_dashboard, validate_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UiError:
    """User-safe error payload with Portuguese title, message, and guidance."""

    title: str
    message: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class DashboardBundle:
    """Cached analytics outputs rendered on the dashboard view."""

    kpis: KpiSummary
    comparison: PeriodComparison | None
    time_series: list[TimeSeriesPoint]
    top_products: list[ProductRankingRow]
    abc_curve: list[AbcCurveRow]
    status_distribution: list[StatusDistributionRow]


def translate_exception(exc: Exception) -> UiError:
    """Convert any exception into a user-safe message without leaking tracebacks."""
    if isinstance(exc, ReportError):
        return UiError(
            title="Não foi possível concluir o processamento",
            message=exc.message,
            suggestion=exc.suggestion,
        )
    exc_type = type(exc)
    logger.warning(
        "Unexpected UI failure: %s.%s", exc_type.__module__, exc_type.__name__
    )
    return UiError(
        title="Ocorreu um erro inesperado ao processar os dados",
        message=(
            "Não foi possível concluir a operação solicitada com os parâmetros atuais."
        ),
        suggestion=(
            "Verifique o arquivo selecionado, limpe os filtros ou tente novamente "
            "com outra planilha."
        ),
    )


def process_uploaded_file(
    content: bytes,
    filename: str,
    selected_format: str,
) -> tuple[pd.DataFrame, ValidationReport]:
    """Read raw report bytes in memory and run initial structural validation."""
    raw_df = read_report(content, filename)
    validation = validate_report(raw_df, selected_format)
    return raw_df, validation


def revalidate_dataframe(
    raw_df: pd.DataFrame,
    selected_format: str,
    manual_mapping: Mapping[CanonicalField, str] | None = None,
) -> ValidationReport:
    """Re-run structural validation using a format key or manual mapping."""
    return validate_report(
        raw_df,
        selected_format,
        manual_mapping=manual_mapping,
    )


def generate_normalized_result(
    raw_df: pd.DataFrame,
    validation_report: ValidationReport,
) -> NormalizationResult:
    """Verify validation gate and normalize raw_df into the canonical schema."""
    ensure_can_generate_dashboard(validation_report)
    return normalize_report(raw_df, validation_report)


def _apply_status_and_product_filters(
    canonical_df: pd.DataFrame,
    selected_statuses: tuple[str, ...],
    product_query: str,
) -> pd.DataFrame:
    filtered = canonical_df
    if selected_statuses:
        status_series = (
            filtered[CanonicalField.STATUS.value].astype("string").str.strip()
        )
        filtered = filtered.loc[status_series.isin(selected_statuses)]
    cleaned_query = product_query.strip()
    if cleaned_query:
        product_series = filtered[CanonicalField.PRODUCT_NAME.value].astype("string")
        filtered = filtered.loc[
            product_series.str.contains(
                cleaned_query, case=False, na=False, regex=False
            )
        ]
    return filtered


def _safe_period_comparison(
    entity_df: pd.DataFrame,
    start_date: date | None,
    end_date: date | None,
) -> PeriodComparison | None:
    try:
        return compare_periods(entity_df, start_date=start_date, end_date=end_date)
    except ValueError:
        return None


def _build_dashboard_bundle(
    entity_df: pd.DataFrame,
    start_date: date | None,
    end_date: date | None,
    granularity: str,
    ranking_metric: str,
) -> DashboardBundle:
    scoped_df = filter_by_period(entity_df, start_date, end_date)
    return DashboardBundle(
        kpis=compute_kpis(scoped_df, start_date=start_date, end_date=end_date),
        comparison=_safe_period_comparison(entity_df, start_date, end_date),
        time_series=build_time_series(
            scoped_df,
            TimeGranularity(granularity),
            start_date=start_date,
            end_date=end_date,
        ),
        top_products=rank_products(
            scoped_df,
            by=ProductRankingMetric(ranking_metric),
            limit=DEFAULT_TOP_PRODUCTS_LIMIT,
        ),
        abc_curve=compute_abc_curve(scoped_df),
        status_distribution=compute_status_distribution(scoped_df),
    )


@st.cache_data(
    max_entries=CACHE_MAX_ENTRIES,
    ttl=CACHE_TTL_SECONDS,
    show_spinner=False,
)
def compute_dashboard_bundle_cached(
    canonical_df: pd.DataFrame,
    start_date: date | None,
    end_date: date | None,
    selected_statuses: tuple[str, ...],
    product_query: str,
    granularity: str,
    ranking_metric: str,
) -> DashboardBundle:
    """Compute bounded-cache dashboard metrics over canonical (non-PII) records."""
    entity_df = _apply_status_and_product_filters(
        canonical_df,
        selected_statuses,
        product_query,
    )
    return _build_dashboard_bundle(
        entity_df, start_date, end_date, granularity, ranking_metric
    )


__all__ = [
    "DashboardBundle",
    "UiError",
    "compute_dashboard_bundle_cached",
    "generate_normalized_result",
    "process_uploaded_file",
    "revalidate_dataframe",
    "translate_exception",
]
