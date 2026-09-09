# 14: Disponibilizar subcomandos e saída JSON

**What to build:** Permitir que o operador governe sessões por subcomandos
estáveis e que automações consumam saída JSON determinística sem misturar
progresso ou decoração.

**Blocked by:** 03/Revisar o objetivo e retomar com reconciliação; 05/Avaliar ações pelo HarnessEngine; 08/Executar um work item governado ponta a ponta.

**Status:** ready-for-agent

- [ ] Há comandos para criar, listar, mostrar, retomar, executar, pausar, cancelar, acompanhar e relatar sessões.
- [ ] Modo interativo e subcomandos usam as mesmas interfaces do núcleo.
- [ ] Saída humana usa stdout, progresso usa stderr e erros retornam exit code não zero.
- [ ] Modo JSON emite um documento determinístico e nenhum texto decorativo.
- [ ] Consulta e relatório local funcionam sem provider.
- [ ] Mensagem ambígua não altera objetivo ou autorização sem confirmação.

