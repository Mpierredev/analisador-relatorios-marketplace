# Estado atual

## Etapa concluída

- **Etapa 0 (Preparação)**: projeto organizado na raiz `analisador-relatorios-marketplace`, repositório remoto público `Mpierredev/analisador-relatorios-marketplace` criado no GitHub, estrutura de pastas, `LICENSE`, `.gitignore`, `.editorconfig`, `README.md`, `pyproject.toml`, `.pre-commit-config.yaml`, CI no GitHub Actions, `CHANGELOG.md` e teste smoke validados.

## Decisões tomadas

- Diretório local `plan/` mantido fora do controle de versão e listado no `.gitignore`.
- Build backend configurado com `hatchling` e layout `src/analisador`, sem dependências de runtime na Etapa 0.
- Teste smoke em `tests/unit/test_package.py` para validar empacotamento e meta de cobertura >= 85%.

## O que está pendente

- Acompanhar a execução inicial do workflow de CI no GitHub Actions.
- Instalar e ativar hooks locais com `pre-commit install`.

## Próximos passos

- Iniciar a **Etapa 1 (Núcleo e esquema)**: definir esquema canônico, enums de status, constantes em `core/config.py`, hierarquia `ReportError`, modelos (`ValidationReport`, `QualityReport`, `KpiSummary`) e testes unitários.
