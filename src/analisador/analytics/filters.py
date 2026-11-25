"""Canonical DataFrame validation, slicing, and monetary conversion helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

import pandas as pd

from analisador.core.config import CENTS_PER_UNIT
from analisador.core.enums import CanonicalField, OrderStatus
from analisador.core.errors import MissingRequiredColumnsError

DEFAULT_EXCLUDED_STATUSES: Final[tuple[OrderStatus, ...]] = (
    OrderStatus.CANCELLED,
    OrderStatus.RETURNED,
)
CORE_ANALYTICS_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.STATUS,
    CanonicalField.PRODUCT_NAME,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
)
_CENT_QUANTIZER: Final[Decimal] = Decimal("0.01")
_CENTS_DIVISOR: Final[Decimal] = Decimal(CENTS_PER_UNIT)
_DAY_END_TIME: Final[time] = time(23, 59, 59, 999999)


def cents_to_brl_decimal(cents: int | Decimal) -> Decimal:
    """Convert an integer cents amount to a 2-decimal-place BRL Decimal."""
    amount = Decimal(cents) / _CENTS_DIVISOR
    return amount.quantize(_CENT_QUANTIZER, rounding=ROUND_HALF_UP)


def build_order_key_series(dataframe: pd.DataFrame) -> pd.Series[Any]:
    """Return a per-row order identifier series treating nulls as distinct."""
    order_col = CanonicalField.ORDER_ID.value
    if order_col not in dataframe.columns:
        return pd.Series(range(len(dataframe)), index=dataframe.index, dtype="int64")
    order_ids: pd.Series[Any] = dataframe[order_col].astype("string")
    null_mask = order_ids.isna()
    if not null_mask.any():
        return order_ids
    fallback = pd.Series(
        [f"na:{pos}" for pos in range(len(dataframe))],
        index=dataframe.index,
        dtype="string",
    )
    prefixed = "id:" + order_ids.fillna("")
    return prefixed.where(~null_mask, fallback)


def count_unique_orders(dataframe: pd.DataFrame) -> int:
    """Count distinct orders using order_id, accounting for any null entries."""
    if dataframe.empty:
        return 0
    order_col = CanonicalField.ORDER_ID.value
    if order_col not in dataframe.columns:
        return len(dataframe)
    order_ids: pd.Series[Any] = dataframe[order_col]
    null_count = int(order_ids.isna().sum())
    unique_non_null = int(order_ids.dropna().nunique())
    return unique_non_null + null_count


def validate_canonical_dataframe(
    dataframe: pd.DataFrame,
    *,
    required_fields: Sequence[CanonicalField] = CORE_ANALYTICS_FIELDS,
) -> None:
    """Verify that dataframe is a pandas DataFrame containing required fields."""
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("O conjunto de dados deve ser um DataFrame do pandas.")
    missing = [
        field.value for field in required_fields if field.value not in dataframe.columns
    ]
    if missing:
        raise MissingRequiredColumnsError(missing)


def normalize_excluded_statuses(
    exclude_statuses: Sequence[OrderStatus | str],
) -> tuple[str, ...]:
    """Convert status values into canonical string values and validate them."""
    normalized: list[str] = []
    for item in exclude_statuses:
        if isinstance(item, OrderStatus):
            normalized.append(item.value)
            continue
        try:
            normalized.append(OrderStatus(str(item).strip()).value)
        except ValueError as exc:
            raise ValueError(
                f"Status de pedido inválido para filtro: {item!r}."
            ) from exc
    return tuple(dict.fromkeys(normalized))


def _coerce_bound_timestamp(
    bound: date | datetime,
    *,
    is_end: bool,
    target_tz: Any,
) -> pd.Timestamp:
    """Convert a date or datetime bound into a Timestamp aligned to target_tz."""
    if isinstance(bound, datetime):
        timestamp = pd.Timestamp(bound)
    else:
        bound_time = _DAY_END_TIME if is_end else time.min
        timestamp = pd.Timestamp(datetime.combine(bound, bound_time))

    if target_tz is None:
        return (
            timestamp.tz_localize(None) if timestamp.tzinfo is not None else timestamp
        )
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(target_tz)
    return timestamp.tz_convert(target_tz)


def resolve_period_bounds(
    dataframe: pd.DataFrame,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Resolve optional date/datetime boundaries aligned with order_date timezone."""
    validate_canonical_dataframe(
        dataframe,
        required_fields=(CanonicalField.ORDER_DATE,),
    )
    order_dates = pd.to_datetime(
        dataframe[CanonicalField.ORDER_DATE.value],
        errors="coerce",
    )
    target_tz = getattr(order_dates.dt, "tz", None)
    start_ts = (
        None
        if start_date is None
        else _coerce_bound_timestamp(start_date, is_end=False, target_tz=target_tz)
    )
    end_ts = (
        None
        if end_date is None
        else _coerce_bound_timestamp(end_date, is_end=True, target_tz=target_tz)
    )
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise ValueError(
            "A data inicial do período não pode ser posterior à data final."
        )
    return start_ts, end_ts


def filter_by_period(
    dataframe: pd.DataFrame,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
) -> pd.DataFrame:
    """Return a copy filtered to the inclusive [start_date, end_date] window."""
    start_ts, end_ts = resolve_period_bounds(dataframe, start_date, end_date)
    if start_ts is None and end_ts is None:
        return dataframe.copy()

    order_dates = pd.to_datetime(
        dataframe[CanonicalField.ORDER_DATE.value],
        errors="coerce",
    )
    mask: pd.Series[Any] = order_dates.notna()
    if start_ts is not None:
        mask = mask & (order_dates >= start_ts)
    if end_ts is not None:
        mask = mask & (order_dates <= end_ts)
    return dataframe.loc[mask].copy()


def filter_sales(
    dataframe: pd.DataFrame,
    *,
    exclude_statuses: Sequence[OrderStatus | str] = DEFAULT_EXCLUDED_STATUSES,
) -> pd.DataFrame:
    """Return rows excluding cancelled, returned, or caller-specified statuses."""
    validate_canonical_dataframe(
        dataframe,
        required_fields=(CanonicalField.STATUS,),
    )
    excluded_values = normalize_excluded_statuses(exclude_statuses)
    if not excluded_values:
        return dataframe.copy()
    status_series = dataframe[CanonicalField.STATUS.value].astype("string").str.strip()
    return dataframe.loc[~status_series.isin(excluded_values)].copy()


__all__ = [
    "CORE_ANALYTICS_FIELDS",
    "DEFAULT_EXCLUDED_STATUSES",
    "build_order_key_series",
    "cents_to_brl_decimal",
    "count_unique_orders",
    "filter_by_period",
    "filter_sales",
    "normalize_excluded_statuses",
    "resolve_period_bounds",
    "validate_canonical_dataframe",
]
