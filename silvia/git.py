"""Git and filesystem identity, isolated checkouts and evaluated-version fingerprints."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from silvia.core import DomainError, digest, encode


def run_git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    if check and result.returncode:
        raise DomainError("git", f"Git {args[0]} failed.", "Inspect Git state; SilvIA preserved the checkout.", exit_code=result.returncode)
    return result.stdout.strip() if result.returncode == 0 else ""


def safe_path(root: Path, relative: str, *, protected: bool = False) -> Path:
    root = root.resolve()
    value = Path(relative)
    if value.is_absolute() or not relative or ".." in value.parts:
        raise DomainError("invalid-path", "Paths must be relative and contained in the assigned root.")
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise DomainError("invalid-path", "Path escapes its assigned root.") from exc
    if protected and any(p.casefold() in {".git", ".silvia", ".harness", ".env", "agents.md", "claude.md", "development.md"} or p.startswith(".env.") for p in value.parts):
        raise DomainError("protected-path", "Runtime, credentials and governance files require a separate protected action.")
    return candidate


def owned_path(root: Path, relative: str, ownership: list | tuple, *, writable: bool = False) -> Path:
    candidate = safe_path(root, relative, protected=writable)
    for path in ownership:
        owner = safe_path(root, path)
        if candidate == owner or owner in candidate.parents:
            return candidate
    raise DomainError("ownership", "Path is outside the work item's ownership.")


def repository(root: Path) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise DomainError("invalid-root", "Project root must be an existing directory.")
    top = run_git(root, "rev-parse", "--show-toplevel", check=False)
    if not top:
        return {"root": str(root), "git_common": None, "identity": None}
    root = Path(top).resolve()
    common = run_git(root, "rev-parse", "--git-common-dir")
    common = str((root / common).resolve())
    remotes = run_git(root, "remote", "-v")
    # Never persist URLs containing credentials; identity is only a comparison hint.
    first = run_git(root, "rev-list", "--max-parents=0", "HEAD", check=False)
    return {"root": str(root), "git_common": common, "identity": digest(remotes + "\n" + first) if remotes else None}


def baseline(root: Path) -> dict:
    root = root.expanduser().resolve()
    remotes = run_git(root, "remote", check=False).splitlines()
    remote_material = []
    for name in sorted(value.strip() for value in remotes if value.strip()):
        urls = run_git(root, "remote", "get-url", "--all", name, check=False).splitlines()
        remote_material.append({"name": name, "url_digests": [digest(url) for url in sorted(urls)]})
    return {"head": run_git(root, "rev-parse", "HEAD", check=False),
            "remotes": remote_material,
            "location": str(root),
            "status": run_git(root, "status", "--porcelain=v1", "--untracked-files=all", check=False),
            "fingerprint": fingerprint(root)}


def fingerprint(root: Path) -> str:
    """Hash tracked + untracked nonignored content, not just HEAD or mtimes."""
    if run_git(root, "rev-parse", "--is-inside-work-tree", check=False):
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"], capture_output=True, check=True, timeout=60)
        names = set(result.stdout.decode("utf-8", errors="surrogateescape").split("\0")) - {""}
    else:
        names = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not any(x in {".silvia", "__pycache__", ".venv"} for x in p.relative_to(root).parts)}
    contents = []
    for name in sorted(names):
        if name.startswith(".silvia/"):
            continue
        path = root / name
        if path.is_symlink():
            value = "link:" + os.readlink(path)
        elif path.is_file():
            value = digest(path.read_bytes())
        else:
            value = "missing"
        contents.append((name, value))
    return digest(encode(contents))


def create_worktree(root: Path, destination: Path, session_id: str) -> None:
    if destination.exists():
        raise DomainError("checkout-conflict", "Worktree destination already exists.")
    if not run_git(root, "rev-parse", "HEAD", check=False):
        raise DomainError("git", "A worktree requires an existing commit.", "Create the initial commit yourself or explicitly select direct checkout.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_git(root, "worktree", "add", "--detach", str(destination), "HEAD")
