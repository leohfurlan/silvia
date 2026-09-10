# F03 — Registro e carregamento de skills

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F03
**Contrato:** contract.md | **Plano:** plan.md

## Evidência e escopo

A fonte local C:/Projetos TI/agent-skills contém 27 diretórios com SKILL.md, 25
openai.yaml e scripts com riscos distintos. Não há versão/origem/capabilities
uniformes; o validador atual rejeita extensões Claude reais. O MVP descobre e
carrega fontes locais, mas não instala, promove, cria junction ou publica.

## Requisitos

- BR01: fonte precisa ser registrada antes da leitura.
- BR02: identidade reproduzível usa origem, commit, caminho e digest.
- BR03: working-copy é exibida e fixada pelo digest.
- BR04: adapters normalizam Codex/Claude e preservam campos desconhecidos.
- BR05: validações por harness aparecem separadamente.
- BR06: leitura de skill nunca concede execução de script.
- BR07: script sem sidecar válido é negado; script declarado ainda passa por F02 e pelo SandboxRunner definido no ADR-0001.
- BR09: ausência de adapter de sandbox compatível nega execução; subprocesso direto no host nunca é fallback.
- BR08: contexto lista arquivos, digests, truncamento e orçamento consumido.

## Edge cases

| Caso | Situação | Resultado |
| --- | --- | --- |
| F03-E01 nome duplicado | duas fontes registradas | seleção exige source_id |
| F03-E02 checkout dirty | recurso modificado | working-copy + novo digest |
| F03-E03 campo Claude | frontmatter não Codex | preservado; relatórios separados |
| F03-E04 path traversal | recurso aponta para fora | rejeição |
| F03-E05 junction externa | alvo fora da raiz | rejeição salvo fonte registrada |
| F03-E06 sidecar ausente | script existe | leitura permitida, execução negada |
| F03-E07 schema major futuro | silvia.yaml desconhecido | capacidades negadas |
| F03-E08 digest mudou | resume de sessão | require-approval para novo contexto |

## Arquitetura

Adapters de parser convertem formatos para NormalizedSkill. Descoberta,
identidade e montagem ficam em um módulo profundo. Execução permanece no
AgentRuntime e autorização no HarnessEngine; o registry nunca chama scripts.

~~~mermaid
sequenceDiagram
  participant U as Operador
  participant R as SkillRegistry
  participant V as Validator adapters
  participant H as HarnessEngine
  U->>R: register_source(path)
  R->>R: discover + resolve + digest
  R->>V: validar por harness
  V-->>R: ValidationReport
  R-->>U: identidade e compatibilidade
  U->>H: solicitar capacidade de script
  H-->>U: decisão separada
~~~

## Cobertura e gates

BR01–BR08 cobrem AC01–AC07 e reprodutibilidade de contexto. Testar com fixtures
Codex, Claude, híbrida, working-copy, junction e sidecar malicioso. Usar
quick_validate.py e claude plugin validate apenas como validators de adapter,
quando disponíveis; não são gates atuais deste repo. Gates rápido/completo do
SilvIA passaram: 7 testes no rápido; checks do repo e 7 testes no completo via
Git Bash, com warning awk não fatal.

## Riscos

O schema detalhado de capabilities deverá ser congelado no contrato antes de
permitir scripts. A fonte agent-skills está fora deste checkout e sua inspeção
não prova estabilidade futura.
