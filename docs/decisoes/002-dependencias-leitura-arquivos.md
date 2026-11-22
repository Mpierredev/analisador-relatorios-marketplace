# ADR 002 — Dependências e estratégia de leitura em memória

## Contexto

A Etapa 2 requer leitura de planilhas `.csv` e `.xlsx` diretamente a partir de `bytes`, com detecção automática de encoding, separador e cabeçalho, respeito aos limites de tamanho/linhas e preservação dos textos brutos para validação e normalização posteriores.

## Decisão

1. Adotar `pandas`, `openpyxl` e `charset-normalizer` como dependências de execução, acompanhadas de `pandas-stubs` e `types-openpyxl` em desenvolvimento para manter o `mypy` estrito na camada `ingestion/`.
2. Ler todos os dados exclusivamente em memória (`io.BytesIO` e `io.StringIO`) como texto bruto (`dtype=str` e `keep_default_na=False` no CSV; serialização controlada e `read_only=True`, `data_only=True` no `.xlsx`), preservando zeros à esquerda e formatos numéricos locais até a Etapa 5.
3. Registrar em `logging` apenas metadados técnicos (extensão, tamanho em bytes, contagem de linhas/colunas e índice de cabeçalho), nunca nomes de arquivos enviados, cabeçalhos ou conteúdo de células.

## Consequências

- Os testes e a execução permanecem isolados de disco e alinhados aos requisitos de privacidade.
- A contagem de linhas durante o carregamento interrompe a leitura imediatamente quando o limite configurado é ultrapassado.
