"""Main report analysis workflow page."""

from __future__ import annotations

from typing import Final

import streamlit as st

from analisador.ui.components import (
    render_dashboard_section,
    render_ui_error,
    render_upload_controls,
    render_validation_section,
)
from analisador.ui.services import UiError
from analisador.ui.state import (
    STATE_FILE_NAME,
    STATE_LAST_ERROR,
    WorkflowStage,
    get_workflow_stage,
    init_session_state,
)

_STAGE_LABELS: Final[dict[WorkflowStage, str]] = {
    WorkflowStage.WAITING_FILE: "Envie uma planilha ou carregue um exemplo pronto",
    WorkflowStage.VALIDATION_PENDING: (
        "Validação pendente — confira as colunas mapeadas"
    ),
    WorkflowStage.VALIDATED: "Arquivo validado — pronto para gerar o painel",
    WorkflowStage.DASHBOARD_READY: "Painel ativo em memória",
}


def render_analyze_page() -> None:
    """Render the sequential upload, validation, mapping, and dashboard page."""
    init_session_state()
    stage = get_workflow_stage()
    st.title("Analisar relatório de vendas")
    st.caption(_STAGE_LABELS[stage])

    last_error = st.session_state.get(STATE_LAST_ERROR)
    if isinstance(last_error, UiError):
        render_ui_error(last_error)

    if stage is WorkflowStage.DASHBOARD_READY:
        file_name = st.session_state.get(STATE_FILE_NAME) or "relatório atual"
        with st.expander(f"Arquivo carregado: {file_name}", expanded=False):
            render_upload_controls()
            render_validation_section()
        render_dashboard_section()
        return

    render_upload_controls()
    render_validation_section()


__all__ = ["render_analyze_page"]
