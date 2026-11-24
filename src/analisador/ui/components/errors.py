"""Visual error rendering component for user-safe ReportError and fallback notices."""

from __future__ import annotations

import streamlit as st

from analisador.ui.services import UiError


def render_ui_error(error: UiError) -> None:
    """Render an error alert with actionable Portuguese guidance and no tracebacks."""
    st.error(f"**{error.title}**\n\n{error.message}")
    st.info(f"**Como resolver:** {error.suggestion}")


__all__ = ["render_ui_error"]
