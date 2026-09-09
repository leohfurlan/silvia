"""Scoped LangChain tools shared by coding, review, and PR agents."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from langchain_core.tools import tool


def _normalise_for_git(path: str) -> str:
    return path.replace("\\", "/").strip("/") or "."


def _relative(repo: Path, requested: str) -> Path:
    candidate = (repo / requested).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("Path escapes the repository") from exc
    return candidate


def _contains(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _owned(repo: Path, requested: str, owned_paths: tuple[str, ...]) -> Path:
    candidate = _relative(repo, requested)
    if not any(_contains(candidate, _relative(repo, owned_path)) for owned_path in owned_paths):
        raise ValueError(f"Path is outside this agent's ownership: {requested}")
    return candidate


def _listing_scope(repo: Path, requested: str, owned_paths: tuple[str, ...]) -> tuple[Path, tuple[Path, ...]]:
    target = _relative(repo, requested)
    roots = tuple(_relative(repo, owned_path) for owned_path in owned_paths)
    if not any(_contains(target, root) or _contains(root, target) for root in roots):
        raise ValueError(f"Path is outside this agent's ownership: {requested}")
    return target, roots


def _run_git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout[-8000:]


def workspace_tools(repo: Path, owned_paths: tuple[str, ...], *, writable: bool):
    @tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the repository and owned scope."""
        target = _owned(repo, path, owned_paths)
        if not target.is_file():
            raise ValueError(f"File does not exist: {path}")
        return target.read_text(encoding="utf-8")

    @tool
    def list_files(path: str = "") -> str:
        """List only owned files below a path or its owned ancestor scope."""
        target, roots = _listing_scope(repo, path or owned_paths[0], owned_paths)
        if not target.exists():
            return ""
        candidates = [target] if target.is_file() else target.rglob("*")
        files = sorted(
            item.relative_to(repo).as_posix()
            for item in candidates
            if item.is_file() and any(_contains(item, root) for root in roots)
        )
        return "\n".join(files)

    @tool
    def git_status() -> str:
        """Return short Git status for the repository without changing it."""
        return _run_git(repo, "status", "--short", "--branch")

    @tool
    def git_branch() -> str:
        """Return the current Git branch without changing the repository."""
        return _run_git(repo, "branch", "--show-current").strip()

    @tool
    def git_diff() -> str:
        """Return the current diff for this agent owned paths."""
        paths = [_normalise_for_git(path) for path in owned_paths if path not in {"", "."}]
        command = ["diff", "HEAD", "--"] + paths
        return _run_git(repo, *command)[-12000:]

    tools = [read_file, list_files, git_status, git_branch, git_diff]

    if writable:
        @tool
        def write_file(path: str, content: str) -> str:
            """Write a UTF-8 text file in the owned scope."""
            target = _owned(repo, path, owned_paths)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"wrote {target.relative_to(repo).as_posix()}"

        tools.append(write_file)
    return tools


async def run_configured_checks(repo: Path, checks: tuple[str, ...]) -> tuple[bool, tuple[str, ...]]:
    if not checks:
        return False, ("No verification command configured; verification remains pending.",)

    async def run(command: str) -> tuple[bool, str]:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        text = output.decode("utf-8", errors="replace").strip()
        return process.returncode == 0, f"$ {command}\n{text[-4000:]}"

    results = await asyncio.gather(*(run(command) for command in checks))
    return all(ok for ok, _ in results), tuple(output for _, output in results)
