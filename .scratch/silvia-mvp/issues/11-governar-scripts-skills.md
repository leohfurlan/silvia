# 11: Governar scripts e capacidades de skills

**What to build:** Interpretar o manifesto sidecar de uma skill e permitir que
um script declarado seja solicitado como capability, mantendo negação por
padrão e autorização separada da leitura das instruções.

**Blocked by:** 06/Conceder e consumir autorizações protegidas; 10/Registrar e carregar uma fonte local de skills.

**Status:** ready-for-agent

- [ ] Ausência, invalidade ou schema major desconhecido do sidecar nega execução.
- [ ] Capacidade declara executável, argv, filesystem, rede, plataforma e necessidade de aprovação.
- [ ] Comandos são executados como argv e não como shell livre.
- [ ] Campos desconhecidos são preservados, mas não concedem capacidade.
- [ ] Capability válida ainda exige decisão do HarnessEngine para a ação concreta.
- [ ] Leitura de SKILL.md permanece possível quando scripts estão negados.

