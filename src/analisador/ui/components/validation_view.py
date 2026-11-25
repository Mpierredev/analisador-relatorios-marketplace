"""Validation summary, data preview, manual column mapping, and dashboard gate."""

from __future__ import annotations

from typing import Final

import pandas as pd
import streamlit as st

from analisador.adapters import get_adapter, has_adapter
from analisador.core.config import PREVIEW_ROW_COUNT
from analisador.core.enums import CanonicalField, Marketplace, ValidationStatus
from analisador.core.models import ValidationReport
from analisador.ui.formatting import FIELD_LABELS, VALIDATION_STATUS_LABELS
from analisador.ui.services import (
    generate_normalized_result,
    revalidate_dataframe,
    translate_exception,
)
from analisador.ui.state import (
    STATE_DASHBOARD_ENABLED,
    STATE_FILE_NAME,
    STATE_LAST_ERROR,
    STATE_MANUAL_MAPPING,
    STATE_NORMALIZED_RESULT,
    STATE_PENDING_FORMAT,
    STATE_RAW_DF,
    STATE_SELECTED_FORMAT,
    STATE_VALIDATION_REPORT,
    reset_dashboard_state,
    set_manual_mapping,
)
from analisador.validation import suggest_column_mapping

_UNMAPPED_OPTION: Final[str] = ""
_MAPPING_FIELDS: Final[tuple[CanonicalField, ...]] = (
    CanonicalField.ORDER_DATE,
    CanonicalField.PRODUCT_NAME,
    CanonicalField.QUANTITY,
    CanonicalField.GROSS_REVENUE,
    CanonicalField.UNIT_PRICE,
    CanonicalField.ORDER_ID,
    CanonicalField.STATUS,
    CanonicalField.SKU,
    CanonicalField.FEES,
    CanonicalField.SHIPPING_COST,
    CanonicalField.NET_REVENUE,
)


def _format_field_list(fields: tuple[CanonicalField, ...]) -> str:
    if not fields:
        return "Nenhuma"
    return ", ".join(FIELD_LABELS.get(field, field.value) for field in fields)


def _apply_suggested_format(suggested_key: str, raw_df: pd.DataFrame) -> None:
    st.session_state[STATE_PENDING_FORMAT] = suggested_key
    st.session_state[STATE_MANUAL_MAPPING] = {}
    reset_dashboard_state()
    try:
        st.session_state[STATE_VALIDATION_REPORT] = revalidate_dataframe(
            raw_df,
            suggested_key,
        )
        st.session_state[STATE_LAST_ERROR] = None
    except Exception as exc:
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)
    st.rerun()


def _render_status_banner(report: ValidationReport, raw_df: pd.DataFrame) -> None:
    status_label = VALIDATION_STATUS_LABELS[report.status]
    file_name = st.session_state.get(STATE_FILE_NAME) or "Arquivo carregado"
    headline = (
        f"**{status_label}** — `{file_name}` "
        f"(compatibilidade: {report.score:.0%}, {len(raw_df)} linhas lidas)."
    )
    if report.status is ValidationStatus.RECOGNIZED:
        st.success(headline)
    elif report.status is ValidationStatus.RECOGNIZED_WITH_WARNINGS:
        st.warning(headline)
    else:
        st.error(headline)

    suggested = report.suggested_adapter
    if suggested and has_adapter(suggested):
        adapter_name = get_adapter(suggested).display_name
        if st.button(
            f"Alternar para o formato sugerido: {adapter_name}",
            key="btn_use_suggested_format",
        ):
            _apply_suggested_format(suggested, raw_df)


def _render_columns_and_warnings(report: ValidationReport) -> None:
    col_req, col_miss, col_opt = st.columns(3)
    col_req.markdown(
        f"**Obrigatórias encontradas**\n\n{_format_field_list(report.found_required)}"
    )
    col_miss.markdown(
        f"**Obrigatórias ausentes**\n\n{_format_field_list(report.missing_required)}"
    )
    col_opt.markdown(
        f"**Opcionais encontradas**\n\n{_format_field_list(report.found_optional)}"
    )
    if report.extra_columns:
        st.caption(
            "Colunas extras preservadas apenas fora do esquema canônico: "
            + ", ".join(report.extra_columns)
        )
    for warning in report.warnings:
        st.warning(warning)


