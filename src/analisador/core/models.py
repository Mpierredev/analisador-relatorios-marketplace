"""Immutable report models for validation, data quality, and KPI summaries."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from analisador.core.config import (
    MAX_DETECTION_SCORE,
    MAX_RATIO,
    MIN_DETECTION_SCORE,
    MIN_RATIO,
)
from analisador.core.enums import CanonicalField, ValidationStatus

_ZERO_DECIMAL: Final[Decimal] = Decimal("0")


def _freeze_mapping[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _require_non_empty_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")


def _require_unit_interval(
    name: str,
    value: float,
    *,
    minimum: float = MIN_RATIO,
    maximum: float = MAX_RATIO,
) -> None:
    if (
        isinstance(value, bool)
        or not math.isfinite(value)
        or value < minimum
        or value > maximum
    ):
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")


def _require_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")


def _require_finite_decimal(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal.")


def _require_non_negative_decimal(name: str, value: Decimal) -> None:
    _require_finite_decimal(name, value)
    if value < _ZERO_DECIMAL:
        raise ValueError(f"{name} must not be negative.")


def _validate_period(
    period_start: datetime | None,
    period_end: datetime | None,
) -> None:
    if period_start is None or period_end is None:
        return
    if (period_start.tzinfo is None) != (period_end.tzinfo is None):
        raise ValueError(
            "period_start and period_end must both be naive or timezone-aware."
        )
    if period_start > period_end:
        raise ValueError("period_start must not be after period_end.")


@dataclass(frozen=True, slots=True)
class AdapterScore:
    """Compatibility score computed for a marketplace adapter."""

    adapter_key: str
    score: float
    matched_required: tuple[CanonicalField, ...] = ()
    matched_optional: tuple[CanonicalField, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text("adapter_key", self.adapter_key)
        _require_unit_interval(
            "score",
            self.score,
            minimum=MIN_DETECTION_SCORE,
            maximum=MAX_DETECTION_SCORE,
        )


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Structural validation outcome for an uploaded spreadsheet."""

    selected_adapter: str
    status: ValidationStatus
    score: float
    column_mapping: Mapping[CanonicalField, str] = field(default_factory=dict)
    found_required: tuple[CanonicalField, ...] = ()
    missing_required: tuple[CanonicalField, ...] = ()
    found_optional: tuple[CanonicalField, ...] = ()
    extra_columns: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    suggested_adapter: str | None = None
    adapter_scores: tuple[AdapterScore, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text("selected_adapter", self.selected_adapter)
        if self.suggested_adapter is not None:
            _require_non_empty_text("suggested_adapter", self.suggested_adapter)
        _require_unit_interval("score", self.score)
        if self.status is not ValidationStatus.UNRECOGNIZED and self.missing_required:
            raise ValueError(
                "missing_required must be empty unless status is UNRECOGNIZED."
            )
        object.__setattr__(self, "column_mapping", _freeze_mapping(self.column_mapping))

    @property
    def can_generate_dashboard(self) -> bool:
        """Return whether minimum validation succeeded to build the dashboard."""
        return (
            self.status is not ValidationStatus.UNRECOGNIZED
            and not self.missing_required
        )

    @property
    def has_warnings(self) -> bool:
        """Return whether validation produced user-facing warnings."""
        return bool(self.warnings)


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Summary of data quality checks performed during normalization."""

    total_rows: int
    valid_rows: int
    ignored_rows: int
    duplicate_rows: int = 0
    invalid_dates: int = 0
    non_positive_quantities: int = 0
    negative_values: int = 0
    outlier_rows: int = 0
    null_counts: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("total_rows", self.total_rows),
            ("valid_rows", self.valid_rows),
            ("ignored_rows", self.ignored_rows),
            ("duplicate_rows", self.duplicate_rows),
            ("invalid_dates", self.invalid_dates),
            ("non_positive_quantities", self.non_positive_quantities),
            ("negative_values", self.negative_values),
            ("outlier_rows", self.outlier_rows),
        ):
            _require_non_negative_int(name, value)

        if self.valid_rows + self.ignored_rows != self.total_rows:
            raise ValueError("valid_rows + ignored_rows must equal total_rows.")

        for column, count in self.null_counts.items():
            _require_non_empty_text("null_counts key", column)
            _require_non_negative_int(f"null_counts[{column!r}]", count)

        object.__setattr__(self, "null_counts", _freeze_mapping(self.null_counts))

    @property
    def valid_rate(self) -> float:
        """Return the proportion of valid rows in the processed dataset."""
        if self.total_rows == 0:
            return MIN_RATIO
        return self.valid_rows / self.total_rows

    @property
    def has_issues(self) -> bool:
        """Return whether any quality issue or warning was detected."""
        has_problem_counts = any(
            count > 0
            for count in (
                self.ignored_rows,
                self.duplicate_rows,
                self.invalid_dates,
                self.non_positive_quantities,
                self.negative_values,
                self.outlier_rows,
            )
        )
        has_nulls = any(count > 0 for count in self.null_counts.values())
        return has_problem_counts or has_nulls or bool(self.warnings)


@dataclass(frozen=True, slots=True)
class KpiSummary:
    """Aggregated sales KPIs computed from canonical records."""

    gross_revenue: Decimal
    order_count: int
    item_count: int
    average_ticket: Decimal
    cancellation_rate: float | None = None
    cancelled_order_count: int = 0
    total_fees: Decimal | None = None
    total_shipping: Decimal | None = None
    net_revenue: Decimal | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None

    def __post_init__(self) -> None:
        _require_finite_decimal("gross_revenue", self.gross_revenue)
        _require_finite_decimal("average_ticket", self.average_ticket)
        _require_non_negative_int("order_count", self.order_count)
        _require_non_negative_int("item_count", self.item_count)
        _require_non_negative_int("cancelled_order_count", self.cancelled_order_count)

        if self.cancelled_order_count > self.order_count:
            raise ValueError("cancelled_order_count must not exceed order_count.")
        if self.cancellation_rate is not None:
            _require_unit_interval("cancellation_rate", self.cancellation_rate)
        if self.total_fees is not None:
            _require_non_negative_decimal("total_fees", self.total_fees)
        if self.total_shipping is not None:
            _require_non_negative_decimal("total_shipping", self.total_shipping)
        if self.net_revenue is not None:
            _require_finite_decimal("net_revenue", self.net_revenue)
        _validate_period(self.period_start, self.period_end)

    @property
    def has_net_revenue(self) -> bool:
        """Return whether net revenue could be calculated for the dataset."""
        return self.net_revenue is not None


__all__ = [
    "AdapterScore",
    "KpiSummary",
    "QualityReport",
    "ValidationReport",
]
