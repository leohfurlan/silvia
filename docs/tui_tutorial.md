# Tutorial — SilvIA

Guia completo de uso: da instalação ao desenvolvimento governado com agentes.

---

## Índice

1. [Iniciando a TUI](#1-iniciando-a-tui)
2. [Layout da tela](#2-layout-da-tela)
3. [Fluxo típico: do zero ao agente rodando](#3-fluxo-típico-do-zero-ao-agente-rodando)
4. [As abas](#4-as-abas)
5. [Atalhos de teclado](#5-atalhos-de-teclado)
6. [Menu de contexto (botão direito)](#6-menu-de-contexto-botão-direito)
7. [Atualização automática](#7-atualização-automática)
8. [Dicas](#8-dicas)
9. [Montando o harness em um projeto novo](#9-montando-o-harness-em-um-projeto-novo)
10. [Do PRD.md ao desenvolvimento completo](#10-do-prdmd-ao-desenvolvimento-completo)

---

## 1. Iniciando a TUI

```bash
# Abre a TUI na sessão mais recente do projeto atual
silvia tui

# Abre diretamente em uma sessão específica
silvia tui <session-id>

# Abre apontando para um projeto em outro diretório
silvia --project C:\Projetos\horebio tui

# Escolhe o tema (padrão: hermes)
silvia tui --theme dark
```

> A TUI exige terminal interativo (`tty`). Não funciona em pipe ou CI —
> use `silvia status --json` para scripting.

---

## 2. Layout da tela

```
┌─────────────────────────────────────────────────────────┐
│ Header — SilvIA                                         │
├─────────────────────────────────────────────────────────┤
│ [Select: Open a session ▼]                              │  ← seletor de sessão
├─────────────────────────────────────────────────────────┤
│ Nome | estado | revision N | cursor N                   │  ← identidade
│ Texto do objetivo                                       │
├──────────────────────────┬──────────────────────────────┤
│ New objective            │ Observable criterion  [Create]│  ← criar sessão
├──────────────────────────┴──────────────────────────────┤
│ [Resume] [Run] [Pause] [Cancel] [Complete]              │  ← ciclo de vida
├─────────────────────────────────────────────────────────┤
│ Mensagem de status                                      │  ← feedback
├─────────────────────────────────────────────────────────┤
│ State | Approvals | Events | Evidence | Memory | Report │  ← abas
│                                                         │
│  conteúdo da aba (JSON com indent=4 ou texto)           │
│                                                         │
│  [controles da aba, ex: Approve / Deny]                 │
├─────────────────────────────────────────────────────────┤
│ Footer — atalhos                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Fluxo típico: do zero ao agente rodando

### 3.1 Criar uma sessão

Preencha os dois campos no topo e clique **Create**:

| Campo | O que escrever |
|---|---|
| **New objective** | Descrição completa do objetivo (ex: `Implementar endpoint GET /health`) |
| **Observable criterion** | Critério mensurável (ex: `curl /health retorna 200 em < 100ms`) |

A sessão criada aparece automaticamente no seletor e no painel de identidade.

### 3.2 Selecionar uma sessão existente

Use o **Select** no topo para escolher qualquer sessão. O painel atualiza com
nome, estado, revisão e cursor de eventos.

### 3.3 Botões de ciclo de vida

| Botão | Quando usar | O que faz |
|---|---|---|
| **Resume** | Sessão interrompida inesperadamente | Calcula reconciliação de efeito externo incerto e mostra o resultado em `#message`. **Não executa** — só prepara. Leia e confirme com **Run**. |
| **Run** | Após Resume, ou para iniciar | Dispara o loop do agente em background. A tela atualiza a cada segundo. |
| **Pause** | Durante execução | Solicita parada limpa. O agente termina a etapa atual e para. |
| **Cancel** | Abandono definitivo | Para o agente e move a sessão para `cancelled`. Irreversível. |
| **Complete** | Ao final | Avalia os gate criteria. Só aceita se todos estiverem satisfeitos. Move para `completed`. |

> **Atalho:** `Ctrl+P` pausa sem clicar em **Pause**.

---

## 4. As abas

### 🗂 State

Snapshot do estado interno atual da sessão em JSON com `indent=4`:

```json
{
    "work-item": { ... },
    "agent":     { ... },
    "attempt":   { ... },
    "effect":    { ... }
}
```

Use para ver o que o agente está fazendo agora, qual work-item está ativo e
quantas tentativas já foram feitas.

---

### ✅ Approvals

Lista todos os pedidos de autorização — pendentes, aprovados ou negados.
Cada item tem um campo `"id"` — esse é o ID de aprovação.

**Para aprovar ou negar:**

1. Localize o item com `"status": "pending"`.
2. Copie o valor de `"id"` (selecione e clique com o botão direito → **Copy**).
3. Cole no campo **"Exact approval ID displayed above"**.
4. Clique **Approve** ou **Deny**.

> A aprovação expira em 15 min por padrão (escopo `invocation`).
> Para escopo mais amplo, use a CLI:
> ```bash
> silvia approve <id> --scope work-item --seconds 3600
> ```

---

### 📋 Events

Últimos 100 eventos da sessão em ordem cronológica:

```
42 session.created       {"name": "...", ...}
43 gate.evaluated        {"outcome": "require-approval", ...}
44 authorization.granted {"scope": "invocation", ...}
```

Botão **Copy all events** copia o log completo para o clipboard.

---

### 🔍 Evidence

Artefatos de evidência registrados (digests, resultados de gates, etc.).

Para inspecionar um artefato:
1. Copie o digest do painel de evidências.
2. Cole em **"Artifact digest to view"**.
3. Clique **View artifact** — o conteúdo aparece abaixo.

---

### 🧠 Memory

Memória contextual da sessão (fatos, decisões, preferências, aprendizados).

**Adicionar memória manualmente:**
1. Digite no campo **"Memory to remember explicitly"**.
2. Clique **Remember** — a memória é promovida imediatamente.

> Para memórias permanentes:
> ```bash
> silvia memory remember "..." --scope project --type decision
> ```

---

### 📄 Report

Relatório Markdown da sessão em tempo real. Útil para revisar antes de
acionar **Complete**.

---

## 5. Atalhos de teclado

| Tecla | Ação |
|---|---|
| `q` | Sair (pausa o agente se estiver rodando) |
| `r` | Forçar refresh manual |
| `t` | Alternar tema (Hermes ↔ Dark) |
| `Ctrl+P` | Pausar execução |
| `Tab` / `Shift+Tab` | Navegar entre campos e botões |
| `Enter` | Confirmar botão focado |

---

## 6. Menu de contexto (botão direito)

Clique com o **botão direito** sobre qualquer `TextArea` ou campo `Input`:

| Opção | Efeito |
|---|---|
| 📋 **Copy** | Copia o texto selecionado (TextArea) ou o valor do campo (Input) |
| 📌 **Paste** | Cola o último texto copiado dentro da TUI no campo editável |

> Em terminais, a TUI não pode ler o clipboard do sistema arbitrariamente. Para conteúdo externo, use o atalho de colagem do seu terminal; o menu **Paste** usa o clipboard local atualizado por **Copy**.

> Clicar fora do menu fecha-o sem ação.

---

## 7. Atualização automática

A TUI atualiza a cada **1 segundo** enquanto está aberta. Não é necessário
pressionar `r` durante execução — State e Approvals refletem o estado em
tempo real.

---

## 8. Dicas

- **Sessão travada?** Abra a aba `Events`. Se o último evento for
  `gate.evaluated` com `"outcome": "require-approval"`, vá para `Approvals`
  e aprove.
- **Agente não avança?** Verifique `State → attempt`. Contador alto indica
  loop de erros — use **Pause** e inspecione os eventos.
- **CLI em paralelo?** `silvia status` e `silvia approvals` funcionam
  enquanto a TUI está aberta (SQLite suporta leituras concorrentes).
- **Encerramento seguro:** `q` pausa o agente antes de fechar, garantindo
  que nenhum efeito fique pendente sem reconciliação.

---

## 9. Montando o harness em um projeto novo

O harness é um conjunto de arquivos versionados que governa o desenvolvimento.
A SilvIA não tem um comando `harness init` — ele é criado uma vez via agente
com a skill `harness-atos-sdd`.

### 9.1 Pedir ao agente para criar

No Antigravity (ou Claude Code), dentro do diretório do projeto:

```
"Montar harness padrão (perfil standard) para este projeto.
 O PRD está em prd.md. O stack é [Python/Node/etc.].
 Os comandos de teste são [pytest / npm test / etc.]."
```

### 9.2 Estrutura gerada

```
meu-projeto/
├── DEVELOPMENT.md              ← fonte canônica para todos os agentes
├── AGENTS.md                   ← aponta para DEVELOPMENT.md
├── CONTEXT.md                  ← vocabulário do domínio
├── .harness/
│   ├── project.yaml            ← nome, perfil, fontes
│   ├── gates.json              ← grupos fast / full / architecture
│   └── scripts/
│       └── run_gates.py        ← runner com evidência local
└── docs/
    ├── product/PRD.md
    ├── agents/
    │   └── authorization.md
    └── specs/
        └── README.md
```

### 9.3 Registrar o projeto na SilvIA

```bash
# Uma única vez por projeto
silvia --project C:\Projetos\meu-projeto init
```

### 9.4 Verificar os gates

```bash
python .harness/scripts/run_gates.py --group fast        # lista
python .harness/scripts/run_gates.py --group fast --run  # executa
```

---

## 10. Do PRD.md ao desenvolvimento completo

Fluxo completo partindo apenas de um `prd.md` existente.

### Visão geral

```
prd.md
  │
  ▼  (agente com harness-atos-sdd)
DEVELOPMENT.md + CONTEXT.md + gates.json
  │
  ▼  (agente, por feature)
docs/specs/Fxx/contract.md + spec.md + plan.md
  │
  ▼  (silvia new)
sessão com objetivo e critérios mensuráveis
  │
  ▼  (silvia tui → Run)
agente implementa → gates → evidência
  │
  ▼  (silvia tui → Complete)
sessão completed + evidência registrada
  │
  ▼  (silvia approve + git autorizado)
commit / PR
```

---

### Fase 1 — Montar o harness (uma vez, antes de tudo)

Peça ao agente:

```
"Montar harness padrão (perfil standard) para o projeto horebio.
 O PRD está em prd.md. O stack é [Python/Node/etc.].
 Os comandos de teste são [pytest / npm test / etc.]."
```

O agente usa a skill `harness-atos-sdd`, cria toda a estrutura acima e
**não faz commit** — você revisa antes de versionar.

---

### Fase 2 — Por feature: contrato e spec (sem código ainda)

Para cada feature do PRD, peça ao agente:

```
"Ler prd.md e criar contract.md e spec.md
 para a feature F01 — [nome da feature]."
```

Resultado: `docs/specs/F01-nome/contract.md` + `spec.md`

O **contrato** define a interface pública (operações, entradas, saídas, erros).
A **spec** define comportamento, invariantes e decisões técnicas.
Nenhum código é escrito ainda.

---

### Fase 3 — Criar a sessão SilvIA para implementar

```bash
silvia --project C:\Projetos\horebio new \
  "Implementar F01 — [nome] conforme docs/specs/F01-nome/spec.md" \
  --criterion "Gates do grupo fast passam" \
  --criterion "Contrato F01-C1 coberto por testes de interface pública"
```

---

### Fase 4 — Abrir a TUI e rodar

```bash
silvia --project C:\Projetos\horebio tui
```

Na TUI:
1. Selecione a sessão criada no seletor.
2. Clique **Run**.
3. Acompanhe a aba **State** em tempo real.
4. Quando aparecer um item na aba **Approvals**, copie o ID e aprove ou negue.
5. Ao fim, verifique a aba **Report**.

---

### Fase 5 — Verificar gates e completar

```bash
# Fora da TUI, ou em outro terminal
python .harness/scripts/run_gates.py --group fast --run
python .harness/scripts/run_gates.py --group full --run
```

Se tudo passar, volte à TUI e clique **Complete**.
A SilvIA avalia os critérios da sessão — se satisfeitos, move para `completed`.

---

### Fase 6 — Autorizar commit e PR

A SilvIA não faz push automaticamente. Após `completed`, o agente vai
solicitar aprovação para `git.commit` e `git.push` — você autoriza via
**Approvals** na TUI ou pela CLI:

```bash
silvia approve <id> --scope invocation
```

---

### Ordem recomendada entre features

Respeite as dependências declaradas no `docs/specs/README.md`. Exemplo
para um projeto típico:

| Onda | Features | Razão |
|---|---|---|
| 1 | Domínio + persistência | Base sem dependências externas |
| 2 | Regras de negócio + autorizações | Consomem a base |
| 3 | Integrações e APIs | Dependem das regras |
| 4 | CLI / UI / relatórios | Consomem tudo acima |

Não inicie uma feature sem ter o contrato da sua dependência estabilizado.
