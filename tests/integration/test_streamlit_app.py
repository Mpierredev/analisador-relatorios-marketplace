"""End-to-end integration tests for the Streamlit UI using AppTest."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from analisador.core.enums import CanonicalField, Marketplace
from analisador.core.errors import UnsupportedFileError
from analisador.ui.services import process_uploaded_file, translate_exception
from analisador.ui.state import (
    STATE_DASHBOARD_ENABLED,
    STATE_FILE_NAME,
    STATE_LAST_ERROR,
    STATE_RAW_DF,
    STATE_SELECTED_FORMAT,
    STATE_UPLOAD_SIGNATURE,
    STATE_VALIDATION_REPORT,
    compute_file_signature,
)

APP_PATH = Path(__file__).resolve().parents[2] / "app.py"


def _run_analyze_page() -> None:
    from analisador.ui.pages import render_analyze_page

    render_analyze_page()


def _run_supported_formats_page() -> None:
    from analisador.ui.pages import render_supported_formats_page

    render_supported_formats_page()


def _run_how_to_export_page() -> None:
    from analisador.ui.pages import render_how_to_export_page

    render_how_to_export_page()


def _run_about_page() -> None:
    from analisador.ui.pages import render_about_page

    render_about_page()


def _ml_xlsx_bytes() -> bytes:
    rows = [
        {
            "N.º de venda": "2001",
            "Data da venda": "01/03/2025 10:00",
            "Estado": "Entregue",
            "Título do anúncio": "Monitor Ultra",
            "SKU": "MON-1",
            "Unidades": 2,
            "Receita por produtos": "R$ 1.200,00",
            "Tarifa de venda e impostos": "R$ 120,00",
            "Custos de envio": "R$ 40,00",
            "Total (BRL)": "R$ 1.040,00",
        },
        {
            "N.º de venda": "2002",
            "Data da venda": "04/03/2025 12:00",
            "Estado": "Cancelada pelo comprador",
            "Título do anúncio": "Suporte Articulado",
            "SKU": "SUP-2",
            "Unidades": 1,
            "Receita por produtos": "R$ 150,00",
            "Tarifa de venda e impostos": "R$ 0,00",
            "Custos de envio": "R$ 0,00",
            "Total (BRL)": "R$ 150,00",
        },
    ]
    buf = BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


def test_app_entrypoint_and_static_pages_render_without_errors() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not app.exception
    assert len(app.title) >= 1
    assert app.title[0].value == "Analisar relatório de vendas"
    assert app.session_state[STATE_DASHBOARD_ENABLED] is False

    for page_fn, expected_title in (
        (_run_supported_formats_page, "Formatos suportados"),
        (_run_how_to_export_page, "Como exportar os relatórios"),
        (_run_about_page, "Sobre o Analisador"),
    ):
        page = AppTest.from_function(page_fn, default_timeout=15).run()
        assert not page.exception
        assert page.title[0].value == expected_title


def test_analyze_page_gated_flow_from_validation_to_dashboard() -> None:
    content = _ml_xlsx_bytes()
    raw_df, report = process_uploaded_file(
        content,
        "vendas_ml.xlsx",
        Marketplace.MERCADO_LIVRE.value,
    )

    at = AppTest.from_function(_run_analyze_page, default_timeout=15).run()
    assert not at.exception

    at.session_state[STATE_SELECTED_FORMAT] = Marketplace.MERCADO_LIVRE.value
    at.session_state[STATE_UPLOAD_SIGNATURE] = compute_file_signature(
        "vendas_ml.xlsx",
        content,
    )
    at.session_state[STATE_FILE_NAME] = "vendas_ml.xlsx"
    at.session_state[STATE_RAW_DF] = raw_df
    at.session_state[STATE_VALIDATION_REPORT] = report
    at.run()

    assert not at.exception
    assert at.session_state[STATE_DASHBOARD_ENABLED] is False
    generate_btn = at.button(key="btn_generate_dashboard")
    assert generate_btn.disabled is False

    generate_btn.click().run()
    assert not at.exception
    assert at.session_state[STATE_DASHBOARD_ENABLED] is True
    metric_labels = [metric.label for metric in at.metric]
    assert "Faturamento bruto" in metric_labels
    assert "Pedidos" in metric_labels
    assert "Receita líquida" in metric_labels

    # Reset button clears dashboard and validation state
    at.button(key="btn_reset_flow").click().run()
    assert not at.exception
    assert at.session_state[STATE_DASHBOARD_ENABLED] is False
    assert at.session_state[STATE_RAW_DF] is None


def test_unrecognized_file_disables_button_until_manual_mapping_applied() -> None:
    csv_bytes = (
        b"quando;item;qtde;total_bruto\n"
        b"01/03/2025;Camisa Polo;2;R$ 160,00\n"
        b"02/03/2025;Calca Jeans;1;R$ 220,00\n"
    )
    raw_df, report = process_uploaded_file(
        csv_bytes,
        "planilha_custom.csv",
        Marketplace.MERCADO_LIVRE.value,
    )
    assert report.can_generate_dashboard is False

    at = AppTest.from_function(_run_analyze_page, default_timeout=15).run()
    at.session_state[STATE_SELECTED_FORMAT] = Marketplace.MERCADO_LIVRE.value
    at.session_state[STATE_UPLOAD_SIGNATURE] = compute_file_signature(
        "planilha_custom.csv",
        csv_bytes,
    )
    at.session_state[STATE_FILE_NAME] = "planilha_custom.csv"
    at.session_state[STATE_RAW_DF] = raw_df
    at.session_state[STATE_VALIDATION_REPORT] = report
    at.run()

    assert not at.exception
    assert at.button(key="btn_generate_dashboard").disabled is True

    at.selectbox(key=f"map_field_{CanonicalField.ORDER_DATE.value}").select("quando")
    at.selectbox(key=f"map_field_{CanonicalField.PRODUCT_NAME.value}").select("item")
    at.selectbox(key=f"map_field_{CanonicalField.QUANTITY.value}").select("qtde")
    at.selectbox(key=f"map_field_{CanonicalField.GROSS_REVENUE.value}").select(
        "total_bruto"
    )
    at.button(key="FormSubmitter:manual_mapping_form-Aplicar mapeamento manual").click()
    at.run()

    assert not at.exception
    assert at.session_state[STATE_SELECTED_FORMAT] == Marketplace.GENERIC.value
    assert at.button(key="btn_generate_dashboard").disabled is False

    at.button(key="btn_generate_dashboard").click().run()
    assert not at.exception
    assert at.session_state[STATE_DASHBOARD_ENABLED] is True


def test_visual_error_state_renders_safely_without_traceback() -> None:
    at = AppTest.from_function(_run_analyze_page, default_timeout=15).run()
    at.session_state[STATE_LAST_ERROR] = translate_exception(
        UnsupportedFileError("Extensão .pdf não é aceita.")
    )
    at.run()

    assert not at.exception
    assert len(at.error) == 1
    assert "Extensão .pdf não é aceita." in at.error[0].value
    assert len(at.info) == 1
