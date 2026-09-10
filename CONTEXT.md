# Contexto de domínio — SilvIA

**Estado:** approved
**Revisão:** r1

SilvIA combina o sobrenome Silva com Inteligência Artificial. É um runtime
local-first e governado para desenvolvimento de software com agentes, skills,
memória e evidências. Não é um assistente geral nem substitui Codex, Claude Code
ou outros ambientes: esses ambientes são superfícies ou adapters.

## Vocabulário

| Termo | Definição | Relações e invariantes |
| --- | --- | --- |
| Projeto | Identidade lógica estável de um repositório | Não depende do caminho do checkout; pode reunir sessões e worktrees |
| Sessão | Registro durável de um objetivo em um projeto | Tem uma revisão vigente e histórico append-only |
| Objetivo | Resultado solicitado, critérios e restrições | Somente o usuário pode aprovar ou ampliar |
| Revisão do objetivo | Versão imutável do objetivo | Nova revisão não herda evidências ou aprovações afetadas |
| Work item | Trabalho limitado derivado do plano aprovado | Declara dependências, ownership, verificação e condição de parada |
| Agente | Executor identificado por papel, modelo e provider | Atua somente no work item e nas capacidades autorizadas |
| Apresentação do agente | Evento estruturado de identidade e responsabilidade | Informa ID, papel, modelo, objetivo, ownership, capacidades e proibições |
| Skill | Instruções e recursos carregados explicitamente | Orienta agentes, mas não altera objetivo, gates ou autorizações |
| Skill working-copy | Skill lida de checkout com alterações locais | Pode ser usada com origem e digest explícitos; não equivale a release |
| Sandbox de capability | Ambiente governado que contém a execução de um script declarado por uma skill | Sem adapter compatível, a capability permanece não executável |
| Memória | Fato, decisão, preferência ou aprendizado reutilizável | Possui proveniência e escopo; nunca concede autorização |
| Candidato de memória | Conteúdo ainda não promovido a memória | Inferência de agente permanece proposta até validação |
| Contexto | Pacote reproduzível entregue a um agente | Registra fontes, skills e memórias incluídas |
| Evidência | Registro verificável de uma execução ou revisão | Refere-se à versão, tentativa, comando e ambiente avaliados |
| Gate | Avaliação determinística anterior a uma transição | Retorna allow, deny, require-approval ou require-evidence |
| Autorização | Consentimento explícito para ação e escopo definidos | Registra revisão do objetivo, responsável, validade e expiração |
| Evento | Fato operacional imutável, sequenciado e versionado | Só é durável após confirmação do armazenamento canônico |
| Artefato | Conteúdo externo ao event log, identificado por digest | Guarda logs extensos, relatórios ou documentos |
| Relatório | Projeção reproduzível de eventos, artefatos e evidências | Não modifica o estado canônico |
| Adapter | Implementação conectada a um seam real | Pode integrar provider, armazenamento, TUI ou outro harness |
| Perfil de provider | Configuração local de endpoint, política e credencial referenciada | Sessões nunca armazenam o segredo |

## Módulos e interfaces

| Módulo | Interface pretendida | Responsabilidade escondida |
| --- | --- | --- |
| SessionRuntime | new, resume, revise, inspect | Persistência, revisões, reconciliação e invariantes da sessão |
| HarnessEngine | evaluate(action) | Gates, capacidades, autorizações e transições fail-closed |
| SkillRegistry | resolve(selection) | Descoberta, normalização, validação, identidade e contexto de skills |
| AgentRuntime | execute(work_item) | Adapters de modelos, concorrência, tentativas e resultados |
| MemoryStore | remember, recall, forget | Proveniência, escopo, validade, conflitos, retenção e redaction |
| ProjectionEngine | render(view) | CLI, TUI, JSONL, Markdown, JSON e futuras projeções |

As interfaces são a superfície de teste. A implementação atual com LangChain é
interna ao AgentRuntime. Um seam ganha adapter somente quando existe variação
real, como armazenamento in-process e SQLite ou projeções TUI e JSONL.

## Estados da sessão

created, planning, running, waiting-for-action, blocked, completed, cancelled e
archived.

- Retomar restaura e reconcilia; não recomeça ações automaticamente.
- Cancelar solicita parada cooperativa, impede novos work items e preserva
  resultados incertos para reconciliação.
- O harness verifica os critérios; o usuário confirma a conclusão.
- Arquivar preserva o histórico e não equivale a excluir.

## Precedência

Quando fontes divergirem, usar: autorização atual e objetivo vigente, artefatos
canônicos aprovados, decisões registradas, evidência atual e, por último,
memória recuperada. Conflitos sem precedência determinística são apresentados
ao usuário, nunca resolvidos silenciosamente.

Implementação pertence às specs; alternativas e consequências pertencem a ADRs.
