"""UI-independent sales analytics library over canonical DataFrames."""

from __future__ import annotations

from analisador.analytics.comparison import (
    MetricDelta,
    PeriodComparison,
    compare_periods,
)
from analisador.analytics.diagnostics import (
    FinancialBreakdown,
    ProductDiagnosticRow,
    analyze_product_diagnostics,
    compute_financial_breakdown,
)
from analisador.analytics.filters import (
    CORE_ANALYTICS_FIELDS,
    DEFAULT_EXCLUDED_STATUSES,
    cents_to_brl_decimal,
    count_unique_orders,
    filter_by_period,
    filter_sales,
    validate_canonical_dataframe,
)
from analisador.analytics.kpis import (
    StatusDistributionRow,
    compute_kpis,
    compute_status_distribution,
)
from analisador.analytics.patterns import (
    HourlySalesRow,
    WeekdaySalesRow,
    compute_hourly_sales,
    compute_weekday_sales,
)
from analisador.analytics.products import (
    AbcClass,
    AbcCurveRow,
    ProductRankingMetric,
    ProductRankingRow,
    compute_abc_curve,
    rank_products,
)
from analisador.analytics.timeseries import (
    TimeGranularity,
    TimeSeriesPoint,
    build_time_series,
)

__all__ = [
    "CORE_ANALYTICS_FIELDS",
    "DEFAULT_EXCLUDED_STATUSES",
    "AbcClass",
    "AbcCurveRow",
    "FinancialBreakdown",
    "HourlySalesRow",
    "MetricDelta",
    "PeriodComparison",
    "ProductDiagnosticRow",
    "ProductRankingMetric",
    "ProductRankingRow",
    "StatusDistributionRow",
    "TimeGranularity",
    "TimeSeriesPoint",
    "WeekdaySalesRow",
    "analyze_product_diagnostics",
    "build_time_series",
    "cents_to_brl_decimal",
    "compare_periods",
    "compute_abc_curve",
    "compute_financial_breakdown",
    "compute_hourly_sales",
    "compute_kpis",
    "compute_status_distribution",
    "compute_weekday_sales",
    "count_unique_orders",
    "filter_by_period",
    "filter_sales",
    "rank_products",
    "validate_canonical_dataframe",
]
