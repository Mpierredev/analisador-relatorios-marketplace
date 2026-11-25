# Como adicionar um novo adapter de marketplace

O projeto isola totalmente o formato específico de cada plataforma na camada `src/analisador/adapters/`. Adicionar um novo marketplace **não deve exigir alterações** nas camadas de `ingestion/`, `validation/`, `normalization/`, `analytics/`, `export/` ou `ui/` (exceto incluir o identificador em `Marketplace` dentro de `src/analisador/core/enums.py`).

---

## 1. Requisitos antes de implementar

1. **Amostra estrutural 100% sintética ou anonimizada:** nunca adicione dados reais de clientes (nomes, CPFs, endereços, e-mails ou IDs reais) em fixtures ou testes.
2. **Mapeamento factual:** inclua apenas cabeçalhos e status efetivamente observados em exportações da plataforma ou em documentação oficial verificável.
3. **Verificação de grão:** confirme se o relatório traz uma linha por item vendido ou uma linha agregadora de carrinho/pedido multi-item, evitando dupla contagem ao somar `gross_revenue`.
4. **Compatibilidade:** o adapter deve registrar `observed_at` (`YYYY-MM-DD`) e `support_tier` (`AdapterSupportTier.VERIFIED` ou `AdapterSupportTier.EXPERIMENTAL`).

---

## 2. Arquivos alterados na adição de um adapter

1. [`src/analisador/core/enums.py`](../src/analisador/core/enums.py) — adicionar o membro correspondente no enum `Marketplace` (ex.: `MAGALU = "magalu"`).
2. `src/analisador/adapters/<marketplace>.py` — definir a constante `Final[MarketplaceAdapter]`.
3. [`src/analisador/adapters/registry.py`](../src/analisador/adapters/registry.py) e [`src/analisador/adapters/__init__.py`](../src/analisador/adapters/__init__.py) — registrar e exportar o novo adapter em `REGISTERED_ADAPTERS`.
4. `tests/fixtures/` — adicionar fixtures **sintéticos** válidos e de borda (colunas faltando, pré-cabeçalho, encoding/moeda característicos).
5. [`tests/unit/test_adapters.py`](../tests/unit/test_adapters.py) e [`tests/unit/test_validation_detection.py`](../tests/unit/test_validation_detection.py) — cobrir contrato, pontuação de similaridade e não colisão com outros marketplaces.
6. [`tests/unit/test_normalization_pipeline.py`](../tests/unit/test_normalization_pipeline.py) — testar fluxo ponta a ponta (`read_report -> validate_report -> normalize_report`) sobre o fixture sintético.
7. [`docs/formatos-suportados.md`](formatos-suportados.md) e [`CHANGELOG.md`](../CHANGELOG.md) — documentar aliases, status aceitos, data de observação e limitações.

---

## 3. Exemplo declarativo de adapter

Consulte [`src/analisador/adapters/mercado_livre.py`](../src/analisador/adapters/mercado_livre.py) como referência real. Estrutura mínima:

```python
from typing import Final

from analisador.adapters.base import MarketplaceAdapter
from analisador.core.config import MEDIUM_CONFIDENCE_THRESHOLD
from analisador.core.enums import (
    AdapterSupportTier,
    CanonicalField,
    DecimalStyle,
    Marketplace,
    OrderStatus,
)

EXEMPLO_ADAPTER: Final[MarketplaceAdapter] = MarketplaceAdapter(
    key=Marketplace.EXEMPLO,
    display_name="Marketplace Exemplo",
    report_type="Relatório de pedidos",
    observed_at="2026-11-25",
    compatibility_note=(
        "Compatível com exportações observadas do Marketplace Exemplo. "
        "Não representa especificação oficial da plataforma."
    ),
    required_fields={
        CanonicalField.ORDER_DATE: ("Data do pedido",),
        CanonicalField.PRODUCT_NAME: ("Nome do produto",),
        CanonicalField.QUANTITY: ("Quantidade",),
        CanonicalField.GROSS_REVENUE: ("Valor dos produtos",),
    },
    optional_fields={
        CanonicalField.ORDER_ID: ("Número do pedido",),
        CanonicalField.STATUS: ("Status",),
        CanonicalField.SKU: ("SKU",),
        CanonicalField.FEES: ("Comissão",),
        CanonicalField.SHIPPING_COST: ("Frete",),
    },
    status_map={
        "entregue": OrderStatus.COMPLETED,
        "cancelado": OrderStatus.CANCELLED,
        "devolvido": OrderStatus.RETURNED,
        "em transporte": OrderStatus.IN_PROGRESS,
    },
    date_formats=("%d/%m/%Y %H:%M", "%d/%m/%Y"),
    decimal_style=DecimalStyle.AUTO,
    min_score=MEDIUM_CONFIDENCE_THRESHOLD,
    support_tier=AdapterSupportTier.EXPERIMENTAL,
)
```

### Observações importantes sobre `MarketplaceAdapter`

- **Normalização de cabeçalhos:** `normalize_header()` converte tudo para minúsculas, remove acentos e substitui pontuação por espaços. Não é preciso repetir variações apenas de maiúsculas/acentos.
- **Chaves de `status_map`:** são automaticamente normalizadas por `normalize_status()` na inicialização; valores não mapeados caem com segurança em `OrderStatus.OTHER`.
- **Não sobreposição:** nenhum `CanonicalField` pode aparecer simultaneamente em `required_fields` e `optional_fields`.
- **Pontuação cruzada:** evite aliases excessivamente genéricos (como `"Total"` isolado em campos obrigatórios) que possam gerar conflito com relatórios de outras plataformas.

---

## 4. Checklist de validação antes do Pull Request

```bash
ruff check .
ruff format --check .
mypy
pytest --cov
```

- [ ] Nenhum dado real de cliente presente em fixtures, código ou documentação.
- [ ] Nenhuma ramificação condicional por nome de marketplace fora de `src/analisador/adapters/`.
- [ ] Todos os testes antigos (Mercado Livre, Shopee e modo genérico) continuam passando sem regressão na pontuação cruzada.
- [ ] Arquivo do adapter abaixo de `300` linhas e tabela atualizada em [`docs/formatos-suportados.md`](formatos-suportados.md).
