# Checklist de cenários de erro

Cinco casos problemáticos validados na interface antes de publicar uma nova versão. Todos precisam retornar orientação clara em português, sem exibir rastros de erro técnico nem vazar dados dos arquivos em log.

1. **Extensão não suportada ou `.xlsx` corrompido (`UnsupportedFileError`)**
   - Enviar `.pdf`, `.txt` ou planilha `.xlsx` truncada na página **Analisar**.
   - A leitura é interrompida na entrada, com mensagem orientando exportar novamente em `.csv` ou `.xlsx` e sem liberar o painel.

2. **Arquivo vazio ou sem linha de cabeçalho (`HeaderNotFoundError`)**
   - Enviar CSV com `0` bytes, apenas linhas em branco ou Excel sem cabeçalho identificável.
   - O sistema bloqueia o avanço e orienta conferir se a planilha contém nomes de colunas.

3. **Arquivo acima do limite operacional (`FileTooLargeError`)**
   - Enviar planilha maior que `25 MB` (`MAX_FILE_SIZE_MB`) ou com mais de `200.000` linhas (`MAX_ROWS`).
   - O envio é recusado com instrução para dividir a exportação em períodos menores.

4. **Colunas obrigatórias ausentes ou formato de outro marketplace (`ValidationStatus.UNRECOGNIZED`)**
   - Enviar tabela com cabeçalhos incompatíveis com o formato escolhido.
   - O botão **Gerar dashboard** permanece desabilitado até o mapeamento manual ou ajuste de formato.

5. **Cabeçalho reconhecido, porém todas as linhas inválidas (`NormalizationError`)**
   - Enviar planilha com colunas válidas e todas as linhas contendo datas inválidas, quantidades zeradas ou preços corrompidos.
   - Ao clicar em **Gerar dashboard**, a tela exibe imediatamente o aviso orientando revisar datas, quantidades e valores sem travar a sessão.
