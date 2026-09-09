# 07: Encapsular Astra atrás do AgentRuntime

**What to build:** Tornar Astra o primeiro adapter do AgentRuntime, permitindo
consultar rotas disponíveis e iniciar um agente identificado sem expor
LangChain ou detalhes do provider como interface do produto.

**Blocked by:** 01/Inicializar o pacote e o comando silvia; 02/Criar e consultar uma sessão durável.

**Status:** ready-for-agent

- [ ] Rotas disponíveis são descobertas a partir da configuração real e redigida.
- [ ] Rota ausente ou proibida não recebe substituição silenciosa.
- [ ] Agente emite apresentação com ID, papel, modelo/provider, revisão, ownership, capacidades e condição de parada.
- [ ] Credenciais e raciocínio oculto não entram em eventos nem resultados públicos.
- [ ] Provider fake e adapter Astra satisfazem o mesmo contrato observável.

