# F04 — Plano do AgentRuntime

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F04
**Contrato:** contract.md | **Spec:** spec.md

1. Aprovar F04-C1 e contratos F01–F03/F07 consumidos.
2. Extrair port de provider e encapsular LangChain/Astra no primeiro adapter.
3. Criar scheduler para grafo, dependências, ownership e apresentação.
4. Introduzir budgets, timeouts, tentativas e resultados incertos.
5. Integrar decisões F02 antes de agente, ferramenta ou gasto.
6. Integrar stop, cancelamento e reconciliação com F01.
7. Implementar SandboxRunner fail-closed e testes de contrato com adapter indisponível e fake.
8. Substituir testes internos por testes na interface e provider fake.
9. Executar integração real autorizada, gates e revisão independente.

Pronto significa AC01–AC09, E01–E08, compatibilidade do adapter atual e nenhuma
rota de execução fora do HarnessEngine.
