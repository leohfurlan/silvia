"""Bounded tools; all writes produce a durable intent before touching the filesystem."""
from __future__ import annotations

import json
import os
from pathlib import Path

from silvia.core import ActionRequest, DomainError, digest, uid
from silvia.git import owned_path, safe_path


def schemas(writable: bool = True) -> list[dict]:
    entries = [("read_file", "Read an owned text file", {"path": {"type": "string"}}, ["path"]),
               ("list_files", "List owned files", {"path": {"type": "string"}}, ["path"])]
    if writable:
        entries.append(("write_file", "Write an owned UTF-8 text file", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]))
    return [{"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": props, "required": required, "additionalProperties": False}}} for name, description, props, required in entries]


class ToolExecutor:
    def __init__(self, store, harness, artifacts):
        self.store, self.harness, self.artifacts = store, harness, artifacts

    def execute(self, session: dict, item: dict, attempt_id: str, call: dict, *, writable: bool) -> str:
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"]["arguments"])
        except (ValueError, TypeError) as exc:
            raise DomainError("invalid-tool", "Tool arguments must be JSON.") from exc
        if name not in {"read_file", "list_files", "write_file"} or not isinstance(args, dict) or not isinstance(args.get("path"), str):
            raise DomainError("invalid-tool", "Unknown tool or invalid arguments.")
        current = self.store.one("SELECT state,revision FROM sessions WHERE id=?", (session["id"],))
        if current["state"] != "running" or current["revision"] != session["revision"]:
            raise DomainError("cancelled", "Execution was paused, cancelled or superseded.")
        root = Path(session["checkout"])
        if name == "list_files":
            target = safe_path(root, args["path"])
            owners = [safe_path(root, p) for p in item["owned_paths"]]
            if not any(target == p or target in p.parents or p in target.parents for p in owners):
                raise DomainError("ownership", "Listing is outside owned scope.")
            files = []
            for path in sorted(target.rglob("*") if target.is_dir() else [target]):
                if path.is_file():
                    resolved = safe_path(root, path.relative_to(root).as_posix())
                    if any(resolved == p or p in resolved.parents for p in owners):
                        files.append(path.relative_to(root).as_posix())
                if len(files) >= 1000:
                    break
            return "\n".join(files)
        target = owned_path(root, args["path"], item["owned_paths"], writable=name == "write_file")
        action = ActionRequest("file.write" if name == "write_file" else "file.read", session["id"], session["revision"], str(target), actor="agent", work_item=item["id"])
        self.harness.authorize(action)
        if name == "read_file":
            if not target.is_file() or target.stat().st_size > 131072:
                raise DomainError("file-limit", "File is missing or exceeds the 128 KiB tool limit.")
            return self.store.redactor.text(target.read_text(encoding="utf-8"))
        if not writable or not isinstance(args.get("content"), str):
            raise DomainError("authorization", "This agent cannot write files.")
        content = args["content"]
        if len(content.encode()) > 131072:
            raise DomainError("file-limit", "Write exceeds the 128 KiB tool limit.")
        self.store.redactor.reject_secret(content)
        effect = {"id": uid(), "session_id": session["id"], "attempt": attempt_id, "status": "pending", "kind": "file.write", "target": args["path"], "expected_digest": digest(content), "previous_digest": digest(target.read_bytes()) if target.is_file() else None}
        with self.store.transaction():
            self.store.put("effect", effect["id"], effect, session["id"], session["revision"])
            self.store.append(session["id"], "tool.started", effect, actor="agent")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Resolve again after creating parents to catch links appearing during traversal.
        owned_path(root, args["path"], item["owned_paths"], writable=True)
        temporary = target.with_name(target.name + ".silvia-" + uid())
        with temporary.open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        with self.store.transaction():
            effect["status"] = "completed"
            self.store.put("effect", effect["id"], effect, session["id"], session["revision"])
            self.store.append(session["id"], "tool.finished", {"effect_id": effect["id"], "digest": effect["expected_digest"]}, actor="agent")
        return "Wrote " + args["path"]
