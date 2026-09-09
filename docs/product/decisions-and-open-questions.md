# Decisões e pendências — SilvIA

**Revisão:** r1
**Estado:** approved

Este documento separa decisões confirmadas, propostas técnicas ainda não
aprovadas e questões que pertencem às specs. Implementação acidental não promove
uma proposta.

## Decisões aprovadas

| ID | Tema | Decisão | Fonte |
| --- | --- | --- | --- |
| D001 | Nome | SilvIA combina Silva, sobrenome do criador, com Inteligência Artificial | entrevista de produto |
| D002 | Identificadores | Marca SilvIA; comando e pacote silvia | entrevista de produto |
| D003 | Comunicação | Interface técnica e neutra | entrevista de produto |
| D004 | Posicionamento | Runtime governado para desenvolvimento, não assistente geral nem substituto de harnesses | entrevista de produto |
| D005 | Usuário inicial | Operador individual local, evoluindo para outros desenvolvedores | entrevista de produto |
| D006 | Processo | Harness Atos SDD standard e fluxo PRD → contrato → spec → plano → implementação → evidência → revisão → entrega | entrevista de produto |
| D007 | Aprovação | Somente o usuário aprova objetivo e artefatos ou amplia escopo | entrevista de produto |
| D008 | Conclusão | Harness verifica critérios; usuário confirma conclusão | entrevista de produto |
| D009 | Arquitetura | Evoluir incrementalmente o runtime atual por módulos profundos | entrevista de produto |
| D010 | LangChain | Implementação interna inicial do AgentRuntime, não parte de sua interface | entrevista de produto |
| D011 | Astra | Adapter de orquestração padrão, substituível pela interface | entrevista de produto |
| D012 | Compatibilidade | bai-workflow e $astra serão aliases depreciados por período documentado | entrevista de produto |
| D013 | Sessão | Um objetivo vigente e um projeto; revisões são imutáveis | entrevista de produto |
| D014 | Retomada | Restaurar e reconciliar; exigir confirmação antes de continuar | entrevista de produto |
| D015 | Isolamento | Worktree Git por padrão; checkout direto por escolha explícita | entrevista de produto |
| D016 | Estado anterior | Registrar baseline e preservar alterações alheias | entrevista de produto |
| D017 | Concorrência | Sessões concorrentes exigem worktrees ou ownership mutável disjunto | entrevista de produto |
| D018 | Autorizações | Escopo por chamada, work item ou sessão; ações críticas são separadas e de uso único por padrão | entrevista de produto |
| D019 | Falhas | Tentativas limitadas, backoff e reconciliação antes de repetir resultado incerto | entrevista de produto |
| D020 | Orçamentos | Limitar concorrência, chamadas, custo, tokens, duração, tentativas e contexto | entrevista de produto |
| D021 | Modelos pagos | Exigem orçamento pré-autorizado ou aprovação específica | entrevista de produto |
| D022 | Revisão | Proporcional ao risco e obrigatória para áreas críticas; duas correções como padrão | entrevista de produto |
| D023 | Skills | Fontes locais registradas; carregamento não autoriza execução de scripts | entrevista e inspeção do catálogo |
| D024 | Identidade de skill | Origem, commit, caminho relativo e digest; tag é opcional | entrevista e inspeção do catálogo |
| D025 | Working copy | Permitida com identificação explícita e confirmação adicional conforme política | entrevista de produto |
| D026 | Compatibilidade de skill | Núcleo normalizado e adapters que preservam campos desconhecidos | entrevista e inspeção do catálogo |
| D027 | Validação de skill | Resultado por harness, além da validação normalizada | entrevista e inspeção do catálogo |
| D028 | Scripts de skill | Manifesto sidecar de capacidades e deny-by-default | entrevista e inspeção do catálogo |
| D029 | Gestão de skills | Instalação, atualização e promoção ficam fora do MVP | entrevista de produto |
| D030 | Memória | Escopos sessão, projeto e usuário; sem promoção automática | entrevista de produto |
| D031 | Formação de memória | Fontes aprovadas geram candidatos; inferências continuam propostas | entrevista de produto |
| D032 | Recuperação | ContextBuilder determinístico registra o conteúdo incluído | entrevista de produto |
| D033 | Conflitos | Usar precedência canônica e nunca resolver conflito silenciosamente | entrevista de produto |
| D034 | Retenção | Logs volumosos têm prazo configurável; memórias promovidas não expiram automaticamente | entrevista de produto |
| D035 | Segurança | Redaction antes da persistência; referências de credenciais usam proteção local | entrevista de produto |
| D036 | Telemetria | Nenhuma telemetria remota no MVP | entrevista de produto |
| D037 | Eventos | Schema versionado, histórico imutável e confirmação antes de considerar durável | entrevista de produto |
| D038 | Payloads | Eventos guardam conteúdo limitado e referência a artefatos extensos com digest | entrevista de produto |
| D039 | Agentes | Apresentação estruturada; frase amigável é apenas projeção opcional | entrevista de produto |
| D040 | TUI | Governa sessões e abre artefatos; não substitui o editor | entrevista de produto |
| D041 | Relatórios | Projeções determinísticas de objetivo, agentes, gates, evidência, memória, custos e pendências | entrevista de produto |
| D042 | Exportação | Pacote redigido com manifesto, artefatos, evidências e digests | entrevista de produto |
| D043 | Operação offline | Consultas e gates locais funcionam sem provider; execução dependente fica bloqueada | entrevista de produto |
| D044 | Plataforma | Windows/PowerShell primeiro; núcleo Python portátil | entrevista de produto |
| D045 | Distribuição | pipx no MVP; nenhuma atualização automática | entrevista de produto |
| D046 | Artefatos SDD | Markdown versionável no repositório; banco guarda índices, estados e referências | entrevista de produto |
| D047 | Persistência | Banco global por usuário; artefatos e evidências permanecem no projeto | entrevista de produto |
| D048 | Migrações | Versionadas, com preflight e recuperação proporcional ao risco | entrevista de produto |
| D049 | Licença | MIT | entrevista de produto |
| D050 | Piloto | Implementar uma feature real do próprio SilvIA | entrevista de produto |
| D051 | Roadmap | Web local → Codex nativo → gestão de skills → colaboração/nuvem | entrevista de produto |
| D052 | Governança futura | Roadmap não autoriza implementação; cada feature percorre o fluxo SDD | entrevista de produto |

