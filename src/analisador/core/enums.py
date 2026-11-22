"""Domain enumerations for the canonical schema and validation states."""

from enum import StrEnum


class OrderStatus(StrEnum):
    """Standardized order status across marketplaces."""

    COMPLETED = "concluido"
    CANCELLED = "cancelado"
    RETURNED = "devolvido"
    IN_PROGRESS = "em_andamento"
    OTHER = "outro"


class Marketplace(StrEnum):
    """Built-in marketplace keys supported by the analyzer."""

    SHOPEE = "shopee"
    MERCADO_LIVRE = "mercado_livre"
    GENERIC = "generico"


class CanonicalField(StrEnum):
    """Column identifiers in the canonical sales schema."""

    ORDER_ID = "order_id"
    ORDER_DATE = "order_date"
    STATUS = "status"
    PRODUCT_NAME = "product_name"
    SKU = "sku"
    QUANTITY = "quantity"
    UNIT_PRICE = "unit_price"
    GROSS_REVENUE = "gross_revenue"
    FEES = "fees"
    SHIPPING_COST = "shipping_cost"
    NET_REVENUE = "net_revenue"
    MARKETPLACE = "marketplace"


class FieldDataType(StrEnum):
    """Logical data types defined by the canonical schema."""

    TEXT = "text"
    DATETIME = "datetime"
    CATEGORY = "category"
    INTEGER = "integer"
    DECIMAL = "decimal"


class FieldRequirement(StrEnum):
    """Requirement level of a field in the canonical schema."""

    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"


class ValidationStatus(StrEnum):
    """Outcome of structural validation against an adapter or mapping."""

    RECOGNIZED = "reconhecido"
    RECOGNIZED_WITH_WARNINGS = "reconhecido_com_avisos"
    UNRECOGNIZED = "nao_reconhecido"


class DecimalStyle(StrEnum):
    """Number formatting convention used by an input source."""

    BR = "br"
    US = "us"
    AUTO = "auto"


__all__ = [
    "CanonicalField",
    "DecimalStyle",
    "FieldDataType",
    "FieldRequirement",
    "Marketplace",
    "OrderStatus",
    "ValidationStatus",
]
