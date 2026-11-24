"""Step-by-step export instructions and downloadable synthetic samples."""

from __future__ import annotations

import streamlit as st

from analisador.ui.samples import list_sample_assets, load_sample_bytes

_ML_STEPS = "\n".join(
    (
        "1. Acesse sua conta no painel de vendedor do **Mercado Livre**.",
        "2. Abra **Vendas** e clique em **Relatórios** ou **Exportar vendas**.",
        "3. Escolha o período desejado e baixe em **Excel (.xlsx)**.",
        "4. Envie na aba **Analisar** escolhendo **Mercado Livre (Verificado)**.",
        "   *Nota:* a coluna `Total (BRL)` já considera descontos e subsídios de "
        "frete definidos pela plataforma.",
    )
)
_SHOPEE_STEPS = "\n".join(
    (
        "1. Acesse a **Central do Vendedor da Shopee** pelo navegador.",
        "2. No menu lateral, vá em **Pedidos** → **Meus Pedidos**.",
        "3. Escolha o período e clique em **Exportar** (`Order.all.*.xlsx`).",
        "4. **Não use** relatórios financeiros (*Minha Renda* / *Income Released*) "
        "para análise de produtos, pois eles não contêm itens, SKUs nem quantidades.",
        "5. Como o suporte à Shopee ainda está em nível **Experimental**, caso sua "
        "planilha tenha diferenças de colunas use **CSV / XLSX genérico**.",
    )
)
_GENERIC_STEPS = "\n".join(
    (
        "1. Garanta cabeçalho com: **Data do pedido**, **Nome do produto**, "
        "**Quantidade** e **Receita bruta** (ou **Preço unitário**).",
        "2. Selecione **CSV / XLSX genérico (mapeamento manual)** na aba **Analisar** "
        "e confira as sugestões automáticas de colunas.",
    )
)


def _render_sample_downloads() -> None:
    st.subheader("Baixar arquivos de exemplo sintéticos")
    st.write(
        "Use estas planilhas fictícias para testar o fluxo completo ou adaptar o "
        "layout das suas próprias planilhas."
    )
    for asset in list_sample_assets():
        st.markdown(f"**{asset.title}** — {asset.description}")
        st.download_button(
            f"Baixar {asset.filename}",
            data=load_sample_bytes(asset),
            file_name=asset.filename,
            mime=asset.mime_type,
            key=f"btn_download_sample_{asset.key}",
        )


def render_how_to_export_page() -> None:
    """Render Portuguese export instructions and downloadable sample files."""
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
    st.divider()
    _render_sample_downloads()


__all__ = ["render_how_to_export_page"]
