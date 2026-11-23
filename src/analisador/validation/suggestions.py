"""Automatic column mapping suggestions using name similarity and inferred types."""

from collections.abc import Mapping, Sequence
from difflib import SequenceMatcher
from typing import Final

import pandas as pd

from analisador.adapters.base import normalize_header
from analisador.core.config import (
    GENERIC_NAME_SIMILARITY_THRESHOLD,
    TYPE_INFERENCE_SAMPLE_ROWS,
)
from analisador.core.enums import CanonicalField
from analisador.validation.types import (
    InferredColumnType,
    infer_column_type,
    infer_dataframe_types,
    sample_dataframe_columns,
)

_TYPE_COMPATIBILITY_BONUS: Final[float] = 0.08

_GENERIC_FIELD_HINTS: Final[Mapping[CanonicalField, tuple[str, ...]]] = {
    CanonicalField.ORDER_DATE: (
        "data",
        "data pedido",
        "data do pedido",
        "data da venda",
        "data venda",
        "dt venda",
        "order date",
        "fecha venta",
    ),
    CanonicalField.PRODUCT_NAME: (
        "produto",
        "nome produto",
        "nome do produto",
        "titulo",
        "titulo anuncio",
        "titulo do anuncio",
        "descricao",
        "item",
        "product name",
    ),
    CanonicalField.QUANTITY: (
        "quantidade",
        "qtd",
        "qtde",
        "unidades",
        "quantity",
        "cantidad",
        "units",
    ),
    CanonicalField.GROSS_REVENUE: (
        "valor",
        "valor total",
        "receita",
        "receita bruta",
        "receita por produtos",
        "faturamento",
        "total venda",
        "gross revenue",
        "revenue",
    ),
    CanonicalField.UNIT_PRICE: (
        "preco unitario",
        "valor unitario",
        "preco",
        "unit price",
        "precio unitario",
    ),
    CanonicalField.ORDER_ID: (
        "pedido",
        "id pedido",
        "id do pedido",
        "numero pedido",
        "numero venda",
        "n o de venda",
        "order id",
    ),
    CanonicalField.STATUS: ("status", "situacao", "estado", "order status"),
    CanonicalField.SKU: ("sku", "codigo sku", "referencia sku"),
    CanonicalField.FEES: ("taxa", "taxas", "comissao", "tarifa", "fees"),
    CanonicalField.SHIPPING_COST: ("frete", "envio", "custo envio", "shipping"),
    CanonicalField.NET_REVENUE: (
        "valor liquido",
        "receita liquida",
        "total liquido",
        "total",
        "net revenue",
    ),
}

_COMPATIBLE_TYPES: Final[Mapping[CanonicalField, tuple[InferredColumnType, ...]]] = {
    CanonicalField.ORDER_DATE: (InferredColumnType.DATE,),
    CanonicalField.PRODUCT_NAME: (
        InferredColumnType.TEXT,
        InferredColumnType.CATEGORY,
    ),
    CanonicalField.QUANTITY: (InferredColumnType.INTEGER,),
    CanonicalField.GROSS_REVENUE: (
        InferredColumnType.MONETARY,
        InferredColumnType.INTEGER,
    ),
    CanonicalField.UNIT_PRICE: (
        InferredColumnType.MONETARY,
        InferredColumnType.INTEGER,
    ),
    CanonicalField.ORDER_ID: (
        InferredColumnType.IDENTIFIER,
        InferredColumnType.TEXT,
        InferredColumnType.INTEGER,
    ),
    CanonicalField.STATUS: (InferredColumnType.CATEGORY, InferredColumnType.TEXT),
    CanonicalField.SKU: (InferredColumnType.IDENTIFIER, InferredColumnType.TEXT),
    CanonicalField.FEES: (InferredColumnType.MONETARY,),
    CanonicalField.SHIPPING_COST: (InferredColumnType.MONETARY,),
    CanonicalField.NET_REVENUE: (
        InferredColumnType.MONETARY,
        InferredColumnType.INTEGER,
    ),
}


