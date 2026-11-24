"""Canonical normalization pipeline from validated raw DataFrames."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from analisador.adapters.base import MarketplaceAdapter
from analisador.adapters.registry import get_adapter, has_adapter
from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import CanonicalField, DecimalStyle
from analisador.core.errors import MissingRequiredColumnsError, NormalizationError
from analisador.core.models import QualityReport, ValidationReport
from analisador.core.schema import CANONICAL_COLUMNS
from analisador.normalization.dates import DateParseResult, parse_date_series
from analisador.normalization.fields import (
    MonetaryFieldsResult,
    QuantityParseResult,
    generate_synthetic_order_ids,
    normalize_monetary_fields,
    normalize_optional_code_series,
    normalize_quantity_series,
    normalize_status_series,
    normalize_text_series,
)
from analisador.normalization.quality import (
    QualityDiagnostics,
    build_quality_report,
    count_duplicate_rows,
    count_iqr_outliers,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Canonical sales DataFrame paired with data quality diagnostics."""

    dataframe: pd.DataFrame
    quality_report: QualityReport
    date_parse_result: DateParseResult


@dataclass(frozen=True, slots=True)
class _NormalizedColumns:
    date_result: DateParseResult
    product: tuple[pd.Series[Any], int]
    qty_result: QuantityParseResult
    status: tuple[pd.Series[Any], int]
    order_id: tuple[pd.Series[Any], int]
    sku: tuple[pd.Series[Any], int]
    monetary: MonetaryFieldsResult


def _resolve_adapter(
    validation_report: ValidationReport,
    adapter: MarketplaceAdapter | None,
) -> MarketplaceAdapter | None:
    if adapter is not None:
        return adapter
    if has_adapter(validation_report.selected_adapter):
        return get_adapter(validation_report.selected_adapter)
    return None


def _validate_inputs(
    raw_df: pd.DataFrame,
    validation_report: ValidationReport,
) -> None:
    if not validation_report.can_generate_dashboard:
        if validation_report.missing_required:
            raise MissingRequiredColumnsError(
                tuple(field.value for field in validation_report.missing_required)
            )
        raise NormalizationError(
            "O relatório precisa ser validado antes da normalização.",
            suggestion="Corrija os avisos de validação ou ajuste o mapeamento.",
        )
    if raw_df.empty:
        raise NormalizationError(
            "O relatório não possui linhas de dados para normalizar.",
            suggestion="Envie um arquivo com ao menos uma linha de venda válida.",
        )


def _project_mapped_columns(
    raw_df: pd.DataFrame,
    column_mapping: Mapping[CanonicalField, str],
) -> dict[CanonicalField, pd.Series[Any]]:
    projected: dict[CanonicalField, pd.Series[Any]] = {}
    available = {str(col) for col in raw_df.columns}
    for canonical_field, source_name in column_mapping.items():
        if source_name not in available:
            raise NormalizationError(
                f"Coluna mapeada ausente na planilha: {source_name}.",
                suggestion="Refaça o mapeamento de colunas antes de normalizar.",
            )
        selected = raw_df[source_name]
        projected[canonical_field] = (
            selected.iloc[:, 0] if isinstance(selected, pd.DataFrame) else selected
        )
    return projected


def _resolve_code_field(
    series: pd.Series[Any] | None,
    index: pd.Index[Any],
    fill_synthetic: bool,
) -> tuple[pd.Series[Any], int]:
    if series is None:
        if fill_synthetic:
            return generate_synthetic_order_ids(len(index), index), 0
        return pd.Series(pd.NA, index=index, dtype="string"), 0
    normalized, blanks = normalize_optional_code_series(series)
    if fill_synthetic and blanks > 0:
        synthetic = generate_synthetic_order_ids(len(index), index)
        return normalized.fillna(synthetic), blanks
    return normalized, blanks


def _normalize_projected_columns(
    projected: Mapping[CanonicalField, pd.Series[Any]],
    raw_index: pd.Index[Any],
    adapter: MarketplaceAdapter | None,
    dayfirst: bool,
    timezone: str,
) -> _NormalizedColumns:
    date_formats = adapter.date_formats if adapter is not None else ()
    dec_style = adapter.decimal_style if adapter is not None else DecimalStyle.AUTO
    status_map = adapter.status_map if adapter is not None else None
    qty_res = normalize_quantity_series(projected[CanonicalField.QUANTITY])
    date_res = parse_date_series(
        projected[CanonicalField.ORDER_DATE],
        dayfirst=dayfirst,
        timezone=timezone,
        date_formats=date_formats,
    )
    prod = normalize_text_series(projected[CanonicalField.PRODUCT_NAME])
    st = normalize_status_series(
        projected.get(CanonicalField.STATUS), raw_index, status_map=status_map
    )
    oid = _resolve_code_field(projected.get(CanonicalField.ORDER_ID), raw_index, True)
    sku = _resolve_code_field(projected.get(CanonicalField.SKU), raw_index, False)
    mon = normalize_monetary_fields(
        projected, qty_res.series, raw_index, decimal_style=dec_style
    )
    return _NormalizedColumns(date_res, prod, qty_res, st, oid, sku, mon)


def _compute_valid_mask(normalized: _NormalizedColumns) -> pd.Series[Any]:
    return (
        normalized.date_result.series.notna()
        & normalized.product[0].notna()
        & normalized.qty_result.series.notna()
        & normalized.monetary.gross_revenue.notna()
    )


