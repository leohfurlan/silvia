# B.AI LangChain workflow

This package implements the SDD-gated workflow used by the repository:

```text
orchestrator (GLM-5.3-Flash)
        │
        ├── coder sub-agents (Qwen3.8-Flash/GLM-5.3-Flash, or DeepSeek-V4-Flash for large context, parallel by disjoint ownership)
        │
        ├── reviewer sub-agents (GLM-5.3-Flash, parallel, read-only)
        │
        └── PR agent (Qwen3.8-Flash) ──> optional `gh pr create`
```

All model calls use the OpenAI-compatible B.AI endpoint. No OpenAI API key is
used. Set `APIKEY_B_AI` (or `BAI_API_KEY`) in the process environment. When `--repo` points to a project, the controller also reads that project's uncommitted `.env.dev` file if the process variable is absent; the value is never sent as task context.

The controller owns the gates. Agents cannot commit, push, migrate, deploy, or
open a PR implicitly. Verification commands are supplied explicitly with
`--check`; omitting them leaves verification pending and prevents the workflow
from claiming that tests passed. `--open-pr` is a separate authorization and
also requires `--head-branch`.

## Install

```bash
python -m pip install -e .
```

## Run

```bash
python -m workflow.cli \
  "Implement the selected specification" \
  --repo . \
  --check "bash tests/test_skill.sh" \
  --max-parallel 3
```

To authorize PR creation after the implementation, review, and checks pass:

```bash
python -m workflow.cli \
  "Implement the selected specification" \
  --repo . \
  --check "bash tests/test_skill.sh" \
  --head-branch codex/my-change \
  --open-pr
```

The orchestrator must return JSON with disjoint `owned_paths`. The controller
rejects overlapping ownership and models outside the configured implementation
handler. Reviewers return `pass`, `changes_requested`, or `blocked`; the coder
may receive review feedback for one bounded correction round (configurable).


## Acompanhamento em tempo real

The CLI prints live progress to stderr by default. Model response chunks,
tool calls, agent completion, review rounds, verification, and PR preparation
are visible while the run is executing. The final JSON remains on stdout, so it
can be redirected or parsed independently.

```bash
python -m workflow.cli \
  "Implement the selected specification" \
  --repo /path/to/nexor_hub \
  --check "uv run ruff check ." \
  --check "uv run pytest tests/ -v" \
  --events-file .workflow/runs/latest.jsonl
```

Use `--no-live` only for automation that needs silent execution. The runtime
does not start tmux; parallelism is managed by asyncio. If multiple panes are
wanted, run the command from tmux or Windows Terminal, while the event stream
continues to work normally.

## Timestamps and returns

Live output is written to stderr with local timestamps in millisecond precision
for lifecycle events, stages, tool calls, tool returns, review rounds,
verification, and PR preparation. Model text is streamed under the agent label.
Tool returns are shortened and sensitive-looking values are masked.

Every event, including model chunks, receives an ISO-8601 UTC timestamp in the
optional JSONL file:

```bash
--events-file C:/Temp/nexor-workflow.jsonl
```
