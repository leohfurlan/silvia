"""Typed contracts and fail-closed parsing for agent outputs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkItem:
    id: str
    purpose: str
    owned_paths: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    context_class: str = "standard"
    model: str = "qwen3.8-flash"


@dataclass(frozen=True)
class TaskPlan:
    summary: str
    acceptance_criteria: tuple[str, ...]
    work_items: tuple[WorkItem, ...]


@dataclass(frozen=True)
class ReviewResult:
    status: str
    findings: tuple[str, ...] = ()
    required_changes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PullRequestDraft:
    title: str
    body: str
    labels: tuple[str, ...] = ()


def _json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Agent did not return a JSON object") from None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ValueError("Agent returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Agent output must be a JSON object")
    return value


def _strings(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(f"{field_name} must not be empty")
        return (value.strip(),)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field_name} must be a string or a list of non-empty strings")
    return tuple(item.strip() for item in value)


def parse_plan(text: str) -> TaskPlan:
    data = _json_object(text)
    raw_items = data.get("work_items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Plan must contain at least one work item")
    items: list[WorkItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("Each work item must be an object")
        required = ("id", "purpose", "owned_paths")
        if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required[:2]):
            raise ValueError("Work items require non-empty id and purpose")
        paths = _strings(raw.get("owned_paths"), "owned_paths")
        if not paths:
            raise ValueError("Every work item must own at least one path")
        context_class = str(raw.get("context_class", "standard")).strip().lower()
        if context_class not in {"standard", "large"}:
            raise ValueError("context_class must be standard or large")
        items.append(
            WorkItem(
                id=raw["id"].strip(),
                purpose=raw["purpose"].strip(),
                owned_paths=paths,
                dependencies=_strings(raw.get("dependencies"), "dependencies"),
                verification=_strings(raw.get("verification"), "verification"),
                context_class=context_class,
                model=str(raw.get("model", "qwen3.8-flash")).strip(),
            )
        )
    ids = {item.id for item in items}
    if len(ids) != len(items) or any(dep not in ids for item in items for dep in item.dependencies):
        raise ValueError("Plan contains duplicate work-item IDs or unknown dependencies")
    return TaskPlan(
        summary=str(data.get("summary", "")).strip(),
        acceptance_criteria=_strings(data.get("acceptance_criteria"), "acceptance_criteria"),
        work_items=tuple(items),
    )


def parse_review(text: str) -> ReviewResult:
    data = _json_object(text)
    status = str(data.get("status", "")).strip().lower()
    if status not in {"pass", "changes_requested", "blocked"}:
        raise ValueError("Review status must be pass, changes_requested, or blocked")
    return ReviewResult(
        status=status,
        findings=_strings(data.get("findings"), "findings"),
        required_changes=_strings(data.get("required_changes"), "required_changes"),
    )


def parse_pr_draft(text: str) -> PullRequestDraft:
    data = _json_object(text)
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    if not title or not body:
        raise ValueError("PR draft requires title and body")
    return PullRequestDraft(title=title, body=body, labels=_strings(data.get("labels"), "labels"))


def serialise(value: Any) -> dict[str, Any]:
    return asdict(value)
