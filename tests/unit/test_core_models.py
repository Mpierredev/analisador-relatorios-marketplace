from datetime import UTC, datetime
from decimal import Decimal

import pytest

import analisador.core as core
from analisador.core.enums import CanonicalField, Marketplace, ValidationStatus
from analisador.core.models import (
    AdapterScore,
    KpiSummary,
    QualityReport,
    ValidationReport,
)


def test_core_package_reexports_match_all() -> None:
    assert core.__all__
    for symbol in core.__all__:
        assert hasattr(core, symbol)


def test_adapter_score_accepts_boundary_scores_and_rejects_invalid() -> None:
    low = AdapterScore(adapter_key=Marketplace.GENERIC, score=0.0)
    high = AdapterScore(
        adapter_key=Marketplace.SHOPEE,
        score=1.0,
        matched_required=(CanonicalField.ORDER_DATE,),
        matched_optional=(CanonicalField.SKU,),
    )
    assert low.score == 0.0
    assert high.matched_required == (CanonicalField.ORDER_DATE,)

    with pytest.raises(ValueError, match="adapter_key must not be empty"):
        AdapterScore(adapter_key="  ", score=0.5)

    for bad_score in (-0.01, 1.01, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="score must be between"):
            AdapterScore(adapter_key=Marketplace.SHOPEE, score=bad_score)


def test_validation_report_dashboard_gate_and_immutable_mapping() -> None:
    raw_mapping = {
        CanonicalField.ORDER_DATE: "Data do Pedido",
        CanonicalField.PRODUCT_NAME: "Produto",
    }
    recognized = ValidationReport(
        selected_adapter=Marketplace.SHOPEE,
        status=ValidationStatus.RECOGNIZED,
        score=0.95,
        column_mapping=raw_mapping,
        found_required=(CanonicalField.ORDER_DATE, CanonicalField.PRODUCT_NAME),
    )
    raw_mapping[CanonicalField.QUANTITY] = "Qtd"

    assert recognized.can_generate_dashboard is True
    assert recognized.has_warnings is False
    assert CanonicalField.QUANTITY not in recognized.column_mapping
    with pytest.raises(TypeError):
        recognized.column_mapping[CanonicalField.SKU] = "SKU"  # type: ignore[index]

    with_warnings = ValidationReport(
        selected_adapter=Marketplace.MERCADO_LIVRE,
        status=ValidationStatus.RECOGNIZED_WITH_WARNINGS,
        score=0.72,
        warnings=("Coluna opcional SKU ausente.",),
    )
    assert with_warnings.can_generate_dashboard is True
    assert with_warnings.has_warnings is True

    unrecognized_no_missing = ValidationReport(
        selected_adapter=Marketplace.SHOPEE,
        status=ValidationStatus.UNRECOGNIZED,
        score=0.20,
        suggested_adapter=Marketplace.MERCADO_LIVRE,
    )
    assert unrecognized_no_missing.can_generate_dashboard is False

    unrecognized_with_missing = ValidationReport(
        selected_adapter=Marketplace.SHOPEE,
        status=ValidationStatus.UNRECOGNIZED,
        score=0.10,
        missing_required=(CanonicalField.ORDER_DATE,),
    )
    assert unrecognized_with_missing.can_generate_dashboard is False


@pytest.mark.parametrize(
    ("kwargs", "match_pattern"),
    [
        (
            {
                "selected_adapter": "",
                "status": ValidationStatus.RECOGNIZED,
                "score": 0.9,
            },
            "selected_adapter must not be empty",
        ),
        (
            {
                "selected_adapter": Marketplace.SHOPEE,
                "status": ValidationStatus.UNRECOGNIZED,
                "score": 0.2,
                "suggested_adapter": "   ",
            },
            "suggested_adapter must not be empty",
        ),
        (
            {
                "selected_adapter": Marketplace.SHOPEE,
                "status": ValidationStatus.RECOGNIZED,
                "score": 1.2,
            },
            "score must be between",
        ),
        (
            {
                "selected_adapter": Marketplace.SHOPEE,
                "status": ValidationStatus.RECOGNIZED,
                "score": 0.9,
                "missing_required": (CanonicalField.ORDER_DATE,),
            },
            "missing_required must be empty unless status is UNRECOGNIZED",
        ),
        (
            {
                "selected_adapter": Marketplace.SHOPEE,
                "status": ValidationStatus.RECOGNIZED_WITH_WARNINGS,
                "score": 0.7,
                "missing_required": (CanonicalField.QUANTITY,),
            },
            "missing_required must be empty unless status is UNRECOGNIZED",
        ),
    ],
)
def test_validation_report_rejects_inconsistent_state(
    kwargs: dict[str, object],
    match_pattern: str,
) -> None:
    with pytest.raises(ValueError, match=match_pattern):
        ValidationReport(**kwargs)  # type: ignore[arg-type]


