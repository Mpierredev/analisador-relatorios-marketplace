"""Canonical sales schema definition and domain record model."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from analisador.core.config import MIN_QUANTITY
from analisador.core.enums import (
    CanonicalField,
    FieldDataType,
    FieldRequirement,
    OrderStatus,
)

_ZERO_DECIMAL: Final[Decimal] = Decimal("0")


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Metadata describing a column in the canonical schema."""

    field: CanonicalField
    data_type: FieldDataType
    requirement: FieldRequirement
    nullable: bool


CANONICAL_SCHEMA: Final[tuple[FieldSpec, ...]] = (
    FieldSpec(
        field=CanonicalField.ORDER_ID,
        data_type=FieldDataType.TEXT,
        requirement=FieldRequirement.OPTIONAL,
        nullable=True,
    ),
    FieldSpec(
        field=CanonicalField.ORDER_DATE,
        data_type=FieldDataType.DATETIME,
        requirement=FieldRequirement.REQUIRED,
        nullable=False,
    ),
    FieldSpec(
        field=CanonicalField.STATUS,
        data_type=FieldDataType.CATEGORY,
        requirement=FieldRequirement.OPTIONAL,
        nullable=False,
    ),
    FieldSpec(
        field=CanonicalField.PRODUCT_NAME,
        data_type=FieldDataType.TEXT,
        requirement=FieldRequirement.REQUIRED,
        nullable=False,
    ),
    FieldSpec(
        field=CanonicalField.SKU,
        data_type=FieldDataType.TEXT,
        requirement=FieldRequirement.OPTIONAL,
        nullable=True,
    ),
    FieldSpec(
        field=CanonicalField.QUANTITY,
        data_type=FieldDataType.INTEGER,
        requirement=FieldRequirement.REQUIRED,
        nullable=False,
    ),
    FieldSpec(
        field=CanonicalField.UNIT_PRICE,
        data_type=FieldDataType.DECIMAL,
        requirement=FieldRequirement.CONDITIONAL,
        nullable=True,
    ),
    FieldSpec(
        field=CanonicalField.GROSS_REVENUE,
        data_type=FieldDataType.DECIMAL,
        requirement=FieldRequirement.REQUIRED,
        nullable=False,
    ),
    FieldSpec(
        field=CanonicalField.FEES,
        data_type=FieldDataType.DECIMAL,
        requirement=FieldRequirement.OPTIONAL,
        nullable=True,
    ),
    FieldSpec(
        field=CanonicalField.SHIPPING_COST,
        data_type=FieldDataType.DECIMAL,
        requirement=FieldRequirement.OPTIONAL,
        nullable=True,
    ),
    FieldSpec(
        field=CanonicalField.NET_REVENUE,
        data_type=FieldDataType.DECIMAL,
        requirement=FieldRequirement.OPTIONAL,
        nullable=True,
    ),
    FieldSpec(
        field=CanonicalField.MARKETPLACE,
        data_type=FieldDataType.CATEGORY,
        requirement=FieldRequirement.REQUIRED,
        nullable=False,
    ),
)

CANONICAL_COLUMNS: Final[tuple[CanonicalField, ...]] = tuple(
    spec.field for spec in CANONICAL_SCHEMA
)

SCHEMA_BY_FIELD: Final[Mapping[CanonicalField, FieldSpec]] = MappingProxyType(
    {spec.field: spec for spec in CANONICAL_SCHEMA}
)

REQUIRED_CANONICAL_FIELDS: Final[frozenset[CanonicalField]] = frozenset(
    spec.field
    for spec in CANONICAL_SCHEMA
    if spec.requirement is FieldRequirement.REQUIRED
)

ALWAYS_REQUIRED_INPUT_FIELDS: Final[frozenset[CanonicalField]] = frozenset(
    {
        CanonicalField.ORDER_DATE,
        CanonicalField.PRODUCT_NAME,
        CanonicalField.QUANTITY,
    }
)

MONETARY_INPUT_FIELDS: Final[frozenset[CanonicalField]] = frozenset(
    {
        CanonicalField.GROSS_REVENUE,
        CanonicalField.UNIT_PRICE,
    }
)


def missing_required_input_fields(
    mapped_fields: Collection[CanonicalField],
) -> tuple[CanonicalField, ...]:
    """Return canonical input fields required before normalization."""
    present = set(mapped_fields)
    missing = [
        spec.field
        for spec in CANONICAL_SCHEMA
        if spec.field in ALWAYS_REQUIRED_INPUT_FIELDS and spec.field not in present
    ]
    if not (present & MONETARY_INPUT_FIELDS):
        missing.append(CanonicalField.GROSS_REVENUE)
    return tuple(missing)


def has_required_input_fields(mapped_fields: Collection[CanonicalField]) -> bool:
    """Return whether minimum required input fields are mapped."""
    return not missing_required_input_fields(mapped_fields)


def _validate_required_texts(*items: tuple[str, str]) -> None:
    for name, value in items:
        if not value.strip():
            raise ValueError(f"{name} must not be empty.")


def _validate_optional_texts(*items: tuple[str, str | None]) -> None:
    for name, value in items:
        if value is not None and not value.strip():
            raise ValueError(f"{name} must not be empty when provided.")


def _validate_decimal_field(
    name: str,
    value: Decimal | None,
    *,
    allow_none: bool,
    require_non_negative: bool,
) -> None:
    if value is None:
        if allow_none:
            return
        raise ValueError(f"{name} must not be None.")
    if not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal.")
    if require_non_negative and value < _ZERO_DECIMAL:
        raise ValueError(f"{name} must not be negative.")


def _validate_record_decimals(record: "CanonicalRecord") -> None:
    for name, value, allow_none, require_non_negative in (
        ("gross_revenue", record.gross_revenue, False, False),
        ("unit_price", record.unit_price, True, False),
        ("net_revenue", record.net_revenue, True, False),
        ("fees", record.fees, True, True),
        ("shipping_cost", record.shipping_cost, True, True),
    ):
        _validate_decimal_field(
            name,
            value,
            allow_none=allow_none,
            require_non_negative=require_non_negative,
        )


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    """Normalized sales line item conforming to the canonical schema."""

    order_date: datetime
    product_name: str
    quantity: int
    gross_revenue: Decimal
    marketplace: str
    order_id: str | None = None
    status: OrderStatus = OrderStatus.OTHER
    sku: str | None = None
    unit_price: Decimal | None = None
    fees: Decimal | None = None
    shipping_cost: Decimal | None = None
    net_revenue: Decimal | None = None

    def __post_init__(self) -> None:
        _validate_required_texts(
            ("product_name", self.product_name),
            ("marketplace", self.marketplace),
        )
        _validate_optional_texts(
            ("order_id", self.order_id),
            ("sku", self.sku),
        )
        if isinstance(self.quantity, bool) or self.quantity < MIN_QUANTITY:
            raise ValueError(f"quantity must be an integer >= {MIN_QUANTITY}.")
        _validate_record_decimals(self)


__all__ = [
    "ALWAYS_REQUIRED_INPUT_FIELDS",
    "CANONICAL_COLUMNS",
    "CANONICAL_SCHEMA",
    "MONETARY_INPUT_FIELDS",
    "REQUIRED_CANONICAL_FIELDS",
    "SCHEMA_BY_FIELD",
    "CanonicalRecord",
    "FieldSpec",
    "has_required_input_fields",
    "missing_required_input_fields",
]
