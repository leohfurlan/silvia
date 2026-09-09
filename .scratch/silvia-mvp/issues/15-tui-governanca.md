# 15: Acompanhar e governar sessões pela TUI

**What to build:** Exibir o estado vivo da sessão em uma TUI acessível e permitir
que o operador responda, aprove, pause ou cancele sem duplicar regras do núcleo.

**Blocked by:** 09/Controlar paralelismo, budgets, cancelamento e reconciliação; 14/Disponibilizar subcomandos e saída JSON.

**Status:** ready-for-agent

- [ ] TUI apresenta objetivo/revisão, agentes, work items, gates, budgets, eventos e pendências.
- [ ] Operador pode responder, aprovar/negar, pausar, cancelar e abrir artefatos.
- [ ] Ações da TUI atravessam as mesmas interfaces e decisões dos subcomandos.
- [ ] Terminal estreito preserva gates e ações críticas.
- [ ] Atraso de projeção mostra cursor/estado e não simula durabilidade.
- [ ] Navegação principal funciona por teclado e não mostra raciocínio oculto ou segredo.

