"""Adapter scoring, header similarity matching, and format detection."""

from analisador.validation.detection import (
    HeaderMatchResult,
    classify_match_status,
    detect_best_adapter,
    match_adapter_headers,
    score_adapters,
)

__all__ = [
    "HeaderMatchResult",
    "classify_match_status",
    "detect_best_adapter",
    "match_adapter_headers",
    "score_adapters",
]
