"""Public synthetic sample catalog and loader for in-app demos and downloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from analisador.core.enums import Marketplace

_SAMPLES_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "samples"
_CSV_MIME: Final[str] = "text/csv"
_XLSX_MIME: Final[str] = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@dataclass(frozen=True, slots=True)
class SampleAsset:
    """Descriptor for a synthetic sample spreadsheet bundled in samples/."""

    key: str
    title: str
    description: str
    filename: str
    format_key: str
    mime_type: str


_SAMPLE_ASSETS: Final[tuple[SampleAsset, ...]] = (
    SampleAsset(
        key="mercado_livre",
        title="Exemplo Mercado Livre (.xlsx)",
        description=(
            "Planilha sintética com bloco de metadados inicial, datas em português, "
            "SKUs, tarifas, envio e Total (BRL)."
        ),
        filename="exemplo_mercado_livre.xlsx",
        format_key=Marketplace.MERCADO_LIVRE.value,
        mime_type=_XLSX_MIME,
    ),
    SampleAsset(
        key="generico",
        title="Exemplo CSV genérico (.csv)",
        description=(
            "Arquivo UTF-8 separado por ponto e vírgula com cabeçalhos personalizados "
            "para testar o mapeamento manual."
        ),
        filename="exemplo_generico.csv",
        format_key=Marketplace.GENERIC.value,
        mime_type=_CSV_MIME,
    ),
    SampleAsset(
        key="shopee",
        title="Exemplo Shopee Experimental (.xlsx)",
        description=(
            "Planilha sintética baseada nos cabeçalhos documentados do relatório "
            "de pedidos da Shopee."
        ),
        filename="exemplo_shopee_experimental.xlsx",
        format_key=Marketplace.SHOPEE.value,
        mime_type=_XLSX_MIME,
    ),
)


def list_sample_assets() -> tuple[SampleAsset, ...]:
    """Return available bundled synthetic sample spreadsheets."""
    return _SAMPLE_ASSETS


def load_sample_bytes(asset: SampleAsset) -> bytes:
    """Read bytes of a bundled synthetic sample file from samples/."""
    target = _SAMPLES_DIR / asset.filename
    return target.read_bytes()


__all__ = [
    "SampleAsset",
    "list_sample_assets",
    "load_sample_bytes",
]
