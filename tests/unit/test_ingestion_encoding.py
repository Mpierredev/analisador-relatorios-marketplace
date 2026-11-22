import codecs
from types import SimpleNamespace

import pytest

from analisador.core.config import UTF8_BOM_ENCODING
from analisador.core.errors import UnsupportedFileError
from analisador.ingestion import encoding as encoding_module
from analisador.ingestion.encoding import decode_text, detect_encoding


def test_detect_encoding_for_empty_bytes() -> None:
    assert detect_encoding(b"") == "utf-8"
    assert decode_text(b"") == ("", "utf-8")


def test_detect_and_decode_utf8_and_utf8_bom() -> None:
    csv_text = "Data,Produto,Preço,Descrição\n2026-10-01,Fone,99.90,Promoção\n"

    utf8_bytes = csv_text.encode("utf-8")
    decoded_utf8, detected_utf8 = decode_text(utf8_bytes)
    assert detected_utf8 == "utf-8"
    assert decoded_utf8 == csv_text

    bom_bytes = codecs.BOM_UTF8 + utf8_bytes
    decoded_bom, detected_bom = decode_text(bom_bytes)
    assert detected_bom == UTF8_BOM_ENCODING
    assert decoded_bom == csv_text
    assert not decoded_bom.startswith("\ufeff")


def test_detect_and_decode_utf16_bom() -> None:
    csv_text = "Data;Produto;Preço\n2026-10-01;Teclado;250,00\n"
    payload = csv_text.encode("utf-16")

    decoded, detected = decode_text(payload)
    assert detected == "utf-16"
    assert decoded == csv_text


def test_detect_and_decode_latin1_and_cp1252() -> None:
    csv_text = (
        "Data;Produto;Mês;Descrição;Preço\n01/10/2026;Ação;Outubro;Algodão;59,90\n"
    )
    latin1_bytes = csv_text.encode("latin-1")

    decoded, detected = decode_text(latin1_bytes)
    assert detected in {"cp1252", "latin-1", "iso8859-1", "iso8859-15", "latin_1"}
    assert decoded == csv_text

    cp1252_text = "Produto;Observação\nCabo;“Promoção” € 10,00\n"
    decoded_cp1252, _ = decode_text(cp1252_text.encode("cp1252"))
    assert decoded_cp1252 == cp1252_text


def test_detect_encoding_falls_back_when_normalizer_returns_untrusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = "Produto;Descrição\nCamisa;Algodão \x81\n".encode("latin-1")

    fake_result = SimpleNamespace(best=lambda: SimpleNamespace(encoding="ascii"))
    monkeypatch.setattr(encoding_module, "from_bytes", lambda _data: fake_result)
    assert detect_encoding(payload) == "latin-1"

    unknown_result = SimpleNamespace(
        best=lambda: SimpleNamespace(encoding="encoding-inexistente")
    )
    monkeypatch.setattr(encoding_module, "from_bytes", lambda _data: unknown_result)
    assert detect_encoding(payload) == "latin-1"

    empty_result = SimpleNamespace(best=lambda: None)
    monkeypatch.setattr(encoding_module, "from_bytes", lambda _data: empty_result)
    assert detect_encoding(payload) == "latin-1"

    trusted_result = SimpleNamespace(best=lambda: SimpleNamespace(encoding="cp1252"))
    monkeypatch.setattr(encoding_module, "from_bytes", lambda _data: trusted_result)
    assert detect_encoding("Produto;Descrição\nCamisa;Algodão\n".encode("cp1252")) == (
        "cp1252"
    )


def test_detect_encoding_rejects_binary_and_corrupted_boms() -> None:
    with pytest.raises(UnsupportedFileError, match="parece ser binário"):
        detect_encoding(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    with pytest.raises(UnsupportedFileError, match="marcador UTF-8 inválido"):
        detect_encoding(codecs.BOM_UTF8 + b"\xff\xfe")

    with pytest.raises(UnsupportedFileError, match="UTF-16 inválida"):
        detect_encoding(codecs.BOM_UTF16_LE + b"abc")


def test_detect_encoding_and_decode_text_raise_when_all_decoders_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(encoding_module, "FALLBACK_ENCODINGS", ("ascii",))
    empty_result = SimpleNamespace(best=lambda: None)
    monkeypatch.setattr(encoding_module, "from_bytes", lambda _data: empty_result)

    with pytest.raises(UnsupportedFileError, match="identificar a codificação"):
        detect_encoding("Ação".encode("latin-1"))

    monkeypatch.setattr(encoding_module, "detect_encoding", lambda _b: "ascii")
    with pytest.raises(UnsupportedFileError, match="decodificar o arquivo CSV"):
        decode_text("Ação".encode("latin-1"))
