"""Deterministic, merge-safe initialization of the Atos SDD harness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

_PROFILE_ORDER = ("minimal", "standard", "high-risk")
_CATALOG_VERSION = 1


class HarnessConflict(ValueError):
    """A controlled harness path is a symlink or escapes the project root."""


@dataclass(frozen=True)
class HarnessInitializationReport:
    profile: str
    catalog_version: int
    created: tuple[str, ...]
    preserve_compatible: tuple[str, ...]
    integration_required: tuple[str, ...]


def _catalog() -> dict[str, dict[str, str]]:
    content = (
        resources.files(__package__)
        .joinpath("harness_templates.json")
        .read_text(encoding="utf-8")
    )
    loaded = json.loads(content)
    if not isinstance(loaded, dict):
        raise RuntimeError("Invalid bundled harness template catalog")
    return loaded


def _templates(profile: str) -> dict[str, str]:
    try:
        upper_bound = _PROFILE_ORDER.index(profile)
    except ValueError as exc:
        raise ValueError(f"Unsupported harness profile: {profile}") from exc

    selected: dict[str, str] = {}
    for layer in _PROFILE_ORDER[: upper_bound + 1]:
        for relative, content in _catalog()[layer].items():
            if relative in selected:
                raise RuntimeError(f"Duplicate harness template: {relative}")
            selected[relative] = content
    return selected


def _render(template: str, *, project_name: str) -> str:
    values = {
        "PROJECT_NAME": project_name,
        "PROFILE": "standard",
        "PRODUCT_REQUIREMENTS": "docs/product/PRD.md",
        "SPECIFICATIONS": "docs/specs",
        "FAST_COMMANDS_JSON": "[]",
        "FULL_COMMANDS_JSON": "[]",
        "ARCHITECTURE_COMMANDS_JSON": "[]",
    }
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace("{{" + name + "}}", value)
    if "{{" in rendered or "}}" in rendered:
        raise RuntimeError("Unresolved bundled harness template marker")
    return rendered


def _target(root: Path, relative: str) -> Path:
    target = root / relative
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise HarnessConflict(f"Harness target escapes project root: {relative}") from exc
    return target


def initialize_standard_harness(
    project_root: Path | str, *, project_name: str | None = None
) -> HarnessInitializationReport:
    """Create the missing standard scaffold without overwriting existing files.

    Existing files with non-identical content are reported for explicit
    integration. A controlled symlink is rejected before any file is created.
    """

    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Project root does not exist: {root}")

    name = project_name or root.name
    templates = {
        relative: _render(content, project_name=name)
        for relative, content in _templates("standard").items()
    }
    plan: list[tuple[str, Path, str, str]] = []
    for relative in sorted(templates):
        target = _target(root, relative)
        if target.is_symlink():
            raise HarnessConflict(f"Controlled harness path is a symlink: {relative}")
        if not target.exists():
            status = "created"
        elif target.is_file() and target.read_text(
            encoding="utf-8", errors="replace"
        ) == templates[relative]:
            status = "preserve-compatible"
        else:
            status = "integration-required"
        plan.append((relative, target, templates[relative], status))

    created: list[str] = []
    compatible: list[str] = []
    integration_required: list[str] = []
    for relative, target, content, status in plan:
        if status == "created":
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with target.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(content)
            except FileExistsError as exc:
                raise HarnessConflict(
                    f"Harness path appeared during initialization: {relative}"
                ) from exc
            created.append(relative)
        elif status == "preserve-compatible":
            compatible.append(relative)
        else:
            integration_required.append(relative)

    return HarnessInitializationReport(
        profile="standard",
        catalog_version=_CATALOG_VERSION,
        created=tuple(created),
        preserve_compatible=tuple(compatible),
        integration_required=tuple(integration_required),
    )
