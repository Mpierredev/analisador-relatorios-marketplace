# ADR 001 — Modelos de domínio sem dependências externas

## Contexto

A camada `core/` define o esquema canônico, constantes operacionais, enums, erros tipados e modelos de relatório compartilhados por todas as outras camadas do projeto. O plano prevê que o núcleo seja testável de forma isolada, sem depender do Streamlit ou de bibliotecas de E/S.

## Decisão

1. Implementar `core/` usando apenas a biblioteca padrão do Python 3.12 (`dataclasses` imutáveis com `frozen=True` e `slots=True`, `StrEnum`, `Decimal` e `MappingProxyType`), mantendo `dependencies` vazio nesta etapa.
2. Tipar `marketplace` em `CanonicalRecord` e chaves de adapter em `ValidationReport` e `AdapterScore` como `str` (compatível com `Marketplace(StrEnum)`), evitando alterar `core/` quando novos marketplaces forem adicionados em `adapters/`.
3. Centralizar a validação mínima de entrada em `missing_required_input_fields`, exigindo data, produto, quantidade e ao menos um campo monetário (`gross_revenue` ou `unit_price`).

## Consequências

- Testes unitários do domínio executam em milissegundos e permanecem desacoplados de Pandas e Streamlit.
- Invariantes de domínio ficam garantidas na instanciação dos modelos sem adicionar custo de inicialização ou memória no ambiente gratuito.