## Fatos descobertos

| ID | Fato | Evidência |
| --- | --- | --- |
| FCT01 | O runtime atual já executa agentes paralelos, revisões, gates e eventos | workflow/ |
| FCT02 | Existem 27 skills na fonte canônica agent-skills; todas possuem SKILL.md | inspeção read-only de C:/Projetos TI/agent-skills |
| FCT03 | Não há manifesto uniforme de versão, origem ou capacidades executáveis | inspeção read-only de C:/Projetos TI/agent-skills |
| FCT04 | Somente duas skills possuem tags semânticas observadas | inspeção read-only de C:/Projetos TI/agent-skills |
| FCT05 | O validador atual rejeita extensões usadas por skills compatíveis com Claude | inspeção read-only de C:/Projetos TI/agent-skills |
| FCT06 | Scripts de skills incluem operações somente leitura e operações de escrita | inspeção read-only de C:/Projetos TI/agent-skills |
| FCT07 | A distribuição atual de skills usa junctions e promoção explícita | inspeção read-only de C:/Projetos TI/agent-skills |

## Propostas técnicas

| ID | Tema | Proposta | Como decidir |
| --- | --- | --- | --- |
| P001 | Persistência | SQLite como adapter canônico e adapter in-process para testes | spec F01 e testes de contrato |
| P002 | Eventos | Tabela transacional de eventos e projeção JSONL | spec F01/F07 e teste de interrupção |
| P003 | TUI | Textual ou biblioteca equivalente sobre o mesmo fluxo de eventos | protótipo F06, sem regras próprias |
| P004 | Busca de memória | Busca textual primeiro; embeddings somente após métricas de recuperação | spec e piloto F05 |
| P005 | Segredos Windows | Credential Manager ou adapter equivalente | spike de segurança e recuperação |
| P006 | Manifesto de skill | Sidecar SilvIA separado dos manifestos Codex e Claude | contrato F03 |
| P007 | Retenção padrão | Noventa dias para logs volumosos, configurável por projeto | spec F05 e estimativa de volume |

## Pendências para especificação

| ID | Questão | Responsável | Impede |
| --- | --- | --- | --- |
| Q001 | Qual será a duração da depreciação de bai-workflow e $astra? | produto | remoção futura dos aliases |
| Q002 | Quais são os limites padrão de custo, tokens, duração e tentativas? | produto e spec F04 | conclusão da F04 |
| Q003 | Qual schema exato representa capacidades de scripts de skills? | spec F03 | execução de scripts |
| Q004 | Qual caminho local padrão guarda o banco e os artefatos globais? | spec F01 | empacotamento |
| Q005 | Qual mecanismo de migration e recuperação será adotado? | spec F01 | persistência durável |
| Q006 | Qual formato e política validam a identidade lógica de projeto? | spec F01 | clones e worktrees |
| Q007 | Qual biblioteca de TUI satisfaz acessibilidade e Windows? | protótipo F06 | implementação da TUI |
| Q008 | Quais tipos de evento formam a versão 1 do schema? | contrato F07 | integrações e projeções |
| Q009 | Como importar uma sessão sem confiar em instruções ou caminhos do pacote? | spec F07 | importação |
| Q010 | Como mensurar relevância e conflitos na memória textual? | spec F05 | conclusão da F05 |

Nenhuma pendência acima reduz as decisões aprovadas nem autoriza sua
implementação. Cada feature futura precisa de contrato, spec e plano aprovados.
