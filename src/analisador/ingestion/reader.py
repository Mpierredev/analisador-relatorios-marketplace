"""In-memory CSV and XLSX ingestion into raw pandas DataFrames."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

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
from analisador.ingestion.xlsx import list_xlsx_sheet_names, read_xlsx_sheet

logger = logging.getLogger(__name__)


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


def _read_xlsx(
    content: bytes,
    max_rows: int,
    *,
    sheet_name: str | None = None,
) -> IngestionResult:
    dataframe, header_row_index, resolved_title = read_xlsx_sheet(
        content,
        max_rows,
        _format_row_limit_error,
        sheet_name=sheet_name,
    )
    return IngestionResult(
        dataframe=dataframe,
        extension=".xlsx",
        header_row_index=header_row_index,
        sheet_name=resolved_title,
    )


def list_xlsx_sheets(
    content: bytes,
    *,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> tuple[str, ...]:
    """List available worksheet names in an XLSX file within size limits."""
    _validate_inputs(content, "planilha.xlsx", max_file_size_bytes, MAX_ROWS)
    return list_xlsx_sheet_names(content)


def read_report_with_metadata(
    content: bytes,
    filename: str,
    *,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    max_rows: int = MAX_ROWS,
    sheet_name: str | None = None,
) -> IngestionResult:
    """Read raw CSV or XLSX bytes into a string DataFrame with metadata."""
    extension = _validate_inputs(content, filename, max_file_size_bytes, max_rows)
    result = (
        _read_csv(content, max_rows)
        if extension == ".csv"
        else _read_xlsx(content, max_rows, sheet_name=sheet_name)
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
    sheet_name: str | None = None,
) -> pd.DataFrame:
    """Read raw CSV or XLSX bytes and return a raw string DataFrame."""
    return read_report_with_metadata(
        content,
        filename,
        max_file_size_bytes=max_file_size_bytes,
        max_rows=max_rows,
        sheet_name=sheet_name,
    ).dataframe


__all__ = [
    "IngestionResult",
    "list_xlsx_sheets",
    "read_report",
    "read_report_with_metadata",
]
