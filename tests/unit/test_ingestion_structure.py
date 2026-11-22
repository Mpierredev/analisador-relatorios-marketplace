import pytest

from analisador.core.errors import HeaderNotFoundError
from analisador.ingestion.structure import detect_header_row, detect_separator


@pytest.mark.parametrize(
    ("csv_text", "expected_separator"),
    [
        ("Data,Produto,Quantidade,Valor\n2026-10-01,Fone,2,199.80\n", ","),
        (
            "Data;Produto;Quantidade;Valor\n"
            "01/10/2026;Fone;1;10,50\n"
            "02/10/2026;Cabo;2;25,00\n"
            "03/10/2026;Capa;1;19,90\n",
            ";",
        ),
        (
            "Data\tProduto\tDescrição\tValor\n"
            "2026-10-01\tMouse\tSem fio, preto; novo\t89,90\n",
            "\t",
        ),
        (
            'Data,Produto,Valor\n2026-10-01,"Fone, Bluetooth","1.234,56"\n',
            ",",
        ),
        ("Data;Produto;Valor\n", ";"),
        (
            "Relatório de Vendas, Loja Centro\n"
            "\n"
            "Data;Produto;Quantidade;Valor\n"
            "01/10/2026;Mouse;1;50,00\n"
            "02/10/2026;Teclado;2;120,00\n",
            ";",
        ),
    ],
)
def test_detect_separator_identifies_delimiter(
    csv_text: str,
    expected_separator: str,
) -> None:
    assert detect_separator(csv_text) == expected_separator


@pytest.mark.parametrize(
    "invalid_text",
    [
        "",
        "   \n\n\t \n",
        "ColunaUnica\nvalor1\nvalor2\n",
    ],
)
def test_detect_separator_rejects_empty_or_single_column_text(
    invalid_text: str,
) -> None:
    with pytest.raises(HeaderNotFoundError):
        detect_separator(invalid_text)


def test_detect_header_row_handles_leading_blank_and_metadata_rows() -> None:
    rows = [
        [],
        ["   ", ""],
        ["Relatório de Pedidos - Exportação"],
        ["Período", "01/10/2026 a 31/10/2026"],
        [],
        ["ID do Pedido", "Data do Pedido", "Produto", "Quantidade", "Valor Total"],
        ["PED-01", "2026-10-01", "Fone Bluetooth", "2", "199,80"],
        ["PED-02", "2026-10-02", "Cabo USB-C", "1", "29,90"],
    ]

    assert detect_header_row(rows) == 5


def test_detect_header_row_handles_header_only_and_tie_break() -> None:
    header_only = [["Data", "Produto", "Quantidade", "Valor"]]
    assert detect_header_row(header_only) == 0

    all_text_rows = [
        ["Produto", "Categoria", "Status"],
        ["Camiseta", "Vestuário", "Concluído"],
    ]
    assert detect_header_row(all_text_rows) == 0


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [[""], ["   "]],
        [["Coluna única"], ["Dado único"]],
        [
            ["1", "2026-10-01", "R$ 100,00", "2"],
            ["2", "2026-10-02T14:30:00Z", "US$ 50.00", "1"],
        ],
    ],
)
def test_detect_header_row_rejects_missing_or_non_textual_headers(
    rows: list[list[str]],
) -> None:
    with pytest.raises(HeaderNotFoundError):
        detect_header_row(rows)