def test_quality_report_rates_issues_and_immutability() -> None:
    empty_report = QualityReport(total_rows=0, valid_rows=0, ignored_rows=0)
    assert empty_report.valid_rate == 0.0
    assert empty_report.has_issues is False

    null_counts = {"sku": 0}
    clean = QualityReport(
        total_rows=10,
        valid_rows=10,
        ignored_rows=0,
        null_counts=null_counts,
    )
    null_counts["sku"] = 5

    assert clean.valid_rate == 1.0
    assert clean.has_issues is False
    assert clean.null_counts["sku"] == 0
    with pytest.raises(TypeError):
        clean.null_counts["order_id"] = 1  # type: ignore[index]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"total_rows": 10, "valid_rows": 9, "ignored_rows": 1},
        {"total_rows": 10, "valid_rows": 10, "ignored_rows": 0, "duplicate_rows": 1},
        {"total_rows": 10, "valid_rows": 10, "ignored_rows": 0, "invalid_dates": 1},
        {
            "total_rows": 10,
            "valid_rows": 10,
            "ignored_rows": 0,
            "non_positive_quantities": 1,
        },
        {"total_rows": 10, "valid_rows": 10, "ignored_rows": 0, "negative_values": 1},
        {"total_rows": 10, "valid_rows": 10, "ignored_rows": 0, "outlier_rows": 1},
        {
            "total_rows": 10,
            "valid_rows": 10,
            "ignored_rows": 0,
            "null_counts": {"sku": 2},
        },
        {
            "total_rows": 10,
            "valid_rows": 10,
            "ignored_rows": 0,
            "warnings": ("Outliers detectados.",),
        },
    ],
)
def test_quality_report_detects_issues(kwargs: dict[str, object]) -> None:
    report = QualityReport(**kwargs)  # type: ignore[arg-type]
    assert report.has_issues is True


@pytest.mark.parametrize(
    ("kwargs", "match_pattern"),
    [
        (
            {"total_rows": -1, "valid_rows": 0, "ignored_rows": 0},
            "total_rows must be a non-negative integer",
        ),
        (
            {"total_rows": True, "valid_rows": 1, "ignored_rows": 0},
            "total_rows must be a non-negative integer",
        ),
        (
            {"total_rows": 10, "valid_rows": 7, "ignored_rows": 2},
            "valid_rows \\+ ignored_rows must equal total_rows",
        ),
        (
            {
                "total_rows": 5,
                "valid_rows": 5,
                "ignored_rows": 0,
                "null_counts": {"": 1},
            },
            "null_counts key must not be empty",
        ),
        (
            {
                "total_rows": 5,
                "valid_rows": 5,
                "ignored_rows": 0,
                "null_counts": {"sku": -1},
            },
            "must be a non-negative integer",
        ),
        (
            {
                "total_rows": 5,
                "valid_rows": 5,
                "ignored_rows": 0,
                "null_counts": {"sku": False},
            },
            "must be a non-negative integer",
        ),
    ],
)
def test_quality_report_rejects_invalid_counts(
    kwargs: dict[str, object],
    match_pattern: str,
) -> None:
    with pytest.raises(ValueError, match=match_pattern):
        QualityReport(**kwargs)  # type: ignore[arg-type]


def test_kpi_summary_creation_and_net_revenue_property() -> None:
    minimal = KpiSummary(
        gross_revenue=Decimal("1000.00"),
        order_count=10,
        item_count=15,
        average_ticket=Decimal("100.00"),
    )
    assert minimal.has_net_revenue is False
    assert minimal.cancellation_rate is None

    start = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 10, 31, 23, 59, tzinfo=UTC)
    full = KpiSummary(
        gross_revenue=Decimal("2500.00"),
        order_count=20,
        item_count=28,
        average_ticket=Decimal("125.00"),
        cancellation_rate=0.10,
        cancelled_order_count=2,
        total_fees=Decimal("250.00"),
        total_shipping=Decimal("120.00"),
        net_revenue=Decimal("2130.00"),
        period_start=start,
        period_end=end,
    )
    assert full.has_net_revenue is True
    assert full.period_start == start

    same_instant = KpiSummary(
        gross_revenue=Decimal("100.00"),
        order_count=1,
        item_count=1,
        average_ticket=Decimal("100.00"),
        period_start=start,
        period_end=start,
    )
    assert same_instant.period_start == same_instant.period_end


def _make_valid_kpi(**overrides: object) -> KpiSummary:
    defaults: dict[str, object] = {
        "gross_revenue": Decimal("500.00"),
        "order_count": 5,
        "item_count": 7,
        "average_ticket": Decimal("100.00"),
    }
    defaults.update(overrides)
    return KpiSummary(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "match_pattern"),
    [
        (
            {"gross_revenue": Decimal("NaN")},
            "gross_revenue must be a finite Decimal",
        ),
        (
            {"average_ticket": Decimal("Infinity")},
            "average_ticket must be a finite Decimal",
        ),
        (
            {"net_revenue": Decimal("NaN")},
            "net_revenue must be a finite Decimal",
        ),
        ({"order_count": -1}, "order_count must be a non-negative integer"),
        ({"item_count": True}, "item_count must be a non-negative integer"),
        (
            {"order_count": 2, "cancelled_order_count": 3},
            "cancelled_order_count must not exceed order_count",
        ),
        ({"cancellation_rate": 1.05}, "cancellation_rate must be between"),
        ({"cancellation_rate": float("nan")}, "cancellation_rate must be between"),
        ({"total_fees": Decimal("-1")}, "total_fees must not be negative"),
        ({"total_fees": Decimal("NaN")}, "total_fees must be a finite Decimal"),
        ({"total_shipping": Decimal("-0.01")}, "total_shipping must not be negative"),
        (
            {
                "period_start": datetime(2026, 10, 10, 12, 0),
                "period_end": datetime(2026, 10, 10, 11, 59),
            },
            "period_start must not be after period_end",
        ),
        (
            {
                "period_start": datetime(2026, 10, 10, 12, 0),
                "period_end": datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
            },
            "must both be naive or timezone-aware",
        ),
        (
            {
                "period_start": datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
                "period_end": datetime(2026, 10, 10, 12, 0),
            },
            "must both be naive or timezone-aware",
        ),
    ],
)
def test_kpi_summary_rejects_invalid_values(
    overrides: dict[str, object],
    match_pattern: str,
) -> None:
    with pytest.raises(ValueError, match=match_pattern):
        _make_valid_kpi(**overrides)
