# 03: Revisar o objetivo e retomar com reconciliação

**What to build:** Permitir revisão explícita e imutável do objetivo e retomada
segura de uma sessão interrompida, apresentando o estado que precisa de
reconciliação antes de continuar.

**Blocked by:** 02/Criar e consultar uma sessão durável.

**Status:** ready-for-agent

- [ ] Revisão exige a versão esperada e cria exatamente a próxima versão.
- [ ] Concorrência ou estado incompatível falha sem alterar a sessão.
- [ ] Retomada não inicia agente, ferramenta nem autorização.
- [ ] Sessão antes marcada como running sem executor ativo passa a waiting-for-action com diagnóstico.
- [ ] Histórico e evidências continuam associados à revisão em que foram produzidos.

