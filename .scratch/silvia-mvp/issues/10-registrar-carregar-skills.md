# 10: Registrar e carregar uma fonte local de skills

**What to build:** Permitir que o operador registre uma fonte local, descubra
skills e carregue um contexto reproduzível que distingue release de working
copy e compatibilidade Codex de compatibilidade Claude.

**Blocked by:** 02/Criar e consultar uma sessão durável.

**Status:** ready-for-agent

- [ ] Somente fontes explicitamente registradas podem ser descobertas.
- [ ] Identidade inclui origem, commit quando disponível, caminho relativo e digest.
- [ ] Checkout modificado aparece como working-copy e mudança de digest é detectada na retomada.
- [ ] Campos específicos de harness são preservados e validações aparecem separadamente.
- [ ] Traversal e junction/symlink fora da fonte registrada são rejeitados.
- [ ] Contexto registra arquivos incluídos, digests, truncamento e orçamento.

