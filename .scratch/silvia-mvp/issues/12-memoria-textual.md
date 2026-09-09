# 12: Propor, promover e recuperar memória textual

**What to build:** Permitir que fontes confiáveis produzam candidatos de
memória, que o operador os promova para um escopo e que o contexto recupere
itens relevantes por busca textual com proveniência e conflitos visíveis.

**Blocked by:** 05/Avaliar ações pelo HarnessEngine; 10/Registrar e carregar uma fonte local de skills.

**Status:** ready-for-agent

- [ ] Memória registra tipo, origem, sessão, escopo, data, validade, confiança e evidência.
- [ ] Inferência de agente permanece candidata até validação.
- [ ] Promoção entre session, project e user nunca é automática.
- [ ] Busca lexical usa escopo, precedência, validade e correspondência textual.
- [ ] Contexto registra exatamente os itens entregues e as exclusões por orçamento.
- [ ] Conflitos não resolvidos são apresentados e não escolhidos silenciosamente.
- [ ] Segredo detectado não é persistido.

