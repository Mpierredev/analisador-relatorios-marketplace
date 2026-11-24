"""In-memory XLSX workbook helpers supporting multi-sheet selection."""

from __future__ import annotations

import io
import itertools
import warnings
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from typing import Any, Final
from zipfile import BadZipFile

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from analisador.core.config import HEADER_SCAN_MAX_ROWS
from analisador.core.errors import (
    FileTooLargeError,
    HeaderNotFoundError,
    UnsupportedFileError,
)
from analisador.ingestion.structure import detect_header_row

_XLSX_READ_ERRORS: Final[tuple[type[Exception], ...]] = (
    InvalidFileException,
    BadZipFile,
    KeyError,
    OSError,
    ValueError,
)


def _stringify_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _stringify_row(row: Sequence[object]) -> list[str]:
    return [_stringify_cell(cell) for cell in row]


def _normalize_headers(raw_header: Sequence[str]) -> list[str]:
    trimmed = list(raw_header)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    counts: dict[str, int] = {}
    headers: list[str] = []
    for idx, cell in enumerate(trimmed):
        base = cell.strip() or f"coluna_{idx + 1}"
        seen = counts.get(base, 0)
        counts[base] = seen + 1
        headers.append(base if seen == 0 else f"{base}.{seen}")
    return headers


def _collect_xlsx_rows(
    remaining_rows: Iterable[list[str]],
    column_count: int,
    max_rows: int,
    limit_error_factory: Callable[[int], FileTooLargeError],
) -> list[list[str]]:
    data_rows: list[list[str]] = []
    for row in remaining_rows:
        if not any(cell.strip() for cell in row):
            continue
        if len(data_rows) >= max_rows:
            raise limit_error_factory(max_rows)
        aligned = (
            [*row, *([""] * (column_count - len(row)))]
            if len(row) < column_count
            else row[:column_count]
        )
        data_rows.append(aligned)
    return data_rows


def open_xlsx_workbook(content: bytes) -> Workbook:
    """Open an XLSX workbook read-only from bytes, silencing benign style noise."""
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Workbook contains no default style.*",
                category=UserWarning,
            )
            return load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except _XLSX_READ_ERRORS as exc:
        raise UnsupportedFileError(
            "Não foi possível abrir o arquivo .xlsx.",
            suggestion="Confirme se a planilha está íntegra e sem proteção por senha.",
        ) from exc


def list_xlsx_sheet_names(content: bytes) -> tuple[str, ...]:
    """Return worksheet names present in an XLSX workbook."""
    workbook = open_xlsx_workbook(content)
    try:
        return tuple(str(name) for name in workbook.sheetnames)
    finally:
        workbook.close()


def _select_worksheet(workbook: Workbook, sheet_name: str | None) -> Any:
    if not workbook.worksheets:
        raise HeaderNotFoundError()
    if sheet_name is None:
        return workbook.worksheets[0]
    available = [str(name) for name in workbook.sheetnames]
    if sheet_name not in available:
        joined = ", ".join(available)
        raise UnsupportedFileError(
            f"Aba '{sheet_name}' não encontrada na planilha.",
            suggestion=f"Escolha uma das abas disponíveis: {joined}.",
        )
    return workbook[sheet_name]


def read_xlsx_sheet(
    content: bytes,
    max_rows: int,
    limit_error_factory: Callable[[int], FileTooLargeError],
    *,
    sheet_name: str | None = None,
) -> tuple[pd.DataFrame, int, str]:
    """Read a selected (or first) worksheet from XLSX bytes into a raw DataFrame."""
    workbook = open_xlsx_workbook(content)
    try:
        sheet = _select_worksheet(workbook, sheet_name)
        rows_iter = sheet.iter_rows(values_only=True)
        sample_rows = [
            _stringify_row(raw)
            for raw in itertools.islice(rows_iter, HEADER_SCAN_MAX_ROWS)
        ]
        header_row_index = detect_header_row(sample_rows)
        headers = _normalize_headers(sample_rows[header_row_index])
        remaining = itertools.chain(
            sample_rows[header_row_index + 1 :],
            (_stringify_row(raw) for raw in rows_iter),
        )
        data_rows = _collect_xlsx_rows(
            remaining, len(headers), max_rows, limit_error_factory
        )
        resolved_title = str(sheet.title)
    finally:
        workbook.close()
    return pd.DataFrame(data_rows, columns=headers), header_row_index, resolved_title


__all__ = ["list_xlsx_sheet_names", "open_xlsx_workbook", "read_xlsx_sheet"]
