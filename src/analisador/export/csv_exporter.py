"""In-memory CSV exporter for canonical sales DataFrames."""

from __future__ import annotations

import io
from typing import Any, Final

import numpy as np
import pandas as pd

from analisador.analytics import validate_canonical_dataframe
from analisador.core.config import CENTS_PER_UNIT, UTF8_BOM_ENCODING
from analisador.core.enums import CanonicalField
from analisador.core.schema import CANONICAL_COLUMNS

_MONETARY_COLUMNS: Final[tuple[str, ...]] = (
    CanonicalField.UNIT_PRICE.value,
    CanonicalField.GROSS_REVENUE.value,
    CanonicalField.FEES.value,
    CanonicalField.SHIPPING_COST.value,
    CanonicalField.NET_REVENUE.value,
)


def _format_cents_column(series: pd.Series[Any]) -> pd.Series[Any]:
    if series.empty:
        return pd.Series([], index=series.index, dtype="string")
    numeric = pd.to_numeric(series, errors="coerce").astype("Int64")
    valid = numeric.notna()
    result = pd.Series("", index=series.index, dtype="string")
    if not valid.any():
        return result
    vals = numeric.loc[valid].astype("int64")
    abs_vals = vals.abs()
    reais = (abs_vals // CENTS_PER_UNIT).astype("string")
    centavos = (abs_vals % CENTS_PER_UNIT).astype("string").str.zfill(2)
    signs = pd.Series(
        np.where(vals.to_numpy() < 0, "-", ""), index=vals.index, dtype="string"
    )
    result.loc[valid] = signs + reais + "." + centavos
    return result


def export_canonical_csv(
    canonical_df: pd.DataFrame,
    *,
    include_bom: bool = True,
) -> bytes:
    """Serialize a canonical DataFrame to CSV bytes with decimal BRL values."""
    validate_canonical_dataframe(canonical_df)
    export_df = canonical_df.copy()

    date_col = CanonicalField.ORDER_DATE.value
    if not export_df.empty:
        parsed_dates = pd.to_datetime(export_df[date_col], errors="coerce")
        export_df[date_col] = parsed_dates.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")

    for column in _MONETARY_COLUMNS:
        if column in export_df.columns:
            export_df[column] = _format_cents_column(export_df[column])

    ordered = [col.value for col in CANONICAL_COLUMNS if col.value in export_df.columns]
    extras = [str(col) for col in export_df.columns if str(col) not in ordered]
    export_df = export_df[[*ordered, *extras]]

    buffer = io.StringIO()
    export_df.to_csv(buffer, index=False, na_rep="")
    encoding = UTF8_BOM_ENCODING if include_bom else "utf-8"
    return buffer.getvalue().encode(encoding)


__all__ = ["export_canonical_csv"]
