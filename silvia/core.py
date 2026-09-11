"""Shared value types. No persistence, terminal or provider dependencies."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return str(uuid.uuid4())


def encode(value: Any) -> str:
    return json.dumps(asdict(value) if is_dataclass(value) else value, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def encode_pretty(value: Any) -> str:
    """Human-readable JSON with indent=4 for display in the TUI."""
    return json.dumps(asdict(value) if is_dataclass(value) else value,
                      ensure_ascii=False, sort_keys=True, indent=4, allow_nan=False)


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


class DomainError(Exception):
    def __init__(self, code: str, message: str, suggestion: str = "Inspect the session and resolve the reported condition.", **details: Any):
        super().__init__(message)
        self.code, self.message, self.suggestion, self.details = code, message, suggestion, details

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "suggestion": self.suggestion, "details": self.details}


@dataclass(frozen=True)
class ObjectiveInput:
    text: str
    criteria: tuple[str, ...]
    constraints: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.text.strip() or not self.criteria or any(not x.strip() for x in self.criteria):
            raise DomainError("invalid-objective", "An objective needs text and at least one observable criterion.")


@dataclass(frozen=True)
class ActionRequest:
    capability: str
    session_id: str
    objective_revision: int
    target: str
    actor: str = "user"
    work_item: str | None = None
    parameters: dict = field(default_factory=dict)
    action_id: str = field(default_factory=uid)


@dataclass(frozen=True)
class GateDecision:
    outcome: str
    rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    request: ActionRequest


@dataclass(frozen=True)
class WorkItem:
    id: str
    purpose: str
    owned_paths: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    verification: tuple[tuple[str, ...], ...] = ()
    profile: str = "default"
    role: str = "implementer"
    stop_condition: str = "Implement the assigned change and report results."
    max_calls: int = 20
    max_tokens: int = 64000
    max_seconds: int = 900
    skills: tuple[dict, ...] = ()


@dataclass(frozen=True)
class AgentDescriptor:
    id: str
    role: str
    model: str
    provider: str
    objective_revision: int
    work_item: str
    ownership: tuple[str, ...]
    capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    budget: dict
    stopping_condition: str


TERMINAL = frozenset({"completed", "cancelled", "archived"})
TRANSITIONS = {
    "created": {"planning", "waiting-for-action", "cancelled"},
    "planning": {"running", "waiting-for-action", "blocked", "cancelled"},
    "running": {"waiting-for-action", "blocked", "cancelled"},
    "waiting-for-action": {"planning", "running", "blocked", "completed", "cancelled"},
    "blocked": {"planning", "waiting-for-action", "cancelled"},
    "completed": {"archived"}, "cancelled": {"archived"}, "archived": set(),
}
