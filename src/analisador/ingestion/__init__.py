"""In-memory file ingestion, encoding detection, and structure discovery."""

from analisador.ingestion.encoding import decode_text, detect_encoding
from analisador.ingestion.reader import (
    IngestionResult,
    read_report,
    read_report_with_metadata,
)
from analisador.ingestion.structure import detect_header_row, detect_separator

__all__ = [
    "IngestionResult",
    "decode_text",
    "detect_encoding",
    "detect_header_row",
    "detect_separator",
    "read_report",
    "read_report_with_metadata",
]
