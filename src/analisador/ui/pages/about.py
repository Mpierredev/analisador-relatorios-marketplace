"""Project overview, privacy guarantees, and operational limits page."""

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
        "- Arquivos enviados ficam apenas na memória da sessão e nunca "
        "são salvos em disco.",
        "- Colunas com dados pessoais de compradores são descartadas na "
        "normalização e nunca entram nos logs.",
        "- O cache analítico guarda apenas agregações do esquema canônico, "
        "isoladas por sessão e expiradas em poucos minutos.",
    )
)


def render_about_page() -> None:
    """Render project overview, privacy guarantees, and operational limits."""
    st.title("Sobre o Analisador")
    st.write(
        "Ferramenta aberta para validar, padronizar e explorar relatórios de vendas "
        "exportados de marketplaces sem precisar de banco de dados ou APIs externas."
    )
    st.subheader("Privacidade")
    st.markdown(_PRIVACY_BULLETS)

    st.subheader("Limites operacionais")
    max_rows_fmt = f"{MAX_ROWS:,}".replace(",", ".")
    limits_md = (
        f"- **Tamanho máximo:** {MAX_FILE_SIZE_MB} MB por arquivo.\n"
        f"- **Linhas máximas:** {max_rows_fmt} linhas por planilha.\n"
        f"- **Cache da sessão:** até {CACHE_MAX_ENTRIES} visões filtradas "
        f"por até {CACHE_TTL_SECONDS} segundos."
    )
    st.markdown(limits_md)


__all__ = ["render_about_page"]
