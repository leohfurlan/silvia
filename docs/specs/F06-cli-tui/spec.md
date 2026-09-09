# F06 — CLI e TUI

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F06
**Contrato:** contract.md | **Plano:** plan.md

## Evidência e escopo

workflow/cli.py usa argparse, um objetivo posicional e flags de checks/PR.
LiveObserver já separa progresso em stderr e resultado JSON em stdout. Evoluir
sem remover bai-workflow. Textual será o adapter TUI e Rich o renderer CLI;
regras permanecem nos módulos F01/F02/F04/F07.

## Requisitos

- BR01: modo interativo e subcomandos atravessam as mesmas interfaces.
- BR02: consulta, memória, relatório e gates locais funcionam sem provider.
- BR03: resume sempre apresenta reconciliação antes de executar.
- BR04: aprovação mostra capability, alvo, revisão, custo e validade.
- BR05: comunicação é técnica, neutra e distingue pendente, falho e não executado.
- BR06: TUI nunca mostra raciocínio oculto ou segredo.
- BR07: --json é determinístico e separado do progresso.
- BR08: aliases legados avisam depreciação sem prazo inventado.

## Edge cases

| Caso | Situação | Resultado |
| --- | --- | --- |
| F06-E01 sem TTY | silvia sem args | ajuda e exit previsível |
| F06-E02 provider offline | session show/report | operação local concluída |
| F06-E03 aprovação ambígua | mensagem informal | pede classificação/confirmação |
| F06-E04 terminal estreito | watch | layout degrada sem ocultar gate |
| F06-E05 stream atrasado | projection lag | exibe cursor e estado de atraso |
| F06-E06 Ctrl+C | agente ativo | solicita cancelamento cooperativo |
| F06-E07 JSON + erro | falha de contrato | erro estruturado, stderr sem segredo |
| F06-E08 alias legado | bai-workflow | compatível + aviso |

## Arquitetura

Textual e Rich dependem de ProjectionEngine. Commands convertem entrada em
operações dos módulos; não manipulam SQLite nem provider diretamente.

~~~mermaid
sequenceDiagram
  participant U as Operador
  participant UI as CLI/TUI
  participant S as SessionRuntime
  participant H as HarnessEngine
  participant P as ProjectionEngine
  U->>UI: resume
  UI->>S: resume_session
  S-->>UI: reconciliação
  U->>UI: confirmar
  UI->>H: avaliar continuação
  H-->>UI: decisão
  UI->>P: acompanhar cursor
  P-->>UI: snapshot + eventos
~~~

## Cobertura e gates

BR01–BR08 cobrem AC01–AC06 e requisitos offline/compatibilidade. Testes de CLI
subprocess cobrem stdout/stderr/exit codes; testes Textual usam piloto de UI
quando a dependência for adicionada. Gates rápido/completo passaram nesta
geração: 7 testes no rápido; checks do repo e 7 testes no completo via Git Bash,
com warning awk não fatal. Propor gate de smoke no PowerShell e acessibilidade
de teclado; comandos serão definidos após a implementação.

## Riscos

Textual/Rich são dependências novas, ainda não instaladas. A duração da
depreciação dos aliases permanece decisão não bloqueante para o MVP.
