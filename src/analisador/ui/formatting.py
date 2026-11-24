"""Brazilian display formatting and domain label dictionaries for the UI."""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Literal

from analisador.adapters import list_adapters
from analisador.analytics import (
    MetricDelta,
    ProductRankingMetric,
    TimeGranularity,
)
from analisador.core.enums import (
    CanonicalField,
    Marketplace,
    OrderStatus,
    ValidationStatus,
)

UNAVAILABLE_LABEL: Final[str] = "Indisponível"

STATUS_LABELS: Final[dict[OrderStatus, str]] = {
    OrderStatus.COMPLETED: "Concluído",
    OrderStatus.CANCELLED: "Cancelado",
    OrderStatus.RETURNED: "Devolvido",
    OrderStatus.IN_PROGRESS: "Em andamento",
    OrderStatus.OTHER: "Outro",
}

FIELD_LABELS: Final[dict[CanonicalField, str]] = {
    CanonicalField.ORDER_ID: "ID do pedido",
    CanonicalField.ORDER_DATE: "Data do pedido",
    CanonicalField.STATUS: "Status do pedido",
    CanonicalField.PRODUCT_NAME: "Nome do produto",
    CanonicalField.SKU: "SKU",
    CanonicalField.QUANTITY: "Quantidade",
    CanonicalField.UNIT_PRICE: "Preço unitário",
    CanonicalField.GROSS_REVENUE: "Receita bruta",
    CanonicalField.FEES: "Taxas e comissões",
    CanonicalField.SHIPPING_COST: "Custo de envio",
    CanonicalField.NET_REVENUE: "Receita líquida",
    CanonicalField.MARKETPLACE: "Marketplace",
}

VALIDATION_STATUS_LABELS: Final[dict[ValidationStatus, str]] = {
    ValidationStatus.RECOGNIZED: "Formato reconhecido",
    ValidationStatus.RECOGNIZED_WITH_WARNINGS: "Reconhecido com avisos",
    ValidationStatus.UNRECOGNIZED: "Formato não reconhecido",
}

GRANULARITY_LABELS: Final[dict[TimeGranularity, str]] = {
    TimeGranularity.DAILY: "Diária",
    TimeGranularity.WEEKLY: "Semanal",
    TimeGranularity.MONTHLY: "Mensal",
}

RANKING_METRIC_LABELS: Final[dict[ProductRankingMetric, str]] = {
    ProductRankingMetric.REVENUE: "Receita bruta",
    ProductRankingMetric.QUANTITY: "Quantidade vendida",
}


def build_format_options() -> list[tuple[str, str]]:
    """Return UI format selector pairs (format_key, display_label)."""
    options: list[tuple[str, str]] = [
        (adapter.key, f"{adapter.display_name} — {adapter.report_type}")
        for adapter in list_adapters()
    ]
    options.append(
        (Marketplace.GENERIC.value, "CSV / XLSX genérico (mapeamento manual)"),
    )
    return options


def format_brl(value: Decimal | None) -> str:
    """Format a Decimal monetary amount in Brazilian Real notation."""
    if value is None:
        return UNAVAILABLE_LABEL
    sign = "-" if value < 0 else ""
    formatted = (
        f"{abs(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    )
    return f"{sign}R$ {formatted}"


def format_int_br(value: int) -> str:
    """Format an integer with Brazilian thousands separators."""
    return f"{value:,}".replace(",", ".")


def format_percent(value: float | Decimal | None, *, decimals: int = 1) -> str:
    """Format a 0.0-1.0 ratio as a Brazilian percentage string."""
    if value is None:
        return UNAVAILABLE_LABEL
    pct_text = f"{float(value) * 100:.{decimals}f}".replace(".", ",")
    return f"{pct_text}%"


def _format_signed_brl(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{format_brl(value)}"


def _format_signed_int(value: int) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{format_int_br(value)}"


def format_metric_delta(
    delta: MetricDelta,
    *,
    kind: Literal["brl", "int", "pct"],
) -> str | None:
    """Format a MetricDelta into a concise Brazilian string for KPI cards."""
    if delta.absolute_delta is None:
        return None
    if kind == "pct":
        pp = float(delta.absolute_delta) * 100
        prefix = "+" if pp > 0 else ""
        value_text = f"{prefix}{pp:.1f}".replace(".", ",")
        return f"{value_text} p.p."

    if kind == "brl" and isinstance(delta.absolute_delta, Decimal):
        abs_text = _format_signed_brl(delta.absolute_delta)
    else:
        abs_text = _format_signed_int(int(delta.absolute_delta))

    if delta.percentage_delta is None:
        return abs_text
    pct_sign = "+" if delta.percentage_delta > 0 else ""
    pct_text = format_percent(delta.percentage_delta)
    return f"{abs_text} ({pct_sign}{pct_text})"


__all__ = [
    "FIELD_LABELS",
    "GRANULARITY_LABELS",
    "RANKING_METRIC_LABELS",
    "STATUS_LABELS",
    "UNAVAILABLE_LABEL",
    "VALIDATION_STATUS_LABELS",
    "build_format_options",
    "format_brl",
    "format_int_br",
    "format_metric_delta",
    "format_percent",
]
