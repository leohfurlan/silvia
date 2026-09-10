---
status: accepted
date: 2026-09-10
---

# Executar capabilities somente por SandboxRunner fail-closed

Scripts declarados por skills só podem ser executados pelo AgentRuntime através do seam SandboxRunner. O runtime exige um adapter de isolamento compatível que aplique filesystem, rede, plataforma, argv e limites; ausência ou incompatibilidade do adapter bloqueia antes de autorização ou efeito, e execução direta no host nunca é fallback.

## Considered Options

Execução direta por subprocesso foi rejeitada porque apenas registrar as declarações do sidecar não contém o processo. Interpretar scripts pelo agente também foi rejeitado porque não preserva a identidade nem o comportamento do executável declarado.

## Consequences

O MVP pode descobrir e validar capabilities mesmo quando nenhuma delas é executável na máquina. Adapters futuros devem passar o mesmo contrato do fake determinístico e produzir resultado ou incerteza reconciliável sem ampliar a interface do AgentRuntime.