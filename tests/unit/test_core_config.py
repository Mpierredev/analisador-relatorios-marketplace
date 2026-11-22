from decimal import Decimal

from analisador.core.config import (
    ABC_CLASS_A_LIMIT,
    ABC_CLASS_B_LIMIT,
    BYTES_PER_MEGABYTE,
    CACHE_MAX_ENTRIES,
    CACHE_TTL_SECONDS,
    CONFLICT_FIELD_PENALTY,
    DEFAULT_TIMEZONE,
    HIGH_CONFIDENCE_THRESHOLD,
    IQR_OUTLIER_MULTIPLIER,
    MAX_DETECTION_SCORE,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    MAX_RATIO,
    MAX_ROWS,
    MEDIUM_CONFIDENCE_THRESHOLD,
    MIN_DETECTION_SCORE,
    MIN_QUANTITY,
    MIN_RATIO,
    OPTIONAL_FIELD_WEIGHT,
    PREVIEW_ROW_COUNT,
    REQUIRED_FIELD_WEIGHT,
    SUPPORTED_EXTENSIONS,
)


def test_operational_limits_and_extensions() -> None:
    assert MAX_FILE_SIZE_MB == 25
    assert MAX_FILE_SIZE_BYTES == MAX_FILE_SIZE_MB * BYTES_PER_MEGABYTE
    assert MAX_ROWS == 200_000
    assert set(SUPPORTED_EXTENSIONS) == {".csv", ".xlsx"}
    assert DEFAULT_TIMEZONE == "America/Sao_Paulo"
    assert MIN_QUANTITY == 1


def test_detection_weights_and_thresholds_are_consistent() -> None:
    assert MIN_RATIO == 0.0
    assert MAX_RATIO == 1.0
    assert MIN_DETECTION_SCORE == MIN_RATIO
    assert MAX_DETECTION_SCORE == MAX_RATIO
    assert REQUIRED_FIELD_WEIGHT + OPTIONAL_FIELD_WEIGHT < MAX_DETECTION_SCORE
    assert CONFLICT_FIELD_PENALTY > 0.0
    assert (
        MIN_DETECTION_SCORE
        < MEDIUM_CONFIDENCE_THRESHOLD
        < HIGH_CONFIDENCE_THRESHOLD
        < MAX_DETECTION_SCORE
    )


def test_analytics_and_ui_constants() -> None:
    assert IQR_OUTLIER_MULTIPLIER == 1.5
    assert Decimal("0") < ABC_CLASS_A_LIMIT < ABC_CLASS_B_LIMIT < Decimal("1")
    assert PREVIEW_ROW_COUNT > 0
    assert CACHE_MAX_ENTRIES > 0
    assert CACHE_TTL_SECONDS > 0
