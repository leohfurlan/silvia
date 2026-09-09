# 09: Controlar paralelismo, budgets, cancelamento e reconciliação

**What to build:** Executar work items independentes em paralelo dentro dos
limites da sessão, pausar quando um orçamento for atingido e tratar parada ou
resultado incerto sem repetição cega.

**Blocked by:** 08/Executar um work item governado ponta a ponta.

**Status:** ready-for-agent

- [ ] Máximo padrão de três agentes simultâneos é respeitado.
- [ ] Chamadas usam timeout de 15 minutos e no máximo duas tentativas transitórias.
- [ ] Revisão/correção usa no máximo duas rodadas por padrão.
- [ ] Custo adicional começa desautorizado e limite excedido pausa a sessão.
- [ ] Cancelamento impede novos work items e solicita parada cooperativa.
- [ ] Tentativa incerta exige reconciliação antes de qualquer retry.
