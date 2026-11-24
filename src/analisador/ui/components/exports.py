"""CSV and Excel download buttons rendered inside the dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import streamlit as st

from analisador.export import export_canonical_csv, export_summary_excel
from analisador.normalization import NormalizationResult
from analisador.ui.state import STATE_FILE_NAME

_XLSX_MIME: Final[str] = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _export_stem() -> str:
    raw_name = str(st.session_state.get(STATE_FILE_NAME) or "relatorio")
    stem = Path(raw_name).stem.strip() or "relatorio"
    return f"analisador_{stem}"


def _build_export_payloads(
    result: NormalizationResult,
    start_date: date | None,
    end_date: date | None,
) -> tuple[bytes, bytes]:
    csv_bytes = export_canonical_csv(result.dataframe)
    xlsx_bytes = export_summary_excel(
        result.dataframe,
        quality_report=result.quality_report,
        net_revenue_source=result.net_revenue_source,
        start_date=start_date,
        end_date=end_date,
    )
    return csv_bytes, xlsx_bytes


def render_export_section(
    result: NormalizationResult,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """Render download buttons for normalized CSV and Excel summary workbook."""
    st.markdown("#### Exportar resultados")
    stem = _export_stem()
    csv_bytes, xlsx_bytes = _build_export_payloads(result, start_date, end_date)
    col_csv, col_xlsx = st.columns(2)
    col_csv.download_button(
        "Baixar dados normalizados (.csv)",
        data=csv_bytes,
        file_name=f"{stem}_normalizado.csv",
        mime="text/csv",
        width="stretch",
        key="btn_download_csv",
    )
    col_xlsx.download_button(
        "Baixar resumo gerencial (.xlsx)",
        data=xlsx_bytes,
        file_name=f"{stem}_resumo.xlsx",
        mime=_XLSX_MIME,
        width="stretch",
        key="btn_download_excel",
    )


__all__ = ["render_export_section"]
