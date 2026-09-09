"""Configuration for the B.AI LangChain workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _dotenv_value(path: Path, name: str) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == name:
            return value.strip().strip(chr(34)).strip(chr(39))
    return ""


@dataclass(frozen=True)
class WorkflowConfig:
    repo: Path
    base_url: str = field(default_factory=lambda: _env("BAI_BASE_URL", "https://api.b.ai/v1"))
    api_key: str = ""
    orchestrator_model: str = field(
        default_factory=lambda: _env("WORKFLOW_ORCHESTRATOR_MODEL", "glm-5.3-flash")
    )
    coder_model: str = field(
        default_factory=lambda: _env("WORKFLOW_CODER_MODEL", "qwen3.8-flash")
    )
    reviewer_model: str = field(
        default_factory=lambda: _env("WORKFLOW_REVIEWER_MODEL", "glm-5.3-flash")
    )
    pr_model: str = field(
        default_factory=lambda: _env("WORKFLOW_PR_MODEL", "qwen3.8-flash")
    )
    max_parallel: int = 3
    max_review_rounds: int = 2
    checks: tuple[str, ...] = ()
    open_pr: bool = False
    base_branch: str = "main"
    head_branch: str = ""
    pr_title: str = ""
    pr_labels: tuple[str, ...] = ()

    @classmethod
    def from_environment(
        cls,
        repo: Path,
        *,
        checks: tuple[str, ...] = (),
        max_parallel: int = 3,
        max_review_rounds: int = 2,
        open_pr: bool = False,
        base_branch: str = "main",
        head_branch: str = "",
        pr_title: str = "",
        pr_labels: tuple[str, ...] = (),
    ) -> "WorkflowConfig":
        api_key = (
            os.environ.get("APIKEY_B_AI")
            or os.environ.get("BAI_API_KEY")
            or _dotenv_value(repo / ".env.dev", "APIKEY_B_AI")
            or _dotenv_value(repo / ".env.dev", "BAI_API_KEY")
            or ""
        )
        return cls(
            repo=repo.resolve(),
            api_key=api_key,
            checks=checks,
            max_parallel=max_parallel,
            max_review_rounds=max_review_rounds,
            open_pr=open_pr,
            base_branch=base_branch,
            head_branch=head_branch,
            pr_title=pr_title,
            pr_labels=pr_labels,
        )

    def validate(self) -> None:
        if not self.repo.is_dir():
            raise ValueError(f"Repository does not exist: {self.repo}")
        if not self.api_key:
            raise ValueError("APIKEY_B_AI (or BAI_API_KEY) is required")
        if self.max_parallel < 1:
            raise ValueError("max_parallel must be at least 1")
        if self.max_review_rounds < 1:
            raise ValueError("max_review_rounds must be at least 1")
        if self.open_pr and not self.head_branch:
            raise ValueError("--head-branch is required with --open-pr")
        if not self.base_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        allowed_handlers = {"qwen3.8-flash", "glm-5.3-flash", "deepseek-v4-flash"}
        for role, model in (
            ("coder", self.coder_model),
            ("reviewer", self.reviewer_model),
            ("pr", self.pr_model),
        ):
            if model not in allowed_handlers:
                raise ValueError(
                    f"{role} model must be qwen3.8-flash, glm-5.3-flash, or deepseek-v4-flash"
                )
