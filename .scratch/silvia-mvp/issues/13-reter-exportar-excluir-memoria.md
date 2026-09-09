# 13: Aplicar retenção, exportação e exclusão de memória

**What to build:** Permitir governar o ciclo de vida dos dados de memória e
histórico, aplicando retenção configurável, exportação redigida e exclusão
auditável.

**Blocked by:** 06/Conceder e consumir autorizações protegidas; 12/Propor, promover e recuperar memória textual.

**Status:** ready-for-agent

- [ ] Logs volumosos usam retenção padrão de 90 dias com configuração por projeto.
- [ ] Memórias promovidas não expiram automaticamente, mas respeitam validade explícita.
- [ ] Exportação contém proveniência e conteúdo redigido, sem credenciais.
- [ ] Exclusão exige autorização e retorna recibo idempotente.
- [ ] Evento de exclusão não conserva o conteúdo que foi removido.
- [ ] Operações não atravessam o escopo de projeto ou usuário autorizado.

