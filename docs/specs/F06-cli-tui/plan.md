# F06 — Plano de CLI e TUI

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F06
**Contrato:** contract.md | **Spec:** spec.md

1. Aprovar F06-C1 e códigos de erro/saída.
2. Reestruturar argparse em subcomandos preservando bai-workflow.
3. Implementar modo --json e renderer Rich sobre ProjectionEngine.
4. Adicionar fluxos locais de projeto, sessão, reconciliação e relatório.
5. Integrar aprovações, pause/cancel e run com F02/F04.
6. Implementar TUI Textual sobre snapshots/eventos F07.
7. Validar PowerShell, terminal sem TTY, acessibilidade e aliases.
8. Executar gates e revisão independente de segurança da apresentação.

F06 depende de F01/F02/F04/F07. Pronto significa AC01–AC06, E01–E08 e paridade
de comportamento entre subcomandos, modo interativo e TUI.
