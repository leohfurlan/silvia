# 04: Isolar sessões em checkouts Git

**What to build:** Associar sessões a uma identidade lógica de projeto,
registrar o baseline do checkout e impedir concorrência mutável insegura,
usando worktree como escolha padrão.

**Blocked by:** 02/Criar e consultar uma sessão durável.

**Status:** ready-for-agent

- [ ] Identidade do projeto não depende apenas do caminho do checkout.
- [ ] Baseline registra commit, remotes, localização e alterações preexistentes.
- [ ] Mudanças preexistentes nunca são limpas ou atribuídas silenciosamente à sessão.
- [ ] Checkout direto exige escolha explícita do operador.
- [ ] Segunda sessão escritora no mesmo checkout é rejeitada; worktrees isoladas podem coexistir.

