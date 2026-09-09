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


def _owned(repo: Path, requested: str, owned_paths: tuple[str, ...]) -> Path:
    candidate = _relative(repo, requested)
    allowed = False
    for owned_path in owned_paths:
        root = _relative(repo, owned_path)
        try:
            candidate.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise ValueError(f"Path is outside this agent's ownership: {requested}")
    return candidate


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
        """List files below an owned repository path."""
        target = _owned(repo, path or owned_paths[0], owned_paths)
        if not target.exists():
            return ""
        if target.is_file():
            return target.relative_to(repo).as_posix()
        files = sorted(item.relative_to(repo).as_posix() for item in target.rglob("*") if item.is_file())
        return "\n".join(files)

    @tool
    def git_diff() -> str:
        """Return the current diff for this agent's owned paths."""
        paths = [_normalise_for_git(path) for path in owned_paths if path not in {"", "."}]
        command = ["git", "diff", "HEAD", "--"] + paths
        completed = subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)
        return completed.stdout[-12000:]

    tools = [read_file, list_files, git_diff]

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
