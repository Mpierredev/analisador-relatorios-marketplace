import pytest

from analisador.core.errors import (
    FileTooLargeError,
    HeaderNotFoundError,
    MissingRequiredColumnsError,
    NormalizationError,
    ReportError,
    UnsupportedFileError,
)


@pytest.mark.parametrize(
    "error_cls",
    [
        UnsupportedFileError,
        FileTooLargeError,
        HeaderNotFoundError,
        MissingRequiredColumnsError,
        NormalizationError,
    ],
)
def test_subclasses_inherit_from_report_error_with_portuguese_defaults(
    error_cls: type[ReportError],
) -> None:
    error = error_cls()

    assert isinstance(error, ReportError)
    assert error.message == error_cls.default_message
    assert error.suggestion == error_cls.default_suggestion
    assert str(error) == error.message
    assert error.message
    assert error.suggestion


def test_report_error_accepts_and_strips_custom_texts() -> None:
    error = ReportError(
        "  Falha personalizada.  ",
        suggestion="  Revise o arquivo enviado.  ",
    )

    assert error.message == "Falha personalizada."
    assert error.suggestion == "Revise o arquivo enviado."
    assert str(error) == "Falha personalizada."


@pytest.mark.parametrize("blank_text", ["", "   ", "\t\n"])
def test_report_error_rejects_blank_message_or_suggestion(blank_text: str) -> None:
    with pytest.raises(ValueError, match="Error message must not be empty"):
        ReportError(blank_text)

    with pytest.raises(ValueError, match="Error suggestion must not be empty"):
        ReportError("Erro válido.", suggestion=blank_text)


def test_missing_required_columns_error_builds_message_from_columns() -> None:
    error = MissingRequiredColumnsError(["Data do Pedido", "Valor Total"])

    assert error.missing_columns == ("Data do Pedido", "Valor Total")
    assert "Data do Pedido, Valor Total" in error.message
    assert error.suggestion == MissingRequiredColumnsError.default_suggestion


def test_missing_required_columns_error_uses_defaults_and_custom_override() -> None:
    default_error = MissingRequiredColumnsError()
    assert default_error.missing_columns == ()
    assert default_error.message == MissingRequiredColumnsError.default_message

    custom_error = MissingRequiredColumnsError(
        ["Quantidade"],
        message="Mapeamento incompleto.",
        suggestion="Selecione a coluna de quantidade.",
    )
    assert custom_error.missing_columns == ("Quantidade",)
    assert custom_error.message == "Mapeamento incompleto."
    assert custom_error.suggestion == "Selecione a coluna de quantidade."
