# F05 — Contrato do MemoryStore

**Contrato:** F05-C1 r1 | **Estado:** draft
**PRD:** ../../product/PRD.md r1, F05
**Spec:** spec.md | **Plano:** plan.md

## Ownership

MemoryStore é dono de MemoryCandidate, MemoryRecord, RecallQuery,
RecallResult e ConflictSet. SessionRuntime fornece identidades; F07 fornece
referências de evidência; AgentRuntime consome apenas o contexto selecionado.

## Interface

| Operação | Entrada | Resultado |
| --- | --- | --- |
| propose | conteúdo, tipo, proveniência, escopo, evidência | MemoryCandidate |
| promote | candidate_id + decisão humana ou regra mecânica | MemoryRecord |
| recall | RecallQuery + orçamento | RecallResult |
| forget | memory_id + autorização | ForgetReceipt |
| apply_retention | política + data de corte | RetentionReport |

Escopos: session, project e user. Tipos iniciais: fact, decision, preference e
learning. RecallResult inclui itens, ordem, score decomposto, conflitos,
referências e motivo de exclusão/truncamento.

## Garantias

- Não há promoção automática entre escopos.
- Inferência de agente nunca vira decisão/fato sem validação.
- Recall não retorna autorização e não muda objetivo/gate.
- Precedência: fontes canônicas atuais antes de memória.
- Exclusão é auditada sem manter o conteúdo excluído no evento.
- Tokens, senhas, chaves e material privado são rejeitados/redigidos antes de persistir.

## Compatibilidade

FTS5 é detalhe interno. Consumers dependem de RecallResult, não de SQL ou score
opaco. Mudança de precedência ou tipos exige revisão deste contrato.

