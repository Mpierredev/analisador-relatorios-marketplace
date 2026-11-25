"""In-memory multi-sheet Excel summary workbook exporter."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
from openpyxl import Workbook

from analisador.analytics import (
    TimeGranularity,
    analyze_product_diagnostics,
    build_time_series,
    compute_abc_curve,
    compute_financial_breakdown,
    compute_kpis,
    compute_status_distribution,
    compute_weekday_sales,
    rank_products,
    validate_canonical_dataframe,
)
from analisador.core.config import DEFAULT_TOP_PRODUCTS_LIMIT
from analisador.core.enums import NetRevenueSource
from analisador.core.models import QualityReport
from analisador.export.excel_diagnostics import write_diagnostics_sheet
from analisador.export.excel_sheets import (
    write_abc_sheet,
    write_kpi_sheet,
    write_products_sheet,
    write_status_and_quality_sheet,
    write_timeseries_sheet,
)


def _write_core_sheets(
    workbook: Workbook,
    canonical_df: pd.DataFrame,
    net_revenue_source: NetRevenueSource,
    start_date: date | None,
    end_date: date | None,
) -> None:
    kpis = compute_kpis(canonical_df, start_date=start_date, end_date=end_date)
    series = build_time_series(
        canonical_df, TimeGranularity.DAILY, start_date=start_date, end_date=end_date
    )
    top = rank_products(
        canonical_df,
        limit=DEFAULT_TOP_PRODUCTS_LIMIT,
        start_date=start_date,
        end_date=end_date,
    )
    abc = compute_abc_curve(canonical_df, start_date=start_date, end_date=end_date)
    write_kpi_sheet(workbook, kpis, net_revenue_source)
    write_timeseries_sheet(workbook, series)
    write_products_sheet(workbook, top)
    write_abc_sheet(workbook, abc)


def _populate_workbook(
    workbook: Workbook,
    canonical_df: pd.DataFrame,
    quality_report: QualityReport | None,
    net_revenue_source: NetRevenueSource,
    start_date: date | None,
    end_date: date | None,
) -> None:
    _write_core_sheets(workbook, canonical_df, net_revenue_source, start_date, end_date)
    statuses = compute_status_distribution(
        canonical_df, start_date=start_date, end_date=end_date
    )
    write_status_and_quality_sheet(workbook, statuses, quality_report)
    breakdown = compute_financial_breakdown(
        canonical_df, start_date=start_date, end_date=end_date
    )
    diagnostics = analyze_product_diagnostics(
        canonical_df, start_date=start_date, end_date=end_date
    )
    weekdays = compute_weekday_sales(
        canonical_df, start_date=start_date, end_date=end_date
    )
    write_diagnostics_sheet(workbook, breakdown, diagnostics, weekdays)


def export_summary_excel(
    canonical_df: pd.DataFrame,
    *,
    quality_report: QualityReport | None = None,
    net_revenue_source: NetRevenueSource = NetRevenueSource.UNAVAILABLE,
    start_date: date | None = None,
    end_date: date | None = None,
) -> bytes:
    """Build an in-memory multi-sheet Excel summary workbook from canonical data."""
    validate_canonical_dataframe(canonical_df)
    workbook = Workbook()
    _populate_workbook(
        workbook,
        canonical_df,
        quality_report,
        net_revenue_source,
        start_date,
        end_date,
    )
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


__all__ = ["export_summary_excel"]
