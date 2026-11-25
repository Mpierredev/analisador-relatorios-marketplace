# Analisador de Relatórios de Marketplaces

Aplicação web gratuita para validar, padronizar e analisar relatórios de vendas exportados do Mercado Livre, Shopee e planilhas CSV/XLSX genéricas, sem banco de dados e com processamento em memória.

[![Demo ao vivo](https://img.shields.io/badge/Demo-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://dashboardmaker.streamlit.app/)
![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
[![CI](https://github.com/Mpierredev/analisador-relatorios-marketplace/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Mpierredev/analisador-relatorios-marketplace/actions/workflows/ci.yml)
![Licença MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green)

**Demo ao vivo:** [dashboardmaker.streamlit.app](https://dashboardmaker.streamlit.app/) (contém três planilhas sintéticas carregáveis em um clique para testar sem enviar arquivos próprios).

![Painel de vendas do Analisador de Relatórios de Marketplaces](docs/assets/dashboard.png)

## Por que este projeto existe

Quem vende em marketplaces no Brasil costuma baixar planilhas bem diferentes entre si: arquivos com linhas de título antes do cabeçalho, encoding Latin-1, separador `;`, valores no formato `R$ 1.234,56`, datas escritas por extenso (`25 de novembro de 2024 11:43 hs.`) e status diferentes em cada canal.

Construí esta ferramenta para automatizar a limpeza, validação e análise dessas exportações antes que virem painel, mantendo o processamento exclusivamente em memória.

## O que o aplicativo faz

- Lê arquivos `.csv` e `.xlsx` em memória, identificando encoding, delimitador, aba e linha de cabeçalho.
- Valida colunas obrigatórias contra formatos conhecidos e libera um mapeamento manual assistido para planilhas fora do padrão.
- Padroniza datas para `America/Sao_Paulo`, converte valores monetários para centavos inteiros (`int64`) e gera diagnóstico de duplicidades, nulos, datas inválidas e *outliers*.
- Calcula faturamento bruto, receita líquida (indicando quando é informada pela planilha ou derivada de taxas e frete), ticket médio, cancelamentos, séries temporais, ranking de produtos e Curva ABC.
- Exporta os dados tratados em CSV (com BOM para Excel) e gera um resumo gerencial em `.xlsx` com cinco abas.

## Como rodar localmente

Requer Python 3.12 ou superior.

```bash
git clone https://github.com/Mpierredev/analisador-relatorios-marketplace.git
cd analisador-relatorios-marketplace
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

Para rodar testes e verificações de código:

```bash
pip install -e ".[dev]"
ruff check .
mypy
pytest --cov
```

Arquivos sintéticos de exemplo estão em [`samples/`](samples/) e podem ser recriados com `python scripts/gerar_amostras.py`. Há também um benchmark sintético até 200 mil linhas em `scripts/benchmark_desempenho.py` (`3,4s` para 50 mil linhas com 10 mil SKUs e `12,9s` no limite de 200 mil linhas).

## Formatos aceitos e limites

| Formato | Chave | Suporte | Observação |
|---|---|---|---|
| Mercado Livre | `mercado_livre` | Verificado | Exportações de vendas em PT, ES e EN |
| Shopee | `shopee` | Experimental | Baseado em cabeçalhos documentados da Central do Vendedor |
| CSV / XLSX genérico | `generico` | Verificado | Mapeamento manual com sugestão por tipo e nome |

- **Privacidade:** arquivos enviados nunca são gravados em disco, banco ou log; colunas extras de compradores (CPF, e-mail, endereço) são descartadas durante a normalização.
- **Limites operacionais:** até `25 MB` e `200.000` linhas por planilha. No plano gratuito do Streamlit Community Cloud, o app hiberna após períodos sem acesso e acorda ao abrir o link.

## Documentação

- [Arquitetura e esquema canônico](docs/arquitetura.md)
- [Formatos suportados e aliases](docs/formatos-suportados.md)
- [Como adicionar um adapter](docs/como-adicionar-adapter.md)
- [Checklist de cenários de erro](docs/checklist-cenarios-erro.md)
- [Como contribuir](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md) · [Licença MIT](LICENSE)
