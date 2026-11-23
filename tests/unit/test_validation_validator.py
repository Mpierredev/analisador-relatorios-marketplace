import io
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

import analisador.validation as validation
from analisador.adapters import MERCADO_LIVRE_ADAPTER, SHOPEE_ADAPTER
from analisador.core.enums import CanonicalField, Marketplace, ValidationStatus
from analisador.core.errors import MissingRequiredColumnsError, ReportError
from analisador.ingestion import read_report
from analisador.validation import (
    ensure_can_generate_dashboard,
    validate_generic_mapping,
    validate_report,
    validate_with_adapter,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture_df(filename: str) -> pd.DataFrame:
    return read_report((FIXTURES_DIR / filename).read_bytes(), filename)


def _build_synthetic_ml_layout_xlsx() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Vendas BR"
    sheet.append([])
    sheet.append(["Neste relatório, você encontra as informações das vendas."])
    sheet.append([None, None, None, "Ir para relatórios de tarifas"])
    sheet.append(["Vendas - Status em 26 de novembro de 2024"])
    sheet.append(["Vendas", None, "Anúncios", "Compradores"])
    sheet.append(
        [
            "N.º de venda",
            "Data da venda",
            "Status",
            "Unidades",
            "Receita por produtos (BRL)",
            "Tarifa de venda e impostos",
            "Tarifas de envio",
            "Total (BRL)",
            "SKU",
            "Título do anúncio",
            "Preço unitário de venda do anúncio (BRL)",
            "Status",
        ]
    )
    sheet.append(
        [
            "2000009000000001",
            "25 de novembro de 2024 11:43 hs.",
            "A caminho",
            1.0,
            260.0,
            -31.2,
            -45.0,
            183.8,
            "SKU-SYN-01",
            "Livro Técnico Sintético Edição 10",
            260.0,
            "São Paulo",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_validation_package_exposes_all_etapa4_symbols() -> None:
    assert validation.__all__
    for symbol in validation.__all__:
        assert hasattr(validation, symbol)


def test_validate_report_approves_shopee_and_synthetic_ml_layout() -> None:
    shopee_df = _load_fixture_df("shopee_pedidos_pt.csv")
    shopee_report = validate_report(shopee_df, Marketplace.SHOPEE)

    assert shopee_report.status is ValidationStatus.RECOGNIZED
    assert shopee_report.can_generate_dashboard is True
    assert shopee_report.missing_required == ()
    assert shopee_report.warnings == ()
    ensure_can_generate_dashboard(shopee_report)

    ml_df = read_report(_build_synthetic_ml_layout_xlsx(), "ml_sintetico.xlsx")
    ml_report = validate_report(ml_df, Marketplace.MERCADO_LIVRE)

    assert ml_report.status is ValidationStatus.RECOGNIZED
    assert ml_report.score == 0.9
    assert ml_report.can_generate_dashboard is True
    assert ml_report.column_mapping[CanonicalField.UNIT_PRICE] == (
        "Preço unitário de venda do anúncio (BRL)"
    )
    assert ml_report.warnings == ()


def test_validate_with_adapter_warnings_and_unit_price_fallback() -> None:
    altered_df = _load_fixture_df("shopee_nomes_alterados.csv")
    altered_report = validate_with_adapter(altered_df, SHOPEE_ADAPTER)

    assert altered_report.status is ValidationStatus.RECOGNIZED_WITH_WARNINGS
    assert altered_report.can_generate_dashboard is True
    assert altered_report.has_warnings is True
    assert any("similaridade" in w.lower() for w in altered_report.warnings)

    unit_only_df = pd.DataFrame(
        {
            "ID do pedido": ["PED-1"],
            "Status do pedido": ["Concluído"],
            "Data de criação do pedido": ["2026-10-15"],
            "Nome do Produto": ["Mouse Sem Fio"],
            "Quantidade": ["2"],
            "Preço original": ["89,90"],
            "Taxa de comissão": ["10,00"],
        }
    )
    unit_report = validate_with_adapter(unit_only_df, SHOPEE_ADAPTER)
    assert unit_report.status is ValidationStatus.RECOGNIZED_WITH_WARNINGS
    assert unit_report.can_generate_dashboard is True
    assert unit_report.missing_required == ()
    assert CanonicalField.UNIT_PRICE in unit_report.found_required
    assert any("quantidade x preço unitário" in w for w in unit_report.warnings)


def test_validate_with_adapter_rejects_missing_wrong_empty_and_unknown() -> None:
    missing_df = _load_fixture_df("shopee_colunas_faltando.csv")
    missing_report = validate_report(missing_df, Marketplace.SHOPEE)
    assert missing_report.status is ValidationStatus.UNRECOGNIZED
    assert missing_report.can_generate_dashboard is False
    with pytest.raises(MissingRequiredColumnsError, match="quantity"):
        ensure_can_generate_dashboard(missing_report)

    ml_df = _load_fixture_df("mercado_livre_vendas_pt.csv")
    wrong_report = validate_report(ml_df, Marketplace.SHOPEE)
    assert wrong_report.status is ValidationStatus.UNRECOGNIZED
    assert wrong_report.suggested_adapter == Marketplace.MERCADO_LIVRE
    assert any("Mercado Livre" in w for w in wrong_report.warnings)

    unknown_df = _load_fixture_df("outro_marketplace_desconhecido.csv")
    unknown_report = validate_report(unknown_df, Marketplace.SHOPEE)
    assert unknown_report.status is ValidationStatus.UNRECOGNIZED
    assert unknown_report.suggested_adapter is None

    header_only_df = pd.DataFrame(
        columns=[
            "ID do pedido",
            "Status do pedido",
            "Data de criação do pedido",
            "Nome do Produto",
            "Quantidade",
            "Valor total do pedido",
        ]
    )
    empty_report = validate_report(header_only_df, Marketplace.SHOPEE)
    assert empty_report.status is ValidationStatus.UNRECOGNIZED
    assert empty_report.can_generate_dashboard is False
    with pytest.raises(ReportError, match="apenas cabeçalho"):
        ensure_can_generate_dashboard(empty_report)


def test_validate_with_custom_adapter_not_in_candidates_and_invalid_format() -> None:
    df = pd.DataFrame(
        {
            "Data da venda": ["2026-10-01"],
            "Título do anúncio": ["Teclado"],
            "Unidades": ["1"],
            "Receita por produtos": ["200,00"],
        }
    )
    custom_report = validate_with_adapter(
        df,
        MERCADO_LIVRE_ADAPTER,
        adapters=(SHOPEE_ADAPTER,),
    )
    assert custom_report.selected_adapter == Marketplace.MERCADO_LIVRE
    assert custom_report.status is ValidationStatus.RECOGNIZED_WITH_WARNINGS
    assert any("receita líquida" in w.lower() for w in custom_report.warnings)

    with pytest.raises(ValueError, match="Unknown report format"):
        validate_report(df, "amazon")


def test_validate_generic_mapping_covers_valid_warnings_and_error_cases() -> None:
    df = pd.DataFrame(
        {
            "dt": ["2026-10-01"],
            "item": ["Fone"],
            "qtd": ["2"],
            "total": ["199,80"],
            "unit": ["99,90"],
            "taxa": ["20,00"],
            "obs": ["ok"],
        }
    )

    clean = validate_report(
        df,
        Marketplace.GENERIC,
        manual_mapping={
            CanonicalField.ORDER_DATE: "dt",
            CanonicalField.PRODUCT_NAME: "item",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "total",
            CanonicalField.FEES: "taxa",
        },
    )
    assert clean.status is ValidationStatus.RECOGNIZED
    assert clean.can_generate_dashboard is True
    assert clean.extra_columns == ("unit", "obs")
    assert clean.warnings == ()

    unit_no_fees = validate_generic_mapping(
        df,
        {
            CanonicalField.ORDER_DATE: "dt",
            CanonicalField.PRODUCT_NAME: "item",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.UNIT_PRICE: "unit",
            CanonicalField.MARKETPLACE: "obs",
        },
    )
    assert unit_no_fees.status is ValidationStatus.RECOGNIZED_WITH_WARNINGS
    assert unit_no_fees.can_generate_dashboard is True
    assert len(unit_no_fees.warnings) == 3

    duplicate_col = validate_generic_mapping(
        df,
        {
            CanonicalField.ORDER_DATE: "dt",
            CanonicalField.PRODUCT_NAME: "dt",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "total",
        },
    )
    assert duplicate_col.status is ValidationStatus.UNRECOGNIZED
    assert duplicate_col.can_generate_dashboard is False
    assert any("mais de um campo" in w for w in duplicate_col.warnings)

    missing_col = validate_generic_mapping(
        df,
        {
            CanonicalField.ORDER_DATE: "dt",
            CanonicalField.PRODUCT_NAME: "inexistente",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "total",
        },
    )
    assert missing_col.status is ValidationStatus.UNRECOGNIZED
    assert missing_col.can_generate_dashboard is False
    assert any("não encontrada" in w for w in missing_col.warnings)

    empty_rows = validate_generic_mapping(
        pd.DataFrame(columns=["dt", "item", "qtd", "total", "taxa"]),
        {
            CanonicalField.ORDER_DATE: "dt",
            CanonicalField.PRODUCT_NAME: "item",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "total",
            CanonicalField.FEES: "taxa",
        },
    )
    assert empty_rows.status is ValidationStatus.UNRECOGNIZED
    assert empty_rows.can_generate_dashboard is False
    with pytest.raises(ReportError, match="apenas cabeçalho"):
        ensure_can_generate_dashboard(empty_rows)
