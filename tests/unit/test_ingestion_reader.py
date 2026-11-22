import codecs
import io
import logging
from collections.abc import Sequence
from datetime import date, datetime
from types import SimpleNamespace

import openpyxl
import pandas as pd
import pytest

import analisador.ingestion as ingestion
from analisador.core.config import UTF8_BOM_ENCODING
from analisador.core.errors import (
    FileTooLargeError,
    HeaderNotFoundError,
    UnsupportedFileError,
)
from analisador.ingestion import reader as reader_module
from analisador.ingestion.reader import read_report, read_report_with_metadata


def _build_xlsx_bytes(
    rows: Sequence[Sequence[object]],
    *,
    sheet_title: str = "Vendas",
) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = sheet_title
    for row in rows:
        sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_ingestion_package_reexports_match_all() -> None:
    assert ingestion.__all__
    for symbol in ingestion.__all__:
        assert hasattr(ingestion, symbol)


def test_read_report_csv_utf8_and_bom() -> None:
    raw_csv = "Pedido,Produto,Quantidade,Valor\n00123,Fone Bluetooth,2,199.80\n"

    df_utf8 = read_report(raw_csv.encode("utf-8"), "vendas.csv")
    assert list(df_utf8.columns) == ["Pedido", "Produto", "Quantidade", "Valor"]
    assert df_utf8.iloc[0]["Pedido"] == "00123"
    assert df_utf8.iloc[0]["Valor"] == "199.80"

    result_bom = read_report_with_metadata(
        codecs.BOM_UTF8 + raw_csv.encode("utf-8"),
        "vendas_bom.CSV",
    )
    assert result_bom.extension == ".csv"
    assert result_bom.encoding == UTF8_BOM_ENCODING
    assert result_bom.separator == ","
    assert result_bom.header_row_index == 0
    assert list(result_bom.dataframe.columns) == [
        "Pedido",
        "Produto",
        "Quantidade",
        "Valor",
    ]


def test_read_report_csv_latin1_semicolon_and_leading_metadata() -> None:
    csv_text = (
        "\n"
        "Relatório de Vendas - Exportação\n"
        "Período;01/10/2026 a 31/10/2026\n"
        "\n"
        " Data ; Produto ; Descrição ; Preço \n"
        "01/10/2026;Camiseta;Algodão;59,90\n"
        "02/10/2026;Calça;NA;120,00\n"
    )

    result = read_report_with_metadata(
        csv_text.encode("latin-1"),
        "relatorio_latin1.csv",
    )

    assert result.separator == ";"
    assert result.header_row_index == 4
    assert list(result.dataframe.columns) == ["Data", "Produto", "Descrição", "Preço"]
    assert len(result.dataframe) == 2
    assert result.dataframe.iloc[0]["Descrição"] == "Algodão"
    assert result.dataframe.iloc[1]["Descrição"] == "NA"


def test_read_report_csv_tab_and_header_only() -> None:
    csv_text = "Data\tProduto\tQuantidade\tValor\n"
    result = read_report_with_metadata(csv_text.encode("utf-8"), "vazio_dados.csv")

    assert result.separator == "\t"
    assert len(result.dataframe) == 0
    assert list(result.dataframe.columns) == ["Data", "Produto", "Quantidade", "Valor"]


def test_read_report_xlsx_with_metadata_types_and_ragged_rows() -> None:
    payload = _build_xlsx_bytes(
        [
            [],
            ["Resumo Mensal de Vendas"],
            [],
            ["Data", "", "Produto", "Produto", "Valor", "", None],
            [datetime(2026, 10, 15, 9, 30), "0042", "Mouse", "Mouse", "89,90"],
            [],
            [date(2026, 10, 16), None, "Teclado", "Teclado", "249,00", "extra"],
            ["2026-10-17", "0099", "Cabo", "Cabo"],
        ],
        sheet_title="Pedidos",
    )

    result = read_report_with_metadata(payload, "vendas.xlsx")

    assert result.extension == ".xlsx"
    assert result.sheet_name == "Pedidos"
    assert result.header_row_index == 3
    assert result.encoding is None
    assert result.separator is None
    assert list(result.dataframe.columns) == [
        "Data",
        "coluna_2",
        "Produto",
        "Produto.1",
        "Valor",
    ]
    assert len(result.dataframe) == 3
    assert result.dataframe.iloc[0]["Data"] == "2026-10-15T09:30:00"
    assert result.dataframe.iloc[0]["coluna_2"] == "0042"
    assert result.dataframe.iloc[1]["Data"] == "2026-10-16T00:00:00"
    assert result.dataframe.iloc[1]["coluna_2"] == ""
    assert result.dataframe.iloc[2]["Valor"] == ""


def test_read_report_csv_exceeding_header_scan_window() -> None:
    lines = ["Data,Produto,Valor", *[f"2026-10-01,Item {i},10.00" for i in range(40)]]
    df = read_report("\n".join(lines).encode("utf-8"), "muitas_linhas_validas.csv")
    assert len(df) == 40


