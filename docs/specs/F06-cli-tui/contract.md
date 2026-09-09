# F06 — Contrato de CLI e TUI

**Contrato:** F06-C1 r1 | **Estado:** draft
**PRD:** ../../product/PRD.md r1, F06
**Spec:** spec.md | **Plano:** plan.md

## Ownership

F06 fornece adapters de apresentação; não possui regras de sessão, autorização
ou execução. Consome SessionRuntime, HarnessEngine, AgentRuntime e ProjectionEngine.

## Interface de comandos

| Comando | Resultado observável |
| --- | --- |
| silvia | abre modo interativo ou ajuda em terminal não interativo |
| silvia session new | cria sessão após coletar projeto/objetivo |
| silvia session list/show | projeta sessões sem provider |
| silvia session resume | mostra reconciliação e pede confirmação |
| silvia run | solicita avanço permitido da sessão |
| silvia watch | acompanha snapshot/eventos e permite governança |
| silvia pause/cancel | solicita transição por F01/F02 |
| silvia report | gera/abre projeção F07 |

Saída normal humana vai para stdout; progresso para stderr; modo --json produz
um documento por comando e nenhum texto decorativo. Erros têm código estável,
mensagem técnica, ação sugerida e exit code não zero.

## TUI

A TUI apresenta objetivo/revisão, agentes, work items, gates, budgets, eventos
e pendências. Permite responder, aprovar/negar, pausar, cancelar e abrir
artefatos. Não edita código nem contém regras de negócio.

## Compatibilidade

Produto e comando são SilvIA/silvia. bai-workflow e $astra permanecem aliases
depreciados; data de remoção é decisão posterior. Automação deve usar
subcomandos e --json, não raspar a TUI.

