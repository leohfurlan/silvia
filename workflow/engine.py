"""Async workflow controller with parallel implementation and review gates."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents import coder_prompt, invoke_agent, orchestrator_prompt, pr_prompt, reviewer_prompt, tools_for
from .config import WorkflowConfig
from .contracts import PullRequestDraft, ReviewResult, TaskPlan, WorkItem, parse_plan, parse_pr_draft, parse_review, serialise
from .intervention import suggested_action
from .observability import NullObserver, Observer, WorkflowEvent
from .session import InterventionRequest, SessionStore, redact_text
from .tools import run_configured_checks


InterventionHandler = Callable[[InterventionRequest], Awaitable[str]]


@dataclass(frozen=True)
class WorkflowResult:
    plan: TaskPlan
    coder_outputs: dict[str, str]
    reviews: dict[str, ReviewResult]
    checks_ok: bool
    check_evidence: tuple[str, ...]
    pr_draft: PullRequestDraft | None = None
    pr_url: str | None = None


class WorkflowPaused(RuntimeError):
    """Raised when the workflow is safely waiting for human intervention."""

    def __init__(self, session: SessionStore):
        self.session = session
        super().__init__(
            f"Workflow paused; resume with --resume {session.session_id} "
            f"(state: {session.state_path})"
        )



class WorkflowAborted(RuntimeError):
    """Raised when the user explicitly denies further execution."""

    def __init__(self, session: SessionStore):
        self.session = session
        super().__init__(
            f"Workflow aborted for session {session.session_id}; "
            f"state: {session.state_path}"
        )


def _normal(path: str) -> str:
    return path.replace("\\", "/").strip("/") or "."


def _overlap(left: str, right: str) -> bool:
    left, right = _normal(left), _normal(right)
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _artifact_status(path: Path) -> str:
    """Read only the declared status in an artifact header."""
    for line in path.read_text(encoding="utf-8").splitlines()[:30]:
        match = re.match(r"^\s*(?:\*\*)?(?:status|estado)(?:\*\*)?\s*:\s*(.+)$", line, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()
    return ""


def _has_status(status: str, markers: tuple[str, ...]) -> bool:
    return any(marker in status for marker in markers)


def _validate_source_truth(repo: Path) -> None:
    """Block contradictory contract/spec/plan status declarations."""
    negative_contract = (
        "não aprovado",
        "nao aprovado",
        "not approved",
        "unapproved",
        "proposto",
        "proposed",
        "não implementado",
        "nao implementado",
        "not implemented",
    )
    positive_followup = (
        "implementada",
        "implementado",
        "implemented",
        "executed",
        "completed",
        "conclu",
    )
    negative_followup = (
        "não ",
        "nao ",
        "not ",
        "no ",
        "nada ",
        "nenhuma",
        "nothing ",
        "none ",
    )
    for contract in sorted(repo.rglob("contract.md")):
        directory = contract.parent
        spec = directory / "spec.md"
        plan = directory / "plan.md"
        if not spec.is_file() or not plan.is_file():
            continue
        contract_status = _artifact_status(contract)
        followup_statuses = {
            name: _artifact_status(path)
            for name, path in (("spec.md", spec), ("plan.md", plan))
        }
        if _has_status(contract_status, negative_contract) and any(
            _has_status(status, positive_followup) and not _has_status(status, negative_followup)
            for status in followup_statuses.values()
        ):
            details = ", ".join(
                f"{name}={status!r}" for name, status in followup_statuses.items()
            )
            raise ValueError(
                f"Source-of-truth conflict in {directory}: "
                f"contract.md={contract_status!r} conflicts with {details}"
            )


def _validate_plan(plan: TaskPlan, config: WorkflowConfig) -> None:
    allowed_models = {"qwen3.8-flash", "glm-5.3-flash", "deepseek-v4-flash"}
    for index, left in enumerate(plan.work_items):
        if left.model not in allowed_models:
            raise ValueError(f"Implementation item {left.id} uses non-handler model {left.model}")
        if left.context_class == "large" and left.model != "deepseek-v4-flash":
            raise ValueError(f"Large-context item {left.id} must use deepseek-v4-flash")
        if left.model == "deepseek-v4-flash" and left.context_class != "large":
            raise ValueError(f"DeepSeek is reserved for large-context item {left.id}")
        for right in plan.work_items[index + 1 :]:
            if any(_overlap(a, b) for a in left.owned_paths for b in right.owned_paths):
                raise ValueError(f"Work items {left.id} and {right.id} have overlapping ownership")


def _ready(items: tuple[WorkItem, ...], completed: set[str]) -> tuple[WorkItem, ...]:
    return tuple(item for item in items if item.id not in completed and set(item.dependencies) <= completed)


async def _parallel_coders(
    config: WorkflowConfig,
    items: tuple[WorkItem, ...],
    context: str,
    observer: Observer,
    invoke: Callable[..., Awaitable[str]],
    session: SessionStore,
    initial_outputs: dict[str, str] | None = None,
) -> dict[str, str]:
    semaphore = asyncio.Semaphore(config.max_parallel)
    results = dict(initial_outputs or {})
    completed = set(results)

    async def run(item: WorkItem) -> tuple[str, str]:
        async with semaphore:
            prompt = (
                f"Task:\n{item.purpose}\n\n"
                f"Owned paths: {', '.join(item.owned_paths)}\n\n"
                f"Context class: {item.context_class}\n\nContext:\n{context}"
            )
            output = await invoke(
                model_name=item.model,
                system_prompt=coder_prompt(),
                user_prompt=prompt,
                tools=tools_for(config, item.owned_paths, writable=True),
                role="coder",
                task_id=item.id,
                phase="coding",
            )
            session.save_coder_output(item.id, output)
            return item.id, output

    remaining = tuple(item for item in items if item.id not in completed)
    while remaining:
        batch = _ready(remaining, completed)
        if not batch:
            raise ValueError("Plan dependencies contain a cycle")
        outcomes = await asyncio.gather(
            *(run(item) for item in batch),
            return_exceptions=True,
        )
        errors: list[BaseException] = []
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                errors.append(outcome)
            else:
                item_id, output = outcome
                results[item_id] = output
                completed.add(item_id)
        if errors:
            raise errors[0]
        remaining = tuple(item for item in remaining if item.id not in completed)
    return results


async def _parallel_reviews(
    config: WorkflowConfig,
    items: tuple[WorkItem, ...],
    context: str,
    invoke: Callable[..., Awaitable[str]],
) -> dict[str, ReviewResult]:
    semaphore = asyncio.Semaphore(config.max_parallel)

    async def run(item: WorkItem) -> tuple[str, ReviewResult]:
        async with semaphore:
            output = await invoke(
                model_name=config.reviewer_model,
                system_prompt=reviewer_prompt(),
                user_prompt=(
                    f"Review item {item.id}: {item.purpose}\n\n"
                    f"Context class: {item.context_class}\n\nContext:\n{context}"
                ),
                tools=tools_for(config, item.owned_paths, writable=False),
                role="reviewer",
                task_id=item.id,
                phase="review",
            )
            return item.id, parse_review(output)

    outcomes = await asyncio.gather(
        *(run(item) for item in items),
        return_exceptions=True,
    )
    errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    if errors:
        raise errors[0]
    return dict(outcomes)


class WorkflowRunner:
    """Run the SDD-gated LangChain workflow with resumable interventions."""

    def __init__(
        self,
        config: WorkflowConfig,
        observer: Observer | None = None,
        *,
        session_id: str | None = None,
        resume: bool = False,
        intervention_handler: InterventionHandler | None = None,
    ):
        self.config = config
        self.observer = observer or NullObserver()
        self.session = SessionStore(config.repo, session_id, resume=resume)
        self.intervention_handler = intervention_handler
        self._intervention_lock = asyncio.Lock()

    async def _stage(self, message: str) -> None:
        await self.observer.emit(WorkflowEvent("stage", message=message))

    def _stop(self, decision: str, error: Exception | None = None) -> None:
        if decision == "abort":
            if error is not None:
                raise WorkflowAborted(self.session) from error
            raise WorkflowAborted(self.session)
        raise WorkflowPaused(self.session)

    async def _intervene(
        self,
        *,
        phase: str,
        role: str,
        model: str,
        task_id: str,
        error: Exception | str,
        attempt: int = 1,
    ) -> str:
        error_text = redact_text(str(error))
        request = InterventionRequest(
            intervention_id=f"{self.session.session_id}-{attempt}-{task_id or phase}",
            session_id=self.session.session_id,
            phase=phase,
            role=role,
            model=model,
            task_id=task_id,
            error=error_text,
            suggested_action=suggested_action(error_text),
            attempt=attempt,
            timestamp=WorkflowEvent("intervention_required").timestamp,
        )
        async with self._intervention_lock:
            self.session.add_intervention(request)
            await self.observer.emit(
                WorkflowEvent(
                    "intervention_required",
                    role=role,
                    model=model,
                    task_id=task_id,
                    message=error_text,
                    payload={
                        "intervention_id": request.intervention_id,
                        "session_id": self.session.session_id,
                        "suggested_action": request.suggested_action,
                    },
                )
            )
            decision = "pause"
            if self.intervention_handler is not None:
                decision = await self.intervention_handler(request)
            if decision not in {"retry", "abort", "pause"}:
                decision = "pause"
            self.session.resolve_intervention(request, decision)
            await self.observer.emit(
                WorkflowEvent(
                    "intervention_resolved",
                    role=role,
                    model=model,
                    task_id=task_id,
                    message=decision,
                    payload={"intervention_id": request.intervention_id},
                )
            )
            return decision

    async def _invoke_resilient(self, **kwargs: Any) -> str:
        attempt = 1
        while True:
            try:
                return await invoke_agent(
                    self.config,
                    observer=self.observer,
                    **{key: value for key, value in kwargs.items() if key not in {"phase"}},
                )
            except Exception as error:
                decision = await self._intervene(
                    phase=str(kwargs["phase"]),
                    role=str(kwargs["role"]),
                    model=str(kwargs["model_name"]),
                    task_id=str(kwargs.get("task_id", "")),
                    error=error,
                    attempt=attempt,
                )
                if decision == "retry":
                    attempt += 1
                    continue
                self._stop(decision, error)

    async def _parse_resilient(
        self,
        parser: Callable[[str], Any],
        raw: str,
        *,
        phase: str,
        role: str,
        model: str,
        task_id: str = "",
    ) -> Any:
        try:
            return parser(raw)
        except Exception as error:
            decision = await self._intervene(
                phase=phase,
                role=role,
                model=model,
                task_id=task_id,
                error=error,
            )
            if decision == "retry":
                return None
            self._stop(decision, error)


    async def _reviews_with_intervention(
        self,
        items: tuple[WorkItem, ...],
        context: str,
        round_number: int,
    ) -> dict[str, ReviewResult]:
        while True:
            try:
                return await _parallel_reviews(
                    self.config,
                    items,
                    context,
                    self._invoke_resilient,
                )
            except WorkflowPaused:
                raise
            except Exception as error:
                decision = await self._intervene(
                    phase="review",
                    role="reviewer",
                    model=self.config.reviewer_model,
                    task_id="",
                    error=error,
                    attempt=round_number,
                )
                if decision == "retry":
                    continue
                self._stop(decision, error)


    async def _validate_config_resilient(self) -> None:
        while True:
            try:
                self.config.validate()
                return
            except Exception as error:
                decision = await self._intervene(
                    phase="setup",
                    role="controller",
                    model="",
                    task_id="",
                    error=error,
                )
                if decision == "retry":
                    continue
                self._stop(decision, error)

    async def _validate_plan_resilient(self, plan: TaskPlan) -> None:
        while True:
            try:
                _validate_plan(plan, self.config)
                return
            except Exception as error:
                decision = await self._intervene(
                    phase="planning",
                    role="controller",
                    model="",
                    task_id="",
                    error=error,
                )
                if decision == "retry":
                    continue
                self._stop(decision, error)

    async def run(self, objective: str) -> WorkflowResult:
        await self._validate_config_resilient()
        state = self.session.state
        resuming = bool(state.get("plan"))
        if resuming:
            stored_objective = str(state.get("objective", "")).strip()
            if objective and stored_objective and objective != stored_objective:
                raise ValueError("Resume objective differs from the original session objective")
            objective = stored_objective
            plan = parse_plan(json.dumps(state["plan"], ensure_ascii=False))
        else:
            self.session.update(objective=objective, phase="planning", status="running")
            await self._stage("orquestrador: criando plano")
            while True:
                plan_text = await self._invoke_resilient(
                    model_name=self.config.orchestrator_model,
                    system_prompt=orchestrator_prompt(),
                    user_prompt=self._context_packet(objective),
                    tools=tools_for(self.config, (".",), writable=False),
                    role="orchestrator",
                    task_id="",
                    phase="planning",
                )
                plan = await self._parse_resilient(
                    parse_plan,
                    plan_text,
                    phase="planning",
                    role="orchestrator",
                    model=self.config.orchestrator_model,
                )
                if plan is not None:
                    break
            self.session.update(objective=objective, plan=serialise(plan), phase="planning", status="running")

        await self._stage("validando consistência das fontes de verdade")
        while True:
            try:
                _validate_source_truth(self.config.repo)
                break
            except Exception as error:
                decision = await self._intervene(
                    phase="planning",
                    role="controller",
                    model="",
                    task_id="",
                    error=error,
                )
                if decision == "retry":
                    continue
                self._stop(decision, error)
        await self._validate_plan_resilient(plan)
        await self._stage(f"plano validado: {len(plan.work_items)} work item(s)")
        self.session.update(phase="coding", status="running")

        coder_outputs = await _parallel_coders(
            self.config,
            plan.work_items,
            json.dumps({"objective": objective, "plan": plan.summary}, ensure_ascii=False),
            self.observer,
            self._invoke_resilient,
            self.session,
            dict(self.session.state.get("coder_outputs", {})),
        )
        await self._stage("implementação concluída; iniciando revisão independente")

        reviews: dict[str, ReviewResult] = {}
        stored_reviews = self.session.state.get("reviews", {})
        if stored_reviews and all(
            isinstance(value, dict) and value.get("status") == "pass"
            for value in stored_reviews.values()
        ):
            reviews = {
                key: parse_review(json.dumps(value, ensure_ascii=False))
                for key, value in stored_reviews.items()
            }

        while not reviews or not all(review.status == "pass" for review in reviews.values()):
            review_passed = False
            for round_number in range(self.config.max_review_rounds):
                await self._stage(f"revisão rodada {round_number + 1}/{self.config.max_review_rounds}")
                try:
                    reviews = await self._reviews_with_intervention(
                        plan.work_items,
                        json.dumps(
                            {
                                "objective": objective,
                                "coder_outputs": coder_outputs,
                                "round": round_number + 1,
                            },
                            ensure_ascii=False,
                        ),
                        round_number + 1,
                    )
                except WorkflowPaused:
                    raise
                self.session.save_reviews(
                    {key: serialise(review) for key, review in reviews.items()},
                    round_number + 1,
                )
                if all(review.status == "pass" for review in reviews.values()):
                    review_passed = True
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
                        self._invoke_resilient,
                        self.session,
                        {},
                    )
            if review_passed:
                break
            decision = await self._intervene(
                phase="review",
                role="controller",
                model=self.config.reviewer_model,
                task_id="",
                error="Review gate blocked: reviewers did not return pass",
            )
            if decision != "retry":
                self._stop(decision, RuntimeError("Review gate blocked: reviewers did not return pass"))
            reviews = {}

        await self._stage("revisão aprovada; executando verificações")
        stored_checks_ok = bool(self.session.state.get("checks_ok"))
        stored_evidence = tuple(str(item) for item in self.session.state.get("check_evidence", []))
        if stored_checks_ok and stored_evidence:
            checks_ok, check_evidence = True, stored_evidence
            await self._stage("verificações já aprovadas; evidência reutilizada da sessão")
        else:
            while True:
                try:
                    checks_ok, check_evidence = await run_configured_checks(
                        self.config.repo,
                        self.config.checks,
                    )
                except Exception as error:
                    decision = await self._intervene(
                        phase="verification",
                        role="controller",
                        model="",
                        task_id="",
                        error=error,
                    )
                    if decision == "retry":
                        continue
                    self._stop(decision, error)
                self.session.save_checks(checks_ok, check_evidence)
                if checks_ok:
                    break
                decision = await self._intervene(
                    phase="verification",
                    role="controller",
                    model="",
                    task_id="",
                    error="Verification gate failed:\n" + "\n".join(check_evidence),
                )
                if decision != "retry":
                    self._stop(decision, RuntimeError("Verification gate failed: "+"\n".join(check_evidence)))
        await self._stage("verificações aprovadas; gerando draft do PR")

        stored_draft = self.session.state.get("pr_draft")
        if isinstance(stored_draft, dict):
            draft = parse_pr_draft(json.dumps(stored_draft, ensure_ascii=False))
            pr_url = self.session.state.get("pr_url")
            return WorkflowResult(plan, coder_outputs, reviews, True, check_evidence, draft, pr_url)

        while True:
            draft_text = await self._invoke_resilient(
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
                role="pr-agent",
                task_id="",
                phase="pr",
            )
            draft = await self._parse_resilient(
                parse_pr_draft,
                draft_text,
                phase="pr",
                role="pr-agent",
                model=self.config.pr_model,
            )
            if draft is not None:
                break
        if self.config.pr_title:
            draft = PullRequestDraft(self.config.pr_title, draft.body, draft.labels)
        if self.config.open_pr:
            while True:
                try:
                    pr_url = self._open_pr(draft)
                    break
                except Exception as error:
                    decision = await self._intervene(
                        phase="pr",
                        role="pr-agent",
                        model=self.config.pr_model,
                        task_id="",
                        error=error,
                    )
                    if decision == "retry":
                        continue
                    self._stop(decision, error)
        else:
            pr_url = None
        self.session.save_pr(serialise(draft), pr_url)
        await self._stage("PR criado" if pr_url else "draft do PR pronto; publicação não autorizada")
        return WorkflowResult(plan, coder_outputs, reviews, True, check_evidence, draft, pr_url)

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
