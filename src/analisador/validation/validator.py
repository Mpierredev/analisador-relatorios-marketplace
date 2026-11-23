"""Report validation against marketplace adapters or manual mappings."""

from collections.abc import Mapping, Sequence

import pandas as pd

from analisador.adapters.base import MarketplaceAdapter
from analisador.adapters.registry import get_adapter, list_adapters
from analisador.core.config import HIGH_CONFIDENCE_THRESHOLD
from analisador.core.enums import CanonicalField, Marketplace, ValidationStatus
from analisador.core.errors import MissingRequiredColumnsError, ReportError
from analisador.core.models import AdapterScore, ValidationReport
from analisador.validation.detection import (
    HeaderMatchResult,
    match_adapter_headers,
    score_adapters,
)
from analisador.validation.generic import validate_generic_mapping


def _find_suggested_adapter(
    selected_adapter: MarketplaceAdapter,
    selected_match: HeaderMatchResult,
    ranked: Sequence[HeaderMatchResult],
    candidates: Sequence[MarketplaceAdapter],
) -> tuple[str | None, str | None]:
    by_key = {item.key: item for item in candidates}
    for match in ranked:
        if match.adapter_key == selected_adapter.key:
            continue
        candidate = by_key[match.adapter_key]
        if (
            not match.missing_required
            and match.score > selected_match.score
            and match.score >= candidate.min_score
        ):
            warning = (
                f"O arquivo parece compatível com o formato {candidate.display_name} "
                f"(pontuação {match.score:.0%})."
            )
            return candidate.key, warning
    return None, None


def _append_mapping_detail_warnings(
    warnings: list[str],
    match: HeaderMatchResult,
    status: ValidationStatus,
) -> None:
    if match.fuzzy_matches:
        pairs = ", ".join(
            f"{field.value} <- '{col}'" for field, col in match.fuzzy_matches.items()
        )
        warnings.append(f"Colunas reconhecidas por similaridade de nome: {pairs}.")
    if match.conflicting_columns:
        conflicts = ", ".join(match.conflicting_columns)
        warnings.append(
            f"Colunas típicas de outro marketplace detectadas: {conflicts}."
        )
    if (
        status is not ValidationStatus.UNRECOGNIZED
        and CanonicalField.FEES not in match.column_mapping
        and CanonicalField.NET_REVENUE not in match.column_mapping
    ):
        warnings.append(
            "Nenhuma coluna de taxas ou valor líquido foi mapeada; os indicadores "
            "de receita líquida ficarão indisponíveis."
        )


