# F04 — Execução multiagente observável

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F04
**Contrato:** contract.md | **Plano:** plan.md

## Evidência e escopo

workflow/agents.py cria ChatOpenAI e agentes LangChain diretamente.
workflow/engine.py paraleliza por asyncio, limita max_parallel e rejeita
ownership sobreposto/modelos inválidos. Há duas rodadas de review, mas não há
sessão, orçamento de custo/tokens, reconciliação ou interface de adapter.

## Requisitos

- BR01: Astra propõe; política determinística escolhe apenas rota callable e autorizada.
- BR02: apresentação estruturada precede qualquer ferramenta.
- BR03: máximo padrão de três agentes simultâneos.
- BR04: chamada tem timeout padrão de 15 minutos e duas tentativas transitórias.
- BR05: correção/revisão tem no máximo duas rodadas por padrão.
- BR06: gasto adicional começa desautorizado.
- BR07: contexto pago exige estimativa e aprovação se não houver orçamento.
- BR08: duração de sessão é ilimitada, com aviso após duas horas.
- BR09: stop é cooperativo; timeout produz resultado incerto e reconciliação.
- BR10: provider indisponível bloqueia execução, mas não funções locais.
- BR11: capability de skill executa somente por SandboxRunner compatível; preflight vem antes de F02 e de qualquer efeito.
- BR12: adapter indisponível ou incapaz de aplicar filesystem, rede, plataforma, argv ou limites retorna sandbox-unavailable/sandbox-incompatible sem fallback host.

## Edge cases

| Caso | Situação | Resultado |
| --- | --- | --- |
| F04-E01 rota inventada | plano cita model inexistente | rejeição antes de spawn |
| F04-E02 ownership sobreposto | itens paralelos conflitantes | plano inválido |
| F04-E03 dependência cíclica | grafo sem nó pronto | bloqueado |
| F04-E04 timeout | provider não confirma término | uncertain + reconcile |
| F04-E05 orçamento excedido | próximo token/chamada ultrapassa | waiting-for-action |
| F04-E06 stream parcial | tokens sem resultado final | falha, não sucesso parcial |
| F04-E07 cancelamento | sessão solicita stop | nenhum novo work item |
| F04-E08 segredo em retorno | padrão sensível | redigido antes de F07 |

## Arquitetura

Extrair port de provider e adapters Astra/LangChain. Scheduler valida grafo,
dependências, ownership e budgets antes de chamar o adapter. Os defaults são
3 agentes, 2 correções, 2 retries transitórios, timeout de 15 minutos e aviso
de sessão em 2 horas.

~~~mermaid
sequenceDiagram
  participant S as SessionRuntime
  participant H as HarnessEngine
  participant R as AgentRuntime
  participant P as Provider adapter
  S->>R: execute(work item)
  R->>H: evaluate(agent/tool capability)
  H-->>R: decisão
  R->>R: validar rota, ownership e budget
  R->>P: invoke contexto fixado
  P-->>R: stream/result/error
  R-->>S: AttemptResult ou reconciliação
~~~

## Cobertura e gates

BR01–BR10 cobrem AC01–AC09 e operação offline. Reusar testes atuais de modelo,
ownership e ciclos, elevando-os à interface AgentRuntime. Provider fake cobre
E01–E08; adapter real exige cenário de integração separado. Gates rápido e
completo passaram nesta geração: 7 testes no rápido; checks do repo e 7 testes
no completo via Git Bash, com warning awk não fatal. Propor testes assíncronos
de contrato e cancelamento; nenhum comando canônico existe ainda.

## Riscos

Uso real do provider tem custo e rede; não é necessário para todo gate. A
medição de tokens/custo depende do adapter e deve distinguir ausente, estimada
e confirmada.
