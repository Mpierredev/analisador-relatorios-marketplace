"""Unit tests for UI formatting, labels, format options, and error translation."""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from analisador.analytics import MetricDelta
from analisador.core.enums import Marketplace
from analisador.core.errors import UnsupportedFileError
from analisador.ui.formatting import (
    UNAVAILABLE_LABEL,
    build_format_options,
    format_brl,
    format_int_br,
    format_metric_delta,
    format_percent,
)
from analisador.ui.services import translate_exception


def test_format_brl_int_and_percent() -> None:
    assert format_brl(Decimal("1234.56")) == "R$ 1.234,56"
    assert format_brl(Decimal("-50.00")) == "-R$ 50,00"
    assert format_brl(None) == UNAVAILABLE_LABEL

    assert format_int_br(0) == "0"
    assert format_int_br(1234567) == "1.234.567"

    assert format_percent(0.125) == "12,5%"
    assert format_percent(Decimal("0.8000"), decimals=0) == "80%"
    assert format_percent(None) == UNAVAILABLE_LABEL


def test_format_metric_delta() -> None:
    brl_delta = MetricDelta(
        current=Decimal("300.00"),
        previous=Decimal("200.00"),
        absolute_delta=Decimal("100.00"),
        percentage_delta=0.5,
    )
    assert format_metric_delta(brl_delta, kind="brl") == "+R$ 100,00 (+50,0%)"

    int_delta = MetricDelta(
        current=4,
        previous=2,
        absolute_delta=2,
        percentage_delta=1.0,
    )
    assert format_metric_delta(int_delta, kind="int") == "+2 (+100,0%)"

    pct_delta = MetricDelta(
        current=0.25,
        previous=0.10,
        absolute_delta=0.15,
        percentage_delta=None,
    )
    assert format_metric_delta(pct_delta, kind="pct") == "+15,0 p.p."

    none_delta = MetricDelta(
        current=None,
        previous=None,
        absolute_delta=None,
        percentage_delta=None,
    )
    assert format_metric_delta(none_delta, kind="brl") is None


def test_build_format_options_includes_adapters_and_generic() -> None:
    options = build_format_options()
    keys = [key for key, _ in options]
    assert Marketplace.MERCADO_LIVRE.value in keys
    assert Marketplace.SHOPEE.value in keys
    assert keys[-1] == Marketplace.GENERIC.value


def test_translate_exception_preserves_report_error_and_hides_sensitive_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    report_err = UnsupportedFileError(
        "Extensão inválida.",
        suggestion="Use .csv ou .xlsx.",
    )
    translated = translate_exception(report_err)
    assert translated.message == "Extensão inválida."
    assert translated.suggestion == "Use .csv ou .xlsx."

    with caplog.at_level(logging.WARNING):
        unexpected = translate_exception(
            RuntimeError("dados pessoais secretos: CPF 123.456.789-00")
        )
    assert "CPF" not in unexpected.message
    assert "CPF" not in caplog.text
    assert "RuntimeError" in caplog.text