def _build_adapter_warnings(
    dataframe: pd.DataFrame,
    adapter: MarketplaceAdapter,
    match: HeaderMatchResult,
    missing_required: tuple[CanonicalField, ...],
    *,
    used_unit_price: bool,
    status: ValidationStatus,
    suggestion_warning: str | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if dataframe.empty:
        warnings.append(
            "O arquivo contém apenas cabeçalho, sem linhas de vendas para analisar."
        )
    if missing_required:
        names = ", ".join(field.value for field in missing_required)
        warnings.append(
            f"Colunas obrigatórias ausentes para {adapter.display_name}: {names}."
        )
    if suggestion_warning is not None:
        warnings.append(suggestion_warning)
    if used_unit_price:
        warnings.append(
            "Coluna de receita bruta ausente; o valor será calculado por "
            "quantidade x preço unitário."
        )
    _append_mapping_detail_warnings(warnings, match, status)
    return tuple(warnings)


def _classify_adapter_status(
    dataframe: pd.DataFrame,
    adapter: MarketplaceAdapter,
    match: HeaderMatchResult,
    missing_required: tuple[CanonicalField, ...],
    *,
    used_unit_price: bool,
) -> ValidationStatus:
    if dataframe.empty or missing_required or match.score < adapter.min_score:
        return ValidationStatus.UNRECOGNIZED
    if (
        used_unit_price
        or match.fuzzy_matches
        or match.conflicting_columns
        or match.score < HIGH_CONFIDENCE_THRESHOLD
    ):
        return ValidationStatus.RECOGNIZED_WITH_WARNINGS
    return ValidationStatus.RECOGNIZED


def _resolve_adapter_fields(
    match: HeaderMatchResult,
) -> tuple[
    tuple[CanonicalField, ...],
    tuple[CanonicalField, ...],
    tuple[CanonicalField, ...],
    bool,
]:
    used_unit_price = (
        match.missing_required == (CanonicalField.GROSS_REVENUE,)
        and CanonicalField.UNIT_PRICE in match.column_mapping
    )
    found_req: tuple[CanonicalField, ...]
    found_opt: tuple[CanonicalField, ...]
    if used_unit_price:
        missing: tuple[CanonicalField, ...] = ()
        found_req = (*match.matched_required, CanonicalField.UNIT_PRICE)
        found_opt = tuple(
            f for f in match.matched_optional if f is not CanonicalField.UNIT_PRICE
        )
    else:
        missing = match.missing_required
        found_req = match.matched_required
        found_opt = match.matched_optional
    return found_req, missing, found_opt, used_unit_price


def _analyze_adapter_headers(
    dataframe: pd.DataFrame,
    adapter: MarketplaceAdapter,
    adapters: Sequence[MarketplaceAdapter] | None,
) -> tuple[tuple[AdapterScore, ...], HeaderMatchResult, str | None, str | None]:
    headers = [str(col) for col in dataframe.columns]
    candidates = list_adapters() if adapters is None else tuple(adapters)
    ranked = score_adapters(headers, candidates)
    scores = tuple(item.to_adapter_score() for item in ranked)
    selected = next(
        (item for item in ranked if item.adapter_key == adapter.key),
        match_adapter_headers(headers, adapter, other_adapters=candidates),
    )
    suggested, suggestion_warning = _find_suggested_adapter(
        adapter, selected, ranked, candidates
    )
    return scores, selected, suggested, suggestion_warning


def _build_adapter_outcome(
    dataframe: pd.DataFrame,
    adapter: MarketplaceAdapter,
    match: HeaderMatchResult,
    suggestion_warning: str | None,
) -> tuple[
    tuple[CanonicalField, ...],
    tuple[CanonicalField, ...],
    tuple[CanonicalField, ...],
    ValidationStatus,
    tuple[str, ...],
]:
    found_req, missing, found_opt, used_unit = _resolve_adapter_fields(match)
    status = _classify_adapter_status(
        dataframe, adapter, match, missing, used_unit_price=used_unit
    )
    warnings = _build_adapter_warnings(
        dataframe,
        adapter,
        match,
        missing,
        used_unit_price=used_unit,
        status=status,
        suggestion_warning=suggestion_warning,
    )
    return found_req, missing, found_opt, status, warnings


def validate_with_adapter(
    dataframe: pd.DataFrame,
    adapter: MarketplaceAdapter,
    *,
    adapters: Sequence[MarketplaceAdapter] | None = None,
) -> ValidationReport:
    """Validate a raw DataFrame against a specific marketplace adapter."""
    scores, match, suggested, sug_warn = _analyze_adapter_headers(
        dataframe, adapter, adapters
    )
    found_req, missing, found_opt, status, warnings = _build_adapter_outcome(
        dataframe, adapter, match, sug_warn
    )
    return ValidationReport(
        adapter.key,
        status,
        match.score,
        match.column_mapping,
        found_req,
        missing,
        found_opt,
        match.extra_columns,
        warnings,
        suggested,
        scores,
    )


def validate_report(
    dataframe: pd.DataFrame,
    selected_format: str,
    *,
    manual_mapping: Mapping[CanonicalField, str] | None = None,
    adapters: Sequence[MarketplaceAdapter] | None = None,
) -> ValidationReport:
    """Validate a raw DataFrame using a marketplace adapter or generic mapping."""
    normalized = selected_format.strip().lower()
    if normalized == Marketplace.GENERIC:
        return validate_generic_mapping(
            dataframe, manual_mapping or {}, adapters=adapters
        )

    candidates = list_adapters() if adapters is None else tuple(adapters)
    adapter = next((item for item in candidates if item.key == normalized), None)
    if adapter is None:
        try:
            adapter = get_adapter(normalized)
        except KeyError as exc:
            raise ValueError(f"Unknown report format: {selected_format!r}") from exc
    return validate_with_adapter(dataframe, adapter, adapters=candidates)


def ensure_can_generate_dashboard(report: ValidationReport) -> None:
    """Raise a typed ReportError when validation does not allow dashboard creation."""
    if report.can_generate_dashboard:
        return
    if report.missing_required:
        raise MissingRequiredColumnsError(
            tuple(field.value for field in report.missing_required)
        )
    message = (
        report.warnings[0]
        if report.warnings
        else "A validação do relatório não foi aprovada para gerar o dashboard."
    )
    raise ReportError(
        message,
        suggestion=(
            "Revise os avisos da validação ou ajuste o mapeamento de colunas "
            "antes de gerar o dashboard."
        ),
    )


__all__ = [
    "ensure_can_generate_dashboard",
    "validate_generic_mapping",
    "validate_report",
    "validate_with_adapter",
]
