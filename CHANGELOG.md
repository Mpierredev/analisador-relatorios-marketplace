# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue o padrão [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [1.0.0] - 2026-11-25

### Adicionado

- Documentação completa para uso e contribuição: `README.md` na raiz com captura de tela real (`docs/assets/dashboard.png`), tabela de desempenho e guia de instalação, `docs/arquitetura.md` com diagramas Mermaid, `docs/como-adicionar-adapter.md` e `CONTRIBUTING.md`.
- Script de benchmark sintético (`scripts/benchmark_desempenho.py`) para medição de latência por etapa, pico de alocação e RSS até 200.000 linhas e alta cardinalidade de SKUs.
- Checklist documentado e testes de integração dos cinco cenários obrigatórios de erro na interface (`docs/checklist-cenarios-erro.md`).
- Suíte de regressão de privacidade, logs em nível `DEBUG` e zero escrita em disco (`tests/unit/test_privacy_and_logs.py`).
- Camada de exportação em memória (`src/analisador/export/`) para geração de CSV canônico e workbook Excel gerencial de cinco abas (`Resumo KPIs`, `Série Temporal`, `Top Produtos`, `Curva ABC` e `Status e Qualidade`), com botões de download no dashboard.
- Amostras sintéticas em `samples/` (`scripts/gerar_amostras.py`) disponíveis para carregamento em um clique na aba `Analisar` e download na página `Como exportar`.
- Classificação declarativa de maturidade de adapters (`AdapterSupportTier`: `verificado` e `experimental`), identificação da origem da receita líquida (`NetRevenueSource`) e seleção explícita de abas em planilhas `.xlsx` multi-aba (`list_xlsx_sheets` e parâmetro `sheet_name`).
- Interface multipágina em Streamlit (`app.py`, `.streamlit/config.toml` e `src/analisador/ui/`) com páginas `Analisar`, `Formatos suportados`, `Como exportar` e `Sobre`, fluxo bloqueado por validação, mapeamento manual para planilhas genéricas, cache limitado por tempo e entradas, cartões de KPI, filtros interativos e gráficos Altair.
- Biblioteca de análises independente da interface em `src/analisador/analytics/` com KPIs gerais e por período, distribuição de status, séries temporais diária/semanal/mensal, ranking de produtos, Curva ABC e comparação com período anterior equivalente (`filters.py`, `kpis.py`, `timeseries.py`, `products.py`, `comparison.py`).
- Parsers vetorizados de moeda brasileira e internacional em centavos (`src/analisador/normalization/currency.py` e `src/analisador/normalization/currency_series.py`), incluindo negativos entre parênteses.
- Parser vetorizado de datas em formatos brasileiros, ISO e datas por extenso em português/espanhol (`src/analisador/normalization/dates.py`), com `dayfirst` explícito e conversão para `America/Sao_Paulo`.
- Normalização de campos, derivação de receita bruta e líquida e relatório de qualidade (`src/analisador/normalization/fields.py`, `src/analisador/normalization/quality.py` e `src/analisador/normalization/pipeline.py`), além de suíte com `hypothesis` em `tests/unit/test_normalization_*.py`.
- Inferência de tipos de coluna e sugestão automática de mapeamento genérico (`src/analisador/validation/types.py` e `src/analisador/validation/suggestions.py`), validação estrutural e trava explícita via `ensure_can_generate_dashboard`.
- Mecanismo declarativo de adapters (`src/analisador/adapters/`), adapters da Shopee e do Mercado Livre com aliases em português, inglês e espanhol, pontuação de similaridade (`src/analisador/validation/detection.py`) e documentação em `docs/formatos-suportados.md`.
- Detecção de encoding (`UTF-8`, `UTF-8` com BOM, `UTF-16` e `Latin-1`/`cp1252`), separador (`,`, `;`, `\t`) e linha de cabeçalho com metadados iniciais em `src/analisador/ingestion/`.
- Núcleo de domínio sem dependências internas (`src/analisador/core/`), estrutura inicial de pacotes, licença MIT, `.pre-commit-config.yaml` e workflow de CI em `.github/workflows/ci.yml`.

### Alterado

- Agregações de `analytics/` (`kpis.py`, `timeseries.py`, `products.py`), formatação monetária do exportador CSV (`export/csv_exporter.py`) e compactação de tipos canônicos (`normalization/dtypes.py`) vetorizados com ganhos de até 43,9x em alta cardinalidade e até 37,8% menos uso de memória.
- Cache do dashboard isolado por sessão via `STATE_SESSION_NONCE` e chave de dataset (`build_dashboard_cache_key`), evitando re-hashing completo do DataFrame a cada alteração de filtro.
- Índice da documentação reorganizado mantendo `README.md` completo na raiz e `docs/README.md` como catálogo de referência.

### Corrigido

- Alinhamento de fuso horário ao comparar limites mistos (`date` e `datetime`) em `src/analisador/analytics/comparison.py`.
- Redesenho imediato de estado e exibição de erro ao acionar o botão `Gerar dashboard` em `src/analisador/ui/components/validation_view.py`.
- Documentação de limite máximo de upload em `docs/checklist-cenarios-erro.md` alinhada para `25 MB` (`MAX_FILE_SIZE_MB`).

[Não publicado]: https://github.com/Mpierredev/analisador-relatorios-marketplace/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Mpierredev/analisador-relatorios-marketplace/releases/tag/v1.0.0
