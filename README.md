# Analisador de Relatórios de Marketplaces

Aplicação web em Streamlit para validar, normalizar e analisar relatórios de vendas exportados de marketplaces (Shopee, Mercado Livre e planilhas CSV ou XLSX genéricas).

Projeto sem banco de dados, sem login, sem armazenamento de arquivos e com custo de infraestrutura R$ 0.

## Estado atual

Etapa 0 concluída: estrutura inicial de pastas, configuração de ferramentas de qualidade (Ruff, mypy, pytest), hooks de pre-commit e integração contínua no GitHub Actions. As funcionalidades do analisador ainda estão em desenvolvimento.

## Arquitetura

O código-fonte fica em `src/analisador/`, organizado em camadas com fluxo de dependências voltado para o núcleo:

- `core/`: esquema canônico, enums, constantes de configuração, erros tipados e modelos de relatório.
- `ingestion/`: leitura em memória de CSV e XLSX, detecção de encoding, separador e cabeçalho.
- `adapters/`: definições declarativas de colunas e mapeamentos por marketplace.
- `validation/`: pontuação de similaridade, validação estrutural e mapeamento manual.
- `normalization/`: conversão de datas, moedas, status e relatório de qualidade.
- `analytics/`: indicadores, séries temporais, rankings, curva ABC e comparativos.
- `export/`: geração de saídas em CSV e Excel.
- `ui/`: interface Streamlit, componentes reutilizáveis e estado da sessão.

## Privacidade

Os arquivos enviados são processados exclusivamente em memória e nunca são gravados em disco, banco de dados ou logs.

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
