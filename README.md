# Analisador de Relatórios de Marketplaces

Aplicação web em Streamlit para validar, normalizar e analisar relatórios de vendas exportados de marketplaces (Shopee, Mercado Livre e planilhas CSV ou XLSX genéricas).

O projeto opera com custo de infraestrutura R$ 0, sem banco de dados, sem login e sem armazenamento de arquivos enviados.

## Recursos

- **Leitura automática em memória**: aceita `.csv` e `.xlsx`, detecta encoding (`UTF-8`, `UTF-8` com BOM e `Latin-1`/`cp1252`), separador (vírgula, ponto e vírgula ou tabulação) e linha de cabeçalho mesmo com metadados iniciais.
- **Validação estrutural e mapeamento manual**: pontua compatibilidade com os formatos conhecidos, lista colunas encontradas ou ausentes e oferece mapeamento manual no modo CSV genérico.
- **Normalização e qualidade dos dados**: padroniza datas, valores monetários, quantidades e status em um esquema canônico e gera relatório de qualidade (duplicidades, nulos, datas inválidas e outliers).
- **Dashboard e exportação**: calcula indicadores de vendas, séries temporais, ranking de produtos, curva ABC, comparação de períodos e exportação dos dados tratados em CSV e Excel.

## Limites operacionais

- Formatos aceitos: `.csv` e `.xlsx`.
- Limite padrão por arquivo: **25 MB** e **200.000 linhas**.
- Aplicações hospedadas no plano gratuito do Streamlit Community Cloud entram em suspensão após períodos sem acesso e são reativadas automaticamente ao abrir a página.

## Arquitetura

O código-fonte fica em `src/analisador/`, organizado em camadas com dependências apontando para o núcleo:

- `core/`: esquema canônico, enums, constantes de configuração, erros tipados e modelos de relatório.
- `ingestion/`: leitura em memória de CSV e XLSX, detecção de encoding, separador e cabeçalho.
- `adapters/`: definições declarativas de colunas e mapeamentos por marketplace.
- `validation/`: pontuação de similaridade, validação estrutural e mapeamento manual.
- `normalization/`: conversão de datas, moedas, status e relatório de qualidade.
- `analytics/`: indicadores, séries temporais, rankings, curva ABC e comparativos.
- `export/`: geração de saídas em CSV e Excel.
- `ui/`: interface Streamlit, componentes reutilizáveis e estado da sessão.

## Privacidade

Os arquivos enviados são processados exclusivamente em memória e nunca são gravados em disco, banco de dados ou registros de log.

## Ambiente de desenvolvimento

Requer Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verificações de qualidade:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov
```

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
