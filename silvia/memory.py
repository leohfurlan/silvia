"""Local textual memory: explicit provenance and deterministic bounded recall."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from silvia.core import ActionRequest, DomainError, encode, now, uid
from silvia.storage import SQLiteStore


class MemoryStore:
    def __init__(self, store: SQLiteStore, harness):
        self.store, self.harness = store, harness

    def _session(self, session_id: str) -> dict:
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not session:
            raise DomainError("not-found", "Memory operation requires an existing session.")
        return session

    def _authorize(self, capability: str, session: dict, target: str, **parameters) -> None:
        self.harness.authorize(ActionRequest(capability, session["id"], session["revision"], target, parameters=parameters))

    @staticmethod
    def _belongs_to_session(value: dict, session: dict) -> bool:
        if value["scope"] == "session":
            return value["session_id"] == session["id"]
        if value["scope"] == "project":
            return value["project_id"] == session["project_id"]
        return value["scope"] == "user"

    def propose(self, content: str, *, session_id: str, scope: str = "session", type: str = "fact",
                source: str = "user", evidence: str | None = None, key: str | None = None, expires_at: str | None = None) -> dict:
        if not content.strip() or scope not in {"session", "project", "user"} or type not in {"fact", "decision", "preference", "learning"} or source not in {"user", "artifact", "evidence", "agent"}:
            raise DomainError("invalid-memory", "Memory content, scope, type or source is invalid.")
        self.store.redactor.reject_secret(content)
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not session:
            raise DomainError("not-found", "Memory provenance requires an existing session.")
        if expires_at:
            try:
                date = datetime.fromisoformat(expires_at)
                if date.tzinfo is None:
                    raise ValueError()
            except ValueError as exc:
                raise DomainError("invalid-memory", "Validity must be an ISO timestamp with timezone.") from exc
        value = {"id": uid(), "content": content, "scope": scope, "type": type, "source": source,
                 "session_id": session_id, "project_id": session["project_id"], "status": "candidate", "created_at": now(),
                 "expires_at": expires_at, "evidence": evidence, "key": key, "confidence": "unvalidated", "version": 1}
        with self.store.transaction():
            self.store.db.execute("INSERT INTO memory VALUES(?,?,?,?,?,?,?)", (value["id"], session["project_id"], session_id, scope, "candidate", content, encode(value)))
            # Events intentionally omit memory content so forgetting does not leave an immutable copy.
            self.store.append(session_id, "memory.proposed", {"id": value["id"], "scope": scope, "source": source})
        return value

    def promote(self, candidate_id: str, *, actor: str = "user") -> dict:
        if actor != "user":
            raise DomainError("authorization", "Memory promotion requires explicit human validation.")
        row = self.store.one("SELECT * FROM memory WHERE id=?", (candidate_id,))
        if not row or row["status"] != "candidate":
            raise DomainError("invalid-memory", "Memory is not a candidate.")
        value = json.loads(row["data"])
        session = self._session(value["session_id"])
        self._authorize("memory.promote", session, candidate_id, scope=value["scope"])
        with self.store.transaction():
            value.update(status="promoted", confidence="human-validated", promoted_at=now())
            self.store.db.execute("UPDATE memory SET status='promoted',data=? WHERE id=?", (encode(value), candidate_id))
            self.store.db.execute("INSERT INTO memory_search VALUES(?,?)", (candidate_id, value["content"]))
            self.store.append(value["session_id"], "memory.promoted", {"id": candidate_id, "scope": value["scope"]}, actor="user")
        return value

    def recall(self, *, session_id: str, query: str = "", budget: int = 4000, types: tuple[str, ...] = ()) -> dict:
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not session or budget < 0:
            raise DomainError("validation", "Recall requires a session and nonnegative context budget.")
        matches = None
        words = re.findall(r"\w+", query, flags=re.UNICODE)
        if words:
            expression = " OR ".join('"' + w.replace('"', '""') + '"' for w in words)
            matches = {r["id"] for r in self.store.all("SELECT id FROM memory_search WHERE memory_search MATCH ?", (expression,))}
        eligible, excluded, conflicts = [], [], []
        for row in self.store.all("SELECT * FROM memory WHERE status='promoted' ORDER BY id"):
            value = json.loads(row["data"])
            reason = None
            if value["scope"] == "session" and value["session_id"] != session_id:
                reason = "session-scope"
            elif value["scope"] == "project" and value["project_id"] != session["project_id"]:
                reason = "project-scope"
            elif value["expires_at"] and value["expires_at"] <= now():
                reason = "expired"
            elif types and value["type"] not in types:
                reason = "type"
            elif matches is not None and value["id"] not in matches:
                reason = "lexical"
            if reason:
                excluded.append({"id": value["id"], "reason": reason})
            else:
                value["score"] = {"scope": {"session": 3, "project": 2, "user": 1}[value["scope"]], "source": 1, "lexical": len(set(words) & set(re.findall(r"\w+", value["content"]))) }
                eligible.append(value)
        groups: dict[str, list] = {}
        for value in eligible:
            if value["key"]:
                groups.setdefault(value["key"], []).append(value)
        conflict_ids = set()
        for key, values in groups.items():
            if len({v["content"] for v in values}) > 1:
                ids = [v["id"] for v in values]
                conflicts.append({"key": key, "ids": ids})
                conflict_ids.update(ids)
        included, used = [], 0
        for value in sorted(eligible, key=lambda v: (-v["score"]["scope"], -v["score"]["lexical"], v["id"])):
            size = len(value["content"].encode("utf-8"))
            if value["id"] in conflict_ids:
                excluded.append({"id": value["id"], "reason": "conflict"})
            elif used + size > budget:
                excluded.append({"id": value["id"], "reason": "budget"})
            else:
                included.append(value)
                used += size
        return {"items": included, "conflicts": conflicts, "excluded": excluded, "bytes_used": used, "budget_bytes": budget}

    def forget(self, memory_id: str, *, session_id: str) -> dict:
        session = self._session(session_id)
        row = self.store.one("SELECT * FROM memory WHERE id=?", (memory_id,))
        value = json.loads(row["data"]) if row else None
        if value and not self._belongs_to_session(value, session):
            raise DomainError("memory-scope", "Memory does not belong to the selected session or project scope.")
        self._authorize("memory.forget", session, memory_id, scope=value["scope"] if value else "unknown")
        with self.store.transaction():
            receipt = {"id": memory_id, "deleted": bool(row), "timestamp": now()}
            self.store.db.execute("DELETE FROM memory_search WHERE id=?", (memory_id,))
            self.store.db.execute("DELETE FROM memory WHERE id=?", (memory_id,))
            # Context snapshots hold selected content in revocable records, never in events.
            for context in self.store.records("context"):
                changed = False
                for memory in context.get("memories", []):
                    if memory["id"] == memory_id:
                        memory["content"] = "[FORGOTTEN]"
                        changed = True
                if changed:
                    context["redacted_after_forget"] = True
                    self.store.put("context", context["id"], context, context["session_id"], context["revision"])
            self.store.append(session_id, "memory.forgotten", receipt, actor="user")
        return receipt

    def apply_retention(self, *, session_id: str, days: int = 90) -> dict:
        if days < 1:
            raise DomainError("validation", "Retention days must be positive.")
        session = self._session(session_id)
        self._authorize("memory.retention", session, session_id, days=days)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self.store.all("SELECT id,data FROM memory WHERE status='candidate' AND session_id=?", (session_id,))
        removed = []
        with self.store.transaction():
            for row in rows:
                if json.loads(row["data"])["created_at"] >= cutoff:
                    continue
                self.store.db.execute("DELETE FROM memory_search WHERE id=?", (row["id"],))
                self.store.db.execute("DELETE FROM memory WHERE id=?", (row["id"],))
                removed.append(row["id"])
            self.store.append(session_id, "memory.retention_applied", {"cutoff": cutoff, "deleted_candidate_ids": removed}, actor="user")
        return {"cutoff": cutoff, "deleted_candidates": removed, "promoted_memories_preserved": True}

    def export(self, session_id: str) -> list[dict]:
        session = self._session(session_id)
        self._authorize("memory.export", session, session_id)
        return self.recall(session_id=session_id, budget=10_000_000)["items"]
