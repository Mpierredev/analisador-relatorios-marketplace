"""Deterministic synthetic sample spreadsheets generator for demos and tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
_PT_MONTHS = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
}
_CATALOG = (
    ("Fone Bluetooth Sem Fio TWS", "FONE-TWS-01", 129.90),
    ("Teclado Mecânico RGB ABNT2", "TEC-RGB-02", 249.00),
    ("Mouse Gamer Óptico 12000 DPI", "MOU-GAM-03", 99.50),
    ("Suporte Articulado para Monitor", "SUP-MON-04", 169.90),
    ("Hub USB-C 7 em 1 HDMI", "HUB-USC-05", 139.00),
    ("Mousepad Speed Grande 80x30", "PAD-SPD-06", 49.90),
)


def _format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _format_pt_datetime(moment: datetime) -> str:
    month_name = _PT_MONTHS[moment.month]
    return f"{moment.day:02d} de {month_name} de {moment.year} {moment:%H:%M} hs."


_ML_HEADERS = [
    "N.º de venda",
    "Data da venda",
    "Estado",
    "Título do anúncio",
    "SKU",
    "Unidades",
    "Receita por produtos",
    "Tarifa de venda e impostos",
    "Custos de envio",
    "Total (BRL)",
]


def _ml_sample_row(idx: int, base: datetime) -> list[object]:
    statuses = ["Entregue"] * 7 + ["Cancelada pelo comprador", "Devolvida", "A caminho"]
    name, sku, price = _CATALOG[idx % len(_CATALOG)]
    qty = (idx % 3) + 1
    status = statuses[idx % len(statuses)]
    gross = round(price * qty, 2)
    fees = 0.0 if status == "Cancelada pelo comprador" else round(gross * 0.14, 2)
    ship = 0.0 if status == "Cancelada pelo comprador" else 18.90
    net = round(gross - fees - ship, 2)
    return [
        f"20000{idx + 101}",
        _format_pt_datetime(base + timedelta(days=idx * 2)),
        status,
        name,
        sku,
        qty,
        _format_brl(gross),
        _format_brl(fees),
        _format_brl(ship),
        _format_brl(net),
    ]


def _build_mercado_livre_sample(output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Vendas"
    ws.append(["Relatório sintético de vendas — demonstração"])
    ws.append(["Período exportado: 01/01/2025 a 28/02/2025"])
    ws.append([])
    ws.append(_ML_HEADERS)
    base = datetime(2025, 1, 3, 10, 15)
    for idx in range(30):
        ws.append(_ml_sample_row(idx, base))
    wb.save(output_path)
    wb.close()


def _build_generic_csv_sample(output_path: Path) -> None:
    statuses = ["Pago", "Pago", "Pago", "Cancelado", "Enviado"]
    base = datetime(2025, 2, 1, 9, 0)
    rows = []
    for idx in range(25):
        name, sku, price = _CATALOG[idx % len(_CATALOG)]
        qty = (idx % 2) + 1
        status = statuses[idx % len(statuses)]
        gross = round(price * qty, 2)
        fees = 0.0 if status == "Cancelado" else round(gross * 0.10, 2)
        rows.append(
            {
                "data_compra": (base + timedelta(days=idx)).strftime("%d/%m/%Y"),
                "descricao_item": name,
                "qtd": qty,
                "valor_venda": _format_brl(gross),
                "status_pedido": status,
                "codigo_sku": sku,
                "taxas": _format_brl(fees),
            }
        )
    pd.DataFrame(rows).to_csv(output_path, sep=";", index=False, encoding="utf-8")


def _build_shopee_sample(output_path: Path) -> None:
    statuses = ["Concluído"] * 6 + ["Cancelado", "Devolvido", "A enviar", "Enviado"]
    base = datetime(2025, 1, 5, 11, 30)
    rows = []
    for idx in range(20):
        name, sku, price = _CATALOG[idx % len(_CATALOG)]
        qty = (idx % 3) + 1
        status = statuses[idx % len(statuses)]
        gross = round(price * qty, 2)
        commission = 0.0 if status == "Cancelado" else round(gross * 0.14, 2)
        rows.append(
            {
                "ID do pedido": f"2501{idx + 1000:04d}XYZ",
                "Status do pedido": status,
                "Hora de criação do pedido": (base + timedelta(days=idx * 2)).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "Nome do Produto": name,
                "Número de referência SKU": sku,
                "Quantidade": qty,
                "Preço acordado": _format_brl(price),
                "Subtotal do produto": _format_brl(gross),
                "Taxa de comissão": _format_brl(commission),
                "Taxa de envio paga pelo comprador": _format_brl(14.50),
            }
        )
    pd.DataFrame(rows).to_excel(output_path, index=False)


def main() -> None:
    """Generate deterministic synthetic sample reports inside samples/."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    _build_mercado_livre_sample(SAMPLES_DIR / "exemplo_mercado_livre.xlsx")
    _build_generic_csv_sample(SAMPLES_DIR / "exemplo_generico.csv")
    _build_shopee_sample(SAMPLES_DIR / "exemplo_shopee_experimental.xlsx")


if __name__ == "__main__":
    main()
