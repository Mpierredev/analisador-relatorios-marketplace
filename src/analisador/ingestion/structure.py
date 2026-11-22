"""CSV separator detection and header row discovery for tabular reports."""

import csv
import io
import re
from collections import Counter
from collections.abc import Sequence
from typing import Final

from analisador.core.config import (
    HEADER_SCAN_MAX_ROWS,
    MIN_HEADER_COLUMNS,
    SUPPORTED_SEPARATORS,
)
from analisador.core.errors import HeaderNotFoundError

_CURRENCY_PREFIX_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[+-]?\s*(?:r\$|us\$|\$|€|brl|usd)\s*",
    re.IGNORECASE,
)
_NUMERIC_ONLY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9.,+\-()\s]+$")
_DATE_CHARS: Final[frozenset[str]] = frozenset("0123456789-/:. TZtz+")

_MIN_HEADER_TEXT_RATIO: Final[float] = 0.5
_FOLLOWING_ROWS_WINDOW: Final[int] = 5
_WIDTH_SCORE_WEIGHT: Final[float] = 0.45
_TEXT_SCORE_WEIGHT: Final[float] = 0.35
_UNIQUENESS_SCORE_WEIGHT: Final[float] = 0.10
_FOLLOWING_SCORE_WEIGHT: Final[float] = 0.10


def _collect_non_empty_lines(text: str) -> list[str]:
    sample_lines: list[str] = []
    for line in io.StringIO(text):
        if line.strip():
            sample_lines.append(line)
        if len(sample_lines) >= HEADER_SCAN_MAX_ROWS:
            break
    return sample_lines


def _score_separator(
    sample_lines: Sequence[str],
    separator: str,
) -> tuple[int, int, int]:
    rows = list(csv.reader(sample_lines, delimiter=separator))
    widths = [len(row) for row in rows if len(row) >= MIN_HEADER_COLUMNS]
    if not widths:
        return (0, 0, 0)
    modal_width, consistent_count = Counter(widths).most_common(1)[0]
    return (consistent_count, modal_width, len(widths))


def detect_separator(text: str) -> str:
    """Detect the column delimiter of CSV text among supported separators."""
    sample_lines = _collect_non_empty_lines(text)
    if not sample_lines:
        raise HeaderNotFoundError(
            "O arquivo CSV não possui linhas preenchidas.",
            suggestion="Verifique se o arquivo enviado contém cabeçalho e dados.",
        )

    best_separator: str | None = None
    best_score = (0, 0, 0)
    for separator in SUPPORTED_SEPARATORS:
        score = _score_separator(sample_lines, separator)
        if score > best_score:
            best_score = score
            best_separator = separator

    if best_separator is None or best_score[0] == 0:
        raise HeaderNotFoundError(
            "Não foi possível identificar o separador de colunas no arquivo CSV.",
            suggestion=(
                "Use vírgula, ponto e vírgula ou tabulação como separador de colunas."
            ),
        )
    return best_separator


def _is_text_header_cell(cell: str) -> bool:
    cleaned = cell.strip()
    if not cleaned or not any(ch.isalpha() for ch in cleaned):
        return False

    without_currency = _CURRENCY_PREFIX_PATTERN.sub("", cleaned).strip()
    if without_currency and _NUMERIC_ONLY_PATTERN.match(without_currency):
        return False

    has_digit = any(ch.isdigit() for ch in cleaned)
    return not (has_digit and all(ch in _DATE_CHARS for ch in cleaned))


def _following_width_ratio(
    non_empty_rows: Sequence[tuple[int, list[str]]],
    candidate_pos: int,
    candidate_width: int,
) -> float:
    following = non_empty_rows[
        candidate_pos + 1 : candidate_pos + 1 + _FOLLOWING_ROWS_WINDOW
    ]
    if not following:
        return 0.0
    min_expected_width = max(MIN_HEADER_COLUMNS, candidate_width - 1)
    matches = sum(1 for _, cells in following if len(cells) >= min_expected_width)
    return matches / len(following)


def _score_header_candidate(
    non_empty_rows: Sequence[tuple[int, list[str]]],
    candidate_pos: int,
    max_width: int,
) -> float | None:
    _, cells = non_empty_rows[candidate_pos]
    if len(cells) < MIN_HEADER_COLUMNS:
        return None

    text_ratio = sum(_is_text_header_cell(cell) for cell in cells) / len(cells)
    if text_ratio < _MIN_HEADER_TEXT_RATIO:
        return None

    width_ratio = len(cells) / max_width
    uniqueness_ratio = len({cell.casefold() for cell in cells}) / len(cells)
    following_ratio = _following_width_ratio(non_empty_rows, candidate_pos, len(cells))
    return (
        width_ratio * _WIDTH_SCORE_WEIGHT
        + text_ratio * _TEXT_SCORE_WEIGHT
        + uniqueness_ratio * _UNIQUENESS_SCORE_WEIGHT
        + following_ratio * _FOLLOWING_SCORE_WEIGHT
    )


def detect_header_row(rows: Sequence[Sequence[str]]) -> int:
    """Return the zero-based row index most likely to be the table header."""
    sampled = rows[:HEADER_SCAN_MAX_ROWS]
    non_empty_rows: list[tuple[int, list[str]]] = []
    for idx, row in enumerate(sampled):
        cells = [cell.strip() for cell in row if cell.strip()]
        if cells:
            non_empty_rows.append((idx, cells))

    candidates = [
        len(cells) for _, cells in non_empty_rows if len(cells) >= MIN_HEADER_COLUMNS
    ]
    if not candidates:
        raise HeaderNotFoundError()

    max_width = max(candidates)
    best_idx: int | None = None
    best_score = -1.0

    for pos, (row_idx, _) in enumerate(non_empty_rows):
        score = _score_header_candidate(non_empty_rows, pos, max_width)
        if score is not None and score > best_score:
            best_score = score
            best_idx = row_idx

    if best_idx is None:
        raise HeaderNotFoundError()
    return best_idx


__all__ = [
    "detect_header_row",
    "detect_separator",
]
