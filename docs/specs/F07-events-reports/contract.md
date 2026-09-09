# F07 — Contrato de eventos, evidências e relatórios

**Contrato:** F07-C1 r1 | **Estado:** draft
**PRD:** ../../product/PRD.md r1, F07
**Spec:** spec.md | **Plano:** plan.md

## Ownership

F07 é dono do envelope EventV1, ArtifactRef, EvidenceRecord, SessionExport e
projeções de relatório. F01 persiste eventos na mesma transação da mutação;
todos os demais módulos produzem payloads tipados.

## EventV1

| Campo | Regra |
| --- | --- |
| schema_version | inteiro 1 |
| event_id | UUID único |
| sequence | inteiro crescente por sessão, sem reutilização |
| timestamp | UTC ISO-8601 |
| project_id, session_id | UUIDs de F01 |
| objective_revision | inteiro positivo |
| correlation_id | agrupa uma operação |
| causation_id | event_id causador ou null |
| actor | controller, user, agent ou tool com ID |
| kind | nome versionado dentro dos grupos canônicos |
| payload | objeto JSON redigido e validado por kind |
| artifact_refs | lista de digest, media type, tamanho e localização lógica |
| redaction | regras/contagens aplicadas, sem conteúdo removido |

Grupos v1: session, objective, artifact, gate, authorization, skill, agent,
work_item, tool, evidence, memory, report e budget.

## Interface

| Operação | Entrada | Resultado |
| --- | --- | --- |
| append | EventDraft dentro de transação | EventV1 durável |
| read | session_id + cursor + limite | EventPage |
| snapshot | session_id + cursor opcional | SessionProjection |
| store_artifact | bytes redigidos + media type | ArtifactRef |
| build_report | sessão + tipo + versão | ArtifactRef |
| export_session | sessão + autorização | ExportManifest |
| verify_import | pacote não confiável | ImportAssessment sem mutação |

## Garantias

- Mutação só é confirmada com evento durável.
- JSONL, TUI, Markdown e JSON são projeções reconstruíveis.
- Eventos históricos não são editados.
- Campos desconhecidos são preservados por leitores compatíveis.
- Payload grande ou binário vira artefato com SHA-256.
- Export nunca inclui segredo nem caminho local confiado como instrução.

## Compatibilidade

Novo campo opcional é compatível. Remoção, nova semântica, mudança de ordering ou
campo obrigatório exige nova versão e projector/migration. Todos F01–F06 são
consumidores e precisam de testes de contrato.