def _ensure_valid_rows(valid_mask: pd.Series[Any], total_rows: int) -> None:
    valid_rows = int(valid_mask.sum())
    logger.info(
        "Normalized report: total_rows=%d valid_rows=%d ignored_rows=%d",
        total_rows,
        valid_rows,
        total_rows - valid_rows,
    )
    if valid_rows == 0:
        raise NormalizationError(
            "Nenhuma linha válida restou após a normalização dos dados.",
            suggestion="Verifique datas, quantidades e valores monetários.",
        )


def _assemble_canonical_dataframe(
    normalized: _NormalizedColumns,
    marketplace_key: str,
    valid_mask: pd.Series[Any],
) -> pd.DataFrame:
    index = normalized.date_result.series.index[valid_mask]
    mon = normalized.monetary
    raw_map: dict[str, pd.Series[Any]] = {
        CanonicalField.ORDER_ID.value: normalized.order_id[0].loc[valid_mask],
        CanonicalField.ORDER_DATE.value: normalized.date_result.series.loc[valid_mask],
        CanonicalField.STATUS.value: normalized.status[0].loc[valid_mask],
        CanonicalField.PRODUCT_NAME.value: normalized.product[0].loc[valid_mask],
        CanonicalField.SKU.value: normalized.sku[0].loc[valid_mask],
        CanonicalField.QUANTITY.value: (
            normalized.qty_result.series.loc[valid_mask].astype("int64")
        ),
        CanonicalField.UNIT_PRICE.value: mon.unit_price.loc[valid_mask],
        CanonicalField.GROSS_REVENUE.value: mon.gross_revenue.loc[valid_mask].astype(
            "int64"
        ),
        CanonicalField.FEES.value: mon.fees.loc[valid_mask],
        CanonicalField.SHIPPING_COST.value: mon.shipping_cost.loc[valid_mask],
        CanonicalField.NET_REVENUE.value: mon.net_revenue.loc[valid_mask],
        CanonicalField.MARKETPLACE.value: pd.Series(
            [marketplace_key] * len(index), index=index, dtype="category"
        ),
    }
    ordered_cols = [field.value for field in CANONICAL_COLUMNS]
    return pd.DataFrame(raw_map, index=index)[ordered_cols].reset_index(drop=True)


def _collect_null_counts(
    projected: Mapping[CanonicalField, pd.Series[Any]],
    normalized: _NormalizedColumns,
) -> dict[str, int]:
    nulls: dict[str, int] = dict(normalized.monetary.null_counts)
    candidates = (
        (CanonicalField.ORDER_ID, normalized.order_id[1]),
        (CanonicalField.ORDER_DATE, normalized.date_result.empty_count),
        (CanonicalField.STATUS, normalized.status[1]),
        (CanonicalField.PRODUCT_NAME, normalized.product[1]),
        (CanonicalField.SKU, normalized.sku[1]),
        (CanonicalField.QUANTITY, normalized.qty_result.empty_count),
    )
    for field, count in candidates:
        if field in projected and count > 0:
            nulls[field.value] = count
    return nulls


def _build_diagnostics(
    total_rows: int,
    canonical_df: pd.DataFrame,
    projected: Mapping[CanonicalField, pd.Series[Any]],
    normalized: _NormalizedColumns,
) -> QualityReport:
    gross_col = canonical_df[CanonicalField.GROSS_REVENUE.value]
    diagnostics = QualityDiagnostics(
        total_rows=total_rows,
        valid_rows=len(canonical_df),
        duplicate_rows=count_duplicate_rows(
            canonical_df, has_mapped_order_id=CanonicalField.ORDER_ID in projected
        ),
        invalid_dates=normalized.date_result.invalid_count,
        non_positive_quantities=normalized.qty_result.non_positive_count,
        malformed_quantities=normalized.qty_result.malformed_count,
        negative_values=normalized.monetary.negative_value_rows,
        outlier_rows=count_iqr_outliers(gross_col),
        null_counts=_collect_null_counts(projected, normalized),
        malformed_monetary=normalized.monetary.malformed_counts,
    )
    return build_quality_report(diagnostics)


def normalize_report(
    raw_df: pd.DataFrame,
    validation_report: ValidationReport,
    *,
    adapter: MarketplaceAdapter | None = None,
    dayfirst: bool = True,
    timezone: str = DEFAULT_TIMEZONE,
) -> NormalizationResult:
    """Normalize a validated raw DataFrame into the canonical sales schema."""
    _validate_inputs(raw_df, validation_report)
    projected = _project_mapped_columns(raw_df, validation_report.column_mapping)
    resolved_adapter = _resolve_adapter(validation_report, adapter)
    normalized = _normalize_projected_columns(
        projected, raw_df.index, resolved_adapter, dayfirst, timezone
    )
    valid_mask = _compute_valid_mask(normalized)
    _ensure_valid_rows(valid_mask, len(raw_df))
    canonical_df = _assemble_canonical_dataframe(
        normalized, validation_report.selected_adapter, valid_mask
    )
    quality_report = _build_diagnostics(
        len(raw_df), canonical_df, projected, normalized
    )
    return NormalizationResult(canonical_df, quality_report, normalized.date_result)


__all__ = [
    "NormalizationResult",
    "normalize_report",
]
