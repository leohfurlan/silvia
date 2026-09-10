"""Persistent project/session service. Resume never invokes agents or repeats effects."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from silvia.core import DomainError, ObjectiveInput, TERMINAL, TRANSITIONS, encode, now, uid
from silvia.git import baseline, create_worktree, fingerprint, repository
from silvia.storage import SQLiteStore


class SessionRuntime:
    def __init__(self, store: SQLiteStore, worktrees: Path):
        self.store, self.worktrees = store, worktrees

    def register_project(self, root: Path, *, project_id: str | None = None) -> dict:
        info = repository(root)
        existing = self.store.one("SELECT p.* FROM projects p JOIN locations l ON l.project_id=p.id WHERE l.path=?", (info["root"],))
        if existing:
            return existing
        common = self.store.one("SELECT * FROM projects WHERE git_common=?", (info["git_common"],)) if info["git_common"] else None
        if project_id:
            common = self.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
            if common is None:
                raise DomainError("project-not-found", "The selected project does not exist.")
        if not common and info["identity"] and self.store.one("SELECT 1 FROM projects WHERE identity=?", (info["identity"],)):
            raise DomainError("ambiguous-project", "Another clone has the same repository identity.", "Use init --project-id to explicitly associate the clone.")
        with self.store.transaction():
            if not common:
                common = {"id": uid(), **info, "created_at": now()}
                self.store.db.execute("INSERT INTO projects VALUES(:id,:root,:git_common,:identity,:created_at)", common)
            self.store.db.execute("INSERT INTO locations VALUES(?,?)", (info["root"], common["id"]))
        return common

    def new_session(self, project_id: str, name: str, objective: ObjectiveInput, checkout_policy: str = "worktree") -> dict:
        project = self.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
        if not project:
            raise DomainError("project-not-found", "Project does not exist.")
        if checkout_policy not in {"worktree", "direct"}:
            raise DomainError("validation", "Checkout policy must be worktree or direct.")
        self.store.redactor.reject_secret(encode(asdict(objective)))
        id, root = uid(), Path(project["root"])
        before = baseline(root)
        checkout = self.worktrees / id if project["git_common"] and checkout_policy == "worktree" else root
        # The intent is retained outside session creation so a failed Git operation is diagnosable.
        with self.store.transaction():
            self.store.put("checkout-intent", id, {"id": id, "root": str(root), "destination": str(checkout), "status": "pending"})
        if checkout != root:
            create_worktree(root, checkout, id)
        try:
            with self.store.transaction():
                stamp = now()
                self.store.db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,NULL,NULL)",
                                      (id, project_id, self.store.redactor.text(name), "created", 1, str(checkout.resolve()), encode(self.store.redactor.clean(before)), stamp, stamp))
                self.store.db.execute("INSERT INTO objectives VALUES(?,?,?,?)", (id, 1, encode(asdict(objective)), stamp))
                self.store.db.execute("INSERT OR IGNORE INTO locations VALUES(?,?)", (str(checkout.resolve()), project_id))
                self.store.put("checkout-intent", id, {"id": id, "destination": str(checkout), "status": "completed"})
                self.store.append(id, "session.created", {"name": name, "checkout_policy": checkout_policy, "baseline": before}, actor="user")
        except sqlite3.IntegrityError as exc:
            raise DomainError("checkout-conflict", "Another session owns this checkout.", "Use an isolated worktree. Any newly created worktree was preserved.") from exc
        return self.inspect_session(id)

    def inspect_session(self, session_id: str) -> dict:
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not session:
            raise DomainError("not-found", "Session does not exist.", "Use silvia session list.")
        revision = self.store.one("SELECT data FROM objectives WHERE session_id=? AND revision=?", (session_id, session["revision"]))
        if not revision:
            raise DomainError("corrupt-session", "Current objective revision is missing.")
        session["objective"], session["baseline"] = json.loads(revision["data"]), json.loads(session["baseline"])
        session["cursor"] = self.store.one("SELECT coalesce(max(sequence),0) AS n FROM events WHERE session_id=?", (session_id,))["n"]
        return session

    def list_sessions(self) -> list[dict]:
        return self.store.all("SELECT id,project_id,name,state,revision,checkout,updated_at FROM sessions ORDER BY created_at DESC")

    def revise_objective(self, session_id: str, expected_revision: int, objective: ObjectiveInput) -> dict:
        self.store.redactor.reject_secret(encode(asdict(objective)))
        with self.store.transaction():
            session = self.inspect_session(session_id)
            if session["revision"] != expected_revision:
                raise DomainError("concurrent-revision", "Objective revision changed.")
            if session["state"] in TERMINAL or session["state"] == "running":
                raise DomainError("invalid-state", "Pause and stop execution before revising the objective.")
            revision = expected_revision + 1
            self.store.db.execute("INSERT INTO objectives VALUES(?,?,?,?)", (session_id, revision, encode(asdict(objective)), now()))
            self.store.db.execute("UPDATE sessions SET revision=?,state='planning',updated_at=? WHERE id=?", (revision, now(), session_id))
            self.store.append(session_id, "objective.revised", {"previous_revision": expected_revision, "objective": asdict(objective), "invalidated": "previous plans, grants and evidence"}, actor="user")
        return self.inspect_session(session_id)

    def transition(self, session_id: str, expected_state: str, target: str, reason: str) -> dict:
        if target == "completed":
            raise DomainError("require-evidence", "Use confirm_completion with a fresh completion assessment.")
        with self.store.transaction():
            self._transition(session_id, expected_state, target, reason)
        return self.inspect_session(session_id)

    def _transition(self, id: str, expected: str, target: str, reason: str):
        session = self.inspect_session(id)
        if session["state"] != expected:
            raise DomainError("concurrent-state", "Session state changed.")
        if target not in TRANSITIONS[expected]:
            raise DomainError("invalid-transition", f"Cannot transition from {expected} to {target}.")
        self.store.db.execute("UPDATE sessions SET state=?,updated_at=? WHERE id=?", (target, now(), id))
        self.store.append(id, "session.transitioned", {"from": expected, "to": target, "reason": reason}, actor="user")

    def pause(self, id: str) -> dict:
        session = self.inspect_session(id)
        if session["state"] == "waiting-for-action":
            return session
        return self.transition(id, session["state"], "waiting-for-action", "pause requested")

    def cancel_session(self, id: str, reason: str = "user cancelled") -> dict:
        session = self.inspect_session(id)
        if session["state"] in TERMINAL:
            raise DomainError("already-terminal", "Session is already terminal.")
        return self.transition(id, session["state"], "cancelled", reason)

    def resume_session(self, id: str) -> dict:
        with self.store.transaction():
            session = self.inspect_session(id)
            if session["runner"]:
                from silvia.agents.leases import alive
                if alive(session["runner"]):
                    raise DomainError("runner-active", "A live process owns this session.", "Use watch, pause or cancel instead of resume.")
            if not Path(session["checkout"]).is_dir():
                raise DomainError("checkout-missing", "Session checkout is missing; no action was repeated.")
            uncertain = []
            for attempt in self.store.records("attempt", id):
                if attempt["status"] in {"running", "uncertain"}:
                    attempt["status"] = "uncertain"
                    self.store.put("attempt", attempt["id"], attempt, id, attempt["revision"])
                    uncertain.append(attempt["id"])
            effects = [x for x in self.store.records("effect", id) if x["status"] == "pending"]
            if session["state"] == "running":
                self._transition(id, "running", "waiting-for-action", "interrupted process; reconciliation required")
            self.store.db.execute("UPDATE sessions SET runner=NULL,heartbeat=NULL WHERE id=?", (id,))
            view = {"uncertain_attempts": uncertain, "uncertain_effects": effects, "fingerprint": fingerprint(Path(session["checkout"])), "confirmation_required": True}
            self.store.append(id, "session.reconciled", view)
        return {"session": self.inspect_session(id), **view}

    def reconcile(self, id: str, record_id: str, resolution: str, reason: str) -> dict:
        if resolution not in {"not-executed", "completed", "abandoned"} or not reason.strip():
            raise DomainError("validation", "Reconciliation requires a resolution and evidence/reason.")
        with self.store.transaction():
            session = self.inspect_session(id)
            if session["runner"]:
                raise DomainError("runner-active", "Reconcile only after the runner stops.")
            kind = "attempt" if self.store.record("attempt", record_id) else "effect"
            record = self.store.record(kind, record_id)
            if not record or record.get("session_id") != id or record["status"] not in {"uncertain", "pending"}:
                raise DomainError("validation", "Record is not an uncertain operation in this session.")
            record.update(status="reconciled", resolution=resolution, reason=reason)
            self.store.put(kind, record_id, record, id, session["revision"])
            # Reconciliation never fabricates passing verification or agent completion.
            self.store.append(id, "session.effect_reconciled", {"kind": kind, "record_id": record_id, "resolution": resolution, "reason": reason}, actor="user")
        return record
