"""Financial breakdown, weekday demand, and product risk Excel worksheet."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from analisador.analytics import (
    FinancialBreakdown,
    ProductDiagnosticRow,
    WeekdaySalesRow,
)

_HEADER_FONT: Final[Font] = Font(bold=True, color="FFFFFF")
_HEADER_FILL: Final[PatternFill] = PatternFill("solid", fgColor="1D4ED8")
_CURRENCY_FMT: Final[str] = "R$ #,##0.00"
_INT_FMT: Final[str] = "#,##0"
_PCT_FMT: Final[str] = "0.0%"
_MAX_COL_WIDTH: Final[int] = 42
_MAX_PRODUCT_DIAGNOSTIC_ROWS: Final[int] = 25
_PRODUCT_DIAG_HEADERS: Final[list[str]] = [
    "Produto",
    "SKU",
    "Pedidos totais",
    "Cancelados",
    "Taxa cancel.",
    "Faturamento bruto",
    "Receita líquida",
    "Margem líq.",
]
_PRODUCT_DIAG_FORMATS: Final[dict[int, str]] = {
    3: _INT_FMT,
    4: _INT_FMT,
    5: _PCT_FMT,
    6: _CURRENCY_FMT,
    7: _CURRENCY_FMT,
    8: _PCT_FMT,
}


def _to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _style_header_row(ws: Worksheet, row_idx: int) -> None:
    for cell in ws[row_idx]:
        if cell.value is not None:
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL


def _apply_row_formats(
    ws: Worksheet,
    row_idx: int,
    formats: dict[int, str],
) -> None:
    for col_idx, fmt in formats.items():
        cell = ws.cell(row=row_idx, column=col_idx)
        if cell.value is not None:
            cell.number_format = fmt


def _append_financial_block(ws: Worksheet, breakdown: FinancialBreakdown) -> None:
    ws.append(["Indicador financeiro", "Valor (R$)", "% sobre bruto"])
    _style_header_row(ws, ws.max_row)
    gross_share = 1.0 if breakdown.gross_revenue > 0 else None
    rows: tuple[tuple[str, float | None, float | None], ...] = (
        ("Faturamento bruto", float(breakdown.gross_revenue), gross_share),
        (
            "Taxas e comissões",
            _to_float(breakdown.fees_total),
            _to_float(breakdown.fees_pct),
        ),
        (
            "Custos de envio",
            _to_float(breakdown.shipping_total),
            _to_float(breakdown.shipping_pct),
        ),
        (
            "Receita líquida",
            _to_float(breakdown.net_revenue),
            _to_float(breakdown.net_margin_pct),
        ),
        ("Faturamento cancelado", float(breakdown.cancelled_revenue), None),
        ("Faturamento devolvido", float(breakdown.returned_revenue), None),
    )
    for label, amount, pct in rows:
        ws.append([label, amount, pct])
        _apply_row_formats(ws, ws.max_row, {2: _CURRENCY_FMT, 3: _PCT_FMT})


def _append_weekday_block(
    ws: Worksheet,
    weekday_sales: Sequence[WeekdaySalesRow],
) -> None:
    ws.append([])
    ws.append(
        ["Dia da semana", "Pedidos", "Itens", "Faturamento bruto", "Participação"]
    )
    _style_header_row(ws, ws.max_row)
    formats = {2: _INT_FMT, 3: _INT_FMT, 4: _CURRENCY_FMT, 5: _PCT_FMT}
    for row in weekday_sales:
        ws.append(
            [
                row.weekday_label,
                row.order_count,
                row.item_count,
                float(row.gross_revenue),
                float(row.revenue_share),
            ]
        )
        _apply_row_formats(ws, ws.max_row, formats)


def _append_product_diagnostics_block(
    ws: Worksheet,
    product_diagnostics: Sequence[ProductDiagnosticRow],
) -> None:
    ws.append([])
    ws.append(_PRODUCT_DIAG_HEADERS)
    _style_header_row(ws, ws.max_row)
    for row in product_diagnostics[:_MAX_PRODUCT_DIAGNOSTIC_ROWS]:
        values = [
            row.product_name,
            row.sku or "",
            row.total_orders,
            row.cancelled_orders,
            row.cancellation_rate,
            float(row.gross_revenue),
            _to_float(row.net_revenue),
            _to_float(row.net_margin_pct),
        ]
        ws.append(values)
        _apply_row_formats(ws, ws.max_row, _PRODUCT_DIAG_FORMATS)


def _autosize_columns(ws: Worksheet) -> None:
    for col_idx, column_cells in enumerate(ws.columns, start=1):
        max_len = max((len(str(c.value or "")) for c in column_cells), default=8)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max_len + 4, _MAX_COL_WIDTH
        )


def write_diagnostics_sheet(
    workbook: Workbook,
    breakdown: FinancialBreakdown,
    product_diagnostics: Sequence[ProductDiagnosticRow],
    weekday_sales: Sequence[WeekdaySalesRow],
) -> None:
    """Populate the financial breakdown, weekday demand, and product risk sheet."""
    ws = workbook.create_sheet("Diagnóstico Financeiro")
    _append_financial_block(ws, breakdown)
    _append_weekday_block(ws, weekday_sales)
    _append_product_diagnostics_block(ws, product_diagnostics)
    _autosize_columns(ws)


__all__ = ["write_diagnostics_sheet"]
