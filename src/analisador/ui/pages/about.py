"""Project overview, privacy guarantees, limits, and architecture page."""

from __future__ import annotations

import streamlit as st

from analisador.core.config import (
    CACHE_MAX_ENTRIES,
    CACHE_TTL_SECONDS,
    MAX_FILE_SIZE_MB,
    MAX_ROWS,
)

_PRIVACY_BULLETS = "\n".join(
    (
        "- Os arquivos enviados são lidos apenas em memória na sessão.",
        "- Nenhum dado de comprador, endereço, documento ou conteúdo de "
        "planilha é gravado em disco ou registrado em logs.",
        "- O cache analítico guarda apenas dados canônicos sem "
        "identificadores pessoais, com limite de entradas e expiração.",
    )
)


def render_about_page() -> None:
    """Render architecture overview, operational limits, and privacy policy."""
    st.title("Sobre o Analisador")
    st.write(
        "Aplicação aberta para validação estrutural, normalização e análise de "
        "relatórios de vendas de marketplaces sem depender de banco de dados "
        "ou APIs externas."
    )
    st.subheader("Privacidade e processamento em memória")
    st.markdown(_PRIVACY_BULLETS)

    st.subheader("Limites operacionais")
    max_rows_fmt = f"{MAX_ROWS:,}".replace(",", ".")
    limits_md = (
        f"- **Tamanho máximo por arquivo:** {MAX_FILE_SIZE_MB} MB.\n"
        f"- **Quantidade máxima de linhas:** {max_rows_fmt}.\n"
        f"- **Cache analítico:** até {CACHE_MAX_ENTRIES} entradas "
        f"por até {CACHE_TTL_SECONDS} segundos."
    )
    st.markdown(limits_md)

    st.subheader("Arquitetura em camadas")
    st.markdown(
        "`ingestão` → `adapters` → `validação` → `normalização` → "
        "`análises` → `interface Streamlit`"
    )


__all__ = ["render_about_page"]
