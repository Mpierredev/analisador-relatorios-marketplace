import pandas as pd
import pytest

from analisador.core.enums import CanonicalField
from analisador.validation.suggestions import (
    InferredColumnType,
    infer_column_type,
    infer_dataframe_types,
    suggest_column_mapping,
)


@pytest.mark.parametrize(
    ("values", "expected_type"),
    [
        (["", "   "], InferredColumnType.EMPTY),
        (
            ["2026-10-01", "2026-10-02T14:30:00Z", "2026-10-03 09:15:00"],
            InferredColumnType.DATE,
        ),
        (["01/10/2026", "02/10/2026 11:20", "03-10-2026"], InferredColumnType.DATE),
        (
            [
                "25 de novembro de 2024 11:43 hs.",
                "12 de fevereiro de 2025 21:45 hs.",
                "15 de outubro de 2026",
            ],
            InferredColumnType.DATE,
        ),
        (["00123", "0042", "09981"], InferredColumnType.IDENTIFIER),
        (["007", "008", "009"], InferredColumnType.IDENTIFIER),
        (["2000009945957908", "2000010740312006"], InferredColumnType.IDENTIFIER),
        (["FONE-BT-01", "MLB3765686597", "TEC-WL-03"], InferredColumnType.IDENTIFIER),
        (["1", "2", "1.0", "5.0"], InferredColumnType.INTEGER),
        (["0", "0.0", "0"], InferredColumnType.TEXT),
        (["50000", "60000", "70000"], InferredColumnType.TEXT),
        (
            ["R$ 1.234,56", "R$ 89,90", "(45,00)", "-31.20"],
            InferredColumnType.MONETARY,
        ),
        (["260.00", "-121.69", "178.46", "0,00"], InferredColumnType.MONETARY),
        (
            ["Concluído", "Cancelado", "Concluído", "A enviar", "Concluído"],
            InferredColumnType.CATEGORY,
        ),
        (
            [
                "Fone de Ouvido Bluetooth Intra-auricular Preto",
                "Teclado Mecânico Compacto Switch Azul",
                "Mochila Impermeável para Notebook 15.6",
            ],
            InferredColumnType.TEXT,
        ),
        (
            ["10 de qualquer coisa de 2024", "produto especial sem data"],
            InferredColumnType.TEXT,
        ),
    ],
)
def test_infer_column_type_identifies_expected_categories(
    values: list[str],
    expected_type: InferredColumnType,
) -> None:
    assert infer_column_type(values) is expected_type


def test_infer_dataframe_types_samples_non_empty_rows_and_validates_param() -> None:
    df = pd.DataFrame(
        {
            "Data": ["", "25 de novembro de 2024 11:43 hs.", "26 de novembro de 2024"],
            "Qtd": ["1.0", "2.0", ""],
            "Valor": ["R$ 120,00", "R$ 240,00", "R$ 80,00"],
            "Vazia": ["", "   ", ""],
        }
    )

    inferred = infer_dataframe_types(df, sample_rows=2)
    assert inferred["Data"] is InferredColumnType.DATE
    assert inferred["Qtd"] is InferredColumnType.INTEGER
    assert inferred["Valor"] is InferredColumnType.MONETARY
    assert inferred["Vazia"] is InferredColumnType.EMPTY

    for bad_sample in (0, -5, True):
        with pytest.raises(ValueError, match="sample_rows must be a positive integer"):
            infer_dataframe_types(df, sample_rows=bad_sample)


def test_suggest_column_mapping_handles_friendly_and_cryptic_headers() -> None:
    friendly_df = pd.DataFrame(
        {
            "Dt Venda": ["01/10/2026", "02/10/2026", "03/10/2026", "04/10/2026"],
            "Produto": [
                "Mouse Sem Fio Ergonômico",
                "Teclado Mecânico USB",
                "Suporte Articulado",
                "Hub USB-C",
            ],
            "Qtd": ["1", "2", "1", "3"],
            "Receita Bruta": ["89,90", "299,00", "159,90", "210,00"],
            "Taxa": ["10,00", "35,00", "18,00", "25,00"],
            "Status": ["Pago", "Pago", "Cancelado", "Pago"],
        }
    )

    friendly_map = suggest_column_mapping(friendly_df)
    assert friendly_map[CanonicalField.ORDER_DATE] == "Dt Venda"
    assert friendly_map[CanonicalField.PRODUCT_NAME] == "Produto"
    assert friendly_map[CanonicalField.QUANTITY] == "Qtd"
    assert friendly_map[CanonicalField.GROSS_REVENUE] == "Receita Bruta"
    assert friendly_map[CanonicalField.FEES] == "Taxa"
    assert friendly_map[CanonicalField.STATUS] == "Status"

    cryptic_df = pd.DataFrame(
        {
            "col_a": ["25 de novembro de 2024 11:43 hs.", "26 de novembro de 2024"],
            "col_b": ["Loja A", "Loja B"],
            "col_c": ["2", "1"],
            "col_d": ["R$ 199,80", "R$ 89,90"],
            "col_e": [
                "Fone de Ouvido Bluetooth com Cancelamento de Ruído",
                "Carregador Rápido USB-C 65W GaN Bivolt",
            ],
        }
    )

    cryptic_map = suggest_column_mapping(cryptic_df)
    assert cryptic_map[CanonicalField.ORDER_DATE] == "col_a"
    assert cryptic_map[CanonicalField.QUANTITY] == "col_c"
    assert cryptic_map[CanonicalField.GROSS_REVENUE] == "col_d"
    assert cryptic_map[CanonicalField.PRODUCT_NAME] == "col_e"


def test_suggest_column_mapping_handles_empty_rows_and_unit_price_only() -> None:
    empty_df = pd.DataFrame(
        columns=["Data da venda", "Título do anúncio", "Unidades", "Preço unitário"]
    )
    suggested_empty = suggest_column_mapping(empty_df)
    assert suggested_empty[CanonicalField.ORDER_DATE] == "Data da venda"
    assert suggested_empty[CanonicalField.PRODUCT_NAME] == "Título do anúncio"
    assert suggested_empty[CanonicalField.QUANTITY] == "Unidades"
    assert suggested_empty[CanonicalField.UNIT_PRICE] == "Preço unitário"
    assert CanonicalField.GROSS_REVENUE not in suggested_empty

    no_text_df = pd.DataFrame(
        {
            "---": ["1", "2"],
            "col_1": ["2026-10-01", "2026-10-02"],
            "col_2": ["3", "4"],
            "col_3": ["R$ 100,00", "R$ 200,00"],
        }
    )
    no_text_map = suggest_column_mapping(no_text_df)
    assert CanonicalField.PRODUCT_NAME not in no_text_map
