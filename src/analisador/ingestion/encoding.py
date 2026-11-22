"""Character encoding detection and text decoding for CSV byte payloads."""

import codecs
from typing import Final

from charset_normalizer import from_bytes

from analisador.core.config import (
    ENCODING_SAMPLE_BYTES,
    FALLBACK_ENCODINGS,
    UTF8_BOM_ENCODING,
)
from analisador.core.errors import UnsupportedFileError

_UTF16_BOMS: Final[tuple[bytes, ...]] = (
    codecs.BOM_UTF16_LE,
    codecs.BOM_UTF16_BE,
)
_TRUSTED_NORMALIZED_ENCODINGS: Final[frozenset[str]] = frozenset(
    {
        "utf-8",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "cp1252",
        "iso8859-1",
        "iso8859-15",
    }
)


def _can_decode(content: bytes, encoding: str) -> bool:
    try:
        content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return False
    return True


def _detect_bom_encoding(content: bytes) -> str | None:
    if content.startswith(codecs.BOM_UTF8):
        if _can_decode(content, UTF8_BOM_ENCODING):
            return UTF8_BOM_ENCODING
        raise UnsupportedFileError(
            "O arquivo possui marcador UTF-8 inválido ou corrompido.",
            suggestion="Salve o arquivo CSV novamente em UTF-8 e envie de novo.",
        )

    if content.startswith(_UTF16_BOMS):
        if _can_decode(content, "utf-16"):
            return "utf-16"
        raise UnsupportedFileError(
            "O arquivo possui codificação UTF-16 inválida ou corrompida.",
            suggestion="Exporte o relatório em UTF-8 ou .xlsx e tente novamente.",
        )
    return None


def _detect_with_normalizer(content: bytes) -> str | None:
    best = from_bytes(content[:ENCODING_SAMPLE_BYTES]).best()
    if best is None:
        return None
    try:
        normalized = codecs.lookup(best.encoding).name
    except LookupError:
        return None
    if normalized in _TRUSTED_NORMALIZED_ENCODINGS and _can_decode(
        content, best.encoding
    ):
        return best.encoding
    return None


def detect_encoding(content: bytes) -> str:
    """Detect a valid text encoding for raw CSV bytes."""
    if not content:
        return "utf-8"

    bom_encoding = _detect_bom_encoding(content)
    if bom_encoding is not None:
        return bom_encoding

    if b"\x00" in content:
        raise UnsupportedFileError(
            "O arquivo parece ser binário e não um CSV válido.",
            suggestion="Envie um arquivo de texto CSV válido ou uma planilha .xlsx.",
        )

    if _can_decode(content, "utf-8"):
        return "utf-8"

    normalized_encoding = _detect_with_normalizer(content)
    if normalized_encoding is not None:
        return normalized_encoding

    for encoding in FALLBACK_ENCODINGS:
        if _can_decode(content, encoding):
            return encoding

    raise UnsupportedFileError(
        "Não foi possível identificar a codificação do arquivo CSV.",
        suggestion="Salve o arquivo em UTF-8 ou Latin-1 e tente novamente.",
    )


def decode_text(content: bytes) -> tuple[str, str]:
    """Decode raw CSV bytes and return the decoded text with its encoding."""
    encoding = detect_encoding(content)
    try:
        return content.decode(encoding), encoding
    except (UnicodeDecodeError, LookupError) as exc:
        raise UnsupportedFileError(
            "Não foi possível decodificar o arquivo CSV.",
            suggestion="Salve o arquivo em UTF-8 ou Latin-1 e tente novamente.",
        ) from exc


__all__ = [
    "decode_text",
    "detect_encoding",
]
