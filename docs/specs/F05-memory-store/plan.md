# F05 — Plano do MemoryStore

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F05
**Contrato:** contract.md | **Spec:** spec.md

1. Aprovar F05-C1, tipos, precedência e política de redaction.
2. Modelar candidatos, memória, conflitos, recibos e queries.
3. Implementar adapter in-process e testes da interface.
4. Implementar tabelas SQLite/FTS5 e os mesmos casos de contrato.
5. Integrar ContextBuilder com orçamento e registro F07.
6. Integrar promoção, exportação, exclusão e retenção com F02.
7. Verificar isolamento, conflito, segredo, expiração e FTS5 empacotado.
8. Executar gates e revisão independente de privacidade.

F05 depende de F01/F02/F07. Pronto significa AC01–AC08 e E01–E08 observáveis,
sem embeddings nem acesso irrestrito do agente ao banco.
