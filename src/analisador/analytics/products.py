"""Product ranking by revenue/quantity and ABC Pareto classification."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Final

import pandas as pd

from analisador.analytics.filters import (
    DEFAULT_EXCLUDED_STATUSES,
    cents_to_brl_decimal,
    count_unique_orders,
    filter_by_period,
    filter_sales,
    validate_canonical_dataframe,
)
from analisador.core.config import (
    ABC_CLASS_A_LIMIT,
    ABC_CLASS_B_LIMIT,
    DEFAULT_TOP_PRODUCTS_LIMIT,
)
from analisador.core.enums import CanonicalField, OrderStatus

_SHARE_QUANTIZER: Final[Decimal] = Decimal("0.0001")
_ZERO_SHARE: Final[Decimal] = Decimal("0.0000")
_PRODUCT_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.PRODUCT_NAME,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)


class ProductRankingMetric(StrEnum):
    """Sorting metric options for product rankings."""

    REVENUE = "receita"
    QUANTITY = "quantidade"


class AbcClass(StrEnum):
    """Pareto ABC inventory/revenue classification tiers."""

    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True, slots=True)
class ProductRankingRow:
    """Ranked performance summary for a single product."""

    rank: int
    product_name: str
    sku: str | None
    quantity: int
    order_count: int
    gross_revenue: Decimal
    net_revenue: Decimal | None
    revenue_share: Decimal


@dataclass(frozen=True, slots=True)
class AbcCurveRow:
    """Product contribution and cumulative Pareto tier in an ABC curve."""

    rank: int
    product_name: str
    sku: str | None
    quantity: int
    gross_revenue: Decimal
    revenue_share: Decimal
    cumulative_share: Decimal
    abc_class: AbcClass


@dataclass(frozen=True, slots=True)
class _AggregatedProduct:
    """Internal integer-cent intermediate aggregation per product."""

    product_name: str
    sku: str | None
    quantity: int
    order_count: int
    gross_cents: int
    net_cents: int | None


def _coerce_metric(metric: ProductRankingMetric | str) -> ProductRankingMetric:
    if isinstance(metric, ProductRankingMetric):
        return metric
    try:
        return ProductRankingMetric(str(metric).strip())
    except ValueError as exc:
        raise ValueError(f"Métrica de ranking inválida: {metric!r}.") from exc


def _first_non_empty_sku(group: pd.DataFrame) -> str | None:
    sku_col = CanonicalField.SKU.value
    if sku_col not in group.columns:
        return None
    cleaned = group[sku_col].astype("string").dropna().str.strip()
    non_empty = cleaned.loc[cleaned != ""]
    if non_empty.empty:
        return None
    return str(non_empty.iloc[0])


def _sum_group_net_cents(group: pd.DataFrame) -> int | None:
    net_col = CanonicalField.NET_REVENUE.value
    if net_col not in group.columns:
        return None
    non_null: pd.Series[Any] = group[net_col].dropna()
    return None if non_null.empty else int(non_null.sum())


def _group_product_metrics(working: pd.DataFrame) -> list[_AggregatedProduct]:
    return [
        _AggregatedProduct(
            product_name=str(product_name),
            sku=_first_non_empty_sku(group),
            quantity=int(group[CanonicalField.QUANTITY.value].sum()),
            order_count=count_unique_orders(group),
            gross_cents=int(group[CanonicalField.GROSS_REVENUE.value].sum()),
            net_cents=_sum_group_net_cents(group),
        )
        for product_name, group in working.groupby("_product_key", sort=False)
    ]


def _aggregate_products(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    exclude_statuses: Sequence[OrderStatus | str],
) -> list[_AggregatedProduct]:
    """Filter period/sales and aggregate metrics per trimmed product_name."""
    validate_canonical_dataframe(dataframe, required_fields=_PRODUCT_REQUIRED_FIELDS)
    sales_df = filter_sales(
        filter_by_period(dataframe, start_date, end_date),
        exclude_statuses=exclude_statuses,
    )
    if sales_df.empty:
        return []
    working = sales_df.copy()
    working["_product_key"] = (
        working[CanonicalField.PRODUCT_NAME.value]
        .astype("string")
        .fillna("")
        .str.strip()
    )
    working = working.loc[working["_product_key"] != ""]
    return [] if working.empty else _group_product_metrics(working)


def _quantize_share(numerator_cents: int, total_cents: int) -> Decimal:
    if total_cents <= 0:
        return _ZERO_SHARE
    return (Decimal(numerator_cents) / Decimal(total_cents)).quantize(
        _SHARE_QUANTIZER,
        rounding=ROUND_HALF_UP,
    )


def _classify_abc(rank: int, raw_cumulative_share: Decimal) -> AbcClass:
    """Assign ABC tier keeping rank 1 in Class A even when exceeding 80%."""
    if rank == 1 or raw_cumulative_share <= ABC_CLASS_A_LIMIT:
        return AbcClass.A
    if raw_cumulative_share <= ABC_CLASS_B_LIMIT:
        return AbcClass.B
    return AbcClass.C


def _to_ranking_row(
    index: int,
    item: _AggregatedProduct,
    total_cents: int,
) -> ProductRankingRow:
    return ProductRankingRow(
        rank=index,
        product_name=item.product_name,
        sku=item.sku,
        quantity=item.quantity,
        order_count=item.order_count,
        gross_revenue=cents_to_brl_decimal(item.gross_cents),
        net_revenue=None
        if item.net_cents is None
        else cents_to_brl_decimal(item.net_cents),
        revenue_share=_quantize_share(item.gross_cents, total_cents),
    )


def _sort_products_by_metric(
    products: list[_AggregatedProduct],
    metric: ProductRankingMetric,
) -> None:
    if metric is ProductRankingMetric.REVENUE:
        products.sort(
            key=lambda p: (-p.gross_cents, -p.quantity, p.product_name.casefold())
        )
    else:
        products.sort(
            key=lambda p: (-p.quantity, -p.gross_cents, p.product_name.casefold())
        )


def rank_products(
    dataframe: pd.DataFrame,
    *,
    by: ProductRankingMetric | str = ProductRankingMetric.REVENUE,
    limit: int | None = DEFAULT_TOP_PRODUCTS_LIMIT,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> list[ProductRankingRow]:
    """Rank products by gross revenue or quantity sold in descending order."""
    if limit is not None and limit <= 0:
        raise ValueError("O limite de produtos do ranking deve ser maior que zero.")
    metric = _coerce_metric(by)
    products = _aggregate_products(
        dataframe,
        start_date=start_date,
        end_date=end_date,
        exclude_statuses=exclude_statuses,
    )
    if not products:
        return []
    _sort_products_by_metric(products, metric)
    total_cents = sum(p.gross_cents for p in products)
    selected = products if limit is None else products[:limit]
    return [
        _to_ranking_row(idx, item, total_cents) for idx, item in enumerate(selected, 1)
    ]


def _build_abc_rows(products: list[_AggregatedProduct]) -> list[AbcCurveRow]:
    total_cents = sum(item.gross_cents for item in products)
    running_cents = 0
    curve: list[AbcCurveRow] = []
    for rank, item in enumerate(products, start=1):
        running_cents += item.gross_cents
        raw_cum = Decimal(running_cents) / Decimal(total_cents)
        curve.append(
            AbcCurveRow(
                rank=rank,
                product_name=item.product_name,
                sku=item.sku,
                quantity=item.quantity,
                gross_revenue=cents_to_brl_decimal(item.gross_cents),
                revenue_share=_quantize_share(item.gross_cents, total_cents),
                cumulative_share=raw_cum.quantize(
                    _SHARE_QUANTIZER, rounding=ROUND_HALF_UP
                ),
                abc_class=_classify_abc(rank, raw_cum),
            )
        )
    return curve


def compute_abc_curve(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> list[AbcCurveRow]:
    """Compute Pareto ABC classification from products with positive gross revenue."""
    products = [
        item
        for item in _aggregate_products(
            dataframe,
            start_date=start_date,
            end_date=end_date,
            exclude_statuses=exclude_statuses,
        )
        if item.gross_cents > 0
    ]
    if not products:
        return []
    products.sort(
        key=lambda p: (-p.gross_cents, -p.quantity, p.product_name.casefold())
    )
    return _build_abc_rows(products)


__all__ = [
    "AbcClass",
    "AbcCurveRow",
    "ProductRankingMetric",
    "ProductRankingRow",
    "compute_abc_curve",
    "rank_products",
]
