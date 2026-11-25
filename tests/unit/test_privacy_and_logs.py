"""Privacy, zero-PII logging, and zero-disk-write regression tests."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from analisador.analytics import (
    ProductRankingMetric,
    TimeGranularity,
    build_time_series,
    compare_periods,
    compute_abc_curve,
    compute_kpis,
    compute_status_distribution,
    rank_products,
)
from analisador.core.enums import Marketplace
from analisador.core.errors import HeaderNotFoundError
from analisador.export import export_canonical_csv, export_summary_excel
from analisador.ingestion import read_report
from analisador.normalization import normalize_report
from analisador.ui.services import (
    compute_dashboard_bundle_cached,
    generate_normalized_result,
    process_uploaded_file,
    translate_exception,
)
from analisador.validation import validate_report

_CANARY_TOKENS: tuple[str, ...] = (
    "CANARY-CPF-99988877766",
    "CANARY-COMPRADOR-SIGILOSO",
    "CANARY-EMAIL@EXEMPLO.TEST",
    "CANARY-ENDERECO-RUA-SECRETA-42",
    "CANARY-PRODUTO-CONFIDENCIAL",
    "CANARY-PEDIDO-777",
    "relatorio_sigiloso_canary",
)


def _canary_xlsx_bytes() -> bytes:
    rows = [
        {
            "N.º de venda": "CANARY-PEDIDO-777",
            "Data da venda": "01/03/2025 10:00",
            "Estado": "Entregue",
            "Título do anúncio": "CANARY-PRODUTO-CONFIDENCIAL",
            "SKU": "SKU-SIGILOSO",
            "Unidades": 2,
            "Receita por produtos": "R$ 250,00",
            "Tarifa de venda e impostos": "R$ 25,00",
            "Custos de envio": "R$ 15,00",
            "Total (BRL)": "R$ 210,00",
            "Comprador": "CANARY-COMPRADOR-SIGILOSO",
            "CPF/CNPJ do comprador": "CANARY-CPF-99988877766",
            "E-mail": "CANARY-EMAIL@EXEMPLO.TEST",
            "Endereço": "CANARY-ENDERECO-RUA-SECRETA-42",
        }
    ]
    buf = BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


def _all_captured_log_text(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join([rec.getMessage() for rec in caplog.records] + [caplog.text])


def test_full_pipeline_never_logs_file_contents_pii_or_filename(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    content = _canary_xlsx_bytes()
    filename = "relatorio_sigiloso_canary.xlsx"

    with caplog.at_level(logging.DEBUG):
        raw_df = read_report(content, filename)
        validation = validate_report(raw_df, Marketplace.MERCADO_LIVRE.value)
        normalized = normalize_report(raw_df, validation)
        df = normalized.dataframe
        compute_kpis(df)
        compare_periods(df)
        build_time_series(df, TimeGranularity.DAILY)
        rank_products(df, by=ProductRankingMetric.REVENUE)
        compute_abc_curve(df)
        compute_status_distribution(df)
        csv_bytes = export_canonical_csv(df)
        xlsx_bytes = export_summary_excel(
            df,
            quality_report=normalized.quality_report,
            net_revenue_source=normalized.net_revenue_source,
        )

        # Also exercise UI orchestration + cached bundle + unexpected exception
        ui_raw, ui_val = process_uploaded_file(
            content, filename, Marketplace.MERCADO_LIVRE.value
        )
        ui_norm = generate_normalized_result(ui_raw, ui_val)
        compute_dashboard_bundle_cached.clear()
        compute_dashboard_bundle_cached(
            ui_norm.dataframe,
            "canary-session-1",
            None,
            None,
            (),
            "",
            TimeGranularity.DAILY.value,
            ProductRankingMetric.REVENUE.value,
        )
        unexpected_ui_err = translate_exception(
            RuntimeError(
                "Falha interna CANARY-CPF-99988877766 CANARY-COMPRADOR-SECRETO"
            )
        )
        expected_ui_err = translate_exception(HeaderNotFoundError("Cabeçalho ausente"))

    captured = _all_captured_log_text(caplog)
    for token in _CANARY_TOKENS:
        assert token not in captured

    # Ensure UI unexpected error translation masks internal PII exception details
    assert "CANARY-CPF-99988877766" not in unexpected_ui_err.message
    assert "CANARY-CPF-99988877766" not in unexpected_ui_err.suggestion
    assert expected_ui_err.message == "Cabeçalho ausente"

    # Extra PII buyer columns are stripped from canonical output and exports
    csv_text = csv_bytes.decode("utf-8-sig")
    for pii_token in (
        "CANARY-CPF-99988877766",
        "CANARY-COMPRADOR-SIGILOSO",
        "CANARY-EMAIL@EXEMPLO.TEST",
        "CANARY-ENDERECO-RUA-SECRETA-42",
    ):
        assert pii_token not in df.to_string()
        assert pii_token not in csv_text
    assert len(xlsx_bytes) > 0

    # Zero files persisted to disk anywhere inside cwd
    assert list(tmp_path.rglob("*")) == []
