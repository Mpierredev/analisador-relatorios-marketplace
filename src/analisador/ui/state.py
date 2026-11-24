"""Explicit st.session_state keys and workflow stage helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

import streamlit as st

from analisador.adapters import list_adapters
from analisador.core.enums import CanonicalField, Marketplace
from analisador.core.models import ValidationReport

STATE_SELECTED_FORMAT: Final[str] = "analisador.selected_format"
STATE_PREVIOUS_FORMAT: Final[str] = "analisador.previous_format"
STATE_PENDING_FORMAT: Final[str] = "analisador.pending_format"
STATE_UPLOAD_SIGNATURE: Final[str] = "analisador.upload_signature"
STATE_FILE_NAME: Final[str] = "analisador.file_name"
STATE_RAW_DF: Final[str] = "analisador.raw_df"
STATE_MANUAL_MAPPING: Final[str] = "analisador.manual_mapping"
STATE_VALIDATION_REPORT: Final[str] = "analisador.validation_report"
STATE_DASHBOARD_ENABLED: Final[str] = "analisador.dashboard_enabled"
STATE_NORMALIZED_RESULT: Final[str] = "analisador.normalized_result"
STATE_LAST_ERROR: Final[str] = "analisador.last_error"


class WorkflowStage(StrEnum):
    """Explicit stages of the report validation and analysis workflow."""

    WAITING_FILE = "aguardando_arquivo"
    VALIDATION_PENDING = "validacao_pendente"
    VALIDATED = "validado"
    DASHBOARD_READY = "dashboard_liberado"


def compute_file_signature(filename: str, content: bytes) -> str:
    """Compute an in-memory fingerprint for upload change detection."""
    digest = hashlib.sha256(content).hexdigest()
    return f"{filename}:{len(content)}:{digest}"


def _default_format_key() -> str:
    adapters = list_adapters()
    return adapters[0].key if adapters else Marketplace.GENERIC.value


def init_session_state() -> None:
    """Ensure all workflow session keys exist with deterministic defaults."""
    default_fmt = _default_format_key()
    defaults: dict[str, Any] = {
        STATE_SELECTED_FORMAT: default_fmt,
        STATE_PREVIOUS_FORMAT: default_fmt,
        STATE_UPLOAD_SIGNATURE: None,
        STATE_FILE_NAME: None,
        STATE_RAW_DF: None,
        STATE_MANUAL_MAPPING: {},
        STATE_VALIDATION_REPORT: None,
        STATE_DASHBOARD_ENABLED: False,
        STATE_NORMALIZED_RESULT: None,
        STATE_LAST_ERROR: None,
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def reset_dashboard_state() -> None:
    """Clear generated normalization/dashboard outputs after validation changes."""
    st.session_state[STATE_DASHBOARD_ENABLED] = False
    st.session_state[STATE_NORMALIZED_RESULT] = None


def reset_analysis_state() -> None:
    """Clear uploaded file, validation report, manual mapping, and dashboard."""
    st.session_state[STATE_UPLOAD_SIGNATURE] = None
    st.session_state[STATE_FILE_NAME] = None
    st.session_state[STATE_RAW_DF] = None
    st.session_state[STATE_MANUAL_MAPPING] = {}
    st.session_state[STATE_VALIDATION_REPORT] = None
    st.session_state[STATE_LAST_ERROR] = None
    reset_dashboard_state()


def set_manual_mapping(mapping: Mapping[CanonicalField, str]) -> None:
    """Store manual column mapping and lock dashboard until revalidated."""
    st.session_state[STATE_MANUAL_MAPPING] = dict(mapping)
    reset_dashboard_state()


def get_workflow_stage() -> WorkflowStage:
    """Determine the current explicit stage from session state."""
    if st.session_state.get(STATE_RAW_DF) is None:
        return WorkflowStage.WAITING_FILE
    report = st.session_state.get(STATE_VALIDATION_REPORT)
    if not isinstance(report, ValidationReport) or not report.can_generate_dashboard:
        return WorkflowStage.VALIDATION_PENDING
    if bool(st.session_state.get(STATE_DASHBOARD_ENABLED, False)):
        return WorkflowStage.DASHBOARD_READY
    return WorkflowStage.VALIDATED


__all__ = [
    "STATE_DASHBOARD_ENABLED",
    "STATE_FILE_NAME",
    "STATE_LAST_ERROR",
    "STATE_MANUAL_MAPPING",
    "STATE_NORMALIZED_RESULT",
    "STATE_PENDING_FORMAT",
    "STATE_PREVIOUS_FORMAT",
    "STATE_RAW_DF",
    "STATE_SELECTED_FORMAT",
    "STATE_UPLOAD_SIGNATURE",
    "STATE_VALIDATION_REPORT",
    "WorkflowStage",
    "compute_file_signature",
    "get_workflow_stage",
    "init_session_state",
    "reset_analysis_state",
    "reset_dashboard_state",
    "set_manual_mapping",
]
