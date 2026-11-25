"""Streamlit application entrypoint for the marketplace report analyzer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st


def _ensure_src_on_path() -> None:
    src_dir = str(Path(__file__).resolve().parent / "src")
    if sys.path and sys.path[0] == src_dir:
        return
    if src_dir in sys.path:
        sys.path.remove(src_dir)
    sys.path.insert(0, src_dir)


def _build_pages() -> list[Any]:
    _ensure_src_on_path()
    from analisador.ui.pages import (
        render_about_page,
        render_analyze_page,
        render_how_to_export_page,
        render_supported_formats_page,
    )

    return [
        st.Page(
            render_analyze_page, title="Analisar", url_path="analisar", default=True
        ),
        st.Page(
            render_supported_formats_page,
            title="Formatos suportados",
            url_path="formatos-suportados",
        ),
        st.Page(
            render_how_to_export_page,
            title="Como exportar",
            url_path="como-exportar",
        ),
        st.Page(render_about_page, title="Sobre", url_path="sobre"),
    ]


def main() -> None:
    """Configure Streamlit page metadata and multipage navigation."""
    st.set_page_config(
        page_title="Analisador de Relatórios de Marketplaces",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.navigation(_build_pages()).run()


if __name__ == "__main__":
    main()
