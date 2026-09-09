# Desenvolvimento — SilvIA

Fonte canônica e neutra do processo. Adaptadores de agentes apontam para este arquivo.

## Fontes

- Vocabulário: [CONTEXT.md](CONTEXT.md)
- Decisões: [docs/adr/](docs/adr/)
- Autorizações: [docs/agents/authorization.md](docs/agents/authorization.md)
- Configuração: [.harness/project.yaml](.harness/project.yaml)
- Requisitos e specs: usar as fontes canônicas quando existirem

## Premissas

1. Separar fatos, decisões, propostas e pendências.
2. Separar requisito, contrato, spec, plano, código e evidência.
3. Testar pela interface pública real.
4. Vincular evidência à versão avaliada.
5. Registrar baseline e falhas preexistentes.
6. Isolar arquivos e recursos de runtime separadamente.
7. Limitar tentativas, tempo, custo e concorrência.
8. Reconciliar efeito externo incerto antes de repetir.
9. Autorizar commit, push, merge, deploy, migration e efeito operacional separadamente.

## Fluxo

Descobrir → especificar o resultado → fazer preflight → implementar a menor fatia → executar gates → revisar pelo risco → integrar → revalidar → solicitar autorização de entrega.

## Estados

Usar `proposed`, `approved`, `implemented`, `tested`, `reviewed`, `integrated`, `delivered` e `blocked`. Um estado não implica o seguinte.

## Gates

Os comandos vivem em [.harness/gates.json](.harness/gates.json).

```text
python .harness/scripts/run_gates.py --group fast
python .harness/scripts/run_gates.py --group fast --run
```

Sem `--run`, o runner apenas lista. Integrar esse runner ao CI existente.
