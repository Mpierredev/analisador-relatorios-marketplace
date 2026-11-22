"""Adapter header matching, similarity scoring, and format detection."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from types import MappingProxyType
from typing import Final

from analisador.adapters.base import MarketplaceAdapter, normalize_header
from analisador.adapters.registry import list_adapters
from analisador.core.config import (
    CONFLICT_FIELD_PENALTY,
    HEADER_SIMILARITY_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    MAX_DETECTION_SCORE,
    MAX_RATIO,
    MIN_DETECTION_SCORE,
    MIN_RATIO,
    OPTIONAL_FIELD_WEIGHT,
    REQUIRED_FIELD_WEIGHT,
)
from analisador.core.enums import CanonicalField, ValidationStatus
from analisador.core.models import AdapterScore

_SCORE_PRECISION: Final[int] = 4

type IndexedHeader = tuple[int, str, str]
type AliasMap = Mapping[CanonicalField, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class HeaderMatchResult:
    """Detailed outcome of comparing report headers against an adapter."""

    adapter_key: str
    score: float
    column_mapping: Mapping[CanonicalField, str]
    matched_required: tuple[CanonicalField, ...]
    missing_required: tuple[CanonicalField, ...]
    matched_optional: tuple[CanonicalField, ...]
    extra_columns: tuple[str, ...]
    conflicting_columns: tuple[str, ...]
    fuzzy_matches: Mapping[CanonicalField, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen_mapping = MappingProxyType(dict(self.column_mapping))
        frozen_fuzzy = MappingProxyType(dict(self.fuzzy_matches))
        object.__setattr__(self, "column_mapping", frozen_mapping)
        object.__setattr__(self, "fuzzy_matches", frozen_fuzzy)

    def to_adapter_score(self) -> AdapterScore:
        """Convert detailed match into the compact core AdapterScore model."""
        return AdapterScore(
            self.adapter_key, self.score, self.matched_required, self.matched_optional
        )


def _validate_similarity_threshold(threshold: float) -> None:
    valid = not isinstance(threshold, bool) and math.isfinite(threshold)
    if not valid or not (MIN_RATIO <= threshold <= MAX_RATIO):
        raise ValueError(
            f"similarity_threshold must be between {MIN_RATIO} and {MAX_RATIO}."
        )


def _match_exact_group(
    alias_map: AliasMap,
    indexed_headers: Sequence[IndexedHeader],
    used_indices: set[int],
    mapping: dict[CanonicalField, str],
) -> None:
    for canonical_field, aliases in alias_map.items():
        for alias in aliases:
            match = next(
                (
                    (idx, raw)
                    for idx, raw, norm in indexed_headers
                    if idx not in used_indices and norm == alias
                ),
                None,
            )
            if match is not None:
                idx, raw = match
                mapping[canonical_field] = raw
                used_indices.add(idx)
                break


def _collect_fuzzy_candidates(
    unmatched_fields: Sequence[tuple[int, CanonicalField, tuple[str, ...], bool]],
    indexed_headers: Sequence[IndexedHeader],
    used_indices: set[int],
    similarity_threshold: float,
) -> list[tuple[float, int, int, int, CanonicalField, str]]:
    candidates: list[tuple[float, int, int, int, CanonicalField, str]] = []
    for order, canonical_field, aliases, is_req in unmatched_fields:
        for idx, raw, norm in indexed_headers:
            if idx in used_indices or not norm:
                continue
            ratio = max(SequenceMatcher(None, norm, alias).ratio() for alias in aliases)
            if ratio >= similarity_threshold:
                candidates.append(
                    (ratio, int(is_req), -order, -idx, canonical_field, raw)
                )
    return sorted(candidates, reverse=True)


def _apply_fuzzy_matches(
    required_aliases: AliasMap,
    optional_aliases: AliasMap,
    indexed_headers: Sequence[IndexedHeader],
    used_indices: set[int],
    mapping: dict[CanonicalField, str],
    similarity_threshold: float,
) -> dict[CanonicalField, str]:
    ordered = [
        *((f, aliases, True) for f, aliases in required_aliases.items()),
        *((f, aliases, False) for f, aliases in optional_aliases.items()),
    ]
    unmatched = [
        (order, f, aliases, is_req)
        for order, (f, aliases, is_req) in enumerate(ordered)
        if f not in mapping
    ]
    candidates = _collect_fuzzy_candidates(
        unmatched, indexed_headers, used_indices, similarity_threshold
    )
    fuzzy_matches: dict[CanonicalField, str] = {}
    for _, _, _, neg_idx, canonical_field, raw in candidates:
        idx = -neg_idx
        if canonical_field in mapping or idx in used_indices:
            continue
        mapping[canonical_field] = raw
        fuzzy_matches[canonical_field] = raw
        used_indices.add(idx)
    return fuzzy_matches


def _collect_unmatched_columns(
    adapter: MarketplaceAdapter,
    other_adapters: Sequence[MarketplaceAdapter],
    indexed_headers: Sequence[IndexedHeader],
    used_indices: set[int],
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    other_aliases = {
        alias
        for candidate in other_adapters
        if candidate.key != adapter.key
        for alias in candidate.all_normalized_aliases()
    }
    exclusive = other_aliases - adapter.all_normalized_aliases()
    unused = [
        (raw, norm)
        for idx, raw, norm in indexed_headers
        if idx not in used_indices and norm
    ]
    extra = tuple(raw for raw, _ in unused)
    conflicts = tuple(raw for raw, norm in unused if norm in exclusive)
    non_empty = sum(1 for _, _, norm in indexed_headers if norm)
    return extra, conflicts, non_empty


def _compute_score(
    matched_required: int,
    total_required: int,
    matched_optional: int,
    total_optional: int,
    conflicts: int,
    non_empty_headers: int,
) -> float:
    req_ratio = matched_required / total_required
    opt_ratio = matched_optional / total_optional if total_optional > 0 else 0.0
    conflict_ratio = conflicts / non_empty_headers if non_empty_headers > 0 else 0.0
    raw = (
        req_ratio * REQUIRED_FIELD_WEIGHT
        + opt_ratio * OPTIONAL_FIELD_WEIGHT
        - conflict_ratio * CONFLICT_FIELD_PENALTY
    )
    clamped = min(MAX_DETECTION_SCORE, max(MIN_DETECTION_SCORE, raw))
    return round(clamped, _SCORE_PRECISION)


def _build_match_result(
    adapter: MarketplaceAdapter,
    other_adapters: Sequence[MarketplaceAdapter],
    indexed_headers: Sequence[IndexedHeader],
    used_indices: set[int],
    mapping: Mapping[CanonicalField, str],
    fuzzy: Mapping[CanonicalField, str],
) -> HeaderMatchResult:
    req, opt = adapter.required_fields, adapter.optional_fields
    m_req = tuple(f for f in req if f in mapping)
    miss_req = tuple(f for f in req if f not in mapping)
    m_opt = tuple(f for f in opt if f in mapping)
    extra, conflicts, n_headers = _collect_unmatched_columns(
        adapter, other_adapters, indexed_headers, used_indices
    )
    score = _compute_score(
        len(m_req), len(req), len(m_opt), len(opt), len(conflicts), n_headers
    )
    return HeaderMatchResult(
        adapter.key, score, mapping, m_req, miss_req, m_opt, extra, conflicts, fuzzy
    )


def match_adapter_headers(
    headers: Sequence[str],
    adapter: MarketplaceAdapter,
    *,
    other_adapters: Sequence[MarketplaceAdapter] = (),
    similarity_threshold: float = HEADER_SIMILARITY_THRESHOLD,
) -> HeaderMatchResult:
    """Match spreadsheet headers against an adapter and compute compatibility score."""
    _validate_similarity_threshold(similarity_threshold)
    indexed = [(idx, raw, normalize_header(raw)) for idx, raw in enumerate(headers)]
    req_aliases = adapter.normalized_required_aliases()
    opt_aliases = adapter.normalized_optional_aliases()
    used_indices: set[int] = set()
    mapping: dict[CanonicalField, str] = {}
    _match_exact_group(req_aliases, indexed, used_indices, mapping)
    _match_exact_group(opt_aliases, indexed, used_indices, mapping)
    fuzzy = _apply_fuzzy_matches(
        req_aliases, opt_aliases, indexed, used_indices, mapping, similarity_threshold
    )
    return _build_match_result(
        adapter, other_adapters, indexed, used_indices, mapping, fuzzy
    )


def score_adapters(
    headers: Sequence[str],
    adapters: Sequence[MarketplaceAdapter] | None = None,
) -> tuple[HeaderMatchResult, ...]:
    """Score headers against all adapters ordered from most to least likely."""
    candidates = list_adapters() if adapters is None else tuple(adapters)
    results = [
        match_adapter_headers(headers, adapter, other_adapters=candidates)
        for adapter in candidates
    ]
    results.sort(
        key=lambda r: (
            -r.score,
            -len(r.matched_required),
            len(r.conflicting_columns),
            r.adapter_key,
        )
    )
    return tuple(results)


def detect_best_adapter(
    headers: Sequence[str],
    adapters: Sequence[MarketplaceAdapter] | None = None,
) -> HeaderMatchResult | None:
    """Return the highest-scoring adapter meeting its minimum threshold."""
    candidates = list_adapters() if adapters is None else tuple(adapters)
    if not candidates:
        return None
    best = score_adapters(headers, candidates)[0]
    by_key = {adapter.key: adapter for adapter in candidates}
    return best if best.score >= by_key[best.adapter_key].min_score else None


def classify_match_status(
    match: HeaderMatchResult,
    adapter: MarketplaceAdapter,
) -> ValidationStatus:
    """Classify structural compatibility from a HeaderMatchResult."""
    if match.missing_required or match.score < adapter.min_score:
        return ValidationStatus.UNRECOGNIZED
    if (
        match.score >= HIGH_CONFIDENCE_THRESHOLD
        and not match.fuzzy_matches
        and not match.conflicting_columns
    ):
        return ValidationStatus.RECOGNIZED
    return ValidationStatus.RECOGNIZED_WITH_WARNINGS


__all__ = [
    "HeaderMatchResult",
    "classify_match_status",
    "detect_best_adapter",
    "match_adapter_headers",
    "score_adapters",
]
