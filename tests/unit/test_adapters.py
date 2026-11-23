import pytest

import analisador.adapters as adapters
from analisador.adapters import (
    MERCADO_LIVRE_ADAPTER,
    REGISTERED_ADAPTERS,
    SHOPEE_ADAPTER,
    MarketplaceAdapter,
    get_adapter,
    has_adapter,
    list_adapters,
    normalize_header,
    normalize_status,
)
from analisador.core.enums import CanonicalField, Marketplace, OrderStatus


def test_adapters_package_reexports_match_all() -> None:
    assert adapters.__all__
    for symbol in adapters.__all__:
        assert hasattr(adapters, symbol)


@pytest.mark.parametrize(
    ("raw_header", "expected"),
    [
        ("  Data de Criação do Pedido! ", "data de criacao do pedido"),
        ("Receita por produtos (BRL)", "receita por produtos brl"),
        ("N.º de venda", "n o de venda"),
        ("Nº de venda", "no de venda"),
        ("SKU Reference No.", "sku reference no"),
        ("Tarifa_de--envio / Frete", "tarifa de envio frete"),
        ("   ---   ", ""),
    ],
)
def test_normalize_header_and_status(raw_header: str, expected: str) -> None:
    assert normalize_header(raw_header) == expected
    assert normalize_status(raw_header) == expected


def test_builtin_adapters_declare_metadata_and_compatibility_notes() -> None:
    assert list_adapters() == REGISTERED_ADAPTERS
    assert len(REGISTERED_ADAPTERS) == 2
    assert has_adapter("shopee") is True
    assert has_adapter(" MERCADO_LIVRE ") is True
    assert has_adapter("desconhecido") is False
    assert get_adapter("SHOPEE") is SHOPEE_ADAPTER
    assert get_adapter("mercado_livre") is MERCADO_LIVRE_ADAPTER

    with pytest.raises(KeyError, match="Unknown marketplace adapter"):
        get_adapter("amazon")

    assert SHOPEE_ADAPTER.observed_at == "2026-11-22"
    assert MERCADO_LIVRE_ADAPTER.observed_at == "2026-11-23"

    for adapter in REGISTERED_ADAPTERS:
        assert "compatível com exportações observadas" in (
            adapter.compatibility_note.lower()
        )
        assert "oficial" in adapter.compatibility_note.lower()
        assert CanonicalField.ORDER_DATE in adapter.required_fields
        assert CanonicalField.PRODUCT_NAME in adapter.required_fields
        assert CanonicalField.QUANTITY in adapter.required_fields
        assert CanonicalField.GROSS_REVENUE in adapter.required_fields
        assert adapter.all_normalized_aliases()


def test_marketplace_adapter_freezes_mappings() -> None:
    required = {
        CanonicalField.ORDER_DATE: (" Data ",),
        CanonicalField.PRODUCT_NAME: ("Produto",),
    }
    optional = {CanonicalField.SKU: ("SKU",)}
    status_map = {"Concluído": OrderStatus.COMPLETED}
    adapter = MarketplaceAdapter(
        key=Marketplace.GENERIC,
        display_name="Custom",
        report_type="Vendas",
        observed_at="2026-11-22",
        compatibility_note="Compatível com exportações observadas.",
        required_fields=required,
        optional_fields=optional,
        status_map=status_map,
    )

    assert adapter.required_fields[CanonicalField.ORDER_DATE] == ("Data",)
    assert adapter.status_map["concluido"] is OrderStatus.COMPLETED
    with pytest.raises(TypeError):
        adapter.required_fields[CanonicalField.QUANTITY] = ("Qtd",)  # type: ignore[index]
    with pytest.raises(TypeError):
        adapter.status_map["novo"] = OrderStatus.OTHER  # type: ignore[index]


@pytest.mark.parametrize(
    ("overrides", "match_pattern"),
    [
        ({"key": "   "}, "key must not be empty"),
        ({"display_name": ""}, "display_name must not be empty"),
        ({"report_type": " "}, "report_type must not be empty"),
        ({"compatibility_note": ""}, "compatibility_note must not be empty"),
        ({"observed_at": "22/11/2026"}, "Invalid isoformat string"),
        ({"min_score": -0.1}, "min_score must be between"),
        ({"min_score": 1.5}, "min_score must be between"),
        ({"min_score": True}, "min_score must be between"),
        ({"required_fields": {}}, "required_fields must not be empty"),
        (
            {
                "required_fields": {CanonicalField.ORDER_DATE: ("Data",)},
                "optional_fields": {CanonicalField.ORDER_DATE: ("Data 2",)},
            },
            "must not overlap",
        ),
        (
            {"required_fields": {CanonicalField.ORDER_DATE: ()}},
            "must declare aliases",
        ),
        (
            {"required_fields": {CanonicalField.ORDER_DATE: ("---",)}},
            "invalid empty alias",
        ),
        (
            {"status_map": {"---": OrderStatus.OTHER}},
            "status_map keys must not be empty",
        ),
    ],
)
def test_marketplace_adapter_rejects_invalid_definitions(
    overrides: dict[str, object],
    match_pattern: str,
) -> None:
    defaults: dict[str, object] = {
        "key": "teste",
        "display_name": "Teste",
        "report_type": "Pedidos",
        "observed_at": "2026-11-22",
        "compatibility_note": "Compatível com exportações observadas.",
        "required_fields": {CanonicalField.ORDER_DATE: ("Data",)},
    }
    defaults.update(overrides)
    with pytest.raises(ValueError, match=match_pattern):
        MarketplaceAdapter(**defaults)  # type: ignore[arg-type]
