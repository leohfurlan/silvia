---
name: astra
description: Use GPT-6 Astra only as the orchestrator for a task, then execute implementation with GPT-5.6 Luna or GLM 5.3 Flash handlers. Use when the user invokes $astra or asks Astra to orchestrate Codex agents.
---

# Astra orchestrator

GPT-6 Astra supplies orchestration decisions only. Codex remains the runtime
that spawns handlers, owns files, runs tools, verifies the result, and reports
to the user.

## Invocation

Treat everything after $astra as the objective. GPT-6 Astra always owns
orchestration. Implementation handlers are restricted to GPT-5.6 Luna and GLM
5.3 Flash:

- $astra build the feature
- $astra debug this; handler: gpt-5.6-luna
- $astra refactor this; handler: glm-5.3-flash

Model names are requests, not guesses. Before dispatch, inspect the current
spawn-agent tool description and custom handler roles. Use only models or roles
that are currently callable. If a requested model is unavailable, report that
fact and use the other allowed handler only when the substitution is low-risk;
otherwise report the blocker.

The handlers have distinct responsibilities:

- GPT-5.6 Luna: normal implementation, review, and bounded code changes.
- GLM 5.3 Flash: loops, repeated iteration, and high-throughput mechanical work.

The GLM route is the OpenAI-compatible B.AI endpoint from the supplied reference
script: base URL https://api.b.ai/v1, model glm-5.3-flash, and credential
environment variable APIKEY_B_AI. The route must be configured and exposed as a
callable handler by the runtime. Never put API keys in an orchestration packet.

When the user did not explicitly choose an allowed route, use this classifier:

- loop construction, repeated iteration, or high-throughput mechanical work:
  use a callable handler pinned to glm-5.3-flash;
- ordinary implementation, review, or bounded code changes:
  use a callable handler pinned to gpt-5.6-luna;
- research, planning, and verification support: choose by normal task fit,
  while all code-writing nodes still use one of the two allowed handlers.

Prefer an exposed agent type that pins both model and provider. Never infer
callability from a config file or send a raw model override across providers.
Classify by the callable model pin, not the handler display name. Do not show
the full model catalog unless asked.

## Workflow

1. Read the objective and relevant local instructions. Inspect enough of the
   workspace to give Astra facts rather than assumptions.
2. Build a compact orchestration packet containing the objective, acceptance
   criteria, workspace context, constraints, protected files, evidence already
   gathered, callable handler menu, concurrency limit, and user preferences.
3. Send the packet to scripts/ask_astra.sh. The helper uses APIKEY_B_AI (or
   BAI_API_KEY) and calls the B.AI Responses API with model gpt-6-astra. Do not read, copy,
   print, or modify credentials.
4. Require a bounded task graph with role, model or handler type, owned files
   or responsibility, dependencies, expected output, verification, and a stop
   condition for every node. Reject any implementation node assigned to a model
   other than GPT-5.6 Luna or GLM 5.3 Flash.
5. Validate the graph against the actual task and current tools. Codex has final
   responsibility for safety and scope. Do not execute invented models, unsafe
   actions, or work outside the user's request.
6. Spawn independent ready nodes in parallel, up to the live collaboration
   limit. Tell every code-writing handler its ownership and that other agents
   share the workspace, so it must preserve and accommodate their edits.
7. Collect results, inspect changed files, and run proportionate verification.
   For complex work, send a concise results packet back through the helper for
   the next graph or final adjudication. Cap this at three Astra calls unless
   the user asks to continue.
8. Finish only when acceptance criteria and verification pass. Report selected
   models, material changes, and concrete proof.

Whenever the helper returns Astra's orchestration output, display it verbatim
under this exact heading:

GPT-6 Astra speaks:

Do not relabel ordinary Codex or handler output as Astra speech.

## Boundaries

- Astra plans and adjudicates; it does not silently replace Codex handlers.
- Exchange decisions, evidence, task packets, diffs, test results, and blockers,
  not hidden reasoning.
- Orchestration does not expand authorization. Publishing, deployment,
  destructive operations, spending, and external messages retain their normal
  approval boundaries.
- If delegation adds no value, use one handler or execute directly after the
  Astra plan.

## Calling Astra

Pass the packet as standard input:

    printf '%s' "$PACKET" | "$HOME/.codex/skills/astra/scripts/ask_astra.sh"

Do not place secrets in the packet. The helper uses the local B.AI
authentication environment and creates no persistent session.
