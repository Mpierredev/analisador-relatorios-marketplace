"""Multipage views for the Streamlit application."""

from __future__ import annotations

from analisador.ui.pages.about import render_about_page
from analisador.ui.pages.analyze import render_analyze_page
from analisador.ui.pages.how_to_export import render_how_to_export_page
from analisador.ui.pages.supported_formats import render_supported_formats_page

__all__ = [
    "render_about_page",
    "render_analyze_page",
    "render_how_to_export_page",
    "render_supported_formats_page",
]
