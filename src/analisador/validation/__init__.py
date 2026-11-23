"""Adapter scoring, type inference, mapping suggestions, and structural validation."""

from analisador.validation.detection import (
    HeaderMatchResult,
    classify_match_status,
    detect_best_adapter,
    match_adapter_headers,
    score_adapters,
)
from analisador.validation.suggestions import (
    InferredColumnType,
    infer_column_type,
    infer_dataframe_types,
    suggest_column_mapping,
)
from analisador.validation.validator import (
    ensure_can_generate_dashboard,
    validate_generic_mapping,
    validate_report,
    validate_with_adapter,
)

__all__ = [
    "HeaderMatchResult",
    "InferredColumnType",
    "classify_match_status",
    "detect_best_adapter",
    "ensure_can_generate_dashboard",
    "infer_column_type",
    "infer_dataframe_types",
    "match_adapter_headers",
    "score_adapters",
    "suggest_column_mapping",
    "validate_generic_mapping",
    "validate_report",
    "validate_with_adapter",
]
