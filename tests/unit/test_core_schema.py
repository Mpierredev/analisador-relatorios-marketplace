from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analisador.core.enums import (
    CanonicalField,
    DecimalStyle,
    FieldDataType,
    FieldRequirement,
    Marketplace,
    OrderStatus,
    ValidationStatus,
)
from analisador.core.schema import (
    ALWAYS_REQUIRED_INPUT_FIELDS,
    CANONICAL_COLUMNS,
    CANONICAL_SCHEMA,
    MONETARY_INPUT_FIELDS,
    REQUIRED_CANONICAL_FIELDS,
    SCHEMA_BY_FIELD,
    CanonicalRecord,
    FieldSpec,
    has_required_input_fields,
    missing_required_input_fields,
)


def test_domain_enums_expose_expected_values() -> None:
    assert {status.value for status in OrderStatus} == {
        "concluido",
        "cancelado",
        "devolvido",
        "em_andamento",
        "outro",
    }
    assert {marketplace.value for marketplace in Marketplace} == {
        "shopee",
        "mercado_livre",
        "generico",
    }
    assert {status.value for status in ValidationStatus} == {
        "reconhecido",
        "reconhecido_com_avisos",
        "nao_reconhecido",
    }
    assert {style.value for style in DecimalStyle} == {"br", "us", "auto"}
    assert {dtype.value for dtype in FieldDataType} == {
        "text",
        "datetime",
        "category",
        "integer",
        "decimal",
    }
    assert {req.value for req in FieldRequirement} == {
        "required",
        "conditional",
        "optional",
    }


def test_canonical_schema_is_complete_and_immutable() -> None:
    assert len(CANONICAL_SCHEMA) == len(CanonicalField)
    assert list(CANONICAL_COLUMNS) == list(CanonicalField)
    assert set(SCHEMA_BY_FIELD.keys()) == set(CanonicalField)
    assert set(REQUIRED_CANONICAL_FIELDS) == {
        CanonicalField.ORDER_DATE,
        CanonicalField.PRODUCT_NAME,
        CanonicalField.QUANTITY,
        CanonicalField.GROSS_REVENUE,
        CanonicalField.MARKETPLACE,
    }
    assert set(ALWAYS_REQUIRED_INPUT_FIELDS) == {
        CanonicalField.ORDER_DATE,
        CanonicalField.PRODUCT_NAME,
        CanonicalField.QUANTITY,
    }
    assert set(MONETARY_INPUT_FIELDS) == {
        CanonicalField.GROSS_REVENUE,
        CanonicalField.UNIT_PRICE,
    }

    with pytest.raises(TypeError):
        SCHEMA_BY_FIELD[CanonicalField.SKU] = FieldSpec(  # type: ignore[index]
            field=CanonicalField.SKU,
            data_type=FieldDataType.TEXT,
            requirement=FieldRequirement.OPTIONAL,
            nullable=True,
        )


@pytest.mark.parametrize(
    ("mapped_fields", "expected_missing", "expected_valid"),
    [
        (
            (
                CanonicalField.ORDER_DATE,
                CanonicalField.PRODUCT_NAME,
                CanonicalField.QUANTITY,
                CanonicalField.GROSS_REVENUE,
            ),
            (),
            True,
        ),
        (
            (
                CanonicalField.ORDER_DATE,
                CanonicalField.PRODUCT_NAME,
                CanonicalField.QUANTITY,
                CanonicalField.UNIT_PRICE,
            ),
            (),
            True,
        ),
        (
            (
                CanonicalField.ORDER_DATE,
                CanonicalField.PRODUCT_NAME,
                CanonicalField.QUANTITY,
                CanonicalField.UNIT_PRICE,
                CanonicalField.GROSS_REVENUE,
            ),
            (),
            True,
        ),
        (
            (
                CanonicalField.ORDER_DATE,
                CanonicalField.PRODUCT_NAME,
                CanonicalField.QUANTITY,
            ),
            (CanonicalField.GROSS_REVENUE,),
            False,
        ),
        (
            (
                CanonicalField.ORDER_DATE,
                CanonicalField.QUANTITY,
                CanonicalField.GROSS_REVENUE,
            ),
            (CanonicalField.PRODUCT_NAME,),
            False,
        ),
        (
            (),
            (
                CanonicalField.ORDER_DATE,
                CanonicalField.PRODUCT_NAME,
                CanonicalField.QUANTITY,
                CanonicalField.GROSS_REVENUE,
            ),
            False,
        ),
    ],
)
def test_required_input_fields_validation(
    mapped_fields: tuple[CanonicalField, ...],
    expected_missing: tuple[CanonicalField, ...],
    expected_valid: bool,
) -> None:
    assert missing_required_input_fields(mapped_fields) == expected_missing
    assert has_required_input_fields(mapped_fields) is expected_valid


