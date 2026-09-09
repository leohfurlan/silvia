# F07 — Plano de eventos e relatórios

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F07
**Contrato:** contract.md | **Spec:** spec.md

1. Aprovar F07-C1 e schemas dos eventos necessários a F01/F02.
2. Implementar EventStore transacional, cursores e testes de atomicidade.
3. Migrar WorkflowEvent/observers atuais para producers/projectors compatíveis.
4. Implementar ArtifactStore por digest e redaction antes da persistência.
5. Implementar snapshots, JSONL e relatórios determinísticos.
6. Acrescentar custo, memória e evidência conforme features provedoras.
7. Implementar export e verificação de import não confiável.
8. Executar testes hostis, integração F01–F06, gates e revisão independente.

F07 deve entregar primeiro o envelope mínimo consumido por F01/F02; relatórios
completos seguem quando F03–F05 estiverem integradas. Pronto significa AC01–AC08,
E01–E10, reconstrução determinística e integridade de export comprovadas.
