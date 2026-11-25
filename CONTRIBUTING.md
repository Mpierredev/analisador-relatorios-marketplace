# Guia de Contribuição

Obrigado pelo interesse em contribuir com o **Analisador de Relatórios de Marketplaces**. Antes de abrir uma alteração, leia as diretrizes abaixo para manter a consistência arquitetural, a qualidade estática e a garantia de privacidade do projeto.

---

## 1. Configuração do ambiente

Requer **Python 3.12+**.

```bash
git clone https://github.com/Mpierredev/analisador-relatorios-marketplace.git
cd analisador-relatorios-marketplace
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Para validar a aplicação localmente:

```bash
streamlit run app.py
```

---

## 2. Portões obrigatórios de qualidade

Todas as alterações precisam passar integralmente nos quatro comandos abaixo antes de enviar um Pull Request:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov
```

A configuração em [`pyproject.toml`](pyproject.toml) exige:

- Zero avisos no **Ruff** (`E`, `F`, `I`, `W`, `UP`, `B`, `SIM`, `N`, `C90`, `RUF`, `T20`, `PT`, complexidade ciclomática `<= 10`).
- **mypy** estrito em todas as camadas internas (`core`, `ingestion`, `adapters`, `validation`, `normalization`, `analytics`, `export`).
- Cobertura mínima de **85%** nas camadas de domínio e processamento.

---

## 3. Padrões de código e arquitetura

- **Idioma:** código-fonte (módulos, classes, funções, variáveis e docstrings) em **inglês**; interface, mensagens de erro, documentação e mensagens de commit em **português do Brasil**.
- **Tamanho e modularidade:** mantenha módulos abaixo de `300` linhas, funções de responsabilidade única com até `30` linhas e aninhamento até `3` níveis.
- **Isolamento de camadas:** consulte [`docs/arquitetura.md`](docs/arquitetura.md). Apenas `app.py` e `src/analisador/ui/` podem importar `streamlit`; `analytics/` só pode depender de `core/`; toda regra específica de marketplace fica restrita a `src/analisador/adapters/`.
- **Desempenho:** prefira operações vetorizadas em pandas/NumPy; evite loops Python linha a linha em `DataFrame`s e nunca utilize `print()` no código de produção (use `logging` sem registrar conteúdo de arquivos enviados).
- **Privacidade:** nunca adicione dados reais de compradores ou planilhas reais em `tests/`, `samples/` ou `docs/`. Toda fixture deve ser 100% sintética.
- **Erros esperados:** utilize subclasses de `ReportError` ([`src/analisador/core/errors.py`](src/analisador/core/errors.py)) com mensagem amigável e sugestão acionável em português.

---

## 4. Fluxo de branches e padrão de commits

- Crie uma branch curta a partir de `main` atualizado (`feat/...`, `fix/...`, `docs/...`, `perf/...`).
- Faça commits pequenos e atômicos no padrão `<prefixo>: <descrição curta no imperativo>`, em português, com até **72 caracteres** na primeira linha.
- Prefixos aceitos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `perf`.

Exemplos:

```text
feat: adiciona suporte a aba selecionavel em planilhas xlsx
fix: corrige arredondamento de centavos na exportacao csv
docs: detalha fluxo de mapeamento manual no guia de uso
```

---

## 5. Checklist de Pull Request

- [ ] A alteração respeita as fronteiras de camadas definidas em [`docs/arquitetura.md`](docs/arquitetura.md).
- [ ] Há testes unitários ou de integração cobrindo o novo comportamento ou correção.
- [ ] `ruff check .`, `ruff format --check .`, `mypy` e `pytest --cov` passaram sem avisos ou falhas.
- [ ] Se um comportamento visível ao usuário ou formato mudou, [`CHANGELOG.md`](CHANGELOG.md) e os guias afetados em `docs/` foram atualizados.
- [ ] Nenhuma informação sensível ou dado real de cliente foi incluído no histórico.
