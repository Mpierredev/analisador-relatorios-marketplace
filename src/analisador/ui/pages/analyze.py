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
    STATE_LAST_ERROR,
    WorkflowStage,
    get_workflow_stage,
    init_session_state,
)

_STAGE_LABELS: Final[dict[WorkflowStage, str]] = {
    WorkflowStage.WAITING_FILE: "Etapa atual: aguardando envio do arquivo",
    WorkflowStage.VALIDATION_PENDING: "Etapa atual: validação pendente",
    WorkflowStage.VALIDATED: "Etapa atual: validado (pronto para gerar dashboard)",
    WorkflowStage.DASHBOARD_READY: "Etapa atual: dashboard liberado",
}


def render_analyze_page() -> None:
    """Render the sequential upload, validation, mapping, and dashboard page."""
    init_session_state()
    st.title("Analisar relatório de vendas")
    st.caption(_STAGE_LABELS[get_workflow_stage()])

    render_upload_controls()
    last_error = st.session_state.get(STATE_LAST_ERROR)
    if isinstance(last_error, UiError):
        render_ui_error(last_error)

    render_validation_section()
    render_dashboard_section()


__all__ = ["render_analyze_page"]
