# 05: Avaliar ações pelo HarnessEngine

**What to build:** Fazer com que toda ação local mutável seja avaliada por
regras determinísticas e produza uma decisão explicável antes de qualquer
efeito.

**Blocked by:** 02/Criar e consultar uma sessão durável.

**Status:** ready-for-agent

- [ ] Toda ação mutável produz allow, deny, require-approval ou require-evidence.
- [ ] Mesma entrada e mesma versão das regras produzem a mesma decisão.
- [ ] Regra ausente, ambígua ou incompatível resulta em deny.
- [ ] Decisão registra sessão, revisão, ator, capability, alvo e motivos.
- [ ] Nenhum adapter mutável conhecido executa sem decisão válida.

