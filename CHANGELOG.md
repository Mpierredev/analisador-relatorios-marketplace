# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue o padrão [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- Detecção de encoding (`UTF-8`, `UTF-8` com BOM, `UTF-16` e `Latin-1`/`cp1252`) em `src/analisador/ingestion/encoding.py`.
- Detecção de separador (`,`, `;`, tabulação) e linha de cabeçalho com metadados ou linhas vazias iniciais em `src/analisador/ingestion/structure.py`.
- Leitura em memória de `.csv` e `.xlsx` com limites de tamanho e linhas em `src/analisador/ingestion/reader.py`.
- Constantes de leitura de arquivos em `src/analisador/core/config.py` e dependências `pandas`, `openpyxl` e `charset-normalizer` no `pyproject.toml`.
- Testes unitários de entrada em `tests/unit/test_ingestion_*.py`.
- Constantes operacionais e limites de entrada em `src/analisador/core/config.py`.
- Enums de domínio e validação em `src/analisador/core/enums.py`.
- Hierarquia tipada de erros `ReportError` em `src/analisador/core/errors.py`.
- Esquema canônico, validação de campos obrigatórios de entrada e `CanonicalRecord` em `src/analisador/core/schema.py`.
- Modelos imutáveis `AdapterScore`, `ValidationReport`, `QualityReport` e `KpiSummary` em `src/analisador/core/models.py`.
- Testes unitários do núcleo em `tests/unit/test_core_*.py`.
- Estrutura inicial de pacotes e diretórios em `src/analisador/`, `tests/`, `docs/`, `samples/` e `scripts/`.
- Licença MIT, `.gitignore`, `.editorconfig` e documentação inicial em `docs/README.md`.
- Configuração de empacotamento e qualidade em `pyproject.toml` com Ruff, mypy e pytest.
- Configuração de hooks em `.pre-commit-config.yaml` e workflow de CI em `.github/workflows/ci.yml`.

### Alterado

- Documentação pública do projeto movida para `docs/README.md`, mantendo apenas documentação geral pública fora do planejamento local.
