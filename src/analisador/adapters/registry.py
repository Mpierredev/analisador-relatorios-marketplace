"""Static registry for built-in marketplace adapters."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from analisador.adapters.base import MarketplaceAdapter
from analisador.adapters.mercado_livre import MERCADO_LIVRE_ADAPTER
from analisador.adapters.shopee import SHOPEE_ADAPTER

REGISTERED_ADAPTERS: Final[tuple[MarketplaceAdapter, ...]] = (
    SHOPEE_ADAPTER,
    MERCADO_LIVRE_ADAPTER,
)

_ADAPTERS_BY_KEY: Final[Mapping[str, MarketplaceAdapter]] = MappingProxyType(
    {adapter.key: adapter for adapter in REGISTERED_ADAPTERS}
)


def list_adapters() -> tuple[MarketplaceAdapter, ...]:
    """Return all registered marketplace adapters."""
    return REGISTERED_ADAPTERS


def get_adapter(key: str) -> MarketplaceAdapter:
    """Return the adapter matching a key or raise KeyError."""
    normalized_key = key.strip().lower()
    if normalized_key not in _ADAPTERS_BY_KEY:
        raise KeyError(f"Unknown marketplace adapter: {key!r}")
    return _ADAPTERS_BY_KEY[normalized_key]


def has_adapter(key: str) -> bool:
    """Return whether an adapter exists for the given key."""
    return key.strip().lower() in _ADAPTERS_BY_KEY


__all__ = [
    "REGISTERED_ADAPTERS",
    "get_adapter",
    "has_adapter",
    "list_adapters",
]
