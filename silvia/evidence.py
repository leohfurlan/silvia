"""Digest-addressed artifacts and evidence bound to an evaluated checkout."""
from __future__ import annotations

import os
from pathlib import Path

from silvia.core import DomainError, digest, now, uid
from silvia.storage import SQLiteStore


class ArtifactStore:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def root(self, session_id: str) -> Path:
        row = self.store.one("SELECT p.root FROM projects p JOIN sessions s ON s.project_id=p.id WHERE s.id=?", (session_id,))
        if not row:
            raise DomainError("not-found", "Session does not exist.")
        return Path(row["root"]) / ".silvia" / "artifacts" / session_id

    def store_artifact(self, session_id: str, content: str, media_type: str = "text/plain") -> dict:
        data = self.store.redactor.text(content).encode("utf-8")
        hash = digest(data)
        root = self.root(session_id)
        root.mkdir(parents=True, exist_ok=True)
        target = root / hash
        if not target.exists():
            temp = root / (hash + "." + uid() + ".tmp")
            with temp.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
        elif digest(target.read_bytes()) != hash:
            raise DomainError("integrity-failed", "Stored artifact content has changed.")
        ref = {"digest": hash, "media_type": media_type, "size": len(data), "location": "artifacts/" + hash}
        with self.store.transaction():
            self.store.put("artifact", session_id + ":" + hash, ref, session_id)
            self.store.append(session_id, "artifact.stored", ref)
        return ref

    def read(self, session_id: str, hash: str) -> bytes:
        if len(hash) != 64 or any(c not in "0123456789abcdef" for c in hash):
            raise DomainError("invalid-artifact", "Artifact identity is not a SHA-256 digest.")
        ref = self.store.record("artifact", session_id + ":" + hash)
        if not ref:
            raise DomainError("not-found", "Artifact is not associated with this session.")
        try:
            data = (self.root(session_id) / hash).read_bytes()
        except OSError as exc:
            raise DomainError("integrity-failed", "Artifact file is missing.") from exc
        if digest(data) != hash or len(data) != ref["size"]:
            raise DomainError("integrity-failed", "Artifact digest or size does not match.")
        return data


class EvidenceStore:
    def __init__(self, store: SQLiteStore, artifacts: ArtifactStore):
        self.store, self.artifacts = store, artifacts

    def record(self, session: dict, *, version: str, command: list[str], attempt: str, work_item: str,
               result: str, output: str, started_at: str, kind: str = "command", criteria: list[str] | None = None) -> dict:
        if result not in {"passed", "failed", "uncertain"} or not version:
            raise DomainError("invalid-evidence", "Evidence needs an evaluated version and explicit result.")
        ref = self.artifacts.store_artifact(session["id"], output)
        record = {"id": uid(), "revision": session["revision"], "session_id": session["id"], "version": version,
                  "command": command, "attempt": attempt, "work_item": work_item, "result": result, "kind": kind,
                  "started_at": started_at, "finished_at": now(), "environment": {"platform": os.name},
                  "artifact": ref, "criteria": criteria or []}
        with self.store.transaction():
            self.store.put("evidence", record["id"], record, session["id"], session["revision"])
            self.store.append(session["id"], "evidence.recorded", record)
        return record
