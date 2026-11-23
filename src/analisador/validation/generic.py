"""Validation logic for user-supplied generic column mappings."""

from collections.abc import Mapping, Sequence

import pandas as pd

from analisador.adapters.base import MarketplaceAdapter
from analisador.adapters.registry import list_adapters
from analisador.core.enums import CanonicalField, Marketplace, ValidationStatus
from analisador.core.models import AdapterScore, ValidationReport
from analisador.core.schema import (
    ALWAYS_REQUIRED_INPUT_FIELDS,
    CANONICAL_SCHEMA,
    missing_required_input_fields,
)
from analisador.validation.detection import score_adapters


def _inspect_manual_mapping(
    headers: Sequence[str],
    column_mapping: Mapping[CanonicalField, str],
) -> tuple[dict[CanonicalField, str], list[str], list[str]]:
    header_set = set(headers)
    valid_mapping: dict[CanonicalField, str] = {}
    seen_columns: dict[str, CanonicalField] = {}
    errors: list[str] = []
    notes: list[str] = []

    for canonical_field, column_name in column_mapping.items():
        if canonical_field is CanonicalField.MARKETPLACE:
            notes.append(
                "O campo marketplace é definido automaticamente e foi ignorado "
                "no mapeamento manual."
            )
            continue
        if not column_name.strip() or column_name not in header_set:
            errors.append(f"Coluna mapeada não encontrada no arquivo: '{column_name}'.")
            continue
        if column_name in seen_columns:
            errors.append(
                f"A coluna '{column_name}' foi associada a mais de um campo; "
                "escolha colunas distintas."
            )
            continue
        seen_columns[column_name] = canonical_field
        valid_mapping[canonical_field] = column_name
    return valid_mapping, errors, notes


def _append_valid_generic_warnings(
    warnings: list[str],
    valid_mapping: Mapping[CanonicalField, str],
    *,
    used_unit_price: bool,
) -> None:
    if used_unit_price:
        warnings.append(
            "Coluna de receita bruta ausente; o valor será calculado por "
            "quantidade x preço unitário."
        )
    if (
        CanonicalField.FEES not in valid_mapping
        and CanonicalField.NET_REVENUE not in valid_mapping
    ):
        warnings.append(
            "Nenhuma coluna de taxas ou valor líquido foi mapeada; os indicadores "
            "de receita líquida ficarão indisponíveis."
        )


def _build_generic_warnings(
    dataframe: pd.DataFrame,
    valid_mapping: Mapping[CanonicalField, str],
    missing_required: tuple[CanonicalField, ...],
    invalid_errors: Sequence[str],
    notes: Sequence[str],
    *,
    used_unit_price: bool,
) -> tuple[str, ...]:
    warnings = [*invalid_errors, *notes]
    if dataframe.empty:
        warnings.append(
            "O arquivo contém apenas cabeçalho, sem linhas de vendas para analisar."
        )
    if missing_required:
        names = ", ".join(field.value for field in missing_required)
        warnings.append(f"Campos obrigatórios pendentes no mapeamento manual: {names}.")
    if not (dataframe.empty or missing_required or invalid_errors):
        _append_valid_generic_warnings(
            warnings, valid_mapping, used_unit_price=used_unit_price
        )
    return tuple(warnings)


def _classify_generic_status(
    dataframe: pd.DataFrame,
    missing_required: tuple[CanonicalField, ...],
    invalid_errors: Sequence[str],
    warnings: Sequence[str],
) -> ValidationStatus:
    if dataframe.empty or missing_required or invalid_errors:
        return ValidationStatus.UNRECOGNIZED
    if warnings:
        return ValidationStatus.RECOGNIZED_WITH_WARNINGS
    return ValidationStatus.RECOGNIZED


def _partition_generic_fields(
    valid_map: Mapping[CanonicalField, str],
) -> tuple[tuple[CanonicalField, ...], tuple[CanonicalField, ...], bool]:
    used_unit = (
        CanonicalField.GROSS_REVENUE not in valid_map
        and CanonicalField.UNIT_PRICE in valid_map
    )
    req_set = set(ALWAYS_REQUIRED_INPUT_FIELDS)
    req_set.add(
        CanonicalField.UNIT_PRICE if used_unit else CanonicalField.GROSS_REVENUE
    )
    found_req = tuple(
        s.field for s in CANONICAL_SCHEMA if s.field in req_set & valid_map.keys()
    )
    found_opt = tuple(
        s.field
        for s in CANONICAL_SCHEMA
        if s.field in valid_map and s.field not in req_set
    )
    return found_req, found_opt, used_unit


def _analyze_generic_inputs(
    headers: Sequence[str],
    column_mapping: Mapping[CanonicalField, str],
    adapters: Sequence[MarketplaceAdapter] | None,
) -> tuple[
    tuple[AdapterScore, ...],
    dict[CanonicalField, str],
    list[str],
    list[str],
    tuple[CanonicalField, ...],
]:
    candidates = list_adapters() if adapters is None else tuple(adapters)
    scores = tuple(
        item.to_adapter_score() for item in score_adapters(headers, candidates)
    )
    valid_map, errors, notes = _inspect_manual_mapping(headers, column_mapping)
    missing = missing_required_input_fields(valid_map.keys())
    return scores, valid_map, errors, notes, missing


def validate_generic_mapping(
    dataframe: pd.DataFrame,
    column_mapping: Mapping[CanonicalField, str],
    *,
    adapters: Sequence[MarketplaceAdapter] | None = None,
) -> ValidationReport:
    """Validate a raw DataFrame against a user-supplied generic column mapping."""
    headers = [str(col) for col in dataframe.columns]
    scores, valid_map, errors, notes, missing = _analyze_generic_inputs(
        headers, column_mapping, adapters
    )
    found_req, found_opt, used_unit = _partition_generic_fields(valid_map)
    extra_cols = tuple(c for c in headers if c not in set(valid_map.values()))
    warnings = _build_generic_warnings(
        dataframe, valid_map, missing, errors, notes, used_unit_price=used_unit
    )
    status = _classify_generic_status(dataframe, missing, errors, warnings)
    missing_out = missing if status is ValidationStatus.UNRECOGNIZED else ()
    return ValidationReport(
        Marketplace.GENERIC,
        status,
        round((4 - len(missing)) / 4, 4),
        valid_map,
        found_req,
        missing_out,
        found_opt,
        extra_cols,
        warnings,
        adapter_scores=scores,
    )


__all__ = ["validate_generic_mapping"]
