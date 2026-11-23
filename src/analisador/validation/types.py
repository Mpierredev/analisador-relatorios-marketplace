"""Column logical type inference for raw DataFrames."""

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Final

import pandas as pd

from analisador.core.config import TYPE_INFERENCE_SAMPLE_ROWS

_TYPE_MATCH_RATIO: Final[float] = 0.75
_MAX_QUANTITY_HINT: Final[int] = 10_000
_CATEGORY_MAX_UNIQUE: Final[int] = 5
_CATEGORY_MIN_SAMPLES: Final[int] = 4
_CATEGORY_MAX_AVG_LENGTH: Final[int] = 25

_PT_MONTHS: Final[frozenset[str]] = frozenset(
    {
        "janeiro",
        "fevereiro",
        "março",
        "marco",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    }
)
_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)
_BR_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{2}[/-]\d{2}[/-]\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?$"
)
_PT_TEXT_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{1,2}\s+de\s+(?P<month>[a-zç]+)\s+de\s+\d{4}"
    r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:h|hs\.?)?)?$",
    re.IGNORECASE,
)
_LEADING_ZERO_ID_RE: Final[re.Pattern[str]] = re.compile(r"^0\d+$")
_LONG_NUMERIC_ID_RE: Final[re.Pattern[str]] = re.compile(r"^\d{8,}$")
_ALNUM_CODE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9._/#-]+$"
)
_INT_QUANTITY_RE: Final[re.Pattern[str]] = re.compile(r"^(\d+)(?:\.0+)?$")
_CURRENCY_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^[+-]?\s*(?:r\$|us\$|\$|€|brl|usd)\s*",
    re.IGNORECASE,
)
_BR_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"^[+-]?(?:\d{1,3}(?:\.\d{3})*|\d+)(?:,\d{1,4})$"
)
_US_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"^[+-]?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,4})$"
)
_SIGNED_INT_RE: Final[re.Pattern[str]] = re.compile(r"^[+-]?\d+$")


class InferredColumnType(StrEnum):
    """Logical column type inferred from sample values."""

    DATE = "date"
    INTEGER = "integer"
    MONETARY = "monetary"
    IDENTIFIER = "identifier"
    CATEGORY = "category"
    TEXT = "text"
    EMPTY = "empty"


def _is_date(value: str) -> bool:
    if _ISO_DATE_RE.match(value) or _BR_DATE_RE.match(value):
        return True
    pt_match = _PT_TEXT_DATE_RE.match(value)
    return pt_match is not None and pt_match.group("month").lower() in _PT_MONTHS


def _is_identifier(value: str) -> bool:
    if _LEADING_ZERO_ID_RE.match(value) or _LONG_NUMERIC_ID_RE.match(value):
        return True
    if _CURRENCY_PREFIX_RE.match(value):
        return False
    return bool(_ALNUM_CODE_RE.match(value))


def _is_integer_quantity(value: str) -> bool:
    match = _INT_QUANTITY_RE.match(value)
    if match is None:
        return False
    int_part = match.group(1)
    if len(int_part) > 1 and int_part[0] == "0":
        return False
    return 1 <= int(int_part) <= _MAX_QUANTITY_HINT


def _is_monetary(value: str) -> bool:
    inner = (
        value[1:-1].strip() if value.startswith("(") and value.endswith(")") else value
    )
    had_currency = bool(_CURRENCY_PREFIX_RE.match(inner))
    cleaned = _CURRENCY_PREFIX_RE.sub("", inner).strip()
    if _BR_NUMBER_RE.match(cleaned) or _US_NUMBER_RE.match(cleaned):
        return True
    if _SIGNED_INT_RE.match(cleaned):
        return had_currency or value.startswith(("-", "("))
    return False


def infer_column_type(values: Sequence[str]) -> InferredColumnType:
    """Infer a column's logical type from non-empty string values."""
    cleaned = [item.strip() for item in values if item.strip()]
    if not cleaned:
        return InferredColumnType.EMPTY

    total = len(cleaned)
    checks = (
        (InferredColumnType.DATE, _is_date),
        (InferredColumnType.IDENTIFIER, _is_identifier),
        (InferredColumnType.INTEGER, _is_integer_quantity),
        (InferredColumnType.MONETARY, _is_monetary),
    )
    for inferred, predicate in checks:
        if sum(predicate(item) for item in cleaned) / total >= _TYPE_MATCH_RATIO:
            return inferred

    avg_length = sum(len(item) for item in cleaned) / total
    unique_count = len({item.casefold() for item in cleaned})
    if (
        total >= _CATEGORY_MIN_SAMPLES
        and unique_count <= _CATEGORY_MAX_UNIQUE
        and avg_length <= _CATEGORY_MAX_AVG_LENGTH
    ):
        return InferredColumnType.CATEGORY
    return InferredColumnType.TEXT


def sample_dataframe_columns(
    dataframe: pd.DataFrame,
    sample_rows: int,
) -> dict[str, list[str]]:
    """Extract up to sample_rows trimmed non-empty strings per column."""
    if isinstance(sample_rows, bool) or sample_rows <= 0:
        raise ValueError("sample_rows must be a positive integer.")

    samples: dict[str, list[str]] = {}
    for col_idx, col_name in enumerate(dataframe.columns):
        series = dataframe.iloc[:, col_idx].astype(str).str.strip()
        non_empty = series[series != ""]
        raw_list: Sequence[object] = non_empty.head(sample_rows).tolist()
        samples[str(col_name)] = [str(item) for item in raw_list]
    return samples


def infer_dataframe_types(
    dataframe: pd.DataFrame,
    *,
    sample_rows: int = TYPE_INFERENCE_SAMPLE_ROWS,
) -> Mapping[str, InferredColumnType]:
    """Infer logical column types across all columns of a raw DataFrame."""
    samples = sample_dataframe_columns(dataframe, sample_rows)
    return {col: infer_column_type(values) for col, values in samples.items()}


__all__ = [
    "InferredColumnType",
    "infer_column_type",
    "infer_dataframe_types",
    "sample_dataframe_columns",
]
