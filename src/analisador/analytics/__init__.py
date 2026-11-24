"""UI-independent sales analytics library over canonical DataFrames."""

from __future__ import annotations

from analisador.analytics.comparison import (
    MetricDelta,
    PeriodComparison,
    compare_periods,
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
    "MetricDelta",
    "PeriodComparison",
    "ProductRankingMetric",
    "ProductRankingRow",
    "StatusDistributionRow",
    "TimeGranularity",
    "TimeSeriesPoint",
    "build_time_series",
    "cents_to_brl_decimal",
    "compare_periods",
    "compute_abc_curve",
    "compute_kpis",
    "compute_status_distribution",
    "count_unique_orders",
    "filter_by_period",
    "filter_sales",
    "rank_products",
    "validate_canonical_dataframe",
]
