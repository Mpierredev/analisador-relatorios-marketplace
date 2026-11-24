"""Report format selector and file uploader component."""

from __future__ import annotations

import streamlit as st

from analisador.core.config import MAX_FILE_SIZE_MB, MAX_ROWS
from analisador.ui.formatting import build_format_options
from analisador.ui.services import (
    process_uploaded_file,
    revalidate_dataframe,
    translate_exception,
)
from analisador.ui.state import (
    STATE_FILE_NAME,
    STATE_LAST_ERROR,
    STATE_MANUAL_MAPPING,
    STATE_PENDING_FORMAT,
    STATE_PREVIOUS_FORMAT,
    STATE_RAW_DF,
    STATE_SELECTED_FORMAT,
    STATE_UPLOAD_SIGNATURE,
    STATE_VALIDATION_REPORT,
    compute_file_signature,
    reset_analysis_state,
    reset_dashboard_state,
)


def _handle_format_change(new_format: str) -> None:
    st.session_state[STATE_PREVIOUS_FORMAT] = new_format
    st.session_state[STATE_MANUAL_MAPPING] = {}
    reset_dashboard_state()
    raw_df = st.session_state.get(STATE_RAW_DF)
    if raw_df is None:
        return
    try:
        st.session_state[STATE_VALIDATION_REPORT] = revalidate_dataframe(
            raw_df,
            new_format,
        )
        st.session_state[STATE_LAST_ERROR] = None
    except Exception as exc:
        st.session_state[STATE_VALIDATION_REPORT] = None
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)


def _handle_uploaded_bytes(filename: str, content: bytes, selected_format: str) -> None:
    signature = compute_file_signature(filename, content)
    if signature == st.session_state.get(STATE_UPLOAD_SIGNATURE):
        return
    st.session_state[STATE_UPLOAD_SIGNATURE] = signature
    st.session_state[STATE_FILE_NAME] = filename
    st.session_state[STATE_MANUAL_MAPPING] = {}
    reset_dashboard_state()
    try:
        raw_df, report = process_uploaded_file(content, filename, selected_format)
        st.session_state[STATE_RAW_DF] = raw_df
        st.session_state[STATE_VALIDATION_REPORT] = report
        st.session_state[STATE_LAST_ERROR] = None
    except Exception as exc:
        st.session_state[STATE_RAW_DF] = None
        st.session_state[STATE_VALIDATION_REPORT] = None
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)


def _sync_format_selector_state(valid_keys: list[str]) -> None:
    pending = st.session_state.pop(STATE_PENDING_FORMAT, None)
    if isinstance(pending, str) and pending in valid_keys:
        st.session_state[STATE_SELECTED_FORMAT] = pending
        st.session_state[STATE_PREVIOUS_FORMAT] = pending
        return
    if st.session_state.get(STATE_SELECTED_FORMAT) not in valid_keys:
        st.session_state[STATE_SELECTED_FORMAT] = valid_keys[0]
        st.session_state[STATE_PREVIOUS_FORMAT] = valid_keys[0]


def _render_format_row(options: list[tuple[str, str]]) -> str:
    option_keys = [key for key, _ in options]
    labels_by_key = dict(options)
    col_fmt, col_action = st.columns([4, 1], vertical_alignment="bottom")
    with col_fmt:
        chosen = st.selectbox(
            "1. Escolha o formato do relatório",
            options=option_keys,
            format_func=lambda key: labels_by_key[key],
            key=STATE_SELECTED_FORMAT,
        )
    with col_action:
        if st.button("Limpar análise", width="stretch", key="btn_reset_flow"):
            reset_analysis_state()
    return str(chosen)


def render_upload_controls() -> None:
    """Render report format selection, file uploader, and reset action."""
    options = build_format_options()
    _sync_format_selector_state([key for key, _ in options])
    chosen = _render_format_row(options)
    if chosen and chosen != st.session_state.get(STATE_PREVIOUS_FORMAT):
        _handle_format_change(chosen)

    uploaded = st.file_uploader(
        "2. Envie a planilha de vendas (.csv ou .xlsx)",
        type=["csv", "xlsx"],
        key="widget_report_file",
    )
    limit_text = f"{MAX_FILE_SIZE_MB} MB e {MAX_ROWS:,} linhas".replace(",", ".")
    st.caption(
        f"Limites: até {limit_text}. Os dados são processados apenas em memória."
    )
    if uploaded is not None:
        _handle_uploaded_bytes(
            uploaded.name,
            bytes(uploaded.getvalue()),
            str(st.session_state[STATE_SELECTED_FORMAT]),
        )


__all__ = ["render_upload_controls"]
