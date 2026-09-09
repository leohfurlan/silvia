# F02 — Contrato do HarnessEngine

**Contrato:** F02-C1 r1 | **Estado:** draft
**PRD:** ../../product/PRD.md r1, F02
**Spec:** spec.md | **Plano:** plan.md

## Ownership e consumidores

HarnessEngine fornece decisões para SessionRuntime, AgentRuntime, CLI/TUI e
qualquer adapter de efeito. Ele é dono de capability, ActionRequest,
GateDecision e AuthorizationGrant; agentes nunca são donos desses registros.

## Interface

| Operação | Entrada | Resultado |
| --- | --- | --- |
| evaluate | ActionRequest + SessionSnapshot + evidências | GateDecision |
| grant | GateDecision require-approval + ApprovalInput | AuthorizationGrant |
| consume | grant_id + ActionRequest | AuthorizationUse |
| assess_completion | objetivo, critérios, evidências e revisões | CompletionAssessment |

ActionRequest contém action_id, capability, actor, project/session/revision,
work_item, alvo resolvido, parâmetros redigidos, risco e custo previsto.
GateDecision possui outcome: allow, deny, require-approval ou require-evidence;
rule_ids, reasons, requisitos e validade. Grants registram responsável, escopo,
expiração e quantidade de usos.

## Garantias

- Mesma entrada e conjunto versionado de regras produzem a mesma decisão.
- Ausência, ambiguidade ou incompatibilidade de regra resulta deny.
- Grant não muda de revisão, alvo ou capability.
- Ações externas, destrutivas, irreversíveis ou pagas usam grant de uso único.
- Alterar gates é ação protegida e não aprova a alteração.
- CompletionAssessment nunca marca completed; fornece satisfação e lacunas.

## Compatibilidade

Novos outcomes ou mudança semântica são breaking. F01, F04, F06 e F07 precisam
de testes de consumidor. A implementação atual em workflow/engine.py contém
gates parciais, mas ainda não implementa este contrato.