def test_canonical_record_minimal_and_full_creation() -> None:
    order_date = datetime(2026, 10, 15, 14, 30, tzinfo=UTC)
    minimal = CanonicalRecord(
        order_date=order_date,
        product_name="Fone Bluetooth",
        quantity=2,
        gross_revenue=Decimal("199.80"),
        marketplace=Marketplace.SHOPEE,
    )

    assert minimal.order_id is None
    assert minimal.status is OrderStatus.OTHER
    assert minimal.sku is None
    assert minimal.unit_price is None
    assert minimal.fees is None
    assert minimal.shipping_cost is None
    assert minimal.net_revenue is None

    full = CanonicalRecord(
        order_date=order_date,
        product_name="Teclado Mecânico",
        quantity=1,
        gross_revenue=Decimal("350.00"),
        marketplace="amazon",
        order_id="PED-1001",
        status=OrderStatus.COMPLETED,
        sku="TEC-01",
        unit_price=Decimal("350.00"),
        fees=Decimal("0.00"),
        shipping_cost=Decimal("0"),
        net_revenue=Decimal("350.00"),
    )

    assert full.marketplace == "amazon"
    assert full.order_id == "PED-1001"
    with pytest.raises(AttributeError):
        full.quantity = 5  # type: ignore[misc]


def _make_valid_record(**overrides: object) -> CanonicalRecord:
    defaults: dict[str, object] = {
        "order_date": datetime(2026, 10, 15, 14, 30, tzinfo=UTC),
        "product_name": "Mouse Sem Fio",
        "quantity": 1,
        "gross_revenue": Decimal("89.90"),
        "marketplace": Marketplace.MERCADO_LIVRE,
    }
    defaults.update(overrides)
    return CanonicalRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "match_pattern"),
    [
        ({"product_name": ""}, "product_name must not be empty"),
        ({"product_name": "   "}, "product_name must not be empty"),
        ({"marketplace": "  "}, "marketplace must not be empty"),
        ({"order_id": ""}, "order_id must not be empty"),
        ({"sku": "   "}, "sku must not be empty"),
        ({"quantity": 0}, "quantity must be an integer >= 1"),
        ({"quantity": -3}, "quantity must be an integer >= 1"),
        ({"quantity": True}, "quantity must be an integer >= 1"),
        ({"gross_revenue": None}, "gross_revenue must not be None"),
        ({"gross_revenue": Decimal("NaN")}, "gross_revenue must be a finite Decimal"),
        (
            {"gross_revenue": Decimal("Infinity")},
            "gross_revenue must be a finite Decimal",
        ),
        ({"unit_price": Decimal("NaN")}, "unit_price must be a finite Decimal"),
        ({"net_revenue": Decimal("-Infinity")}, "net_revenue must be a finite Decimal"),
        ({"fees": Decimal("-0.01")}, "fees must not be negative"),
        ({"fees": Decimal("NaN")}, "fees must be a finite Decimal"),
        ({"shipping_cost": Decimal("-5.00")}, "shipping_cost must not be negative"),
    ],
)
def test_canonical_record_rejects_invalid_values(
    overrides: dict[str, object],
    match_pattern: str,
) -> None:
    with pytest.raises(ValueError, match=match_pattern):
        _make_valid_record(**overrides)
