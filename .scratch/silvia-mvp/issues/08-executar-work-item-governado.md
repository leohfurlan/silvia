# 08: Executar um work item governado ponta a ponta

**What to build:** Executar um work item autorizado sobre checkout isolado,
atribuindo contexto, tentativa, ferramentas e resultado à sessão e à revisão
corretas.

**Blocked by:** 03/Revisar o objetivo e retomar com reconciliação; 04/Isolar sessões em checkouts Git; 06/Conceder e consumir autorizações protegidas; 07/Encapsular Astra atrás do AgentRuntime.

**Status:** ready-for-agent

- [ ] Work item só inicia com dependências satisfeitas, ownership válido e decisão aplicável.
- [ ] Contexto entregue ao agente é fixado e registrado antes da execução.
- [ ] Tentativa possui identidade e eventos duráveis de início e resultado.
- [ ] Ferramenta fora do ownership ou capability autorizada é rejeitada antes do efeito.
- [ ] Stream parcial ou ausência de resultado final não é apresentado como sucesso.

