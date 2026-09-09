# F07 — Eventos, evidências, exportações e relatórios

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F07
**Contrato:** contract.md | **Plano:** plan.md

## Evidência e escopo

workflow/observability.py possui WorkflowEvent, LiveObserver e JsonlObserver.
O evento atual contém kind, role, model, task_id, message, payload e timestamp,
sem schema/session/sequence/correlation. JSONL escreve diretamente em arquivo e
não é recuperável a partir de estado canônico. _safe_tool_output já redige
alguns segredos e trunca resultados, podendo ser aprofundado.

## Requisitos

- BR01: cada mutação e decisão persistida possui EventV1 na mesma transação.
- BR02: sequência é crescente por sessão; paginação usa cursor opaco.
- BR03: payload é validado e redigido antes da persistência.
- BR04: logs extensos ficam em artefatos com digest e tamanho.
- BR05: projeções podem ser reconstruídas e indicam o cursor aplicado.
- BR06: relatórios cobrem objetivo, agentes, gates, evidências, memória, custo e pendências.
- BR07: custo ausente, estimado e confirmado são estados distintos.
- BR08: export contém manifesto, versões, digests e conteúdo redigido.
- BR09: importação é validada como entrada não confiável antes de qualquer mutação.
- BR10: resumo por modelo é opcional e não altera relatório determinístico.

## Edge cases

| Caso | Situação | Resultado |
| --- | --- | --- |
| F07-E01 evento duplicado | mesmo event_id | idempotente ou conflito, sem segunda sequência |
| F07-E02 causation ausente | referência desconhecida | rejeição |
| F07-E03 payload inválido | kind/schema incompatível | nenhuma mutação confirmada |
| F07-E04 segredo multilinha | chave privada em retorno | não persistida |
| F07-E05 artefato alterado | digest não confere | integrity-failed |
| F07-E06 projector interrompido | JSONL parcial | reconstrução a partir do cursor |
| F07-E07 schema futuro | import version maior | assessment incompatible, sem import |
| F07-E08 zip traversal | caminho ../ no pacote | rejeição |
| F07-E09 custo estimado | provider sem cobrança | relatório rotula estimated |
| F07-E10 evento desconhecido | kind novo compatível | preservado e projetado como desconhecido |

## Arquitetura

EventStore participa da transação SQLite F01. ProjectionEngine lê páginas e
produz snapshot, JSONL e relatórios. ArtifactStore usa nomes por digest e nunca
executa conteúdo importado.

~~~mermaid
sequenceDiagram
  participant M as Módulo
  participant DB as SQLite/EventStore
  participant P as ProjectionEngine
  participant A as ArtifactStore
  M->>DB: mutação + EventDraft
  DB-->>M: commit + EventV1
  P->>DB: read(cursor)
  DB-->>P: EventPage
  P->>A: relatório/JSONL redigido
  A-->>P: ArtifactRef
~~~

## Cobertura e gates

BR01–BR10 cobrem AC01–AC08. Testes de contrato validam envelope, ordering,
atomicidade, redaction, rebuild, todos E01–E10 e consumidores F01–F06.
Importação usa fixtures hostis. Gates rápido/completo passaram nesta geração:
7 testes no rápido; checks do repo e 7 testes no completo via Git Bash, com
warning awk não fatal. Propor validação JSON Schema e teste de redaction; os
comandos ainda não existem.

## Riscos

O catálogo exato de payloads por kind deve ser congelado incrementalmente sem
transformar o envelope em união impossível de evoluir. Exportação/importação
não entra antes de redaction e integridade estarem cobertas.
