# F01 — Contrato de sessões e objetivos

**Contrato:** F01-C1 r1
**Estado:** draft
**PRD:** ../../product/PRD.md r1, F01
**Spec:** spec.md | **Plano:** plan.md

## Identidade e ownership

SessionRuntime fornece o contrato. CLI/TUI (F06), HarnessEngine (F02),
AgentRuntime (F04), MemoryStore (F05) e eventos/relatórios (F07) o consomem.
O runtime é dono de project_id, session_id e objective_revision.

## Operações

| Operação | Entrada | Resultado | Erros |
| --- | --- | --- | --- |
| register_project | raiz resolvida, remotes normalizados, commit observado | ProjectView | invalid-root, ambiguous-project |
| new_session | project_id, nome, ObjectiveInput, checkout policy | SessionView | project-not-found, checkout-conflict |
| revise_objective | session_id, expected_revision, ObjectiveInput | SessionView com revisão +1 | not-found, concurrent-revision, invalid-state |
| resume_session | session_id | ReconciliationView; nenhuma execução | not-found, corrupt-session, incompatible-store |
| transition | session_id, expected_state, target, reason | SessionView | invalid-transition, concurrent-state |
| cancel_session | session_id, motivo | CancellationView | not-found, already-terminal |
| inspect_session | session_id | SessionView | not-found |

ObjectiveInput contém texto não vazio, critérios observáveis e restrições.
ProjectView identifica o projeto por UUID local; caminhos e worktrees são
localizações associadas. SessionView inclui revisão vigente, estado, baseline,
checkout e cursor durável de evento.

## Invariantes

- Criação da sessão e revisão 1 é atômica.
- Revisões anteriores nunca são alteradas.
- Resume e inspect não concedem autorização nem disparam trabalho.
- Mutação e evento correspondente pertencem à mesma transação.
- Um checkout mutável possui no máximo uma sessão escritora.
- Erro de schema, corrupção ou concorrência falha sem mutação parcial.

## Compatibilidade e testes

SQLite e adapter in-process devem passar pelos mesmos testes de contrato. O
schema usa migrations SQL numeradas e tabela schema_migrations. Alteração
incompatível exige nova revisão deste contrato e coordenação com F02, F04–F07.

