# Harness contract

The controller implements the repository's SDD boundaries as deterministic
gates. Model output is input to a gate, never the gate itself.

```text
objective + source-of-truth context
        ↓
orchestrator plan (validated JSON and disjoint ownership)
        ↓
parallel coder sub-agents
        ↓
parallel read-only reviewers
        ↓
configured verification commands
        ↓
PR draft
        ↓  only with --open-pr and --head-branch
GitHub pull request
```

The controller preserves these authorizations as separate actions:

- Editing files is performed only by a coder within its assigned paths.
- Reviewers are read-only and must return `pass`.
- Verification is pending, not successful, when no command is configured.
- Commit and push are never performed by this package.
- PR creation requires the explicit `--open-pr` flag and a head branch.
- Migration, deployment, merge, and operational effects remain outside the workflow.

The orchestrator must return `work_items` with `id`, `purpose`,
`owned_paths`, `dependencies`, `verification`, `context_class`, and `model`. The controller
rejects duplicate IDs, cycles, unknown dependencies, overlapping ownership,
and handler models outside Qwen3.8-Flash, GLM 5.3 Flash, and DeepSeek-V4-Flash. DeepSeek is valid only for work items classified as large context.
