"""Unit tests for UI services, state helpers, bounded cache, and Altair charts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
import pytest

from analisador.analytics import ProductRankingMetric, TimeGranularity
from analisador.core.enums import CanonicalField, Marketplace, OrderStatus
from analisador.core.errors import MissingRequiredColumnsError
from analisador.ui.components.charts import (
    build_abc_chart,
    build_status_chart,
    build_timeseries_chart,
    build_top_products_chart,
)
from analisador.ui.components.dashboard import _active_comparison
from analisador.ui.services import (
    compute_dashboard_bundle_cached,
    generate_normalized_result,
    process_uploaded_file,
    revalidate_dataframe,
)
from analisador.ui.state import compute_file_signature


def _sample_ml_xlsx_bytes() -> bytes:
    rows = [
        {
            "N.º de venda": "1001",
            "Data da venda": "01/03/2025 10:00",
            "Estado": "Entregue",
            "Título do anúncio": "Teclado Sem Fio",
            "SKU": "TEC-1",
            "Unidades": 2,
            "Receita por produtos": "R$ 300,00",
            "Tarifa de venda e impostos": "R$ 30,00",
            "Custos de envio": "R$ 20,00",
            "Total (BRL)": "R$ 250,00",
        },
        {
            "N.º de venda": "1002",
            "Data da venda": "03/03/2025 14:00",
            "Estado": "Entregue",
            "Título do anúncio": "Mouse Óptico",
            "SKU": "MOU-2",
            "Unidades": 1,
            "Receita por produtos": "R$ 100,00",
            "Tarifa de venda e impostos": "R$ 10,00",
            "Custos de envio": "R$ 5,00",
            "Total (BRL)": "R$ 85,00",
        },
        {
            "N.º de venda": "1003",
            "Data da venda": "04/03/2025 16:00",
            "Estado": "Cancelada pelo comprador",
            "Título do anúncio": "Cabo HDMI",
            "SKU": "CAB-3",
            "Unidades": 1,
            "Receita por produtos": "R$ 50,00",
            "Tarifa de venda e impostos": "R$ 0,00",
            "Custos de envio": "R$ 0,00",
            "Total (BRL)": "R$ 50,00",
        },
    ]
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return buffer.getvalue()


def test_file_signature_and_pipeline_orchestration() -> None:
    content = _sample_ml_xlsx_bytes()
    sig1 = compute_file_signature("ml.xlsx", content)
    sig2 = compute_file_signature("ml.xlsx", content)
    assert sig1 == sig2
    assert sig1 != compute_file_signature("outro.xlsx", content)

    raw_df, report = process_uploaded_file(
        content,
        "ml.xlsx",
        Marketplace.MERCADO_LIVRE.value,
    )
    assert len(raw_df) == 3
    assert report.can_generate_dashboard is True

    shopee_report = revalidate_dataframe(raw_df, Marketplace.SHOPEE.value)
    assert shopee_report.can_generate_dashboard is False
    with pytest.raises(MissingRequiredColumnsError):
        generate_normalized_result(raw_df, shopee_report)

    normalized = generate_normalized_result(raw_df, report)
    assert normalized.quality_report.valid_rows == 3


def test_cached_dashboard_bundle_and_chart_builders() -> None:
    content = _sample_ml_xlsx_bytes()
    raw_df, report = process_uploaded_file(
        content,
        "ml.xlsx",
        Marketplace.MERCADO_LIVRE.value,
    )
    normalized = generate_normalized_result(raw_df, report)
    compute_dashboard_bundle_cached.clear()

    bundle = compute_dashboard_bundle_cached(
        normalized.dataframe,
        "sessao-1:sig-a:mercado_livre",
        date(2025, 3, 1),
        date(2025, 3, 4),
        (OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value),
        "",
        TimeGranularity.DAILY.value,
        ProductRankingMetric.REVENUE.value,
    )
    assert bundle.kpis.gross_revenue == Decimal("400.00")
    assert bundle.kpis.net_revenue == Decimal("335.00")
    assert len(bundle.time_series) == 4
    assert len(bundle.top_products) == 2
    assert len(bundle.abc_curve) == 2
    assert len(bundle.status_distribution) == 2

    # Charts convert cleanly to Vega-Lite specs with Brazilian axis formats
    ts_spec = build_timeseries_chart(bundle.time_series).to_dict()
    assert ts_spec["mark"]["type"] == "line"
    assert ts_spec["encoding"]["x"]["axis"]["format"] == "%d/%m"
    assert _active_comparison(bundle) is None
    assert (
        build_top_products_chart(
            bundle.top_products,
            ProductRankingMetric.REVENUE,
        ).to_dict()["mark"]["type"]
        == "bar"
    )
    assert (
        build_status_chart(bundle.status_distribution).to_dict()["mark"]["type"]
        == "bar"
    )
    assert build_abc_chart(bundle.abc_curve).to_dict()["mark"]["type"] == "bar"

    filtered_bundle = compute_dashboard_bundle_cached(
        normalized.dataframe,
        "sessao-1:sig-a:mercado_livre",
        None,
        None,
        (OrderStatus.COMPLETED.value,),
        "Teclado",
        TimeGranularity.MONTHLY.value,
        ProductRankingMetric.QUANTITY.value,
    )
    assert filtered_bundle.kpis.gross_revenue == Decimal("300.00")
    assert len(filtered_bundle.top_products) == 1
    assert CanonicalField.PRODUCT_NAME.value in normalized.dataframe.columns
    monthly_spec = build_timeseries_chart(filtered_bundle.time_series).to_dict()
    assert monthly_spec["encoding"]["x"]["axis"]["format"] == "%m/%Y"

    # Changing cache_key prevents reusing cached outputs across sessions/datasets
    other_df = normalized.dataframe.iloc[:1].copy()
    isolated_bundle = compute_dashboard_bundle_cached(
        other_df,
        "sessao-2:sig-b:mercado_livre",
        date(2025, 3, 1),
        date(2025, 3, 4),
        (OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value),
        "",
        TimeGranularity.DAILY.value,
        ProductRankingMetric.REVENUE.value,
    )
    assert isolated_bundle.kpis.gross_revenue == Decimal("300.00")


def test_resolve_samples_dir_fallback_to_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    from pathlib import Path

    from analisador.ui import samples as samples_mod

    assert isinstance(tmp_path, Path)
    cwd_samples = tmp_path / "samples"
    cwd_samples.mkdir()
    target_file = cwd_samples / "exemplo_generico.csv"
    target_file.write_bytes(b"col_a;col_b\n1;2\n")

    monkeypatch.setattr(
        samples_mod, "_SAMPLES_DIR_REL_CANDIDATE", tmp_path / "missing_samples"
    )
    monkeypatch.chdir(tmp_path)

    generic_asset = next(
        asset for asset in samples_mod.list_sample_assets() if asset.key == "generico"
    )
    assert samples_mod.load_sample_bytes(generic_asset) == b"col_a;col_b\n1;2\n"
