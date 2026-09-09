"""Async workflow controller with parallel implementation and review gates."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .agents import coder_prompt, invoke_agent, orchestrator_prompt, pr_prompt, reviewer_prompt, tools_for
from .config import WorkflowConfig
from .contracts import PullRequestDraft, ReviewResult, TaskPlan, WorkItem, parse_plan, parse_pr_draft, parse_review
from .observability import NullObserver, Observer, WorkflowEvent
from .tools import run_configured_checks


@dataclass(frozen=True)
class WorkflowResult:
    plan: TaskPlan
    coder_outputs: dict[str, str]
    reviews: dict[str, ReviewResult]
    checks_ok: bool
    check_evidence: tuple[str, ...]
    pr_draft: PullRequestDraft | None = None
    pr_url: str | None = None


def _normal(path: str) -> str:
    return path.replace("\\", "/").strip("/") or "."


def _overlap(left: str, right: str) -> bool:
    left, right = _normal(left), _normal(right)
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _validate_plan(plan: TaskPlan, config: WorkflowConfig) -> None:
    allowed_models = {"gpt-5.6-luna", "glm-5.3-flash"}
    for index, left in enumerate(plan.work_items):
        if left.model not in allowed_models:
            raise ValueError(f"Implementation item {left.id} uses non-handler model {left.model}")
        for right in plan.work_items[index + 1 :]:
            if any(_overlap(a, b) for a in left.owned_paths for b in right.owned_paths):
                raise ValueError(f"Work items {left.id} and {right.id} have overlapping ownership")


def _ready(items: tuple[WorkItem, ...], completed: set[str]) -> tuple[WorkItem, ...]:
    return tuple(item for item in items if item.id not in completed and set(item.dependencies) <= completed)


async def _parallel_coders(
    config: WorkflowConfig, items: tuple[WorkItem, ...], context: str, observer: Observer
) -> dict[str, str]:
    semaphore = asyncio.Semaphore(config.max_parallel)

    async def run(item: WorkItem) -> tuple[str, str]:
        async with semaphore:
            prompt = f"Task:\n{item.purpose}\n\nOwned paths: {', '.join(item.owned_paths)}\n\nContext:\n{context}"
            output = await invoke_agent(
                config,
                model_name=item.model,
                system_prompt=coder_prompt(),
                user_prompt=prompt,
                tools=tools_for(config, item.owned_paths, writable=True),
                observer=observer,
                role="coder",
                task_id=item.id,
            )
            return item.id, output

    results: dict[str, str] = {}
    completed: set[str] = set()
    remaining = items
    while remaining:
        batch = _ready(remaining, completed)
        if not batch:
            raise ValueError("Plan dependencies contain a cycle")
        for item_id, output in await asyncio.gather(*(run(item) for item in batch)):
            results[item_id] = output
            completed.add(item_id)
        remaining = tuple(item for item in remaining if item.id not in completed)
    return results


async def _parallel_reviews(
    config: WorkflowConfig, items: tuple[WorkItem, ...], context: str, observer: Observer
) -> dict[str, ReviewResult]:
    semaphore = asyncio.Semaphore(config.max_parallel)

    async def run(item: WorkItem) -> tuple[str, ReviewResult]:
        async with semaphore:
            output = await invoke_agent(
                config,
                model_name=config.reviewer_model,
                system_prompt=reviewer_prompt(),
                user_prompt=f"Review item {item.id}: {item.purpose}\n\nContext:\n{context}",
                tools=tools_for(config, item.owned_paths, writable=False),
                observer=observer,
                role="reviewer",
                task_id=item.id,
            )
            return item.id, parse_review(output)

    return dict(await asyncio.gather(*(run(item) for item in items)))


class WorkflowRunner:
    """Run the SDD-gated LangChain workflow in the current repository."""

    def __init__(self, config: WorkflowConfig, observer: Observer | None = None):
        self.config = config
        self.observer = observer or NullObserver()

    async def _stage(self, message: str) -> None:
        await self.observer.emit(WorkflowEvent("stage", message=message))

    async def run(self, objective: str) -> WorkflowResult:
        self.config.validate()
        await self._stage("orquestrador: criando plano")
        plan_text = await invoke_agent(
            self.config,
            model_name=self.config.orchestrator_model,
            system_prompt=orchestrator_prompt(),
            user_prompt=self._context_packet(objective),
            tools=tools_for(self.config, (".",), writable=False),
            observer=self.observer,
            role="orchestrator",
        )
        plan = parse_plan(plan_text)
        _validate_plan(plan, self.config)
        await self._stage(f"plano validado: {len(plan.work_items)} work item(s)")

        coder_outputs = await _parallel_coders(
            self.config,
            plan.work_items,
            json.dumps({"objective": objective, "plan": plan.summary}, ensure_ascii=False),
            self.observer,
        )
        await self._stage("implementação concluída; iniciando revisão independente")
        reviews: dict[str, ReviewResult] = {}
        for round_number in range(self.config.max_review_rounds):
            await self._stage(f"revisão rodada {round_number + 1}/{self.config.max_review_rounds}")
            reviews = await _parallel_reviews(
                self.config,
                plan.work_items,
                json.dumps(
                    {"objective": objective, "coder_outputs": coder_outputs, "round": round_number + 1},
                    ensure_ascii=False,
                ),
                self.observer,
            )
            if all(review.status == "pass" for review in reviews.values()):
                break
            if round_number + 1 < self.config.max_review_rounds:
                await self._stage("revisão solicitou correções; reabrindo coders")
                coder_outputs = await _parallel_coders(
                    self.config,
                    plan.work_items,
                    json.dumps(
                        {
                            "objective": objective,
                            "review_feedback": {
                                key: review.required_changes for key, review in reviews.items()
                            },
                        },
                        ensure_ascii=False,
                    ),
                    self.observer,
                )

        if not all(review.status == "pass" for review in reviews.values()):
            await self._stage("gate de revisão bloqueado")
            raise RuntimeError("Workflow stopped: review gate did not pass")

        await self._stage("revisão aprovada; executando verificações")
        checks_ok, check_evidence = await run_configured_checks(self.config.repo, self.config.checks)
        if not checks_ok:
            await self._stage("gate de verificação bloqueado")
            raise RuntimeError("Workflow stopped: verification gate failed")
        await self._stage("verificações aprovadas; gerando draft do PR")

        draft_text = await invoke_agent(
            self.config,
            model_name=self.config.pr_model,
            system_prompt=pr_prompt(),
            user_prompt=json.dumps(
                {
                    "objective": objective,
                    "acceptance_criteria": plan.acceptance_criteria,
                    "reviews": {key: review.findings for key, review in reviews.items()},
                    "check_evidence": check_evidence,
                },
                ensure_ascii=False,
            ),
            tools=tools_for(self.config, (".",), writable=False),
            observer=self.observer,
            role="pr-agent",
        )
        draft = parse_pr_draft(draft_text)
        if self.config.pr_title:
            draft = PullRequestDraft(self.config.pr_title, draft.body, draft.labels)
        pr_url = self._open_pr(draft) if self.config.open_pr else None
        await self._stage("PR criado" if pr_url else "draft do PR pronto; publicação não autorizada")
        return WorkflowResult(plan, coder_outputs, reviews, checks_ok, check_evidence, draft, pr_url)

    def _context_packet(self, objective: str) -> str:
        files = sorted(
            path.relative_to(self.config.repo).as_posix()
            for path in self.config.repo.rglob("*")
            if path.is_file()
        )
        return json.dumps(
            {
                "objective": objective,
                "repository": str(self.config.repo),
                "files": files[:500],
                "configured_checks": self.config.checks,
                "harness_rule": "PR requires implementation, verification evidence, independent review, and explicit authorization.",
            },
            ensure_ascii=False,
        )

    def _open_pr(self, draft: PullRequestDraft) -> str:
        if not self.config.head_branch:
            raise ValueError("--head-branch is required with --open-pr")
        command = [
            "gh",
            "pr",
            "create",
            "--base",
            self.config.base_branch,
            "--head",
            self.config.head_branch,
            "--title",
            draft.title,
            "--body",
            draft.body,
        ]
        for label in draft.labels or self.config.pr_labels:
            command.extend(["--label", label])
        completed = subprocess.run(command, cwd=self.config.repo, check=True, capture_output=True, text=True)
        return completed.stdout.strip()
