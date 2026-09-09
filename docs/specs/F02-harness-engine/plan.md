# F02 — Plano do HarnessEngine

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F02
**Contrato:** contract.md | **Spec:** spec.md

1. Aprovar F02-C1, capabilities iniciais e dependências F01/F07.
2. Modelar ActionRequest, decisões, grants, uso e avaliação de conclusão.
3. Extrair regras atuais de modelo, ownership, revisão, checks e PR.
4. Persistir grants/usos atomicamente com eventos por F01/F07.
5. Fazer AgentRuntime, ferramentas e CLI consumirem decisões, removendo atalhos.
6. Cobrir matriz de capabilities, replay, expiração e revisão alterada.
7. Executar gates existentes e revisão independente de segurança/autorização.

F02 desbloqueia F03–F06. Pronto significa que nenhum caminho mutável conhecido
contorna evaluate/consume e que AC01–AC07 passam pela interface pública.
