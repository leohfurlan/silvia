# F01 — Plano de sessões e objetivos

**Estado:** draft
**PRD:** ../../product/PRD.md r1, F01
**Contrato:** contract.md | **Spec:** spec.md

1. Congelar F01-C1 e o contrato mínimo de eventos F07 consumido nas transações.
2. Introduzir tipos de projeto, sessão, objetivo, estados e erros, testados pela interface.
3. Implementar adapter in-process e testes de contrato.
4. Implementar SQLite, migrations numeradas, backup e os mesmos testes.
5. Integrar descoberta Git, baseline e exclusão de checkout escritor.
6. Integrar criação, revisão, retomada, reconciliação e cancelamento ao controller.
7. Conectar comandos F06 sem remover o comando legado.
8. Executar gates, teste de interrupção e revisão independente.

F01 é provedora de F02–F07. F02 e F07 precisam de contratos acordados antes da
integração. Definição de pronto: AC01–AC09 observáveis, adapters conformes,
migration recuperável e gates obrigatórios executados na mesma versão.
