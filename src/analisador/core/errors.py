"""Typed domain error hierarchy with user-facing guidance in Portuguese."""

from collections.abc import Sequence
from typing import ClassVar


class ReportError(Exception):
    """Base error for expected failures during report processing."""

    default_message: ClassVar[str] = "Não foi possível processar o relatório."
    default_suggestion: ClassVar[str] = "Verifique o arquivo enviado e tente novamente."

    def __init__(
        self,
        message: str | None = None,
        *,
        suggestion: str | None = None,
    ) -> None:
        resolved_message = self.default_message if message is None else message.strip()
        if not resolved_message:
            raise ValueError("Error message must not be empty.")

        resolved_suggestion = (
            self.default_suggestion if suggestion is None else suggestion.strip()
        )
        if not resolved_suggestion:
            raise ValueError("Error suggestion must not be empty.")

        self.message: str = resolved_message
        self.suggestion: str = resolved_suggestion
        super().__init__(self.message)


class UnsupportedFileError(ReportError):
    """Raised when the uploaded file format or encoding is not supported."""

    default_message: ClassVar[str] = "Formato de arquivo não suportado."
    default_suggestion: ClassVar[str] = (
        "Envie um arquivo válido nos formatos .csv ou .xlsx."
    )


class FileTooLargeError(ReportError):
    """Raised when the file exceeds size or row limits."""

    default_message: ClassVar[str] = "O arquivo enviado ultrapassa o limite permitido."
    default_suggestion: ClassVar[str] = (
        "Divida o relatório em períodos menores ou reduza a quantidade de linhas."
    )


class HeaderNotFoundError(ReportError):
    """Raised when no valid header row can be found in the report."""

    default_message: ClassVar[str] = (
        "Não foi possível identificar a linha de cabeçalho no arquivo."
    )
    default_suggestion: ClassVar[str] = (
        "Confirme se o arquivo não está vazio e contém uma linha com nomes de colunas."
    )


class MissingRequiredColumnsError(ReportError):
    """Raised when mandatory columns are missing for the selected format."""

    default_message: ClassVar[str] = (
        "O relatório não contém todas as colunas obrigatórias."
    )
    default_suggestion: ClassVar[str] = (
        "Verifique o formato escolhido ou use o mapeamento manual de colunas."
    )

    def __init__(
        self,
        missing_columns: Sequence[str] = (),
        *,
        message: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.missing_columns: tuple[str, ...] = tuple(missing_columns)
        resolved_message = message
        if resolved_message is None and self.missing_columns:
            joined_columns = ", ".join(self.missing_columns)
            resolved_message = (
                f"Colunas obrigatórias ausentes no relatório: {joined_columns}."
            )
        super().__init__(resolved_message, suggestion=suggestion)


class NormalizationError(ReportError):
    """Raised when data cannot be normalized into the canonical schema."""

    default_message: ClassVar[str] = (
        "Não foi possível normalizar os dados do relatório."
    )
    default_suggestion: ClassVar[str] = (
        "Revise os formatos de data, quantidade e valores monetários na planilha."
    )


__all__ = [
    "FileTooLargeError",
    "HeaderNotFoundError",
    "MissingRequiredColumnsError",
    "NormalizationError",
    "ReportError",
    "UnsupportedFileError",
]
