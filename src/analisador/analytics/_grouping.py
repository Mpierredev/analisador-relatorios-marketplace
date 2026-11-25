"""Shared internal helpers for vectorized analytics GroupBy extractions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from analisador.analytics.filters import build_order_key_series, cents_to_brl_decimal
from analisador.core.enums import CanonicalField


@dataclass(frozen=True, slots=True)
class AggregatedProduct:
    """Internal integer-cent intermediate aggregation per product."""

    product_name: str
    sku: str | None
    quantity: int
    order_count: int
    gross_cents: int
    net_cents: int | None


def extract_optional_int_sums(
    grouped: Any,
    col_name: str,
    row_count: int,
    *,
    enabled: bool,
) -> list[int | None]:
    """Extract nullable integer sums per group preserving all-NA groups as None."""
    if not enabled:
        return [None] * row_count
    values = grouped[col_name].sum(min_count=1).tolist()
    return [None if pd.isna(val) else int(val) for val in values]


def extract_optional_str_first(
    grouped: Any,
    col_name: str,
    row_count: int,
    *,
    enabled: bool,
) -> list[str | None]:
    """Extract first non-null string per group, returning None when absent."""
    if not enabled:
        return [None] * row_count
    values = grouped[col_name].first().tolist()
    return [None if pd.isna(val) else str(val) for val in values]


def extract_optional_brl_sums(
    grouped: Any,
    col_name: str,
    row_count: int,
    *,
    enabled: bool,
) -> list[Decimal | None]:
    """Extract nullable BRL Decimal sums per group from cent columns."""
    ints = extract_optional_int_sums(grouped, col_name, row_count, enabled=enabled)
    return [None if val is None else cents_to_brl_decimal(val) for val in ints]


def _prepare_sku_series(sales_df: pd.DataFrame) -> pd.Series[Any] | None:
    sku_col = CanonicalField.SKU.value
    if sku_col not in sales_df.columns:
        return None
    cleaned = sales_df[sku_col].astype("string").str.strip()
    return cleaned.mask(cleaned == "", pd.NA)


def _product_working_frame(
    sales_df: pd.DataFrame,
    product_keys: pd.Series[Any],
    non_empty: pd.Series[Any],
) -> pd.DataFrame:
    scoped = sales_df.loc[non_empty]
    cols: dict[str, pd.Series[Any]] = {
        "_product_key": product_keys.loc[non_empty],
        "_order_key": build_order_key_series(scoped),
        "_qty": scoped[CanonicalField.QUANTITY.value],
        "_gross": scoped[CanonicalField.GROSS_REVENUE.value],
    }
    sku_series = _prepare_sku_series(scoped)
    if sku_series is not None:
        cols["_sku"] = sku_series
    net_col = CanonicalField.NET_REVENUE.value
    if net_col in scoped.columns:
        cols["_net"] = scoped[net_col]
    return pd.DataFrame(cols, index=scoped.index)


def aggregate_product_metrics(
    sales_df: pd.DataFrame,
    product_keys: pd.Series[Any],
    non_empty: pd.Series[Any],
) -> list[AggregatedProduct]:
    """Vectorized GroupBy product aggregation from a filtered sales frame."""
    working = _product_working_frame(sales_df, product_keys, non_empty)
    grouped = working.groupby("_product_key", observed=True, sort=False)
    agg_df = grouped.agg(
        quantity=("_qty", "sum"),
        order_count=("_order_key", "nunique"),
        gross_cents=("_gross", "sum"),
    )
    has_sku, has_net = "_sku" in working.columns, "_net" in working.columns
    sku_vals = extract_optional_str_first(grouped, "_sku", len(agg_df), enabled=has_sku)
    net_vals = extract_optional_int_sums(grouped, "_net", len(agg_df), enabled=has_net)
    return [
        AggregatedProduct(str(name), sku, int(qty), int(orders), int(gross), net)
        for name, sku, qty, orders, gross, net in zip(
            agg_df.index.tolist(),
            sku_vals,
            agg_df["quantity"].tolist(),
            agg_df["order_count"].tolist(),
            agg_df["gross_cents"].tolist(),
            net_vals,
            strict=True,
        )
    ]


__all__ = [
    "AggregatedProduct",
    "aggregate_product_metrics",
    "extract_optional_brl_sums",
    "extract_optional_int_sums",
    "extract_optional_str_first",
]
