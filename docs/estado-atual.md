# Estado atual

## Etapa concluída

- **Etapa 2 (Leitura de arquivos)**: integrados os commits da Etapa 1 em `main`, atualizado `README.md` sem plano interno e implementada na branch `feat/leitura-arquivos` a camada `src/analisador/ingestion/` (`encoding.py`, `structure.py`, `reader.py`, `__init__.py`), constantes de ingestão em `core/config.py`, ADR `002` e testes unitários em `tests/unit/test_ingestion_*.py`.

## Decisões tomadas

- Adicionadas dependências `pandas`, `openpyxl` e `charset-normalizer` (com stubs em `dev`) após aprovação explícita.
- Leitura executada apenas em memória como texto bruto (`dtype=str`, `keep_default_na=False` e `openpyxl` em `read_only=True`/`data_only=True`).

## O que está pendente

- Revisar, integrar `feat/leitura-arquivos` em `main` e publicar com `git push`.
- Acompanhar execução do CI no GitHub Actions após o push.
- Instalar hooks locais com `pre-commit install`.

## Próximos passos

- Iniciar a **Etapa 3 (Adapters e detecção)**: implementar adapters declarativos (Shopee e Mercado Livre), normalização de cabeçalhos, pontuação de similaridade e fixtures sintéticos.
