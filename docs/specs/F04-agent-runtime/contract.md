# F04 — Contrato do AgentRuntime

**Contrato:** F04-C1 r1 | **Estado:** draft
**PRD:** ../../product/PRD.md r1, F04
**Spec:** spec.md | **Plano:** plan.md

## Ownership

AgentRuntime é dono de AgentDescriptor, ExecutionRequest, AttemptResult e
ReconciliationResult. Consome sessão F01, decisões F02, contexto de skill F03 e
eventos F07. Astra/LangChain e futuros providers são adapters.

## Interface

| Operação | Entrada | Resultado |
| --- | --- | --- |
| available_routes | perfil local redigido | RouteDescriptor[] |
| plan | objetivo/revisão + contexto + limites | ProposedTaskGraph |
| execute | ExecutionRequest + GateDecision | AttemptResult |
| stop | agent_id + prazo | StopResult |
| reconcile | tentativa incerta | ReconciliationResult |

ExecutionRequest contém sessão/revisão, work item, ownership resolvido,
AgentDescriptor, contexto fixado, orçamento e decisão F02. AgentDescriptor
contém ID, papel, model/provider, capacidades, proibições e stop condition.

## Garantias

- Rota indisponível ou não permitida não sofre substituição silenciosa.
- Work items paralelos possuem dependências satisfeitas e ownership disjunto.
- Cada tentativa tem ID, limite e eventos de início/fim/falha.
- Limite excedido pausa; não amplia orçamento.
- Resultado incerto exige reconcile antes de retry.
- O adapter não persiste credencial nem raciocínio oculto.

## Compatibilidade

Adapters devem passar testes de contrato com provider fake determinístico. O
LangChain atual é implementação parcial; não define o contrato público.

