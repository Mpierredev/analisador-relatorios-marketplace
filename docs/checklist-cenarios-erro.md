# Checklist de Verificação — Cinco Cenários de Erro

Este documento registra os **5 cenários obrigatórios de tratamento de erros** antes do empacotamento/lançamento da ferramenta. Todos os cenários devem apresentar mensagem clara em português, sugestão prática de correção, nenhum *traceback* técnico visível ao usuário e nenhum vazamento de conteúdo de arquivo nos logs.

## Cenário 1 — Extensão não suportada ou `.xlsx` corrompido (`UnsupportedFileError`)
- **Como reproduzir**: Enviar um arquivo com extensão `.pdf`/`.txt` ou um arquivo `.xlsx` truncado/corrompido na página **Analisar**.
- **Comportamento esperado**:
  - A leitura é bloqueada na camada de ingestão antes de qualquer interpretação tabular.
  - A interface exibe o banner de erro em português informando formato inválido ou planilha corrompida, acompanhado da sugestão para exportar novamente em `.csv` ou `.xlsx`.
  - O estado anterior do dashboard permanece limpo (`dashboard_liberado = False`), sem exceções na tela.
- **Resultado verificado**: Aprovado em teste de integração automatizado (`AppTest`) e inspeção da camada `ui.services`.

## Cenário 2 — Arquivo vazio ou sem cabeçalho identificável (`HeaderNotFoundError`)
- **Como reproduzir**: Enviar um CSV totalmente vazio (`0` bytes), um CSV só com quebras de linha/células em branco ou um Excel sem linha de cabeçalho identificável.
- **Comportamento esperado**:
  - A camada de ingestão rejeita o arquivo com `HeaderNotFoundError`.
  - A interface exibe orientação em português explicando que nenhuma linha de cabeçalho tabular foi encontrada e sugerindo confirmar se a exportação contém os nomes das colunas.
  - Nenhuma tabela parcial ou cálculo zerado é liberado para o dashboard.
- **Resultado verificado**: Aprovado em teste de integração automatizado (`AppTest`).

## Cenário 3 — Arquivo acima do limite operacional (`FileTooLargeError`)
- **Como reproduzir**: Enviar arquivo com tamanho superior a `25 MB` (`MAX_FILE_SIZE_MB`) ou planilha tabular com mais de `200.000` linhas (`MAX_ROWS`).
- **Comportamento esperado**:
  - A ingestão interrompe a carga imediatamente ao detectar excesso de bytes ou excesso de linhas.
  - A interface exibe mensagem informando o limite operacional e orientando a dividir o período exportado em lotes menores.
  - Nenhuma estrutura gigante permanece retida em memória de sessão ou em cache.
- **Resultado verificado**: Aprovado em teste de integração automatizado (`AppTest`) com simulação dos limites operacionais.

## Cenário 4 — Colunas obrigatórias ausentes ou arquivo de outro marketplace (`ValidationStatus.UNRECOGNIZED`)
- **Como reproduzir**: Enviar uma planilha tabular cujos cabeçalhos não correspondem ao formato selecionado (ex.: colunas arbitrárias `quando;item;qtde;total_bruto` com formato *Mercado Livre* selecionado).
- **Comportamento esperado**:
  - A etapa **2. Validação e mapeamento** exibe as colunas faltantes, sugestões automáticas por similaridade/tipo e o formulário de mapeamento manual.
  - O botão **Gerar dashboard** permanece explicitamente **desabilitado** (`disabled=True`) até que todas as colunas obrigatórias sejam mapeadas ou outro formato válido seja escolhido.
  - Ao completar o mapeamento manual e aplicar, o sistema alterna para o modo genérico e libera o botão **Gerar dashboard**.
- **Resultado verificado**: Aprovado em teste de integração automatizado (`AppTest`).

## Cenário 5 — Colunas válidas, mas todas as linhas falham na normalização (`NormalizationError`)
- **Como reproduzir**: Enviar um relatório com todas as colunas obrigatórias válidas (ex.: formato *Mercado Livre*), porém com 100% das linhas contendo datas inválidas, quantidades não positivas (`0` ou negativas) ou valores monetários corrompidos, e clicar em **Gerar dashboard**.
- **Comportamento esperado**:
  - A validação estrutural reconhece o cabeçalho e habilita o botão **Gerar dashboard**.
  - Ao acionar **Gerar dashboard**, a normalização descarta as linhas irrecuperáveis, constata `valid_rows == 0` e dispara `NormalizationError`.
  - A página **Analisar** captura a exceção via `translate_exception`, exibe banner amigável orientando revisar datas, quantidades e valores monetários, e mantém o dashboard bloqueado sem exibir *traceback*.
- **Resultado verificado**: Aprovado em teste de integração automatizado (`AppTest`).
