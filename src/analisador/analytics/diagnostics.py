"""Financial breakdown and per-product risk diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

import pandas as pd

from analisador.analytics._grouping import (
    extract_optional_int_sums,
    extract_optional_str_first,
)
from analisador.analytics.filters import (
    CORE_ANALYTICS_FIELDS,
    DEFAULT_EXCLUDED_STATUSES,
    build_order_key_series,
    cents_to_brl_decimal,
    filter_by_period,
    filter_sales,
    normalize_excluded_statuses,
    validate_canonical_dataframe,
)
from analisador.core.enums import CanonicalField, OrderStatus

_SHARE_QUANTIZER: Final[Decimal] = Decimal("0.0001")
_BREAKDOWN_REQUIRED_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.GROSS_REVENUE,
)


@dataclass(frozen=True, slots=True)
class FinancialBreakdown:
    """Gross-to-net revenue decomposition and loss breakdown for a period."""

    gross_revenue: Decimal
    fees_total: Decimal | None
    shipping_total: Decimal | None
    net_revenue: Decimal | None
    cancelled_revenue: Decimal
    returned_revenue: Decimal
    fees_pct: Decimal | None
    shipping_pct: Decimal | None
    net_margin_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class ProductDiagnosticRow:
    """Per-product profitability, fees, shipping, and cancellation diagnostics."""

    product_name: str
    sku: str | None
    sold_quantity: int
    order_count: int
    total_orders: int
    gross_revenue: Decimal
    fees_total: Decimal | None
    shipping_total: Decimal | None
    net_revenue: Decimal | None
    net_margin_pct: Decimal | None
    cancelled_orders: int
    returned_orders: int
    cancellation_rate: float


def _opt_brl(cents: int | None) -> Decimal | None:
    return None if cents is None else cents_to_brl_decimal(cents)


def _compute_ratio(
    numerator_cents: int | None, denominator_cents: int
) -> Decimal | None:
    if numerator_cents is None or denominator_cents <= 0:
        return None
    return (Decimal(numerator_cents) / Decimal(denominator_cents)).quantize(
        _SHARE_QUANTIZER, rounding=ROUND_HALF_UP
    )


def _sum_optional_cents(dataframe: pd.DataFrame, field: CanonicalField) -> int | None:
    column = field.value
    if dataframe.empty or column not in dataframe.columns:
        return None
    non_null: pd.Series[Any] = dataframe[column].dropna()
    return None if non_null.empty else int(non_null.sum())


def _sum_status_cents(period_df: pd.DataFrame, target_status: OrderStatus) -> int:
    if period_df.empty:
        return 0
    statuses = (
        period_df[CanonicalField.STATUS.value].astype("string").fillna("").str.strip()
    )
    matched = period_df.loc[statuses == target_status.value]
    return (
        0 if matched.empty else int(matched[CanonicalField.GROSS_REVENUE.value].sum())
    )


def _build_breakdown(
    period_df: pd.DataFrame,
    gross: int,
    fees: int | None,
    shipping: int | None,
    net: int | None,
) -> FinancialBreakdown:
    cancelled = _sum_status_cents(period_df, OrderStatus.CANCELLED)
    returned = _sum_status_cents(period_df, OrderStatus.RETURNED)
    return FinancialBreakdown(
        gross_revenue=cents_to_brl_decimal(gross),
        fees_total=_opt_brl(fees),
        shipping_total=_opt_brl(shipping),
        net_revenue=_opt_brl(net),
        cancelled_revenue=cents_to_brl_decimal(cancelled),
        returned_revenue=cents_to_brl_decimal(returned),
        fees_pct=_compute_ratio(fees, gross),
        shipping_pct=_compute_ratio(shipping, gross),
        net_margin_pct=_compute_ratio(net, gross),
    )


def compute_financial_breakdown(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> FinancialBreakdown:
    """Compute gross-to-net revenue decomposition and cancellation/return losses."""
    validate_canonical_dataframe(dataframe, required_fields=_BREAKDOWN_REQUIRED_FIELDS)
    period_df = filter_by_period(dataframe, start_date, end_date)
    sales_df = filter_sales(period_df, exclude_statuses=exclude_statuses)
    gross = (
        0 if sales_df.empty else int(sales_df[CanonicalField.GROSS_REVENUE.value].sum())
    )
    fees = _sum_optional_cents(sales_df, CanonicalField.FEES)
    shipping = _sum_optional_cents(sales_df, CanonicalField.SHIPPING_COST)
    net = _sum_optional_cents(sales_df, CanonicalField.NET_REVENUE)
    return _build_breakdown(period_df, gross, fees, shipping, net)


def _attach_optional_cols(
    cols: dict[str, pd.Series[Any]],
    scoped: pd.DataFrame,
    sale_mask: pd.Series[Any],
) -> None:
    sku_col = CanonicalField.SKU.value
    if sku_col in scoped.columns:
        cleaned = scoped[sku_col].astype("string").str.strip()
        cols["_sku"] = cleaned.mask(cleaned == "", pd.NA)
    for target, field in (
        ("_sale_fees", CanonicalField.FEES),
        ("_sale_shipping", CanonicalField.SHIPPING_COST),
        ("_sale_net", CanonicalField.NET_REVENUE),
    ):
        if field.value in scoped.columns:
            cols[target] = scoped[field.value].where(sale_mask, pd.NA)


def _diagnostic_working_frame(
    period_df: pd.DataFrame, excluded: tuple[str, ...]
) -> pd.DataFrame:
    names = (
        period_df[CanonicalField.PRODUCT_NAME.value]
        .astype("string")
        .fillna("")
        .str.strip()
    )
    scoped = period_df.loc[names != ""]
    if scoped.empty:
        return pd.DataFrame()
    statuses = (
        scoped[CanonicalField.STATUS.value].astype("string").fillna("").str.strip()
    )
    order_keys = build_order_key_series(scoped)
    sale_mask = ~statuses.isin(excluded)
    cols: dict[str, pd.Series[Any]] = {
        "_product_key": names.loc[scoped.index],
        "_order_key": order_keys,
        "_cancel_key": order_keys.where(statuses == OrderStatus.CANCELLED.value, pd.NA),
        "_return_key": order_keys.where(statuses == OrderStatus.RETURNED.value, pd.NA),
        "_sale_order_key": order_keys.where(sale_mask, pd.NA),
        "_sale_qty": scoped[CanonicalField.QUANTITY.value].where(sale_mask, 0),
        "_sale_gross": scoped[CanonicalField.GROSS_REVENUE.value].where(sale_mask, 0),
    }
    _attach_optional_cols(cols, scoped, sale_mask)
    return pd.DataFrame(cols, index=scoped.index)


def _build_diagnostic_row(
    name: str,
    sku: str | None,
    counts: tuple[int, int, int, int, int],
    money: tuple[int, int | None, int | None, int | None],
) -> ProductDiagnosticRow:
    sold_qty, sale_orders, total_orders, cancelled, returned = counts
    gross_cents, fees_cents, shipping_cents, net_cents = money
    return ProductDiagnosticRow(
        product_name=name,
        sku=sku,
        sold_quantity=sold_qty,
        order_count=sale_orders,
        total_orders=total_orders,
        gross_revenue=cents_to_brl_decimal(gross_cents),
        fees_total=_opt_brl(fees_cents),
        shipping_total=_opt_brl(shipping_cents),
        net_revenue=_opt_brl(net_cents),
        net_margin_pct=_compute_ratio(net_cents, gross_cents),
        cancelled_orders=cancelled,
        returned_orders=returned,
        cancellation_rate=(cancelled / total_orders) if total_orders > 0 else 0.0,
    )


def _extract_diag_extras(
    grouped: Any, working: pd.DataFrame, n_rows: int
) -> tuple[list[str | None], list[int | None], list[int | None], list[int | None]]:
    return (
        extract_optional_str_first(grouped, "_sku", n_rows, enabled="_sku" in working),
        extract_optional_int_sums(
            grouped, "_sale_fees", n_rows, enabled="_sale_fees" in working
        ),
        extract_optional_int_sums(
            grouped, "_sale_shipping", n_rows, enabled="_sale_shipping" in working
        ),
        extract_optional_int_sums(
            grouped, "_sale_net", n_rows, enabled="_sale_net" in working
        ),
    )


def _group_product_diagnostics(working: pd.DataFrame) -> list[ProductDiagnosticRow]:
    grouped = working.groupby("_product_key", observed=True, sort=False)
    agg_df = grouped.agg(
        total_orders=("_order_key", "nunique"),
        cancelled_orders=("_cancel_key", "nunique"),
        returned_orders=("_return_key", "nunique"),
        sale_orders=("_sale_order_key", "nunique"),
        sold_qty=("_sale_qty", "sum"),
        gross_cents=("_sale_gross", "sum"),
    )
    skus, fees, shipping, nets = _extract_diag_extras(grouped, working, len(agg_df))
    rows: list[ProductDiagnosticRow] = []
    for idx, product_name in enumerate(agg_df.index.tolist()):
        counts = (
            int(agg_df["sold_qty"].iloc[idx]),
            int(agg_df["sale_orders"].iloc[idx]),
            int(agg_df["total_orders"].iloc[idx]),
            int(agg_df["cancelled_orders"].iloc[idx]),
            int(agg_df["returned_orders"].iloc[idx]),
        )
        money = (
            int(agg_df["gross_cents"].iloc[idx]),
            fees[idx],
            shipping[idx],
            nets[idx],
        )
        rows.append(_build_diagnostic_row(str(product_name), skus[idx], counts, money))
    return rows


def analyze_product_diagnostics(
    dataframe: pd.DataFrame,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
    limit: int | None = None,
) -> list[ProductDiagnosticRow]:
    """Compute per-product margin, deduction, and cancellation diagnostics."""
    validate_canonical_dataframe(dataframe, required_fields=CORE_ANALYTICS_FIELDS)
    if limit is not None and limit <= 0:
        raise ValueError("limit deve ser maior que zero.")
    excluded = normalize_excluded_statuses(exclude_statuses)
    period_df = filter_by_period(dataframe, start_date, end_date)
    if period_df.empty:
        return []
    working = _diagnostic_working_frame(period_df, excluded)
    if working.empty:
        return []
    rows = _group_product_diagnostics(working)
    rows.sort(key=lambda r: (-r.gross_revenue, -r.cancelled_orders, r.product_name))
    return rows if limit is None else rows[:limit]


__all__ = [
    "FinancialBreakdown",
    "ProductDiagnosticRow",
    "analyze_product_diagnostics",
    "compute_financial_breakdown",
]
