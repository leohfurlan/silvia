# F05 — Memória com proveniência

**Estado:** draft | **PRD:** ../../product/PRD.md r1, F05
**Contrato:** contract.md | **Plano:** plan.md

## Escopo e evidência

Não existe memória no runtime atual. Implementar memória textual local sobre
SQLite FTS5; embeddings ficam fora do MVP. Candidatos vêm do usuário, decisões
aprovadas, artefatos canônicos e evidências. Inferências permanecem propostas.

## Requisitos

- BR01: toda entrada tem tipo, origem, sessão, escopo, timestamp, validade,
  confiança e referência de evidência quando aplicável.
- BR02: promoção de escopo exige ação explícita.
- BR03: recall filtra projeto/escopo, validade, tipo e orçamento antes do texto.
- BR04: ranking usa escopo, precedência da fonte, validade e correspondência lexical.
- BR05: contexto enviado ao agente registra itens e versões exatos.
- BR06: conflito não resolvido é retornado e não selecionado silenciosamente.
- BR07: logs volumosos usam retenção padrão de 90 dias, configurável.
- BR08: memória promovida não expira automaticamente, mas pode ter validade.
- BR09: exportar e esquecer exigem F02 e produzem recibos/evidência.

## Edge cases

| Caso | Situação | Resultado |
| --- | --- | --- |
| F05-E01 conteúdo vazio | propose vazio | invalid-memory |
| F05-E02 segredo | token detectado | conteúdo não persistido |
| F05-E03 projeto diferente | recall sem seleção explícita | item excluído |
| F05-E04 validade vencida | memória expirada | excluída com motivo |
| F05-E05 decisões opostas | mesma chave sem supersessão | ConflictSet |
| F05-E06 orçamento zero | recall | lista vazia e truncamento registrado |
| F05-E07 FTS5 ausente | inicialização | diagnóstico; fallback simples só se explícito |
| F05-E08 exclusão repetida | memory_id já removido | recibo idempotente sem conteúdo |

## Arquitetura

MemoryStore encapsula tabelas e FTS5. ContextBuilder usa RecallResult e
precedência canônica; não expõe acesso geral ao banco para modelos.

~~~mermaid
sequenceDiagram
  participant S as Fonte
  participant M as MemoryStore
  participant U as Operador
  participant C as ContextBuilder
  S->>M: propose com proveniência
  M-->>U: candidato
  U->>M: promote
  C->>M: recall(query, budget)
  M-->>C: itens + conflitos + exclusões
  C-->>C: registrar contexto exato
~~~

## Cobertura e gates

BR01–BR09 cobrem AC01–AC08. Testes públicos cobrem E01–E08, precedência,
redaction, retenção e isolamento entre projetos. SQLite real deve participar
dos testes de integração; adapter fake não prova FTS5. Gates rápido/completo
passaram nesta geração: 7 testes no rápido; checks do repo e 7 testes no
completo via Git Bash, com warning awk não fatal. Propor teste de disponibilidade
FTS5 no ambiente empacotado.

## Riscos

Confiança não pode ser score produzido livremente por modelo; a implementação
deve derivá-la de classe de fonte e validações registradas. Direito de exclusão
precisa coexistir com eventos sem reter o conteúdo apagado.
