# F01 — Sessões e objetivos duráveis

**Estado:** draft
**PRD:** ../../product/PRD.md r1, F01
**Contrato:** contract.md | **Plano:** plan.md

## Escopo e evidência

Implementar SessionRuntime sobre o runner efêmero de workflow/engine.py. A CLI
atual aceita apenas um objetivo em workflow/cli.py; não há banco, migration,
projeto ou sessão. Reutilizar eventos de workflow/observability.py por meio do
contrato F07, sem manter JSONL como fonte canônica.

## Comportamento verificável

- BR01: criar sessão produz UUIDs de projeto/sessão, revisão 1 e estado created.
- BR02: revisar exige expected_revision; concorrência rejeita sem nova revisão.
- BR03: retomar retorna reconciliação e zero agentes/ferramentas iniciados.
- BR04: transições aceitam apenas o grafo definido no CONTEXT.md.
- BR05: cancelar impede novos work items, solicita parada cooperativa e registra incertezas.
- BR06: conclusão só ocorre após F02 declarar critérios satisfeitos e confirmação humana.
- BR07: Git usa worktree por padrão; modo direto exige escolha explícita.
- BR08: baseline dirty é registrado e nunca limpo pelo runtime.
- BR09: sessões escritoras concorrentes não compartilham checkout.

## Edge cases

| Caso | Entrada/precondição | Resultado |
| --- | --- | --- |
| F01-E01 objetivo vazio | texto vazio | invalid-objective, nenhuma sessão |
| F01-E02 revisão concorrente | expected_revision antiga | concurrent-revision |
| F01-E03 interrupção atômica | falha entre estado e evento | ambos ausentes ou ambos confirmados |
| F01-E04 schema futuro | versão não suportada | incompatible-store, somente leitura diagnóstica |
| F01-E05 clone ambíguo | remotes iguais, identidade não confirmada | ambiguous-project |
| F01-E06 checkout ocupado | outra sessão escritora | checkout-conflict |
| F01-E07 retomada running | processo anterior desapareceu | waiting-for-action com reconciliação |
| F01-E08 cancelamento terminal | completed/cancelled | already-terminal, estado preservado |

## Decisões técnicas

SQLite via sqlite3 da stdlib é o adapter persistente; adapter in-process serve
testes. Dados ficam em LOCALAPPDATA/SilvIA/data e configuração em
APPDATA/SilvIA. Migrations SQL são numeradas, transacionais e precedidas por
backup recuperável. O UUID de projeto é associado localmente a remotes,
primeiro commit observado e localizações; união de clones requer confirmação.

~~~mermaid
sequenceDiagram
  participant U as Operador
  participant S as SessionRuntime
  participant P as Store
  participant E as EventStore
  U->>S: new_session(ObjectiveInput)
  S->>P: begin + sessão + revisão 1
  S->>E: session.created
  P-->>S: commit com sequence
  S-->>U: SessionView
  U->>S: resume_session(id)
  S-->>U: ReconciliationView
  U->>S: confirmar continuação
~~~

## Cobertura

BR01 cobre AC01; BR02 AC02; BR04 AC03; BR03 AC04; BR05 AC05; BR06 AC06;
BR07 AC07; BR08 AC08; BR09 AC09. Testar pela interface SessionRuntime contra
os dois adapters, incluindo todos F01-E01–E08.

## Gates

| Gate | Fonte | Comando/cwd | Política | Evidência |
| --- | --- | --- | --- | --- |
| rápido | .harness/gates.json | python -m unittest discover -s tests -p test_workflow.py / raiz | existente obrigatório | passed: 7 testes |
| completo | .harness/gates.json | bash tests/test_skill.sh / raiz, via Git Bash | existente obrigatório | passed: checks do repo e 7 testes; warning awk não fatal |
| contrato SessionRuntime | lacuna | suite proposta contra dois adapters | proposto | não executado |

## Riscos e prontidão

Definir na implementação o caminho exato dos arquivos SQL e o formato do
registro de projeto. O contrato está pronto para aprovação, mas SQLite,
migrations e integração F07 ainda não existem.
