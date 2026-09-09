"""Durable checkpoints and intervention records for workflow runs."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(text: str) -> str:
    text = re.sub(
        r"(?im)^\s*(APIKEY_B_AI|BAI_API_KEY|OPENAI_API_KEY|SECRET_KEY|[A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY)[A-Z0-9_]*)\s*=.*$",
        r"\1=[REDACTED]",
        text,
    )
    return re.sub(
        r"-----BEGIN [^-]+ PRIVATE KEY-----.*?-----END [^-]+ PRIVATE KEY-----",
        "[PRIVATE_KEY_REDACTED]",
        text,
        flags=re.DOTALL,
    )


def _session_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", value):
        raise ValueError("Invalid session id")
    return value


@dataclass(frozen=True)
class InterventionRequest:
    intervention_id: str
    session_id: str
    phase: str
    role: str
    model: str
    task_id: str
    error: str
    suggested_action: str
    attempt: int
    timestamp: str

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["error"] = redact_text(str(data["error"]))
        data["suggested_action"] = redact_text(str(data["suggested_action"]))
        return data


class SessionStore:
    """Persist resumable workflow state without storing credentials."""

    def __init__(self, repo: Path, session_id: str | None = None, *, resume: bool = False):
        self.repo = repo.resolve()
        self.root = self.repo / ".workflow" / "sessions"
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.session_id = _session_id(session_id)
        self.directory = self.root / self.session_id
        self.state_path = self.directory / "state.json"
        self.interventions_path = self.directory / "interventions.jsonl"
        if resume:
            if not self.state_path.is_file():
                raise ValueError(f"Workflow session does not exist: {self.session_id}")
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        else:
            self.state = {
                "version": 1,
                "session_id": self.session_id,
                "objective": "",
                "status": "running",
                "phase": "planning",
                "plan": None,
                "coder_outputs": {},
                "reviews": {},
                "review_round": 0,
                "checks_ok": False,
                "check_evidence": [],
                "pr_draft": None,
                "pr_url": None,
                "pending_intervention": None,
            }
            self.save()

    @property
    def path(self) -> Path:
        return self.directory

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def update(self, **values: Any) -> None:
        self.state.update(values)
        self.save()

    def set_plan(self, plan: dict[str, object], objective: str) -> None:
        self.update(objective=objective, plan=plan, phase="coding", status="running")

    def save_coder_output(self, task_id: str, output: str) -> None:
        outputs = dict(self.state.get("coder_outputs", {}))
        outputs[task_id] = redact_text(output)
        self.update(coder_outputs=outputs, phase="coding", status="running")

    def save_reviews(self, reviews: dict[str, object], round_number: int) -> None:
        self.update(reviews=reviews, review_round=round_number, phase="review", status="running")

    def save_checks(self, checks_ok: bool, evidence: tuple[str, ...]) -> None:
        self.update(
            checks_ok=checks_ok,
            check_evidence=[redact_text(item) for item in evidence],
            phase="verification",
            status="running",
        )

    def save_pr(self, draft: dict[str, object], url: str | None) -> None:
        self.update(pr_draft=draft, pr_url=url, phase="completed", status="completed")

    def add_intervention(self, request: InterventionRequest) -> None:
        self.update(
            pending_intervention=request.as_dict(),
            phase=request.phase,
            status="waiting_user",
        )
        with self.interventions_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(request.as_dict(), ensure_ascii=False) + "\n")

    def resolve_intervention(self, request: InterventionRequest, decision: str) -> None:
        record = request.as_dict()
        record.update({"event": "resolved", "decision": decision, "resolved_at": _now()})
        with self.interventions_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        if decision == "pause":
            self.update(status="waiting_user")
        else:
            status = "aborted" if decision == "abort" else "running"
            self.update(pending_intervention=None, status=status)

    def pause(self) -> None:
        self.update(status="waiting_user")
