# PRD — SilvIA

**Revisão:** r1
**Estado:** approved
**Responsável pelo produto:** Leonardo

## Visão

SilvIA é um aplicativo CLI local-first para conduzir desenvolvimento de
software com agentes, skills, memória e evidências sob um harness determinístico.
Ele transforma uma ideia em artefatos aprovados, implementação verificada e
entrega explicitamente autorizada, sem confundir sugestão de modelo com decisão.

O nome combina Silva, sobrenome do criador, com Inteligência Artificial. A marca
é SilvIA; comando e pacote usam silvia. A linguagem da interface é técnica e
neutra.

## Problema

O runtime atual executa agentes em paralelo e emite eventos, mas a invocação é
efêmera. Faltam sessões retomáveis, objetivo versionado, skills reproduzíveis,
memória com proveniência, gates persistentes e relatórios que expliquem o que
aconteceu. Ferramentas existentes também tendem a misturar contexto, execução,
aprovação e entrega.

## Resultado

Um operador individual deve conseguir conduzir uma feature real do próprio
SilvIA, interromper e retomar a sessão, manter objetivo e autorizações intactos,
acompanhar os agentes e obter um relatório baseado em evidências. Depois, o
produto evoluirá para outros desenvolvedores sem introduzir colaboração no MVP.

## Princípios

1. Objetivo vigente e harness são autoritativos; modelos, skills e memória não.
2. Somente o usuário aprova ou amplia objetivo, PRD, contrato, spec e plano.
3. Toda ação é atribuível a projeto, sessão, revisão, work item e agente.
4. Histórico é append-only; relatórios são projeções reproduzíveis.
5. Estados configurado, executado, aprovado e entregue permanecem distintos.
6. O funcionamento principal é local e não envia telemetria no MVP.
7. Credenciais e conteúdo sensível são redigidos antes da persistência.
8. Frameworks e providers ficam atrás de interfaces substituíveis.

## Fluxo canônico

Ideia → descoberta/entrevista → PRD aprovado → contrato → spec → plano aprovado
→ implementação → gates e evidências → revisão independente → confirmação
humana de conclusão → entrega separadamente autorizada.

Se os artefatos necessários não existirem, SilvIA aciona skills de descoberta e
gera propostas. Ele não inicia implementação especulativa. Descobertas durante
a implementação viram proposta ou pendência; não alteram retroativamente uma
fonte aprovada.

## Escopo do MVP

- Sessões persistentes vinculadas a um projeto, objetivo e revisão.
- Retomada com reconciliação e confirmação antes de continuar.
- Identidade lógica de projeto independente do caminho físico.
- Worktree Git por padrão e baseline de alterações preexistentes.
- Avaliação determinística de ações e autorizações com escopo e validade.
- Descoberta e carregamento explícito de skills locais registradas.
- Astra como adapter padrão de orquestração.
- Execução multiagente com ownership, limites e apresentação estruturada.
- Memória de sessão, projeto e usuário com proveniência.
- CLI por subcomandos e modo interativo.
- TUI para observar e governar sessões.
- Eventos versionados, JSONL, relatórios Markdown e JSON.
- Instalação por pipx e suporte inicial validado no Windows/PowerShell.

## Fora do MVP

- Colaboração simultânea entre usuários ou sincronização em nuvem.
- Interface web ou projeção nativa de agentes no Codex.
- Instalação, atualização, junctions, tags ou promoção de skills.
- Atualizações automáticas do aplicativo ou das skills.
- Telemetria remota.
- Marketplace de modelos ou skills.
- Execução destrutiva como capacidade comum.
- Commit, push, PR, merge, migration, deploy ou efeito externo implícitos.

## Features

Os IDs são estáveis e não devem ser reutilizados.

| ID | Resultado | Estado | Pré-requisitos |
| --- | --- | --- | --- |
| F01 | Criar, revisar e retomar sessões com objetivo preservado | approved | none |
| F02 | Avaliar ações e autorizações por harness determinístico | approved | F01 |
| F03 | Descobrir, validar e carregar skills reproduzíveis | approved | F01, F02 |
| F04 | Orquestrar agentes observáveis com limites e ownership | approved | F01, F02 |
| F05 | Guardar e recuperar memória não autoritativa | approved | F01, F02 |
| F06 | Operar sessões pela CLI e TUI | approved | F01, F02, F04 |
| F07 | Gerar eventos, evidências, exportações e relatórios | approved | F01, F04 |
| F08 | Disponibilizar interface web local | proposed | F06, F07 |
| F09 | Projetar agentes e sessões nativamente no Codex | proposed | F07, F08 |
| F10 | Gerenciar instalação e promoção protegida de skills | proposed | F03, F07 |
| F11 | Colaborar e sincronizar sessões em nuvem | proposed | F07, F08, F09 |

## F01 — Sessões e objetivos

- F01-AC01 — Cada sessão possui ID, projeto, objetivo vigente e revisão imutável.
- F01-AC02 — Revisar o objetivo cria nova revisão e reavalia trabalho e aprovações afetados.
- F01-AC03 — Estados suportados são created, planning, running,
  waiting-for-action, blocked, completed, cancelled e archived.
- F01-AC04 — Retomar restaura o estado, apresenta reconciliação e não executa automaticamente.
- F01-AC05 — Cancelar impede novos work items, solicita parada cooperativa e preserva incertezas.
- F01-AC06 — O harness verifica os critérios e o usuário confirma a conclusão.
- F01-AC07 — Worktrees são padrão em Git; checkout direto exige escolha explícita.
- F01-AC08 — Alterações preexistentes são atribuídas ao baseline e preservadas.
- F01-AC09 — Sessões concorrentes não compartilham ownership mutável.

