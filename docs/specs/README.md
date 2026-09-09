# Especificações

Criar uma pasta por feature ou fatia:

```text
docs/specs/Fxx-short-name/
├── contract.md
├── spec.md
├── plan.md
└── review.md
```

O PRD possui intenção. O contrato possui a interface. A spec possui comportamento e decisões técnicas. O plano possui ordem e checkpoints. A evidência referencia a versão avaliada.

## Features do MVP

| Feature | Artefatos | Dependências |
| --- | --- | --- |
| F01 — Sessões e objetivos | [contrato](F01-session-runtime/contract.md), [spec](F01-session-runtime/spec.md), [plano](F01-session-runtime/plan.md) | none |
| F02 — Harness e autorizações | [contrato](F02-harness-engine/contract.md), [spec](F02-harness-engine/spec.md), [plano](F02-harness-engine/plan.md) | F01 |
| F03 — Skills | [contrato](F03-skill-registry/contract.md), [spec](F03-skill-registry/spec.md), [plano](F03-skill-registry/plan.md) | F01, F02 |
| F04 — Agentes | [contrato](F04-agent-runtime/contract.md), [spec](F04-agent-runtime/spec.md), [plano](F04-agent-runtime/plan.md) | F01, F02 |
| F05 — Memória | [contrato](F05-memory-store/contract.md), [spec](F05-memory-store/spec.md), [plano](F05-memory-store/plan.md) | F01, F02, F07 mínimo |
| F06 — CLI e TUI | [contrato](F06-cli-tui/contract.md), [spec](F06-cli-tui/spec.md), [plano](F06-cli-tui/plan.md) | F01, F02, F04, F07 mínimo |
| F07 — Eventos e relatórios | [contrato](F07-events-reports/contract.md), [spec](F07-events-reports/spec.md), [plano](F07-events-reports/plan.md) | F01 e F04 para o produto completo |

## Ordem e checkpoints

O envelope mínimo F07-C1 e a transação F01-C1 são definidos juntos na primeira
onda, eliminando o ciclo documental entre persistência e eventos:

1. F01 + envelope mínimo F07: sessão, revisão, event_id, sequence e atomicidade.
2. F02: decisões e autorizações persistidas pelo contrato anterior.
3. F03 e F04: skills e execução podem avançar em paralelo após F02.
4. F05: memória consome sessão, autorização e eventos.
5. F06: CLI/TUI integra as interfaces estabilizadas.
6. F07 completo: relatórios e exportação integram F03–F06.

F08–F11 permanecem propostas no PRD. Não possuem specs prontas nem autorização
de implementação.
