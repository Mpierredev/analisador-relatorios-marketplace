# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue o padrão [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- Parsers vetorizados de moeda brasileira e internacional em centavos (`src/analisador/normalization/currency.py` e `src/analisador/normalization/currency_series.py`), incluindo negativos entre parênteses.
- Parser vetorizado de datas em formatos brasileiros, ISO e datas por extenso em português/espanhol (`src/analisador/normalization/dates.py`), com `dayfirst` explícito e conversão para `America/Sao_Paulo`.
- Normalização de campos, derivação de receita bruta e líquida e relatório de qualidade (`src/analisador/normalization/fields.py`, `src/analisador/normalization/quality.py` e `src/analisador/normalization/pipeline.py`).
- Constantes de normalização e IQR em `src/analisador/core/config.py` e suíte de testes unitários e baseados em propriedades (`hypothesis`) em `tests/unit/test_normalization_*.py`.
- Inferência de tipos de coluna e sugestão automática de mapeamento genérico em `src/analisador/validation/types.py` e `src/analisador/validation/suggestions.py`.
- Validação estrutural para adapters e mapeamento manual em `src/analisador/validation/validator.py` e `src/analisador/validation/generic.py`, gerando `ValidationReport` com bloqueio explícito via `ensure_can_generate_dashboard`.
- Alias observado `Preço unitário de venda do anúncio (BRL)` no adapter do Mercado Livre (`docs/formatos-suportados.md`).
- Constantes `TYPE_INFERENCE_SAMPLE_ROWS` e `GENERIC_NAME_SIMILARITY_THRESHOLD` em `src/analisador/core/config.py`.
- Testes unitários de sugestão e validação em `tests/unit/test_validation_suggestions.py` e `tests/unit/test_validation_validator.py`.
- Mecanismo declarativo de adapters, normalização de cabeçalhos/status e registro em `src/analisador/adapters/`.
- Adapters declarativos da Shopee e do Mercado Livre com aliases em português, inglês e espanhol e documentação em `docs/formatos-suportados.md`.
- Pontuação de similaridade e detecção de adapters em `src/analisador/validation/detection.py`.
- Constante `HEADER_SIMILARITY_THRESHOLD` em `src/analisador/core/config.py`.
- Fixtures sintéticos em `tests/fixtures/` e testes unitários em `tests/unit/test_adapters.py` e `tests/unit/test_validation_detection.py`.
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
