# F03 — Contrato do SkillRegistry

**Contrato:** F03-C1 r1 | **Estado:** draft
**PRD:** ../../product/PRD.md r1, F03
**Spec:** spec.md | **Plano:** plan.md

## Ownership

SkillRegistry é dono de SkillSource, SkillIdentity, NormalizedSkill,
ValidationReport e CapabilityManifest. AgentRuntime consome contexto resolvido;
HarnessEngine decide se uma capacidade pode ser executada.

## Interface

| Operação | Entrada | Resultado |
| --- | --- | --- |
| register_source | URI/path explícito + nome | SkillSource |
| discover | source_id | lista de SkillCandidate |
| resolve | source_id + nome/caminho | ResolvedSkill |
| validate | SkillIdentity + harnesses | ValidationReport |
| build_context | identidades + orçamento | SkillContext |

SkillIdentity contém source URI, commit opcional, caminho relativo e SHA-256 do
conteúdo carregado. Tag é metadado. Dirty checkout produz working-copy.
NormalizedSkill preserva extensões desconhecidas sem atribuir capacidade.

O sidecar silvia.yaml v1 contém schema_version e capabilities. Cada capacidade
de script declara executable relativo, argv permitido, filesystem read/write,
network hosts, platforms e requires_approval. Comandos são argv, nunca shell.

## Garantias

- Apenas fontes registradas são descobertas.
- Path traversal e symlinks/junctions fora da fonte resolvida são rejeitados.
- Ausência ou invalidade do sidecar permite leitura e nega scripts.
- Digest cobre SKILL.md, sidecar e recursos efetivamente incluídos.
- Validadores Codex/Claude não se substituem e não alteram o conteúdo.

## Compatibilidade

F04 consome SkillContext; F02 consome capacidades; F07 registra identidade e
validação. Campos desconhecidos são preservados, mas schema major desconhecido
nega capacidades executáveis.

