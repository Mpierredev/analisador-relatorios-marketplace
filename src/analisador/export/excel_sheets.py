"""Worksheet formatting and per-sheet writers for Excel summary exports."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Final

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from analisador.analytics import (
    AbcCurveRow,
    ProductRankingRow,
    StatusDistributionRow,
    TimeSeriesPoint,
)
from analisador.core.enums import NetRevenueSource, OrderStatus
from analisador.core.models import KpiSummary, QualityReport

_HEADER_FONT: Final[Font] = Font(bold=True, color="FFFFFF")
_HEADER_FILL: Final[PatternFill] = PatternFill("solid", fgColor="1D4ED8")
_CURRENCY_FMT: Final[str] = "R$ #,##0.00"
_INT_FMT: Final[str] = "#,##0"
_PCT_FMT: Final[str] = "0.0%"
_DATE_FMT: Final[str] = "yyyy-mm-dd"
_MAX_COL_WIDTH: Final[int] = 42

_NET_SOURCE_LABELS: Final[dict[NetRevenueSource, str]] = {
    NetRevenueSource.REPORTED: "Informada pelo relatório",
    NetRevenueSource.DERIVED: "Derivada (bruta - taxas - envio)",
    NetRevenueSource.MIXED: "Mista (informada e derivada)",
    NetRevenueSource.UNAVAILABLE: "Indisponível (sem taxas/líquido)",
}
_STATUS_LABELS: Final[dict[OrderStatus, str]] = {
    OrderStatus.COMPLETED: "Concluído",
    OrderStatus.CANCELLED: "Cancelado",
    OrderStatus.RETURNED: "Devolvido",
    OrderStatus.IN_PROGRESS: "Em andamento",
    OrderStatus.OTHER: "Outro",
}
_TS_HEADERS: Final[list[str]] = [
    "Período",
    "Faturamento bruto",
    "Receita líquida",
    "Pedidos",
    "Itens",
    "Ticket médio",
]
_PROD_HEADERS: Final[list[str]] = [
    "Posição",
    "Produto",
    "SKU",
    "Quantidade",
    "Pedidos",
    "Faturamento bruto",
    "Receita líquida",
    "Participação",
]
_ABC_HEADERS: Final[list[str]] = [
    "Posição",
    "Produto",
    "SKU",
    "Quantidade",
    "Faturamento bruto",
    "Participação",
    "Acumulado",
    "Classe ABC",
]
_STATUS_HEADERS: Final[list[str]] = [
    "Status",
    "Pedidos",
    "Itens",
    "Faturamento bruto",
    "Part. pedidos",
    "Part. rec.",
]
_TS_FORMATS: Final[dict[int, str]] = {
    1: _DATE_FMT,
    2: _CURRENCY_FMT,
    3: _CURRENCY_FMT,
    4: _INT_FMT,
    5: _INT_FMT,
    6: _CURRENCY_FMT,
}
_PROD_FORMATS: Final[dict[int, str]] = {
    1: _INT_FMT,
    4: _INT_FMT,
    5: _INT_FMT,
    6: _CURRENCY_FMT,
    7: _CURRENCY_FMT,
    8: _PCT_FMT,
}
_ABC_FORMATS: Final[dict[int, str]] = {
    1: _INT_FMT,
    4: _INT_FMT,
    5: _CURRENCY_FMT,
    6: _PCT_FMT,
    7: _PCT_FMT,
}
_STATUS_FORMATS: Final[dict[int, str]] = {
    2: _INT_FMT,
    3: _INT_FMT,
    4: _CURRENCY_FMT,
    5: _PCT_FMT,
    6: _PCT_FMT,
}


def _to_excel_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _style_worksheet(
    worksheet: Worksheet,
    column_formats: dict[int, str] | None = None,
) -> None:
    for cell in worksheet[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
    if column_formats:
        for row in worksheet.iter_rows(min_row=2):
            for col_idx, fmt in column_formats.items():
                target = row[col_idx - 1]
                if target.value is not None:
                    target.number_format = fmt
    for col_idx, column_cells in enumerate(worksheet.columns, start=1):
        max_len = max((len(str(c.value or "")) for c in column_cells), default=8)
        worksheet.column_dimensions[get_column_letter(col_idx)].width = min(
            max_len + 4, _MAX_COL_WIDTH
        )


def write_kpi_sheet(
    workbook: Workbook,
    kpis: KpiSummary,
    net_source: NetRevenueSource,
) -> None:
    """Populate the primary KPI summary sheet."""
    ws = workbook.active
    assert ws is not None
    ws.title = "Resumo KPIs"
    ws.append(["Indicador", "Valor"])
    rows: list[tuple[str, Any, str | None]] = [
        ("Faturamento bruto", _to_excel_float(kpis.gross_revenue), _CURRENCY_FMT),
        ("Receita líquida", _to_excel_float(kpis.net_revenue), _CURRENCY_FMT),
        ("Origem da receita líquida", _NET_SOURCE_LABELS[net_source], None),
        ("Total de taxas", _to_excel_float(kpis.total_fees), _CURRENCY_FMT),
        ("Total de envio", _to_excel_float(kpis.total_shipping), _CURRENCY_FMT),
        ("Pedidos", kpis.order_count, _INT_FMT),
        ("Pedidos cancelados", kpis.cancelled_order_count, _INT_FMT),
        ("Taxa de cancelamento", kpis.cancellation_rate, _PCT_FMT),
        ("Itens vendidos", kpis.item_count, _INT_FMT),
        ("Ticket médio", _to_excel_float(kpis.average_ticket), _CURRENCY_FMT),
    ]
    for label, val, fmt in rows:
        ws.append([label, "Indisponível" if val is None else val])
        if val is not None and fmt is not None:
            ws.cell(row=ws.max_row, column=2).number_format = fmt
    _style_worksheet(ws)


def write_timeseries_sheet(
    workbook: Workbook, points: Sequence[TimeSeriesPoint]
) -> None:
    """Populate the daily time series worksheet."""
    ws = workbook.create_sheet("Série Temporal")
    ws.append(_TS_HEADERS)
    for p in points:
        ws.append(
            [
                p.period_start,
                float(p.gross_revenue),
                _to_excel_float(p.net_revenue),
                p.order_count,
                p.item_count,
                float(p.average_ticket),
            ]
        )
    _style_worksheet(ws, _TS_FORMATS)


def write_products_sheet(workbook: Workbook, rows: Sequence[ProductRankingRow]) -> None:
    """Populate the top products worksheet."""
    ws = workbook.create_sheet("Top Produtos")
    ws.append(_PROD_HEADERS)
    for item in rows:
        ws.append(
            [
                item.rank,
                item.product_name,
                item.sku or "",
                item.quantity,
                item.order_count,
                float(item.gross_revenue),
                _to_excel_float(item.net_revenue),
                float(item.revenue_share),
            ]
        )
    _style_worksheet(ws, _PROD_FORMATS)


def write_abc_sheet(workbook: Workbook, rows: Sequence[AbcCurveRow]) -> None:
    """Populate the ABC Pareto classification worksheet."""
    ws = workbook.create_sheet("Curva ABC")
    ws.append(_ABC_HEADERS)
    for item in rows:
        ws.append(
            [
                item.rank,
                item.product_name,
                item.sku or "",
                item.quantity,
                float(item.gross_revenue),
                float(item.revenue_share),
                float(item.cumulative_share),
                item.abc_class.value,
            ]
        )
    _style_worksheet(ws, _ABC_FORMATS)


def _append_quality_block(ws: Worksheet, quality: QualityReport | None) -> None:
    if quality is None:
        return
    ws.append([])
    ws.append(["Diagnóstico de qualidade", "Quantidade"])
    for label, count in (
        ("Total de linhas lidas", quality.total_rows),
        ("Linhas válidas", quality.valid_rows),
        ("Linhas ignoradas", quality.ignored_rows),
        ("Duplicidades", quality.duplicate_rows),
        ("Datas inválidas", quality.invalid_dates),
        ("Outliers (IQR)", quality.outlier_rows),
    ):
        ws.append([label, count])


def write_status_and_quality_sheet(
    workbook: Workbook,
    status_rows: Sequence[StatusDistributionRow],
    quality: QualityReport | None,
) -> None:
    """Populate order status distribution and data quality summary worksheet."""
    ws = workbook.create_sheet("Status e Qualidade")
    ws.append(_STATUS_HEADERS)
    for item in status_rows:
        ws.append(
            [
                _STATUS_LABELS.get(item.status, item.status.value),
                item.order_count,
                item.item_count,
                float(item.gross_revenue),
                item.order_share,
                float(item.revenue_share),
            ]
        )
    _style_worksheet(ws, _STATUS_FORMATS)
    _append_quality_block(ws, quality)


__all__ = [
    "write_abc_sheet",
    "write_kpi_sheet",
    "write_products_sheet",
    "write_status_and_quality_sheet",
    "write_timeseries_sheet",
]
