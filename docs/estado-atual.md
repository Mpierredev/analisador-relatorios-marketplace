# Estado atual

## Etapa concluída

- **Etapa 1 (Núcleo e esquema)**: implementados na branch `feat/nucleo-esquema` os módulos de `src/analisador/core/` (`config.py`, `enums.py`, `errors.py`, `schema.py`, `models.py` e `__init__.py`), testes unitários em `tests/unit/test_core_*.py`, ADR `docs/decisoes/001-modelos-core-sem-dependencias.md` e atualizações em `README.md` e `CHANGELOG.md`.

## Decisões tomadas

- Núcleo implementado apenas com biblioteca padrão (`dataclasses` imutáveis com `slots=True`, `StrEnum`, `Decimal` e `MappingProxyType`), sem dependências externas.
- Campos de identificador de marketplace nos modelos usam `str` compatível com `Marketplace(StrEnum)` para permitir novos adapters sem alterar `core/`.
- Validação mínima de entrada exige `order_date`, `product_name`, `quantity` e ao menos um campo monetário (`gross_revenue` ou `unit_price`).

## O que está pendente

- Revisar, integrar a branch `feat/nucleo-esquema` em `main` (via PR ou merge) e enviar ao repositório remoto.
- Acompanhar execução do CI no GitHub Actions após atualização do remoto.
- Instalar hooks locais com `pre-commit install`.

## Próximos passos

- Iniciar a **Etapa 2 (Leitura de arquivos)**: implementar detecção de encoding, separador e cabeçalho, leitura de CSV e XLSX em memória e limites em `src/analisador/ingestion/`.
