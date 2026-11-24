"""Supported marketplaces and generic column contract documentation page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analisador.adapters import MarketplaceAdapter, list_adapters
from analisador.core.enums import AdapterSupportTier, CanonicalField
from analisador.core.schema import ALWAYS_REQUIRED_INPUT_FIELDS, CANONICAL_SCHEMA
from analisador.ui.formatting import FIELD_LABELS, SUPPORT_TIER_LABELS


def _render_adapter_section(adapter: MarketplaceAdapter) -> None:
    tier_label = SUPPORT_TIER_LABELS[adapter.support_tier]
    st.subheader(f"{adapter.display_name} — {adapter.report_type} ({tier_label})")
    if adapter.support_tier is AdapterSupportTier.EXPERIMENTAL:
        st.info(
            "Suporte experimental: aguardando exportação real de pedidos da "
            "Shopee Brasil para calibração final."
        )
    st.caption(
        f"Referência observada em {adapter.observed_at}. {adapter.compatibility_note}"
    )
    rows = [
        {
            "Campo canônico": FIELD_LABELS.get(field, field.value),
            "Exigência": "Obrigatório",
            "Aliases aceitos": ", ".join(aliases),
        }
        for field, aliases in adapter.required_fields.items()
    ]
    rows.extend(
        {
            "Campo canônico": FIELD_LABELS.get(field, field.value),
            "Exigência": "Opcional",
            "Aliases aceitos": ", ".join(aliases),
        }
        for field, aliases in adapter.optional_fields.items()
    )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _build_generic_rows() -> list[dict[str, str]]:
    return [
        {
            "Campo canônico": FIELD_LABELS.get(spec.field, spec.field.value),
            "Exigência": (
                "Obrigatório"
                if spec.field in ALWAYS_REQUIRED_INPUT_FIELDS
                else (
                    "Obrigatório (ou Preço unitário)"
                    if spec.field is CanonicalField.GROSS_REVENUE
                    else "Opcional"
                )
            ),
            "Tipo": spec.data_type.value,
            "Aceita nulos": "Sim" if spec.nullable else "Não",
        }
        for spec in CANONICAL_SCHEMA
        if spec.field is not CanonicalField.MARKETPLACE
    ]


def render_supported_formats_page() -> None:
    """Render accepted marketplace adapters and generic schema requirements."""
    st.title("Formatos suportados")
    st.write(
        "Os arquivos devem estar nos formatos `.csv` (UTF-8, UTF-8 com BOM ou Latin-1, "
        "separados por vírgula, ponto e vírgula ou tabulação) ou `.xlsx`."
    )
    for adapter in list_adapters():
        _render_adapter_section(adapter)

    st.subheader("CSV / XLSX genérico (mapeamento manual)")
    st.write(
        "Qualquer planilha tabular pode ser analisada no modo genérico mediante "
        "mapeamento manual dos campos mínimos."
    )
    st.dataframe(pd.DataFrame(_build_generic_rows()), width="stretch", hide_index=True)


__all__ = ["render_supported_formats_page"]
