"""In-memory CSV and XLSX ingestion into raw pandas DataFrames."""

import csv
import io
import itertools
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final
from zipfile import BadZipFile

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from analisador.core.config import (
    BYTES_PER_MEGABYTE,
    HEADER_SCAN_MAX_ROWS,
    MAX_FILE_SIZE_BYTES,
    MAX_ROWS,
    SUPPORTED_EXTENSIONS,
)
from analisador.core.errors import (
    FileTooLargeError,
    HeaderNotFoundError,
    UnsupportedFileError,
)
from analisador.ingestion.encoding import decode_text
from analisador.ingestion.structure import detect_header_row, detect_separator

logger = logging.getLogger(__name__)

_XLSX_READ_ERRORS: Final[tuple[type[Exception], ...]] = (
    InvalidFileException,
    BadZipFile,
    KeyError,
    OSError,
    ValueError,
)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Raw DataFrame and technical metadata produced during ingestion."""

    dataframe: pd.DataFrame
    extension: str
    header_row_index: int
    encoding: str | None = None
    separator: str | None = None
    sheet_name: str | None = None


def _validate_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _format_size_limit(max_file_size_bytes: int) -> str:
    if max_file_size_bytes % BYTES_PER_MEGABYTE == 0:
        return f"{max_file_size_bytes // BYTES_PER_MEGABYTE} MB"
    return f"{max_file_size_bytes / BYTES_PER_MEGABYTE:.1f} MB"


def _format_row_limit_error(max_rows: int) -> FileTooLargeError:
    formatted_rows = f"{max_rows:,}".replace(",", ".")
    return FileTooLargeError(
        f"O relatório ultrapassa o limite de {formatted_rows} linhas.",
        suggestion="Exporte um período menor para manter o arquivo dentro do limite.",
    )


def _validate_inputs(
    content: bytes,
    filename: str,
    max_file_size_bytes: int,
    max_rows: int,
) -> str:
    _validate_positive_int("max_file_size_bytes", max_file_size_bytes)
    _validate_positive_int("max_rows", max_rows)

    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            "Formato de arquivo não suportado.",
            suggestion="Envie um arquivo válido com extensão .csv ou .xlsx.",
        )
    if len(content) > max_file_size_bytes:
        limit_label = _format_size_limit(max_file_size_bytes)
        raise FileTooLargeError(
            f"O arquivo ultrapassa o limite de {limit_label}.",
            suggestion="Reduza o período exportado ou envie um arquivo menor.",
        )
    if not content:
        raise HeaderNotFoundError(
            "O arquivo enviado está vazio.",
            suggestion="Envie uma planilha com linha de cabeçalho e dados de vendas.",
        )
    return extension


def _sample_csv_rows(text: str, separator: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in io.StringIO(text):
        if not line.strip():
            rows.append([])
        else:
            rows.append(next(csv.reader([line], delimiter=separator), []))
        if len(rows) >= HEADER_SCAN_MAX_ROWS:
            break
    return rows


def _parse_csv_dataframe(
    text: str,
    separator: str,
    header_row_index: int,
    max_rows: int,
) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(
            io.StringIO(text),
            sep=separator,
            header=0,
            skiprows=header_row_index,
            dtype=str,
            keep_default_na=False,
            nrows=max_rows + 1,
        )
    except pd.errors.EmptyDataError as exc:
        raise HeaderNotFoundError() from exc
    except pd.errors.ParserError as exc:
        raise UnsupportedFileError(
            "Não foi possível interpretar a estrutura do arquivo CSV.",
            suggestion="Verifique se há aspas desbalanceadas ou arquivo corrompido.",
        ) from exc

    if len(dataframe) > max_rows:
        raise _format_row_limit_error(max_rows)
    dataframe.columns = pd.Index([str(col).strip() for col in dataframe.columns])
    return dataframe


def _read_csv(content: bytes, max_rows: int) -> IngestionResult:
    text, encoding = decode_text(content)
    separator = detect_separator(text)
    sample_rows = _sample_csv_rows(text, separator)
    header_row_index = detect_header_row(sample_rows)
    dataframe = _parse_csv_dataframe(text, separator, header_row_index, max_rows)
    return IngestionResult(
        dataframe=dataframe,
        extension=".csv",
        header_row_index=header_row_index,
        encoding=encoding,
        separator=separator,
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
) -> list[list[str]]:
    data_rows: list[list[str]] = []
    for row in remaining_rows:
        if not any(cell.strip() for cell in row):
            continue
        if len(data_rows) >= max_rows:
            raise _format_row_limit_error(max_rows)
        if len(row) < column_count:
            aligned = [*row, *([""] * (column_count - len(row)))]
        else:
            aligned = row[:column_count]
        data_rows.append(aligned)
    return data_rows


def _open_xlsx_workbook(content: bytes) -> Workbook:
    try:
        return load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except _XLSX_READ_ERRORS as exc:
        raise UnsupportedFileError(
            "Não foi possível abrir o arquivo .xlsx.",
            suggestion="Confirme se a planilha está íntegra e sem proteção por senha.",
        ) from exc


def _read_xlsx(content: bytes, max_rows: int) -> IngestionResult:
    workbook = _open_xlsx_workbook(content)
    try:
        if not workbook.worksheets:
            raise HeaderNotFoundError()
        sheet = workbook.worksheets[0]
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
        data_rows = _collect_xlsx_rows(remaining, len(headers), max_rows)
        sheet_name = str(sheet.title)
    finally:
        workbook.close()

    return IngestionResult(
        dataframe=pd.DataFrame(data_rows, columns=headers),
        extension=".xlsx",
        header_row_index=header_row_index,
        sheet_name=sheet_name,
    )


def read_report_with_metadata(
    content: bytes,
    filename: str,
    *,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    max_rows: int = MAX_ROWS,
) -> IngestionResult:
    """Read raw CSV or XLSX bytes into a string DataFrame with metadata."""
    extension = _validate_inputs(content, filename, max_file_size_bytes, max_rows)
    result = (
        _read_csv(content, max_rows)
        if extension == ".csv"
        else _read_xlsx(content, max_rows)
    )
    logger.info(
        "Relatório lido em memória: extensao=%s bytes=%d linhas=%d colunas=%d "
        "cabecalho=%d",
        result.extension,
        len(content),
        len(result.dataframe),
        len(result.dataframe.columns),
        result.header_row_index,
    )
    return result


def read_report(
    content: bytes,
    filename: str,
    *,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    max_rows: int = MAX_ROWS,
) -> pd.DataFrame:
    """Read raw CSV or XLSX bytes and return a raw string DataFrame."""
    return read_report_with_metadata(
        content,
        filename,
        max_file_size_bytes=max_file_size_bytes,
        max_rows=max_rows,
    ).dataframe


__all__ = [
    "IngestionResult",
    "read_report",
    "read_report_with_metadata",
]
