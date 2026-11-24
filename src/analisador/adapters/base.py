"""Declarative marketplace adapter contract and header normalization."""

import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Final

from analisador.core.config import (
    MAX_DETECTION_SCORE,
    MEDIUM_CONFIDENCE_THRESHOLD,
    MIN_DETECTION_SCORE,
)
from analisador.core.enums import (
    AdapterSupportTier,
    CanonicalField,
    DecimalStyle,
    OrderStatus,
)

_NON_ALNUM_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


def normalize_header(header: str) -> str:
    """Normalize a column header by stripping accents, punctuation, and extra spaces."""
    decomposed = unicodedata.normalize("NFKD", header)
    ascii_lower = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    ).lower()
    return _NON_ALNUM_PATTERN.sub(" ", ascii_lower).strip()


def normalize_status(value: str) -> str:
    """Normalize a marketplace status text for dictionary lookup."""
    return normalize_header(value)


def _require_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")


def _validate_score(score: float) -> None:
    if (
        isinstance(score, bool)
        or not math.isfinite(score)
        or score < MIN_DETECTION_SCORE
        or score > MAX_DETECTION_SCORE
    ):
        raise ValueError(
            f"min_score must be between {MIN_DETECTION_SCORE} "
            f"and {MAX_DETECTION_SCORE}."
        )


def _freeze_alias_map(
    raw_map: Mapping[CanonicalField, tuple[str, ...]],
    group_name: str,
) -> Mapping[CanonicalField, tuple[str, ...]]:
    frozen: dict[CanonicalField, tuple[str, ...]] = {}
    for canonical_field, aliases in raw_map.items():
        if not aliases:
            raise ValueError(f"{group_name}.{canonical_field} must declare aliases.")
        cleaned = tuple(alias.strip() for alias in aliases)
        if any(not normalize_header(alias) for alias in cleaned):
            raise ValueError(
                f"{group_name}.{canonical_field} contains an invalid empty alias."
            )
        frozen[canonical_field] = cleaned
    return MappingProxyType(frozen)


def _freeze_status_map(
    raw_status_map: Mapping[str, OrderStatus],
) -> Mapping[str, OrderStatus]:
    normalized: dict[str, OrderStatus] = {}
    for raw_label, order_status in raw_status_map.items():
        key = normalize_status(raw_label)
        if not key:
            raise ValueError("status_map keys must not be empty.")
        normalized[key] = order_status
    return MappingProxyType(normalized)


def _deduplicated_normalized_aliases(
    alias_map: Mapping[CanonicalField, tuple[str, ...]],
) -> Mapping[CanonicalField, tuple[str, ...]]:
    result: dict[CanonicalField, tuple[str, ...]] = {}
    for canonical_field, aliases in alias_map.items():
        deduped = tuple(dict.fromkeys(normalize_header(alias) for alias in aliases))
        result[canonical_field] = deduped
    return result


@dataclass(frozen=True, slots=True)
class MarketplaceAdapter:
    """Declarative specification for a marketplace report format."""

    key: str
    display_name: str
    report_type: str
    observed_at: str
    compatibility_note: str
    required_fields: Mapping[CanonicalField, tuple[str, ...]]
    optional_fields: Mapping[CanonicalField, tuple[str, ...]] = field(
        default_factory=dict
    )
    status_map: Mapping[str, OrderStatus] = field(default_factory=dict)
    date_formats: tuple[str, ...] = ()
    decimal_style: DecimalStyle = DecimalStyle.AUTO
    min_score: float = MEDIUM_CONFIDENCE_THRESHOLD
    support_tier: AdapterSupportTier = AdapterSupportTier.EXPERIMENTAL

    def __post_init__(self) -> None:
        _require_text("key", self.key)
        _require_text("display_name", self.display_name)
        _require_text("report_type", self.report_type)
        _require_text("compatibility_note", self.compatibility_note)
        date.fromisoformat(self.observed_at)
        _validate_score(self.min_score)
        if not self.required_fields:
            raise ValueError("required_fields must not be empty.")
        if set(self.required_fields) & set(self.optional_fields):
            raise ValueError("required_fields and optional_fields must not overlap.")
        req = _freeze_alias_map(self.required_fields, "required_fields")
        opt = _freeze_alias_map(self.optional_fields, "optional_fields")
        object.__setattr__(self, "required_fields", req)
        object.__setattr__(self, "optional_fields", opt)
        object.__setattr__(self, "status_map", _freeze_status_map(self.status_map))

    def normalized_required_aliases(self) -> Mapping[CanonicalField, tuple[str, ...]]:
        """Return deduplicated normalized aliases for required fields."""
        return _deduplicated_normalized_aliases(self.required_fields)

    def normalized_optional_aliases(self) -> Mapping[CanonicalField, tuple[str, ...]]:
        """Return deduplicated normalized aliases for optional fields."""
        return _deduplicated_normalized_aliases(self.optional_fields)

    def all_normalized_aliases(self) -> frozenset[str]:
        """Return all normalized column aliases declared by this adapter."""
        required_aliases = self.normalized_required_aliases().values()
        optional_aliases = self.normalized_optional_aliases().values()
        return frozenset(
            alias for group in (*required_aliases, *optional_aliases) for alias in group
        )


__all__ = [
    "MarketplaceAdapter",
    "normalize_header",
    "normalize_status",
]
