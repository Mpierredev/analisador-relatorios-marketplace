import io
import logging
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

import analisador.normalization as normalization
from analisador.core.enums import (
    CanonicalField,
    Marketplace,
    NetRevenueSource,
    OrderStatus,
)
from analisador.core.errors import MissingRequiredColumnsError, NormalizationError
from analisador.core.models import QualityReport, ValidationReport
from analisador.core.schema import CANONICAL_COLUMNS
from analisador.ingestion import read_report
from analisador.normalization import normalize_report
from analisador.normalization.dtypes import (
    compact_categorical_text,
    compact_quantity_series,
)
from analisador.normalization.quality import count_duplicate_rows
from analisador.validation import validate_report

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _build_synthetic_ml_xlsx_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Vendas BR"
    sheet.append([])
    sheet.append(["Neste relatório você encontra as vendas do período."])
    sheet.append([None, None, "Relatório sintético"])
    sheet.append(["Vendas - síntese"])
    sheet.append(["Vendas", None, "Anúncios", "Compradores"])
    extra_cols = [f"Extra {i}" for i in range(1, 40)]
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
            *extra_cols,
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
            -121.69,
            178.46,
            "SKU-SYN-01",
            "  Produto   Sintético   Alpha  ",
            260.0,
            *["dado"] * len(extra_cols),
        ]
    )
    sheet.append(
        [
            "2000009000000002",
            "12 de fevereiro de 2025 21:45 hs.",
            "Entregue",
            1.0,
            37.9,
            -13.32,
            "",
            24.58,
            "SKU-SYN-02",
            "Produto Sintético Beta",
            37.9,
            *["dado"] * len(extra_cols),
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_normalization_package_exports_all_symbols() -> None:
    assert normalization.__all__
    for symbol in normalization.__all__:
        assert hasattr(normalization, symbol)


def test_normalize_synthetic_mercado_livre_real_layout() -> None:
    raw_df = read_report(_build_synthetic_ml_xlsx_bytes(), "ml_sintetico.xlsx")
    validation = validate_report(raw_df, Marketplace.MERCADO_LIVRE)
    result = normalize_report(raw_df, validation)
    df = result.dataframe

    assert list(df.columns) == [field.value for field in CANONICAL_COLUMNS]
    assert len(df) == 2
    assert df["status"].tolist() == [
        OrderStatus.IN_PROGRESS.value,
        OrderStatus.COMPLETED.value,
    ]
    assert df["product_name"].iloc[0] == "Produto Sintético Alpha"
    assert df["quantity"].tolist() == [1, 1]
    assert df["gross_revenue"].tolist() == [26_000, 3_790]
    assert df["fees"].tolist() == [3_120, 1_332]
    assert int(df["shipping_cost"].iloc[0]) == 12_169
    assert pd.isna(df["shipping_cost"].iloc[1])
    assert df["net_revenue"].tolist() == [17_846, 2_458]
    assert df["marketplace"].tolist() == [
        Marketplace.MERCADO_LIVRE.value,
        Marketplace.MERCADO_LIVRE.value,
    ]
    assert str(df["order_date"].dtype) == "datetime64[us, America/Sao_Paulo]"
    assert result.quality_report.valid_rows == 2
    assert result.quality_report.ignored_rows == 0
    assert result.quality_report.negative_values == 0
    assert result.quality_report.null_counts == {"shipping_cost": 1}


def test_normalize_shopee_fixture_derives_net_revenue() -> None:
    path = FIXTURES_DIR / "shopee_pedidos_pt.csv"
    raw_df = read_report(path.read_bytes(), path.name)
    validation = validate_report(raw_df, Marketplace.SHOPEE)
    result = normalize_report(raw_df, validation)
    df = result.dataframe

    assert len(df) == 2
    assert df["status"].tolist() == [
        OrderStatus.COMPLETED.value,
        OrderStatus.CANCELLED.value,
    ]
    assert df["gross_revenue"].tolist() == [19_980, 3_490]
    assert df["fees"].tolist() == [2_398, 419]
    assert df["shipping_cost"].tolist() == [1_450, 0]
    assert df["net_revenue"].tolist() == [16_132, 3_071]
    assert isinstance(result.quality_report, QualityReport)
    assert result.quality_report.has_issues is False


def test_normalize_generic_derives_gross_revenue_and_synthetic_ids() -> None:
    raw_df = pd.DataFrame(
        {
            "dt": ["15/10/2026", "16/10/2026"],
            "item": ["Item A", "Item B"],
            "qtd": ["2", "3.0"],
            "preco": ["R$ 50,00", "25.00"],
            "st": ["Pago", "Desconhecido"],
        }
    )
    validation = validate_report(
        raw_df,
        Marketplace.GENERIC,
        manual_mapping={
            CanonicalField.ORDER_DATE: "dt",
            CanonicalField.PRODUCT_NAME: "item",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.UNIT_PRICE: "preco",
            CanonicalField.STATUS: "st",
        },
    )
    result = normalize_report(raw_df, validation)
    df = result.dataframe

    assert df["order_id"].tolist() == ["SYN-000001", "SYN-000002"]
    assert df["gross_revenue"].tolist() == [10_000, 7_500]
    assert df["net_revenue"].isna().all()
    assert df["status"].tolist() == [
        OrderStatus.COMPLETED.value,
        OrderStatus.OTHER.value,
    ]
    assert result.quality_report.duplicate_rows == 0


def test_normalize_quality_report_detects_all_anomalies() -> None:
    raw_df = pd.DataFrame(
        {
            "id": ["ORD-1", "ORD-1", "ORD-1", "ORD-2", "ORD-3", "ORD-4", "ORD-5", ""],
            "data": [
                "2026-10-01",
                "2026-10-01",
                "2026-10-01",
                "2026-10-02",
                "2026-10-03",
                "2026-10-04",
                "data-invalida",
                "2026-10-05",
            ],
            "produto": [
                "Caderno",
                "Caderno",
                "Caneta",
                "Mochila",
                "Estojo",
                "Notebook",
                "Produto X",
                "Produto Y",
            ],
            "sku": ["SKU-1", "SKU-1", "SKU-2", "SKU-3", "SKU-4", "SKU-5", "S6", ""],
            "qtd": ["1", "1", "1", "1", "2", "1", "1", "0"],
            "receita": [
                "100,00",
                "100,00",
                "50,00",
                "110,00",
                "-20,00",
                "5000,00",
                "80,00",
                "abc",
            ],
        }
    )
    validation = validate_report(
        raw_df,
        Marketplace.GENERIC,
        manual_mapping={
            CanonicalField.ORDER_ID: "id",
            CanonicalField.ORDER_DATE: "data",
            CanonicalField.PRODUCT_NAME: "produto",
            CanonicalField.SKU: "sku",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "receita",
        },
    )
    result = normalize_report(raw_df, validation)
    qr = result.quality_report

    assert qr.total_rows == 8
    assert qr.valid_rows == 6
    assert qr.ignored_rows == 2
    assert qr.duplicate_rows == 1
    assert qr.invalid_dates == 1
    assert qr.non_positive_quantities == 1
    assert qr.negative_values == 1
    assert qr.outlier_rows == 2
    assert qr.null_counts == {"order_id": 1, "sku": 1}
    assert qr.has_issues is True
    assert result.dataframe["order_id"].notna().all()


def test_normalize_rejects_unvalidated_empty_or_all_invalid_reports() -> None:
    raw_df = pd.DataFrame(
        {"data": ["2026-10-01"], "prod": ["Item"], "qtd": ["1"], "val": ["10,00"]}
    )
    bad_val = validate_report(raw_df, Marketplace.SHOPEE)
    with pytest.raises(MissingRequiredColumnsError):
        normalize_report(raw_df, bad_val)

    unrecognized = ValidationReport(
        selected_adapter=Marketplace.GENERIC,
        status=bad_val.status,
        score=0.0,
        warnings=("Planilha vazia.",),
    )
    with pytest.raises(NormalizationError, match="validado"):
        normalize_report(raw_df, unrecognized)

    approved_empty = ValidationReport(
        selected_adapter=Marketplace.GENERIC,
        status=validate_report(
            raw_df,
            Marketplace.GENERIC,
            manual_mapping={
                CanonicalField.ORDER_DATE: "data",
                CanonicalField.PRODUCT_NAME: "prod",
                CanonicalField.QUANTITY: "qtd",
                CanonicalField.GROSS_REVENUE: "val",
            },
        ).status,
        score=1.0,
        column_mapping={
            CanonicalField.ORDER_DATE: "data",
            CanonicalField.PRODUCT_NAME: "prod",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "val",
        },
    )
    with pytest.raises(NormalizationError, match="não possui linhas"):
        normalize_report(raw_df.iloc[0:0], approved_empty)

    with pytest.raises(NormalizationError, match="Coluna mapeada ausente"):
        normalize_report(raw_df.drop(columns=["val"]), approved_empty)

    all_bad = pd.DataFrame(
        {"data": ["bad"], "prod": ["Item"], "qtd": ["0"], "val": ["abc"]}
    )
    with pytest.raises(NormalizationError, match="Nenhuma linha válida"):
        normalize_report(all_bad, approved_empty)


def test_normalize_report_never_logs_cell_contents(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_df = pd.DataFrame(
        {
            "data": ["2026-10-15"],
            "prod": ["SEGREDO-PRODUTO-CONFIDENCIAL"],
            "qtd": ["1"],
            "val": ["100,00"],
            "id": ["SEGREDO-PEDIDO-999"],
        }
    )
    validation = validate_report(
        raw_df,
        Marketplace.GENERIC,
        manual_mapping={
            CanonicalField.ORDER_ID: "id",
            CanonicalField.ORDER_DATE: "data",
            CanonicalField.PRODUCT_NAME: "prod",
            CanonicalField.QUANTITY: "qtd",
            CanonicalField.GROSS_REVENUE: "val",
        },
    )
    with caplog.at_level(logging.INFO, logger="analisador.normalization.pipeline"):
        normalize_report(raw_df, validation)

    joined_logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "SEGREDO-PRODUTO-CONFIDENCIAL" not in joined_logs
    assert "SEGREDO-PEDIDO-999" not in joined_logs
    assert "valid_rows=1" in joined_logs


def test_quality_iqr_outliers_handles_small_or_constant_samples() -> None:
    assert normalization.count_iqr_outliers(pd.Series([100, 200, 300])) == 0
    assert normalization.count_iqr_outliers(pd.Series([100, 100, 100, 100])) == 0
    assert normalization.count_iqr_outliers(pd.Series([100, 105, 110, 115, 5_000])) == 1


def test_normalize_report_tracks_net_revenue_source() -> None:
    df_mixed = pd.DataFrame(
        {
            "data": ["2025-01-01", "2025-01-02"],
            "prod": ["Item A", "Item B"],
            "qtd": ["1", "1"],
            "bruto": ["100,00", "200,00"],
            "taxas": ["10,00", "20,00"],
            "liquido": ["85,00", ""],
        }
    )
    mapping_full: dict[CanonicalField, str] = {
        CanonicalField.ORDER_DATE: "data",
        CanonicalField.PRODUCT_NAME: "prod",
        CanonicalField.QUANTITY: "qtd",
        CanonicalField.GROSS_REVENUE: "bruto",
        CanonicalField.FEES: "taxas",
        CanonicalField.NET_REVENUE: "liquido",
    }
    mixed_res = normalize_report(
        df_mixed,
        validate_report(df_mixed, Marketplace.GENERIC, manual_mapping=mapping_full),
    )
    assert mixed_res.net_revenue_source is NetRevenueSource.MIXED

    reported_df = df_mixed.iloc[[0]]
    reported_res = normalize_report(
        reported_df,
        validate_report(reported_df, Marketplace.GENERIC, manual_mapping=mapping_full),
    )
    assert reported_res.net_revenue_source is NetRevenueSource.REPORTED

    derived_df = df_mixed.drop(columns=["liquido"])
    derived_map: dict[CanonicalField, str] = {
        k: v for k, v in mapping_full.items() if k != CanonicalField.NET_REVENUE
    }
    derived_res = normalize_report(
        derived_df,
        validate_report(derived_df, Marketplace.GENERIC, manual_mapping=derived_map),
    )
    assert derived_res.net_revenue_source is NetRevenueSource.DERIVED

    unavail_df = df_mixed[["data", "prod", "qtd", "bruto"]]
    unavail_map: dict[CanonicalField, str] = {
        CanonicalField.ORDER_DATE: "data",
        CanonicalField.PRODUCT_NAME: "prod",
        CanonicalField.QUANTITY: "qtd",
        CanonicalField.GROSS_REVENUE: "bruto",
    }
    unavail_res = normalize_report(
        unavail_df,
        validate_report(unavail_df, Marketplace.GENERIC, manual_mapping=unavail_map),
    )
    assert unavail_res.net_revenue_source is NetRevenueSource.UNAVAILABLE


def test_dtype_compaction_and_empty_duplicate_guard() -> None:
    empty_qty = compact_quantity_series(pd.Series([], dtype="Int64"))
    assert str(empty_qty.dtype) == "int32"

    large_qty = compact_quantity_series(pd.Series([3_000_000_000], dtype="Int64"))
    assert str(large_qty.dtype) == "int64"

    empty_txt = compact_categorical_text(pd.Series([], dtype="string"))
    assert len(empty_txt) == 0

    assert count_duplicate_rows(pd.DataFrame(), has_mapped_order_id=True) == 0
