"""Data quality metrics, IQR outlier detection, and QualityReport assembly."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from analisador.core.config import (
    IQR_LOWER_QUANTILE,
    IQR_OUTLIER_MULTIPLIER,
    IQR_UPPER_QUANTILE,
    MIN_OUTLIER_SAMPLE_SIZE,
)
from analisador.core.enums import CanonicalField
from analisador.core.models import QualityReport


@dataclass(frozen=True, slots=True)
class QualityDiagnostics:
    """Diagnostic issue counters gathered during normalization."""

    total_rows: int
    valid_rows: int
    duplicate_rows: int
    invalid_dates: int
    non_positive_quantities: int
    malformed_quantities: int
    negative_values: int
    outlier_rows: int
    null_counts: Mapping[str, int]
    malformed_monetary: Mapping[str, int]


def count_iqr_outliers(values: pd.Series[Any]) -> int:
    """Count rows outside [Q1 - k*IQR, Q3 + k*IQR] for a numeric Series."""
    valid = values.dropna().astype("float64")
    if len(valid) < MIN_OUTLIER_SAMPLE_SIZE:
        return 0
    q1 = float(valid.quantile(IQR_LOWER_QUANTILE))
    q3 = float(valid.quantile(IQR_UPPER_QUANTILE))
    iqr = q3 - q1
    if iqr <= 0.0:
        return 0
    lower = q1 - IQR_OUTLIER_MULTIPLIER * iqr
    upper = q3 + IQR_OUTLIER_MULTIPLIER * iqr
    outlier_mask = (valid < lower) | (valid > upper)
    return int(outlier_mask.sum())


def count_duplicate_rows(
    canonical_df: pd.DataFrame,
    *,
    has_mapped_order_id: bool,
) -> int:
    """Count exact duplicate canonical rows (excluding synthetic order IDs)."""
    if canonical_df.empty:
        return 0
    subset_fields = [
        CanonicalField.ORDER_DATE,
        CanonicalField.PRODUCT_NAME,
        CanonicalField.SKU,
        CanonicalField.QUANTITY,
        CanonicalField.GROSS_REVENUE,
        CanonicalField.STATUS,
    ]
    if has_mapped_order_id:
        subset_fields.insert(0, CanonicalField.ORDER_ID)
    subset = [field.value for field in subset_fields if field.value in canonical_df]
    return int(canonical_df.duplicated(subset=subset).sum())


def _append_count_warnings(
    warnings: list[str],
    counters: tuple[tuple[int, str], ...],
) -> None:
    for count, message in counters:
        if count > 0:
            warnings.append(message)


def _core_warning_pairs(diagnostics: QualityDiagnostics) -> tuple[tuple[int, str], ...]:
    ignored = diagnostics.total_rows - diagnostics.valid_rows
    return (
        (ignored, f"{ignored} linha(s) ignorada(s) por campos obrigatórios inválidos."),
        (
            diagnostics.invalid_dates,
            f"{diagnostics.invalid_dates} data(s) inválida(s).",
        ),
        (
            diagnostics.non_positive_quantities,
            f"{diagnostics.non_positive_quantities} linha(s) com quantidade <= 0.",
        ),
        (
            diagnostics.malformed_quantities,
            f"{diagnostics.malformed_quantities} quantidade(s) não inteira(s).",
        ),
        (
            diagnostics.negative_values,
            f"{diagnostics.negative_values} linha(s) com preço ou receita negativos.",
        ),
        (
            diagnostics.duplicate_rows,
            f"{diagnostics.duplicate_rows} linha(s) duplicada(s) detectada(s).",
        ),
        (
            diagnostics.outlier_rows,
            f"{diagnostics.outlier_rows} valor(es) discrepante(s) por IQR.",
        ),
    )


def build_quality_warnings(diagnostics: QualityDiagnostics) -> tuple[str, ...]:
    """Build user-facing Portuguese quality warnings without exposing cell data."""
    warnings: list[str] = []
    _append_count_warnings(warnings, _core_warning_pairs(diagnostics))
    for field_name, count in diagnostics.malformed_monetary.items():
        if count > 0:
            warnings.append(
                f"{count} valor(es) monetário(s) inválido(s) ignorado(s) "
                f"na coluna '{field_name}'."
            )
    return tuple(warnings)


def build_quality_report(diagnostics: QualityDiagnostics) -> QualityReport:
    """Assemble an immutable QualityReport from normalization diagnostics."""
    ignored_rows = diagnostics.total_rows - diagnostics.valid_rows
    warnings = build_quality_warnings(diagnostics)
    filtered_nulls = {
        col: count for col, count in diagnostics.null_counts.items() if count > 0
    }
    return QualityReport(
        total_rows=diagnostics.total_rows,
        valid_rows=diagnostics.valid_rows,
        ignored_rows=ignored_rows,
        duplicate_rows=diagnostics.duplicate_rows,
        invalid_dates=diagnostics.invalid_dates,
        non_positive_quantities=diagnostics.non_positive_quantities,
        negative_values=diagnostics.negative_values,
        outlier_rows=diagnostics.outlier_rows,
        null_counts=filtered_nulls,
        warnings=warnings,
    )


__all__ = [
    "QualityDiagnostics",
    "build_quality_report",
    "build_quality_warnings",
    "count_duplicate_rows",
    "count_iqr_outliers",
]
