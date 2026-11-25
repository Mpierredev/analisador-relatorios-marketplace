"""Canonical dtype compaction helpers for memory-efficient normalization."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from analisador.core.enums import CanonicalField
from analisador.core.schema import CANONICAL_COLUMNS

_INT32_INFO = np.iinfo(np.int32)


def compact_quantity_series(series: pd.Series[Any]) -> pd.Series[Any]:
    """Downcast non-null integer quantities to int32 when values fit safely."""
    if series.empty:
        return series.astype("int32")
    min_val = int(series.min())
    max_val = int(series.max())
    if min_val >= int(_INT32_INFO.min) and max_val <= int(_INT32_INFO.max):
        return series.astype("int32")
    return series.astype("int64")


def compact_categorical_text(series: pd.Series[Any]) -> pd.Series[Any]:
    """Convert repetitive text columns to category when cardinality <= 50%."""
    if series.empty:
        return series
    unique_count = int(series.nunique(dropna=True))
    if unique_count <= max(1, len(series) // 2):
        return series.astype("category")
    return series


def finalize_canonical_frame(
    raw_map: dict[str, pd.Series[Any]],
    index: pd.Index[Any],
    marketplace_key: str,
) -> pd.DataFrame:
    """Compact categorical/integer columns and order canonical schema fields."""
    raw_map[CanonicalField.PRODUCT_NAME.value] = compact_categorical_text(
        raw_map[CanonicalField.PRODUCT_NAME.value]
    )
    raw_map[CanonicalField.SKU.value] = compact_categorical_text(
        raw_map[CanonicalField.SKU.value]
    )
    raw_map[CanonicalField.QUANTITY.value] = compact_quantity_series(
        raw_map[CanonicalField.QUANTITY.value]
    )
    raw_map[CanonicalField.MARKETPLACE.value] = pd.Series(
        [marketplace_key] * len(index), index=index, dtype="category"
    )
    ordered_cols = [field.value for field in CANONICAL_COLUMNS]
    return pd.DataFrame(raw_map, index=index)[ordered_cols].reset_index(drop=True)


__all__ = [
    "compact_categorical_text",
    "compact_quantity_series",
    "finalize_canonical_frame",
]
