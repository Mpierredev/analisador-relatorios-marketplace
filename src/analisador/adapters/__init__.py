"""Declarative marketplace adapters and header normalization utilities."""

from analisador.adapters.base import (
    MarketplaceAdapter,
    normalize_header,
    normalize_status,
)
from analisador.adapters.mercado_livre import MERCADO_LIVRE_ADAPTER
from analisador.adapters.registry import (
    REGISTERED_ADAPTERS,
    get_adapter,
    has_adapter,
    list_adapters,
)
from analisador.adapters.shopee import SHOPEE_ADAPTER

__all__ = [
    "MERCADO_LIVRE_ADAPTER",
    "REGISTERED_ADAPTERS",
    "SHOPEE_ADAPTER",
    "MarketplaceAdapter",
    "get_adapter",
    "has_adapter",
    "list_adapters",
    "normalize_header",
    "normalize_status",
]
