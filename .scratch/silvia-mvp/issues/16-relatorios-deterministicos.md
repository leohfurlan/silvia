# 16: Gerar relatórios determinísticos da sessão

**What to build:** Produzir relatórios Markdown e JSON reconstruíveis a partir
do histórico durável, permitindo auditar objetivo, trabalho, decisões e
evidências sem depender de um resumo de modelo.

**Blocked by:** 06/Conceder e consumir autorizações protegidas; 08/Executar um work item governado ponta a ponta; 12/Propor, promover e recuperar memória textual.

**Status:** ready-for-agent

- [ ] Relatório inclui objetivo/revisões, work items, agentes, gates, autorizações, evidências, memória, consumo e pendências.
- [ ] Estados configurado, executado, aprovado, falho e bloqueado permanecem distintos.
- [ ] Custo ausente, estimado e confirmado são rotulados separadamente.
- [ ] Markdown e JSON referenciam o mesmo cursor e produzem conteúdo equivalente.
- [ ] Logs grandes aparecem como artefatos por digest, não inline sem limite.
- [ ] Resumo narrativo opcional não altera a projeção determinística.

