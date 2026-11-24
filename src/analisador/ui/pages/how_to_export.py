"""Step-by-step instructions to export sales reports from marketplaces."""

from __future__ import annotations

import streamlit as st

_ML_STEPS = "\n".join(
    (
        "1. Acesse sua conta no painel de vendedor do **Mercado Livre**.",
        "2. Abra **Vendas** e clique em **Relatórios** ou **Exportar vendas**.",
        "3. Escolha o período desejado e baixe em **Excel (.xlsx)**.",
        "4. Envie na aba **Analisar** escolhendo **Mercado Livre**.",
    )
)
_SHOPEE_STEPS = "\n".join(
    (
        "1. Acesse a **Central do Vendedor da Shopee** pelo navegador.",
        "2. No menu lateral, vá em **Pedidos** → **Meus Pedidos** "
        "(não utilize relatórios financeiros *Minha Renda* para produtos).",
        "3. Escolha o período e clique em **Exportar** (`Order.all.*.xlsx`).",
        "4. Para cabeçalhos diferentes, use o modo **CSV / XLSX genérico**.",
    )
)
_GENERIC_STEPS = "\n".join(
    (
        "1. Garanta uma linha de cabeçalho clara com ao menos: **Data do "
        "pedido**, **Nome do produto**, **Quantidade** e **Receita bruta** "
        "(ou **Preço unitário**).",
        "2. Selecione **CSV / XLSX genérico (mapeamento manual)** na aba "
        "**Analisar** e associe as colunas sugeridas.",
    )
)


def render_how_to_export_page() -> None:
    """Render Portuguese instructions on how to export compatible spreadsheets."""
    st.title("Como exportar os relatórios")
    st.write(
        "Siga os passos abaixo na central do seu marketplace para baixar um arquivo "
        "`.xlsx` ou `.csv` compatível."
    )
    st.subheader("Mercado Livre (Relatório de vendas)")
    st.markdown(_ML_STEPS)
    st.subheader("Shopee (Relatório de pedidos)")
    st.markdown(_SHOPEE_STEPS)
    st.subheader("Planilhas próprias (CSV / XLSX genérico)")
    st.markdown(_GENERIC_STEPS)


__all__ = ["render_how_to_export_page"]
