"""Visual error and quality diagnostics components."""

from __future__ import annotations

import streamlit as st

from analisador.core.models import QualityReport
from analisador.ui.formatting import format_int_br
from analisador.ui.services import UiError


def render_ui_error(error: UiError) -> None:
    """Render an error alert with actionable Portuguese guidance and no tracebacks."""
    st.error(f"**{error.title}**\n\n{error.message}")
    st.info(f"**Como resolver:** {error.suggestion}")


def render_quality_summary(quality: QualityReport) -> None:
    """Render collapsible data quality metrics and normalization warnings."""
    valid_fmt = format_int_br(quality.valid_rows)
    title = f"Relatório de qualidade dos dados — {valid_fmt} linhas válidas"
    with st.expander(title, expanded=quality.has_issues):
        cols = st.columns(5)
        cols[0].metric("Linhas válidas", valid_fmt)
        cols[1].metric("Linhas ignoradas", format_int_br(quality.ignored_rows))
        cols[2].metric("Duplicidades", format_int_br(quality.duplicate_rows))
        cols[3].metric("Datas inválidas", format_int_br(quality.invalid_dates))
        cols[4].metric("Outliers (IQR)", format_int_br(quality.outlier_rows))
        if quality.non_positive_quantities > 0 or quality.negative_values > 0:
            st.caption(
                f"Quantidades <= 0: {quality.non_positive_quantities} | "
                f"Valores negativos: {quality.negative_values}."
            )
        for warning in quality.warnings:
            st.warning(warning)


__all__ = ["render_quality_summary", "render_ui_error"]