def test_read_report_xlsx_header_only_and_empty_sheet() -> None:
    header_only = _build_xlsx_bytes([["Data", "Produto", "Valor"]])
    df_header_only = read_report(header_only, "apenas_cabecalho.xlsx")
    assert len(df_header_only) == 0
    assert list(df_header_only.columns) == ["Data", "Produto", "Valor"]

    empty_xlsx = _build_xlsx_bytes([])
    with pytest.raises(HeaderNotFoundError):
        read_report(empty_xlsx, "vazio.xlsx")


def test_read_report_rejects_unsupported_empty_and_corrupted_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(UnsupportedFileError, match="não suportado"):
        read_report(b"a,b\n1,2\n", "relatorio.txt")

    with pytest.raises(UnsupportedFileError, match="não suportado"):
        read_report(b"a,b\n1,2\n", "sem_extensao")

    with pytest.raises(HeaderNotFoundError, match="está vazio"):
        read_report(b"", "vazio.csv")

    with pytest.raises(UnsupportedFileError, match=r"arquivo \.xlsx"):
        read_report(b"conteudo invalido", "corrompido.xlsx")

    fake_workbook = SimpleNamespace(worksheets=[], close=lambda: None)
    monkeypatch.setattr(
        reader_module,
        "load_workbook",
        lambda *_args, **_kwargs: fake_workbook,
    )
    with pytest.raises(HeaderNotFoundError):
        read_report(b"placeholder", "sem_abas.xlsx")


def test_read_report_rejects_csv_parser_and_empty_data_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_parser_error(*_args: object, **_kwargs: object) -> pd.DataFrame:
        raise pd.errors.ParserError("broken csv")

    monkeypatch.setattr(pd, "read_csv", _raise_parser_error)
    with pytest.raises(UnsupportedFileError, match="interpretar a estrutura"):
        read_report(b"Data,Produto\n2026-10-01,Mouse\n", "quebrado.csv")

    def _raise_empty_data(*_args: object, **_kwargs: object) -> pd.DataFrame:
        raise pd.errors.EmptyDataError("empty")

    monkeypatch.setattr(pd, "read_csv", _raise_empty_data)
    with pytest.raises(HeaderNotFoundError):
        read_report(b"Data,Produto\n", "vazio_apos_pular.csv")


def test_read_report_enforces_size_and_row_limits() -> None:
    csv_payload = b"Data,Produto,Valor\n01/10/2026,Item,10.00\n"

    with pytest.raises(FileTooLargeError, match=r"1\.0 MB|0\.0 MB"):
        read_report(csv_payload, "grande.csv", max_file_size_bytes=10)

    with pytest.raises(FileTooLargeError, match="1 MB"):
        read_report(
            b"a,b\n" + (b"1,2\n" * 300_000),
            "excede_1mb.csv",
            max_file_size_bytes=1024 * 1024,
        )

    csv_3_rows = b"Data,Produto,Valor\n1,A,10\n2,B,20\n3,C,30\n"
    with pytest.raises(FileTooLargeError, match="2 linhas"):
        read_report(csv_3_rows, "muitas_linhas.csv", max_rows=2)

    xlsx_3_rows = _build_xlsx_bytes(
        [
            ["Data", "Produto", "Valor"],
            ["1", "A", "10"],
            ["2", "B", "20"],
            ["3", "C", "30"],
        ]
    )
    with pytest.raises(FileTooLargeError, match="2 linhas"):
        read_report(xlsx_3_rows, "muitas_linhas.xlsx", max_rows=2)


@pytest.mark.parametrize(
    ("kwargs", "match_pattern"),
    [
        ({"max_file_size_bytes": 0}, "max_file_size_bytes must be a positive integer"),
        (
            {"max_file_size_bytes": True},
            "max_file_size_bytes must be a positive integer",
        ),
        ({"max_rows": 0}, "max_rows must be a positive integer"),
        ({"max_rows": False}, "max_rows must be a positive integer"),
    ],
)
def test_read_report_rejects_invalid_limit_arguments(
    kwargs: dict[str, int],
    match_pattern: str,
) -> None:
    with pytest.raises(ValueError, match=match_pattern):
        read_report(b"a,b\n1,2\n", "dados.csv", **kwargs)


def test_read_report_never_logs_file_contents_or_filename(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_payload = (
        b"Pedido,Cliente,Produto,Valor\n"
        b"PED-SIGILOSO-999,Cliente Secreto,Produto Confidencial,150.00\n"
    )

    with caplog.at_level(logging.DEBUG, logger="analisador"):
        read_report(secret_payload, "relatorio_confidencial_loja.csv")

    combined_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "extensao=.csv" in combined_logs
    assert "PED-SIGILOSO-999" not in combined_logs
    assert "Cliente Secreto" not in combined_logs
    assert "Produto Confidencial" not in combined_logs
    assert "relatorio_confidencial_loja.csv" not in combined_logs
