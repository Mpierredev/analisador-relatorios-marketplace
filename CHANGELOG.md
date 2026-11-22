# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue o padrão [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- Constantes operacionais e limites de entrada em `src/analisador/core/config.py`.
- Enums de domínio e validação em `src/analisador/core/enums.py`.
- Hierarquia tipada de erros `ReportError` em `src/analisador/core/errors.py`.
- Esquema canônico, validação de campos obrigatórios de entrada e `CanonicalRecord` em `src/analisador/core/schema.py`.
- Modelos imutáveis `AdapterScore`, `ValidationReport`, `QualityReport` e `KpiSummary` em `src/analisador/core/models.py`.
- Testes unitários do núcleo em `tests/unit/test_core_*.py` e registro de decisão em `docs/decisoes/001-modelos-core-sem-dependencias.md`.
- Estrutura inicial de pacotes e diretórios em `src/analisador/`, `tests/`, `docs/`, `samples/` e `scripts/`.
- Licença MIT, `.gitignore`, `.editorconfig` e `README.md` inicial em português.
- Configuração de empacotamento e qualidade em `pyproject.toml` com Ruff, mypy e pytest.
- Configuração de hooks em `.pre-commit-config.yaml` e workflow de CI em `.github/workflows/ci.yml`.
- Registro de estado inicial em `docs/estado-atual.md`.
