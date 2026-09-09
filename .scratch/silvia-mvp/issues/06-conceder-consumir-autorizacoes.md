# 06: Conceder e consumir autorizações protegidas

**What to build:** Permitir que o operador conceda uma autorização exatamente
para a ação apresentada e que o runtime a consuma sem permitir replay,
mudança de alvo ou herança entre revisões.

**Blocked by:** 05/Avaliar ações pelo HarnessEngine.

**Status:** ready-for-agent

- [ ] Grant registra ação, alvo, revisão, responsável, escopo, expiração e usos.
- [ ] Grant expirado, consumido ou pertencente a outra revisão é rejeitado.
- [ ] Ações externas, irreversíveis, destrutivas ou pagas são de uso único por padrão.
- [ ] Resultado externo incerto exige reconciliação antes de nova autorização.
- [ ] Avaliação de conclusão apresenta critérios e evidências, mas não conclui sem confirmação humana.

