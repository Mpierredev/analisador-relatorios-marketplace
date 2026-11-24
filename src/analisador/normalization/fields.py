"""Vectorized field normalizers for text, codes, quantities, status, and money."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

import numpy as np
import pandas as pd

from analisador.adapters.base import normalize_status
from analisador.core.config import (
    MAX_MONETARY_INTEGER_DIGITS,
    MIN_QUANTITY,
    SYNTHETIC_ORDER_ID_PREFIX,
)
from analisador.core.enums import (
    CanonicalField,
    DecimalStyle,
    FieldDataType,
    OrderStatus,
)
from analisador.core.schema import CANONICAL_SCHEMA
from analisador.normalization.currency_series import parse_currency_series_to_cents

_QUANTITY_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<int>[+-]?\d+)(?:[.,]0+)?$")
_MONETARY_FIELDS: Final[tuple[CanonicalField, ...]] = tuple(
    spec.field for spec in CANONICAL_SCHEMA if spec.data_type is FieldDataType.DECIMAL
)


def _build_generic_status_map() -> Mapping[str, OrderStatus]:
    groups = (
        (
            OrderStatus.COMPLETED,
            "concluido|concluida|entregue|finalizado|pago|aprovado|"
            "completed|delivered|paid|completado|entregada",
        ),
        (OrderStatus.CANCELLED, "cancelado|cancelada|anulado|cancelled|canceled"),
        (
            OrderStatus.RETURNED,
            "devolvido|devolvida|reembolsado|reembolsada|returned|refunded|devuelto",
        ),
        (
            OrderStatus.IN_PROGRESS,
            "em andamento|pendente|a enviar|enviado|a caminho|"
            "pending|processing|shipped|in transit|pendiente|en camino",
        ),
    )
    return MappingProxyType(
        {label: status for status, raw in groups for label in raw.split("|")}
    )


_GENERIC_STATUS_MAP: Final[Mapping[str, OrderStatus]] = _build_generic_status_map()


@dataclass(frozen=True, slots=True)
class QuantityParseResult:
    """Result of normalizing raw order item quantities."""

    series: pd.Series[Any]
    empty_count: int
    non_positive_count: int
    malformed_count: int


@dataclass(frozen=True, slots=True)
class MonetaryFieldsResult:
    """Normalized monetary columns in integer cents plus diagnostic counts."""

    unit_price: pd.Series[Any]
    gross_revenue: pd.Series[Any]
    fees: pd.Series[Any]
    shipping_cost: pd.Series[Any]
    net_revenue: pd.Series[Any]
    null_counts: dict[str, int]
    malformed_counts: dict[str, int]
    negative_value_rows: int
    reported_net_mask: pd.Series[Any]
    derived_net_mask: pd.Series[Any]


def _clean_string_series(
    series: pd.Series[Any],
    *,
    collapse_spaces: bool,
) -> tuple[pd.Series[Any], int]:
    cleaned = series.fillna("").astype(str).str.strip()
    if collapse_spaces:
        cleaned = cleaned.str.replace(r"\s+", " ", regex=True)
    blank_mask = cleaned == ""
    normalized: pd.Series[Any] = cleaned.mask(blank_mask, pd.NA).astype("string")
    return normalized, int(blank_mask.sum())


def normalize_text_series(series: pd.Series[Any]) -> tuple[pd.Series[Any], int]:
    """Trim, collapse internal spaces, convert blanks to NA, and count blanks."""
    return _clean_string_series(series, collapse_spaces=True)


def normalize_optional_code_series(
    series: pd.Series[Any],
) -> tuple[pd.Series[Any], int]:
    """Trim optional identifier codes, convert blanks to NA, and count blanks."""
    return _clean_string_series(series, collapse_spaces=False)


def generate_synthetic_order_ids(
    length: int,
    index: pd.Index[Any],
) -> pd.Series[Any]:
    """Build deterministic synthetic order IDs aligned to the given index."""
    ids = [f"{SYNTHETIC_ORDER_ID_PREFIX}{pos:06d}" for pos in range(1, length + 1)]
    return pd.Series(ids, index=index, dtype="string")


def _parse_int_tokens(
    cleaned: pd.Series[Any],
    non_empty_mask: pd.Series[Any],
) -> tuple[pd.Series[Any], pd.Series[Any], pd.Series[Any]]:
    extracted = cleaned.str.extract(_QUANTITY_RE)["int"]
    has_match = extracted.notna()
    abs_digits = extracted.fillna("").str.lstrip("+-").str.lstrip("0")
    within_limit = has_match & (abs_digits.str.len() <= MAX_MONETARY_INTEGER_DIGITS)

    parsed = pd.Series(pd.NA, index=cleaned.index, dtype="Int64")
    if within_limit.any():
        parsed.iloc[np.flatnonzero(within_limit.to_numpy(dtype=bool))] = extracted.loc[
            within_limit
        ].to_numpy(dtype=np.int64)
    malformed_mask = non_empty_mask & (~within_limit)
    return parsed, within_limit, malformed_mask


def normalize_quantity_series(series: pd.Series[Any]) -> QuantityParseResult:
    """Parse integer quantities accepting whole Excel floats like '1.0'."""
    cleaned = series.fillna("").astype(str).str.strip()
    non_empty_mask = cleaned != ""
    empty_count = int((~non_empty_mask).sum())
    parsed, within_limit, malformed_mask = _parse_int_tokens(cleaned, non_empty_mask)

    positive_mask = within_limit & (parsed >= MIN_QUANTITY).fillna(False)
    non_positive_mask = within_limit & (~positive_mask)
    return QuantityParseResult(
        series=parsed.where(positive_mask, pd.NA),
        empty_count=empty_count,
        non_positive_count=int(non_positive_mask.sum()),
        malformed_count=int(malformed_mask.sum()),
    )


def normalize_status_series(
    series: pd.Series[Any] | None,
    index: pd.Index[Any],
    *,
    status_map: Mapping[str, OrderStatus] | None = None,
) -> tuple[pd.Series[Any], int]:
    """Map raw status values via adapter status_map into canonical OrderStatus."""
    categories = [status.value for status in OrderStatus]
    cat_dtype = pd.CategoricalDtype(categories=categories, ordered=False)
    if series is None:
        default_vals = [OrderStatus.OTHER.value] * len(index)
        return pd.Series(default_vals, index=index, dtype=cat_dtype), 0

    cleaned = series.fillna("").astype(str).str.strip()
    non_empty = cleaned != ""
    empty_count = int((~non_empty).sum())
    lookup = _GENERIC_STATUS_MAP if status_map is None else status_map
    unique_labels = cleaned.loc[non_empty].unique()
    translation = {
        label: lookup.get(normalize_status(label), OrderStatus.OTHER).value
        for label in unique_labels
    }
    mapped = cleaned.map(translation).fillna(OrderStatus.OTHER.value)
    return mapped.astype(cat_dtype), empty_count


def _parse_optional_monetary(
    raw_series: pd.Series[Any] | None,
    index: pd.Index[Any],
    decimal_style: DecimalStyle,
) -> tuple[pd.Series[Any], int, int]:
    if raw_series is None:
        return pd.Series(pd.NA, index=index, dtype="Int64"), 0, 0
    cleaned = raw_series.fillna("").astype(str).str.strip()
    non_empty = cleaned != ""
    empty_count = int((~non_empty).sum())
    parsed = parse_currency_series_to_cents(raw_series, decimal_style=decimal_style)
    malformed_count = int((non_empty & parsed.isna()).sum())
    return parsed, empty_count, malformed_count


def _parse_monetary_columns(
    mapped_columns: Mapping[CanonicalField, pd.Series[Any]],
    index: pd.Index[Any],
    decimal_style: DecimalStyle,
) -> tuple[dict[CanonicalField, pd.Series[Any]], dict[str, int], dict[str, int]]:
    parsed_by_field: dict[CanonicalField, pd.Series[Any]] = {}
    null_counts: dict[str, int] = {}
    malformed_counts: dict[str, int] = {}
    for field in _MONETARY_FIELDS:
        parsed, empty_cnt, malformed_cnt = _parse_optional_monetary(
            mapped_columns.get(field), index, decimal_style
        )
        parsed_by_field[field] = parsed
        if empty_cnt > 0:
            null_counts[field.value] = empty_cnt
        if malformed_cnt > 0:
            malformed_counts[field.value] = malformed_cnt
    return parsed_by_field, null_counts, malformed_counts


def _derive_gross_and_net(
    parsed: Mapping[CanonicalField, pd.Series[Any]],
    quantity: pd.Series[Any],
    fees: pd.Series[Any],
    shipping_cost: pd.Series[Any],
    has_net_col: bool,
) -> tuple[pd.Series[Any], pd.Series[Any]]:
    unit_price = parsed[CanonicalField.UNIT_PRICE]
    resolved_gross = parsed[CanonicalField.GROSS_REVENUE].copy()
    derive_gross = resolved_gross.isna() & quantity.notna() & unit_price.notna()
    if derive_gross.any():
        derived = quantity.loc[derive_gross].astype("int64") * unit_price.loc[
            derive_gross
        ].astype("int64")
        resolved_gross.loc[derive_gross] = derived

    resolved_net = parsed[CanonicalField.NET_REVENUE].copy()
    can_derive_net = fees.notna() | (has_net_col & shipping_cost.notna())
    derive_net = resolved_net.isna() & resolved_gross.notna() & can_derive_net
    if derive_net.any():
        fee_part = fees.loc[derive_net].fillna(0)
        ship_part = shipping_cost.loc[derive_net].fillna(0)
        resolved_net.loc[derive_net] = (
            resolved_gross.loc[derive_net] - fee_part - ship_part
        )
    return resolved_gross, resolved_net


def _count_negative_monetary_rows(*series_list: pd.Series[Any]) -> int:
    neg_mask = np.zeros(len(series_list[0]), dtype=bool)
    for col in series_list:
        neg_mask |= (col < 0).fillna(False).to_numpy(dtype=bool)
    return int(neg_mask.sum())


def normalize_monetary_fields(
    mapped_columns: Mapping[CanonicalField, pd.Series[Any]],
    quantity: pd.Series[Any],
    index: pd.Index[Any],
    *,
    decimal_style: DecimalStyle = DecimalStyle.AUTO,
) -> MonetaryFieldsResult:
    """Parse monetary columns to integer cents, derive revenues, and count issues."""
    parsed, null_counts, malformed_counts = _parse_monetary_columns(
        mapped_columns, index, decimal_style
    )
    fees = parsed[CanonicalField.FEES].abs()
    ship = parsed[CanonicalField.SHIPPING_COST].abs()
    unit_price = parsed[CanonicalField.UNIT_PRICE]
    has_net = CanonicalField.NET_REVENUE in mapped_columns
    gross_rev, net_rev = _derive_gross_and_net(parsed, quantity, fees, ship, has_net)
    reported_net = parsed[CanonicalField.NET_REVENUE].notna()
    return MonetaryFieldsResult(
        unit_price,
        gross_rev,
        fees,
        ship,
        net_rev,
        null_counts,
        malformed_counts,
        _count_negative_monetary_rows(unit_price, gross_rev, net_rev),
        reported_net,
        net_rev.notna() & (~reported_net),
    )


__all__ = [
    "MonetaryFieldsResult",
    "QuantityParseResult",
    "generate_synthetic_order_ids",
    "normalize_monetary_fields",
    "normalize_optional_code_series",
    "normalize_quantity_series",
    "normalize_status_series",
    "normalize_text_series",
]
