# F02 — Harness e autorizações determinísticas

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F02
**Contrato:** contract.md | **Plano:** plan.md

## Escopo e evidência

Extrair decisões determinísticas hoje espalhadas por workflow/engine.py,
workflow/config.py e workflow/tools.py. Já existem validação de modelos,
ownership disjunto, revisão, checks e flag separada para PR. Não existem grants
persistentes, revisão do objetivo nas decisões ou avaliação uniforme por ação.

## Requisitos

- BR01: toda mutação e todo efeito passa por evaluate antes da execução.
- BR02: resultado usa somente os quatro outcomes do contrato.
- BR03: grants são vinculados a ação, alvo, revisão, escopo e expiração.
- BR04: grants críticos são de uso único; repetição exige reconciliação.
- BR05: memória, prompt, skill e modelo não criam nem alteram grants.
- BR06: proposta de gate fica não autoritativa até aprovação.
- BR07: completion lista critérios satisfeitos, ausentes e evidências inválidas.

## Edge cases

| Caso | Situação | Resultado |
| --- | --- | --- |
| F02-E01 regra ausente | capability desconhecida | deny |
| F02-E02 grant expirado | consume após expiração | deny, nenhum efeito |
| F02-E03 revisão mudou | grant da revisão anterior | deny |
| F02-E04 replay | grant uso único já consumido | deny + reconciliação |
| F02-E05 alvo divergente | mesmo comando, outro caminho | deny |
| F02-E06 evidência antiga | código posterior ao gate | require-evidence |
| F02-E07 gate editado pelo agente | regra proposta no diff | require-approval |

## Decisões

HarnessEngine é módulo in-process puro sobre snapshots imutáveis; persistência
de grants e eventos pertence a F01/F07. Regras versionáveis vêm do harness e
são compiladas para representação normalizada. Adapters executam efeitos apenas
com AuthorizationUse válido.

~~~mermaid
sequenceDiagram
  participant A as Actor
  participant H as HarnessEngine
  participant U as Operador
  participant X as EffectAdapter
  A->>H: evaluate(ActionRequest)
  alt allow
    H-->>X: decisão válida
  else require approval
    H-->>U: decisão e escopo
    U->>H: grant(ApprovalInput)
    H->>X: consume(grant)
  else deny ou evidence
    H-->>A: motivos/requisitos
  end
~~~

## Cobertura e gates

BR01–BR07 mapeiam AC01–AC07. Testes de tabela cobrem todas as capabilities,
outcomes e E01–E07; testes de consumidor provam que adapters não executam sem
decisão. Gates existentes rápido e completo passaram nesta geração: 7 testes no
rápido; checks do repo e 7 testes no completo via Git Bash, com warning awk não
fatal. É proposto um gate de arquitetura que detecte subprocesso,
escrita ou rede fora de adapters autorizados; comando ainda não existe.

## Riscos

O catálogo inicial de capabilities e a serialização das regras pertencem à
implementação, mas não podem reduzir as garantias do contrato. Integração exige
F01-C1 e envelope F07-C1.
