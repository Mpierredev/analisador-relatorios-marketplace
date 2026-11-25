"""Unit tests for in-memory CSV and multi-sheet Excel exporters."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from openpyxl import load_workbook

from analisador.core.config import DEFAULT_TIMEZONE
from analisador.core.enums import NetRevenueSource, OrderStatus
from analisador.core.models import QualityReport
from analisador.export import export_canonical_csv, export_summary_excel

_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def _sample_canonical_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "order_id": "ORD-1",
                "order_date": pd.Timestamp("2025-02-01 10:00:00", tz=_TZ),
                "status": OrderStatus.COMPLETED.value,
                "product_name": "Teclado RGB",
                "sku": "TEC-1",
                "quantity": 2,
                "unit_price": 15_000,
                "gross_revenue": 30_000,
                "fees": 3_000,
                "shipping_cost": 1_500,
                "net_revenue": 25_500,
                "marketplace": "mercado_livre",
            },
            {
                "order_id": "ORD-2",
                "order_date": pd.Timestamp("2025-02-02 15:00:00", tz=_TZ),
                "status": OrderStatus.CANCELLED.value,
                "product_name": "Mouse Pad",
                "sku": pd.NA,
                "quantity": 1,
                "unit_price": 5_000,
                "gross_revenue": 5_000,
                "fees": pd.NA,
                "shipping_cost": pd.NA,
                "net_revenue": pd.NA,
                "marketplace": "mercado_livre",
            },
        ]
    )
    for nullable_col in ("unit_price", "fees", "shipping_cost", "net_revenue"):
        df[nullable_col] = df[nullable_col].astype("Int64")
    return df


def test_export_canonical_csv_with_bom_and_decimal_values() -> None:
    dataframe = _sample_canonical_df()

    csv_with_bom = export_canonical_csv(dataframe, include_bom=True)
    assert csv_with_bom.startswith(b"\xef\xbb\xbf")
    parsed = pd.read_csv(io.BytesIO(csv_with_bom), dtype=str, keep_default_na=False)
    assert list(parsed["gross_revenue"]) == ["300.00", "50.00"]
    assert list(parsed["net_revenue"]) == ["255.00", ""]
    assert list(parsed["order_date"]) == ["2025-02-01 10:00:00", "2025-02-02 15:00:00"]

    no_bom = export_canonical_csv(dataframe.iloc[0:0], include_bom=False)
    assert not no_bom.startswith(b"\xef\xbb\xbf")

    neg_and_all_na = dataframe.copy()
    neg_and_all_na["unit_price"] = pd.Series([pd.NA, pd.NA], dtype="Int64")
    neg_and_all_na["net_revenue"] = pd.Series([-5, -105], dtype="Int64")
    csv_neg = export_canonical_csv(neg_and_all_na, include_bom=False).decode("utf-8")
    parsed_neg = pd.read_csv(io.StringIO(csv_neg), dtype=str, keep_default_na=False)
    assert list(parsed_neg["unit_price"]) == ["", ""]
    assert list(parsed_neg["net_revenue"]) == ["-0.05", "-1.05"]


def test_export_summary_excel_creates_five_formatted_sheets() -> None:
    dataframe = _sample_canonical_df()
    quality = QualityReport(
        total_rows=3,
        valid_rows=2,
        ignored_rows=1,
        duplicate_rows=0,
        invalid_dates=1,
        outlier_rows=0,
    )

    xlsx_bytes = export_summary_excel(
        dataframe,
        quality_report=quality,
        net_revenue_source=NetRevenueSource.REPORTED,
    )
    wb = load_workbook(io.BytesIO(xlsx_bytes), data_only=False)
    try:
        assert wb.sheetnames == [
            "Resumo KPIs",
            "Série Temporal",
            "Top Produtos",
            "Curva ABC",
            "Status e Qualidade",
        ]
        kpi_sheet: Any = wb["Resumo KPIs"]
        kpi_values = {
            row[0]: row[1] for row in kpi_sheet.iter_rows(min_row=2, values_only=True)
        }
        assert Decimal(str(kpi_values["Faturamento bruto"])) == Decimal("300.0")
        assert Decimal(str(kpi_values["Receita líquida"])) == Decimal("255.0")
        assert kpi_values["Origem da receita líquida"] == "Informada pelo relatório"
        assert kpi_values["Pedidos"] == 2
        assert kpi_values["Pedidos cancelados"] == 1

        abc_sheet: Any = wb["Curva ABC"]
        abc_rows = list(abc_sheet.iter_rows(min_row=2, values_only=True))
        assert abc_rows[0][1] == "Teclado RGB"
        assert abc_rows[0][7] == "A"
    finally:
        wb.close()

    no_quality_xlsx = export_summary_excel(dataframe, quality_report=None)
    assert len(no_quality_xlsx) > 0