def _resolve_initial_mapping(raw_df: pd.DataFrame) -> dict[CanonicalField, str]:
    stored = st.session_state.get(STATE_MANUAL_MAPPING)
    if isinstance(stored, dict) and stored:
        return dict(stored)
    return dict(suggest_column_mapping(raw_df))


def _render_manual_mapping_form(raw_df: pd.DataFrame) -> None:
    st.subheader("Mapeamento manual de colunas")
    st.caption(
        "Associe ao menos Data do pedido, Nome do produto, Quantidade e "
        "Receita bruta (ou Preço unitário)."
    )
    columns = [_UNMAPPED_OPTION, *(str(col) for col in raw_df.columns)]
    defaults = _resolve_initial_mapping(raw_df)
    selections: dict[CanonicalField, str] = {}

    with st.form("manual_mapping_form"):
        left_col, right_col = st.columns(2)
        for index, field in enumerate(_MAPPING_FIELDS):
            target_col = left_col if index % 2 == 0 else right_col
            default_val = defaults.get(field, _UNMAPPED_OPTION)
            idx = columns.index(default_val) if default_val in columns else 0
            label = FIELD_LABELS.get(field, field.value)
            chosen = target_col.selectbox(
                label,
                options=columns,
                index=idx,
                format_func=lambda val: "— Não mapear —" if val == "" else val,
                key=f"map_field_{field.value}",
            )
            if chosen:
                selections[field] = chosen
        submitted = st.form_submit_button("Aplicar mapeamento manual")

    if submitted:
        _submit_manual_mapping(raw_df, selections)


def _submit_manual_mapping(
    raw_df: pd.DataFrame,
    selections: dict[CanonicalField, str],
) -> None:
    set_manual_mapping(selections)
    st.session_state[STATE_PENDING_FORMAT] = Marketplace.GENERIC.value
    try:
        st.session_state[STATE_VALIDATION_REPORT] = revalidate_dataframe(
            raw_df,
            Marketplace.GENERIC.value,
            manual_mapping=selections,
        )
        st.session_state[STATE_LAST_ERROR] = None
    except Exception as exc:
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)
    st.rerun()


def _handle_generate_click(raw_df: pd.DataFrame, report: ValidationReport) -> None:
    try:
        normalized = generate_normalized_result(raw_df, report)
        st.session_state[STATE_NORMALIZED_RESULT] = normalized
        st.session_state[STATE_DASHBOARD_ENABLED] = True
        st.session_state[STATE_LAST_ERROR] = None
    except Exception as exc:
        reset_dashboard_state()
        st.session_state[STATE_LAST_ERROR] = translate_exception(exc)
    st.rerun()


def _render_generate_button(raw_df: pd.DataFrame) -> None:
    active_report = st.session_state.get(STATE_VALIDATION_REPORT)
    can_generate = (
        isinstance(active_report, ValidationReport)
        and active_report.can_generate_dashboard
    )
    clicked = st.button(
        "Gerar dashboard",
        type="primary",
        disabled=not can_generate,
        key="btn_generate_dashboard",
    )
    if not can_generate:
        st.caption(
            "O botão será liberado quando todas as colunas obrigatórias forem "
            "validadas ou mapeadas manualmente."
        )
    if clicked and isinstance(active_report, ValidationReport):
        _handle_generate_click(raw_df, active_report)


def render_validation_section() -> None:
    """Render structural validation details, preview, mapping, and gate button."""
    raw_df = st.session_state.get(STATE_RAW_DF)
    report = st.session_state.get(STATE_VALIDATION_REPORT)
    if not isinstance(raw_df, pd.DataFrame) or not isinstance(report, ValidationReport):
        return

    st.subheader("Validação e prévia dos dados")
    _render_status_banner(report, raw_df)
    _render_columns_and_warnings(report)

    preview_count = min(len(raw_df), PREVIEW_ROW_COUNT)
    with st.expander(f"Prévia das primeiras {preview_count} linhas", expanded=False):
        st.dataframe(raw_df.head(PREVIEW_ROW_COUNT), width="stretch", hide_index=True)

    selected_format = str(st.session_state.get(STATE_SELECTED_FORMAT, ""))
    if (
        selected_format == Marketplace.GENERIC.value
        or not report.can_generate_dashboard
    ):
        _render_manual_mapping_form(raw_df)
    _render_generate_button(raw_df)


__all__ = ["render_validation_section"]
