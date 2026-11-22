from pathlib import Path

import pytest

import analisador.validation as validation
from analisador.adapters import (
    MERCADO_LIVRE_ADAPTER,
    SHOPEE_ADAPTER,
    MarketplaceAdapter,
)
from analisador.core.enums import CanonicalField, Marketplace, ValidationStatus
from analisador.ingestion import read_report
from analisador.validation import (
    classify_match_status,
    detect_best_adapter,
    match_adapter_headers,
    score_adapters,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture_headers(filename: str) -> list[str]:
    payload = (FIXTURES_DIR / filename).read_bytes()
    dataframe = read_report(payload, filename)
    return [str(column) for column in dataframe.columns]


def test_validation_package_reexports_match_all() -> None:
    assert validation.__all__
    for symbol in validation.__all__:
        assert hasattr(validation, symbol)


@pytest.mark.parametrize(
    ("fixture_name", "expected_adapter"),
    [
        ("shopee_pedidos_pt.csv", Marketplace.SHOPEE),
        ("shopee_orders_en.csv", Marketplace.SHOPEE),
        ("shopee_pedidos_es.csv", Marketplace.SHOPEE),
        ("mercado_livre_vendas_pt.csv", Marketplace.MERCADO_LIVRE),
        ("mercado_livre_ventas_es.csv", Marketplace.MERCADO_LIVRE),
        ("mercado_livre_sales_en.csv", Marketplace.MERCADO_LIVRE),
    ],
)
def test_detects_supported_marketplace_fixtures_in_all_languages(
    fixture_name: str,
    expected_adapter: Marketplace,
) -> None:
    headers = _load_fixture_headers(fixture_name)
    best = detect_best_adapter(headers)

    assert best is not None
    assert best.adapter_key == expected_adapter
    assert best.missing_required == ()
    assert best.score >= 0.85
    assert best.fuzzy_matches == {}
    assert best.conflicting_columns == ()

    adapter = (
        SHOPEE_ADAPTER
        if expected_adapter is Marketplace.SHOPEE
        else MERCADO_LIVRE_ADAPTER
    )
    assert classify_match_status(best, adapter) is ValidationStatus.RECOGNIZED
    adapter_score = best.to_adapter_score()
    assert adapter_score.adapter_key == expected_adapter
    assert adapter_score.score == best.score


def test_detects_shopee_with_extra_columns() -> None:
    headers = _load_fixture_headers("shopee_colunas_extras.csv")
    best = detect_best_adapter(headers)

    assert best is not None
    assert best.adapter_key == Marketplace.SHOPEE
    assert best.extra_columns == ("Observação Interna", "Canal Campanha")
    assert best.conflicting_columns == ()
    assert classify_match_status(best, SHOPEE_ADAPTER) is ValidationStatus.RECOGNIZED


def test_detects_missing_required_columns_and_marks_unrecognized() -> None:
    headers = _load_fixture_headers("shopee_colunas_faltando.csv")
    result = match_adapter_headers(
        headers,
        SHOPEE_ADAPTER,
        other_adapters=(SHOPEE_ADAPTER, MERCADO_LIVRE_ADAPTER),
    )

    assert result.adapter_key == Marketplace.SHOPEE
    assert set(result.missing_required) == {
        CanonicalField.QUANTITY,
        CanonicalField.GROSS_REVENUE,
    }
    assert result.score < SHOPEE_ADAPTER.min_score
    assert classify_match_status(result, SHOPEE_ADAPTER) is (
        ValidationStatus.UNRECOGNIZED
    )
    assert detect_best_adapter(headers) is None


def test_detects_shopee_with_altered_column_names_via_similarity() -> None:
    headers = _load_fixture_headers("shopee_nomes_alterados.csv")
    best = detect_best_adapter(headers)

    assert best is not None
    assert best.adapter_key == Marketplace.SHOPEE
    assert best.missing_required == ()
    assert CanonicalField.ORDER_DATE in best.fuzzy_matches
    assert CanonicalField.PRODUCT_NAME in best.fuzzy_matches
    assert CanonicalField.QUANTITY in best.fuzzy_matches
    assert CanonicalField.GROSS_REVENUE in best.fuzzy_matches
    assert classify_match_status(best, SHOPEE_ADAPTER) is (
        ValidationStatus.RECOGNIZED_WITH_WARNINGS
    )


def test_rejects_unknown_marketplace_and_penalizes_cross_adapter_conflicts() -> None:
    unknown_headers = _load_fixture_headers("outro_marketplace_desconhecido.csv")
    assert detect_best_adapter(unknown_headers) is None
    ranked_unknown = score_adapters(unknown_headers)
    assert all(item.score < SHOPEE_ADAPTER.min_score for item in ranked_unknown)

    ml_headers = _load_fixture_headers("mercado_livre_vendas_pt.csv")
    shopee_on_ml = match_adapter_headers(
        ml_headers,
        SHOPEE_ADAPTER,
        other_adapters=(SHOPEE_ADAPTER, MERCADO_LIVRE_ADAPTER),
    )
    assert shopee_on_ml.conflicting_columns
    assert shopee_on_ml.score < SHOPEE_ADAPTER.min_score

    ranked_ml = score_adapters(ml_headers)
    assert ranked_ml[0].adapter_key == Marketplace.MERCADO_LIVRE
    assert ranked_ml[1].adapter_key == Marketplace.SHOPEE
    assert ranked_ml[0].score > ranked_ml[1].score


def test_detection_edge_cases_empty_headers_no_adapters_and_thresholds() -> None:
    assert detect_best_adapter(["Data", "Produto"], adapters=()) is None

    empty_match = match_adapter_headers(
        ["", "   "],
        SHOPEE_ADAPTER,
        other_adapters=(SHOPEE_ADAPTER, MERCADO_LIVRE_ADAPTER),
    )
    assert empty_match.score == 0.0
    assert empty_match.extra_columns == ()
    assert empty_match.conflicting_columns == ()

    minimal_adapter = MarketplaceAdapter(
        key="simples",
        display_name="Simples",
        report_type="Vendas",
        observed_at="2026-11-22",
        compatibility_note="Compatível com exportações observadas.",
        required_fields={
            CanonicalField.ORDER_DATE: ("Data",),
            CanonicalField.PRODUCT_NAME: ("Produto",),
        },
        min_score=0.5,
    )
    exact_minimal = match_adapter_headers(["Data", "Produto"], minimal_adapter)
    assert exact_minimal.score == 0.7
    assert classify_match_status(exact_minimal, minimal_adapter) is (
        ValidationStatus.RECOGNIZED_WITH_WARNINGS
    )

    competing_fuzzy = match_adapter_headers(
        [
            "Data pedido",
            "Data do pedidos",
            "Nome Produto",
            "Quantidades",
            "Valor total pedido",
        ],
        SHOPEE_ADAPTER,
    )
    assert competing_fuzzy.column_mapping[CanonicalField.ORDER_DATE] == (
        "Data do pedidos"
    )
    assert "Data pedido" in competing_fuzzy.extra_columns

    with pytest.raises(ValueError, match="similarity_threshold must be between"):
        match_adapter_headers(["Data"], SHOPEE_ADAPTER, similarity_threshold=1.5)

    with pytest.raises(ValueError, match="similarity_threshold must be between"):
        match_adapter_headers(["Data"], SHOPEE_ADAPTER, similarity_threshold=True)
