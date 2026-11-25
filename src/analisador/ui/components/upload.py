"""Report format selector, multi-sheet selector, uploader, and 1-click samples."""

from __future__ import annotations

from typing import Final

import streamlit as st

from analisador.core.config import MAX_FILE_SIZE_MB, MAX_ROWS
from analisador.core.enums import Marketplace
from analisador.ui.formatting import build_format_options
from analisador.ui.samples import SampleAsset, list_sample_assets, load_sample_bytes
from analisador.ui.services import (
    detect_xlsx_sheets,
    process_uploaded_file,
    revalidate_dataframe,
    translate_exception,
)
from analisador.ui.state import (
    STATE_AVAILABLE_SHEETS,
    STATE_FILE_NAME,
    STATE_LAST_ERROR,
    STATE_MANUAL_MAPPING,
    STATE_MULTI_SHEET_BYTES,
    STATE_PENDING_FORMAT,
    STATE_PREVIOUS_FORMAT,
    STATE_RAW_DF,
    STATE_SELECTED_FORMAT,
    STATE_SELECTED_SHEET,
    STATE_UPLOAD_SIGNATURE,
    STATE_VALIDATION_REPORT,
    compute_file_signature,
    reset_analysis_state,
    reset_dashboard_state,
)
from analisador.validation import suggest_column_mapping

_XLSX_MIME_EXT: Final[str] = ".xlsx"


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


def _load_bytes_into_session(
    filename: str,
    content: bytes,
    selected_format: str,
    *,
    auto_suggest_generic: bool = False,
) -> None:
    reset_dashboard_state()
    sheets = detect_xlsx_sheets(content, filename)
    selected_sheet = sheets[0] if sheets else None
    st.session_state[STATE_AVAILABLE_SHEETS] = sheets if len(sheets) > 1 else ()
    st.session_state[STATE_SELECTED_SHEET] = selected_sheet
    st.session_state[STATE_MULTI_SHEET_BYTES] = content if len(sheets) > 1 else None

    raw_df, report = process_uploaded_file(
        content,
        filename,
        selected_format,
        sheet_name=selected_sheet,
    )
    if auto_suggest_generic and selected_format == Marketplace.GENERIC.value:
        suggested = dict(suggest_column_mapping(raw_df))
        st.session_state[STATE_MANUAL_MAPPING] = suggested
        report = revalidate_dataframe(raw_df, selected_format, manual_mapping=suggested)
    else:
        st.session_state[STATE_MANUAL_MAPPING] = {}

    st.session_state[STATE_RAW_DF] = raw_df
    st.session_state[STATE_VALIDATION_REPORT] = report
    st.session_state[STATE_LAST_ERROR] = None


def _handle_uploaded_bytes(filename: str, content: bytes, selected_format: str) -> None:
    signature = compute_file_signature(filename, content)
    if signature == st.session_state.get(STATE_UPLOAD_SIGNATURE):
        return
    st.session_state[STATE_UPLOAD_SIGNATURE] = signature
    st.session_state[STATE_FILE_NAME] = filename
    try:
        _load_bytes_into_session(filename, content, selected_format)
    except Exception as exc:
        st.session_state[STATE_RAW_DF] = None
        st.session_state[STATE_VALIDATION_REPORT] = None
        st.session_state[STATE_AVAILABLE_SHEETS] = ()
        st.session_state[STATE_MULTI_SHEET_BYTES] = None
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)


def _activate_sample_asset(asset: SampleAsset) -> None:
    content = load_sample_bytes(asset)
    st.session_state[STATE_PENDING_FORMAT] = asset.format_key
    st.session_state[STATE_UPLOAD_SIGNATURE] = compute_file_signature(
        asset.filename, content
    )
    st.session_state[STATE_FILE_NAME] = asset.filename
    try:
        _load_bytes_into_session(
            asset.filename,
            content,
            asset.format_key,
            auto_suggest_generic=True,
        )
    except Exception as exc:
        st.session_state[STATE_RAW_DF] = None
        st.session_state[STATE_VALIDATION_REPORT] = None
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)
    st.rerun()


def _render_sample_buttons() -> None:
    st.caption("Ou carregue uma planilha de exemplo pronta em 1 clique:")
    assets = list_sample_assets()
    cols = st.columns(len(assets))
    for idx, asset in enumerate(assets):
        if cols[idx].button(
            asset.title,
            width="stretch",
            key=f"btn_load_sample_{asset.key}",
        ):
            _activate_sample_asset(asset)


def _render_sheet_selector() -> None:
    sheets = st.session_state.get(STATE_AVAILABLE_SHEETS, ())
    raw_bytes = st.session_state.get(STATE_MULTI_SHEET_BYTES)
    filename = str(st.session_state.get(STATE_FILE_NAME) or f"planilha{_XLSX_MIME_EXT}")
    if len(sheets) <= 1 or not isinstance(raw_bytes, bytes):
        return
    current = str(st.session_state.get(STATE_SELECTED_SHEET) or sheets[0])
    idx = sheets.index(current) if current in sheets else 0
    chosen = st.selectbox(
        "Aba da planilha (.xlsx)", options=list(sheets), index=idx, key="widget_sheet"
    )
    if chosen != current:
        st.session_state[STATE_SELECTED_SHEET] = chosen
        reset_dashboard_state()
        raw_df, report = process_uploaded_file(
            raw_bytes,
            filename,
            str(st.session_state[STATE_SELECTED_FORMAT]),
            sheet_name=chosen,
        )
        st.session_state[STATE_RAW_DF] = raw_df
        st.session_state[STATE_VALIDATION_REPORT] = report
        st.rerun()


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
            "Formato do relatório",
            options=option_keys,
            format_func=lambda key: labels_by_key[key],
            key=STATE_SELECTED_FORMAT,
        )
    with col_action:
        if st.button("Limpar análise", width="stretch", key="btn_reset_flow"):
            reset_analysis_state()
    return str(chosen)


def render_upload_controls() -> None:
    """Render format selector, file uploader, sheet switcher, and 1-click samples."""
    options = build_format_options()
    _sync_format_selector_state([key for key, _ in options])
    chosen = _render_format_row(options)
    if chosen and chosen != st.session_state.get(STATE_PREVIOUS_FORMAT):
        _handle_format_change(chosen)

    uploaded = st.file_uploader(
        "Planilha de vendas (.csv ou .xlsx)",
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
    _render_sheet_selector()
    _render_sample_buttons()


__all__ = ["render_upload_controls"]
