# F03 — Plano do SkillRegistry

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F03
**Contrato:** contract.md | **Spec:** spec.md

1. Aprovar F03-C1 e schema JSON/YAML canônico do sidecar.
2. Implementar fontes registradas e resolução segura de caminhos.
3. Implementar identidade, working-copy e digest do contexto.
4. Adicionar adapters Codex e Claude com preservação de extensões.
5. Integrar validators como diagnósticos separados.
6. Montar SkillContext consumido por F04 e eventos F07.
7. Integrar capabilities com F02, sem executor dentro do registry.
8. Verificar fixtures, regressões e fonte agent-skills real em cenário de integração.

Pronto significa AC01–AC07, E01–E08 e teste de consumidor F04 aprovados. Gestão
de instalação/promoção permanece F10 e fora deste plano.
