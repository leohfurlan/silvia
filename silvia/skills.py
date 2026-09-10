"""Explicit local skill discovery and reproducible, non-executing context resolution."""
from __future__ import annotations

from pathlib import Path

import yaml

from silvia.core import DomainError, digest, encode, uid
from silvia.git import run_git, safe_path
from silvia.storage import SQLiteStore


class SkillRegistry:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def register_source(self, path: Path, name: str) -> dict:
        path = path.expanduser().resolve()
        if not path.is_dir() or not name.strip():
            raise DomainError("invalid-source", "A source requires a name and existing local directory.")
        existing = self.store.one("SELECT * FROM sources WHERE path=? OR name=?", (str(path), name))
        if existing:
            if existing["path"] != str(path) or existing["name"] != name:
                raise DomainError("source-conflict", "Source name or path already belongs to another registration.")
            return existing
        value = {"id": uid(), "name": name, "path": str(path)}
        with self.store.transaction():
            self.store.db.execute("INSERT INTO sources VALUES(:id,:name,:path)", value)
        return value

    def discover(self, source_id: str) -> list[dict]:
        source = self._source(source_id)
        root = Path(source["path"])
        result = []
        for path in sorted(root.rglob("SKILL.md")):
            relative = path.relative_to(root).as_posix()
            safe_path(root, relative)
            result.append({"source_id": source["id"], "path": path.parent.relative_to(root).as_posix(), "name": path.parent.name})
        return result

    def _source(self, id: str) -> dict:
        source = self.store.one("SELECT * FROM sources WHERE id=? OR name=?", (id, id))
        if not source:
            raise DomainError("source-not-registered", "Skill source must be explicitly registered.")
        return source

    def resolve(self, source_id: str, path: str) -> dict:
        source = self._source(source_id)
        root = safe_path(Path(source["path"]), path)
        instruction = safe_path(root, "SKILL.md")
        if not instruction.is_file():
            raise DomainError("invalid-skill", "Selected directory has no SKILL.md.")
        text = instruction.read_text(encoding="utf-8")
        self.store.redactor.reject_secret(text)
        metadata = {}
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) != 3:
                raise DomainError("invalid-skill", "Invalid frontmatter.")
            try:
                metadata = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as exc:
                raise DomainError("invalid-skill", "Invalid YAML frontmatter.") from exc
            if not isinstance(metadata, dict):
                raise DomainError("invalid-skill", "Frontmatter must be a mapping.")
        files = {"SKILL.md": digest(text)}
        sidecar, errors = {}, []
        sidepath = safe_path(root, "silvia.yaml")
        if sidepath.is_file():
            raw = sidepath.read_text(encoding="utf-8")
            self.store.redactor.reject_secret(raw)
            files["silvia.yaml"] = digest(raw)
            try:
                sidecar = yaml.safe_load(raw)
                if not isinstance(sidecar, dict) or sidecar.get("schema_version") != 1 or not isinstance(sidecar.get("capabilities", []), list):
                    raise ValueError("Unsupported sidecar schema")
                names = set()
                for cap in sidecar.get("capabilities", []):
                    required = ("name", "executable", "argv", "filesystem", "network", "platforms", "requires_approval")
                    if not isinstance(cap, dict) or not all(k in cap for k in required):
                        raise ValueError("Incomplete capability declaration")
                    if not isinstance(cap["name"], str) or not cap["name"].strip() or cap["name"] in names:
                        raise ValueError("Capability names must be unique and nonempty")
                    names.add(cap["name"])
                    if not isinstance(cap["executable"], str) or not isinstance(cap["argv"], list) or not all(isinstance(x, str) for x in cap["argv"]):
                        raise ValueError("Invalid executable or arguments")
                    if not isinstance(cap["filesystem"], dict) or not isinstance(cap["network"], list) or not isinstance(cap["platforms"], list) or not isinstance(cap["requires_approval"], bool):
                        raise ValueError("Invalid capability policy declaration")
                    script = safe_path(root, cap["executable"])
                    if not script.is_file():
                        raise ValueError("Capability executable is missing")
                    files[cap["executable"]] = digest(script.read_bytes())
            except (yaml.YAMLError, ValueError, TypeError, KeyError) as exc:
                errors.append(str(exc))
                sidecar = {}
        commit = run_git(root, "rev-parse", "HEAD", check=False) or None
        dirty = run_git(root, "status", "--porcelain", "--", ".", check=False)
        identity = {"source_uri": Path(source["path"]).as_uri(), "source_id": source["id"], "commit": commit,
                    "path": path, "digest": digest(encode(files)), "state": "working-copy" if dirty or not commit else "committed"}
        return {"identity": identity, "instructions": text, "metadata": metadata, "files": files,
                "capabilities": sidecar.get("capabilities", []), "validation": {"normalized": {"valid": bool(metadata.get("name")) and bool(metadata.get("description")), "errors": errors},
                "codex": {"status": "not-executed", "reason": "External validator not configured"}, "claude": {"status": "not-executed", "reason": "External validator not configured"}}}

    def validate(self, source_id: str, path: str) -> dict:
        return self.resolve(source_id, path)["validation"]

    def build_context(self, selections: list[dict], budget: int) -> dict:
        included, excluded, used = [], [], 0
        for selection in selections:
            skill = self.resolve(selection["source_id"], selection["path"])
            expected = selection.get("digest")
            if expected and expected != skill["identity"]["digest"]:
                raise DomainError("skill-changed", "Selected skill changed since approval.", "Review the new digest and approve a new plan/context.")
            size = len(skill["instructions"].encode("utf-8"))
            if used + size > budget:
                excluded.append({"identity": skill["identity"], "reason": "budget"})
            else:
                included.append(skill)
                used += size
        return {"items": included, "excluded": excluded, "bytes_used": used}