## F02 — Harness e autorizações

- F02-AC01 — Toda ação mutável recebe allow, deny, require-approval ou require-evidence.
- F02-AC02 — Autorizações registram ação, escopo, revisão, responsável e expiração.
- F02-AC03 — Capacidades podem valer por chamada, work item ou sessão.
- F02-AC04 — Ações externas, irreversíveis e pagas são de uso único por padrão.
- F02-AC05 — Agentes podem propor gates, mas não torná-los autoritativos.
- F02-AC06 — Memória, skill ou saída de modelo não fabricam autorização.
- F02-AC07 — Ações destrutivas futuras exigem alvo resolvido, preflight,
  autorização específica, evidência e recuperação quando aplicável.

## F03 — Skills

- F03-AC01 — Fontes locais precisam ser explicitamente registradas.
- F03-AC02 — A identidade combina origem, commit, caminho relativo e digest.
- F03-AC03 — Tags são opcionais; checkout modificado recebe estado working-copy.
- F03-AC04 — O núcleo normaliza formatos; adapters preservam extensões desconhecidas.
- F03-AC05 — Validadores de cada harness produzem resultados separados.
- F03-AC06 — Ler instruções não autoriza executar scripts.
- F03-AC07 — Scripts sem capacidades declaradas em manifesto sidecar são negados.

## F04 — Agentes

- F04-AC01 — Astra é o adapter padrão, não uma dependência da interface do produto.
- F04-AC02 — A política valida disponibilidade, classe, custo e modelos permitidos.
- F04-AC03 — Modelo pago exige orçamento autorizado ou aprovação específica.
- F04-AC04 — Cada agente apresenta ID, papel, modelo, provider, objetivo,
  work item, ownership, capacidades, proibições e condição de parada.
- F04-AC05 — Concorrência, chamadas, tokens, custo, tempo, contexto e tentativas têm limites.
- F04-AC06 — Exceder limite pausa a sessão e não amplia o orçamento.
- F04-AC07 — Falhas seguem política limitada; resultado externo incerto exige reconciliação.
- F04-AC08 — Revisão independente é proporcional ao risco e obrigatória para
  código, harness, segurança, persistência, autorização e integrações.
- F04-AC09 — Correções e revisões são limitadas, com duas rodadas como padrão.

## F05 — Memória

- F05-AC01 — Existem escopos de sessão, projeto e usuário, sem promoção automática.
- F05-AC02 — Cada memória registra tipo, origem, sessão, escopo, data, validade,
  confiança e evidência.
- F05-AC03 — Usuário, decisões aprovadas, artefatos e evidências geram candidatos;
  inferências de agentes continuam propostas.
- F05-AC04 — O ContextBuilder filtra por escopo, validade, tipo, confiança e orçamento.
- F05-AC05 — O pacote registra exatamente as memórias entregues ao agente.
- F05-AC06 — Conflitos sem precedência determinística são apresentados ao usuário.
- F05-AC07 — Histórico volumoso tem retenção configurável; memórias promovidas
  não expiram automaticamente.
- F05-AC08 — Exportação e exclusão são suportadas.

## F06 — CLI e TUI

- F06-AC01 — Há modo interativo e subcomandos estáveis sob silvia.
- F06-AC02 — A TUI cria e abre sessões, recebe respostas, governa aprovações,
  pausa, cancela e abre artefatos e relatórios.
- F06-AC03 — Código e documentos permanecem no editor escolhido pelo usuário.
- F06-AC04 — Comunicação é técnica e neutra; falhas e pendências não são suavizadas.
- F06-AC05 — Sem provider, consulta, memória, relatórios e gates locais continuam disponíveis.
- F06-AC06 — bai-workflow e $astra permanecem aliases depreciados durante transição documentada.

## F07 — Eventos, evidências e relatórios

- F07-AC01 — Evento só é durável após sequência e confirmação no armazenamento canônico.
- F07-AC02 — O envelope possui versão, sessão, revisão, agente, work item,
  correlação, sequência, timestamp e payload redigido.
- F07-AC03 — Campos desconhecidos são preservados e versões antigas têm projeções compatíveis.
- F07-AC04 — Logs extensos ficam em artefatos com digest; eventos guardam referências.
- F07-AC05 — Relatórios cobrem objetivo, revisões, work items, agentes, gates,
  evidências, memória, custos e pendências.
- F07-AC06 — Custos estimados são distintos de cobranças confirmadas.
- F07-AC07 — Sessão exportada inclui manifesto, eventos redigidos, artefatos,
  evidências e digests, nunca segredos.
- F07-AC08 — Resumo narrativo é opcional e não substitui a projeção determinística.

## Requisitos não funcionais

- Falhar fechado diante de schema incompatível, corrupção ou autorização ausente.
- Redigir tokens, senhas, chaves e material privado antes da persistência.
- Usar proteção do usuário do Windows para referências de credenciais.
- Migrar o banco com versão, preflight e caminho de recuperação.
- Manter eventos históricos imutáveis.
- Preservar funcionamento local e ausência de telemetria no MVP.
- Manter núcleo Python portátil, apesar da validação inicial no Windows.

## Métrica de sucesso do MVP

O SilvIA implementa uma feature real no próprio repositório, é interrompido e
retomado, preserva objetivo e evidências, produz relatório reproduzível e não
atravessa nenhuma autorização. Uma sessão exportada mantém integridade
verificável por manifesto e digests.

## Ondas

1. F01 e F02: sessões e autoridade.
2. F03 e F04: skills e execução multiagente.
3. F05: memória com proveniência.
4. F06 e F07: TUI, eventos, evidências e relatórios.
5. F08 a F11: roadmap, cada feature sujeita a aprovação e specs próprias.