def _name_candidates(
    columns: Sequence[str],
    inferred_types: Mapping[str, InferredColumnType],
) -> list[tuple[float, int, CanonicalField, str]]:
    candidates: list[tuple[float, int, CanonicalField, str]] = []
    for canonical_field, hints in _GENERIC_FIELD_HINTS.items():
        allowed = _COMPATIBLE_TYPES[canonical_field]
        for col_idx, col_name in enumerate(columns):
            norm = normalize_header(col_name)
            if not norm:
                continue
            col_type = inferred_types[col_name]
            if col_type is not InferredColumnType.EMPTY and col_type not in allowed:
                continue
            ratio = max(SequenceMatcher(None, norm, hint).ratio() for hint in hints)
            if ratio < GENERIC_NAME_SIMILARITY_THRESHOLD:
                continue
            bonus = _TYPE_COMPATIBILITY_BONUS if col_type == allowed[0] else 0.0
            candidates.append((ratio + bonus, -col_idx, canonical_field, col_name))
    return sorted(candidates, reverse=True)


def _pick_longest_text_column(
    columns: Sequence[str],
    used: set[str],
    inferred_types: Mapping[str, InferredColumnType],
    samples: Mapping[str, list[str]],
) -> str | None:
    best_col: str | None = None
    best_avg = -1.0
    for target_type in (InferredColumnType.TEXT, InferredColumnType.CATEGORY):
        for col in columns:
            if col in used or inferred_types[col] is not target_type:
                continue
            vals = samples[col]
            avg_len = sum(len(v) for v in vals) / len(vals) if vals else 0.0
            if avg_len > best_avg:
                best_avg = avg_len
                best_col = col
        if best_col is not None:
            return best_col
    return None


def _apply_type_fallbacks(
    columns: Sequence[str],
    used: set[str],
    inferred: Mapping[str, InferredColumnType],
    mapping: dict[CanonicalField, str],
) -> None:
    type_fallbacks = (
        (CanonicalField.ORDER_DATE, InferredColumnType.DATE),
        (CanonicalField.GROSS_REVENUE, InferredColumnType.MONETARY),
        (CanonicalField.QUANTITY, InferredColumnType.INTEGER),
    )
    for canonical_field, target_type in type_fallbacks:
        if canonical_field is CanonicalField.GROSS_REVENUE and (
            CanonicalField.GROSS_REVENUE in mapping
            or CanonicalField.UNIT_PRICE in mapping
        ):
            continue
        if canonical_field in mapping:
            continue
        match = next(
            (c for c in columns if c not in used and inferred[c] is target_type),
            None,
        )
        if match is not None:
            mapping[canonical_field] = match
            used.add(match)


def suggest_column_mapping(
    dataframe: pd.DataFrame,
    *,
    sample_rows: int = TYPE_INFERENCE_SAMPLE_ROWS,
) -> Mapping[CanonicalField, str]:
    """Suggest a canonical column mapping using name similarity and type inference."""
    samples = sample_dataframe_columns(dataframe, sample_rows)
    columns = list(samples.keys())
    inferred = {col: infer_column_type(vals) for col, vals in samples.items()}
    mapping: dict[CanonicalField, str] = {}
    used: set[str] = set()

    for _, _, canonical_field, col_name in _name_candidates(columns, inferred):
        if canonical_field not in mapping and col_name not in used:
            mapping[canonical_field] = col_name
            used.add(col_name)

    _apply_type_fallbacks(columns, used, inferred, mapping)
    if CanonicalField.PRODUCT_NAME not in mapping:
        product_col = _pick_longest_text_column(columns, used, inferred, samples)
        if product_col is not None:
            mapping[CanonicalField.PRODUCT_NAME] = product_col
    return mapping


__all__ = [
    "InferredColumnType",
    "infer_column_type",
    "infer_dataframe_types",
    "suggest_column_mapping",
]
