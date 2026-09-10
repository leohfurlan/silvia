"""Deterministic fail-closed decisions and atomic, scope-bound grants."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from silvia.core import ActionRequest, DomainError, GateDecision, TERMINAL, digest, encode, now, uid
from silvia.storage import SQLiteStore

LOCAL = frozenset({"session.run", "file.read", "file.write", "agent.invoke", "memory.remember", "memory.forget", "skill.read"})
PROTECTED = frozenset({"plan.approve", "command.execute", "skill.execute", "provider.spend", "session.export", "memory.promote", "memory.forget", "memory.retention", "memory.export", "git.commit", "git.push", "git.pr", "git.merge", "deploy", "migration", "filesystem.delete", "gate.change"})


class HarnessEngine:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def evaluate(self, action: ActionRequest) -> GateDecision:
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (action.session_id,))
        outcome, rule, reason = "deny", "v1.unknown", "Unknown capability."
        if not session or action.objective_revision != session["revision"]:
            rule, reason = "v1.revision", "Session or objective revision is no longer current."
        elif session["state"] in TERMINAL and action.capability != "session.export":
            rule, reason = "v1.terminal", "Terminal sessions cannot execute new work."
        elif action.capability in PROTECTED:
            outcome, rule, reason = "require-approval", "v1.protected", "Explicit scoped authorization is required."
        elif action.capability in LOCAL:
            outcome, rule, reason = "allow", "v1.local", "Local capability is permitted within its validated scope."
        return GateDecision(outcome, (rule,), (reason,), action)

    def request(self, action: ActionRequest) -> dict:
        decision = self.evaluate(action)
        with self.store.transaction():
            value = {"id": action.action_id, **asdict(decision), "status": "pending"}
            self.store.put("approval", action.action_id, value, action.session_id, action.objective_revision)
            self.store.append(action.session_id, "gate.evaluated", value, actor=action.actor)
        return value

    def grant(self, approval_id: str, *, scope: str = "invocation", seconds: int = 900, uses: int = 1, actor: str = "user") -> dict:
        if actor != "user" or scope not in {"invocation", "work-item", "session"} or not 1 <= seconds <= 86400 or uses < 1:
            raise DomainError("authorization", "Invalid human approval scope, duration or uses.")
        with self.store.transaction():
            approval = self.store.record("approval", approval_id)
            if not approval or approval["status"] != "pending":
                raise DomainError("authorization", "Approval is not pending.")
            action = ActionRequest(**approval["request"])
            if self.evaluate(action).outcome != "require-approval":
                raise DomainError("authorization", "Request no longer qualifies for approval.")
            if action.capability in PROTECTED and uses != 1:
                raise DomainError("authorization", "Protected actions require one-use authorization.")
            grant = {"id": uid(), "approval_id": approval_id, "request": asdict(action), "scope": scope, "uses": uses,
                     "remaining": uses, "responsible": actor, "created_at": now(), "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()}
            approval["status"] = "approved"
            self.store.put("grant", grant["id"], grant, action.session_id, action.objective_revision)
            self.store.put("approval", approval_id, approval, action.session_id, action.objective_revision)
            self.store.append(action.session_id, "authorization.granted", grant, actor="user")
        return grant

    def deny(self, approval_id: str, reason: str) -> dict:
        with self.store.transaction():
            value = self.store.record("approval", approval_id)
            if not value or value["status"] != "pending":
                raise DomainError("authorization", "Approval is not pending.")
            value.update(status="denied", reason=reason)
            action = value["request"]
            self.store.put("approval", approval_id, value, action["session_id"], action["objective_revision"])
            self.store.append(action["session_id"], "authorization.denied", {"approval_id": approval_id, "reason": reason}, actor="user")
        return value

    def consume(self, grant_id: str, action: ActionRequest) -> dict:
        with self.store.transaction():
            grant = self.store.record("grant", grant_id)
            if not grant or grant["remaining"] < 1 or grant["expires_at"] <= now():
                raise DomainError("authorization", "Authorization is absent, expired or already consumed.")
            original = grant["request"]
            fields = ("capability", "session_id", "objective_revision", "target", "parameters")
            if grant["scope"] == "invocation":
                fields += ("action_id",)
            if grant["scope"] in {"invocation", "work-item"}:
                fields += ("work_item",)
            current = asdict(action)
            if any(current[k] != original[k] for k in fields) or self.evaluate(action).outcome != "require-approval":
                raise DomainError("authorization", "Authorization does not match the current action, target or revision.")
            grant["remaining"] -= 1
            self.store.put("grant", grant_id, grant, action.session_id, action.objective_revision)
            use = {"id": uid(), "grant_id": grant_id, "action": current, "timestamp": now()}
            self.store.put("authorization-use", use["id"], use, action.session_id, action.objective_revision)
            self.store.append(action.session_id, "authorization.consumed", use)
            return use

    def authorize(self, action: ActionRequest) -> dict:
        decision = self.evaluate(action)
        if decision.outcome == "allow":
            return {"outcome": "allow", "rules": decision.rule_ids}
        if decision.outcome == "deny":
            raise DomainError("authorization", decision.reasons[0])
        # Reuse the exact persisted request, never a model-supplied grant identity.
        for approval in self.store.records("approval", action.session_id):
            old = approval["request"]
            if all(old[k] == asdict(action)[k] for k in ("capability", "session_id", "objective_revision", "target", "parameters", "work_item")):
                if approval["status"] == "approved":
                    for grant in self.store.records("grant", action.session_id):
                        if grant["approval_id"] == approval["id"] and grant["remaining"] and grant["expires_at"] > now():
                            return self.consume(grant["id"], ActionRequest(**old))
                if approval["status"] == "pending":
                    raise DomainError("require-approval", "Action is waiting for human approval.", "Inspect and approve or deny the request, then run again.", approval_id=approval["id"])
        request = self.request(action)
        raise DomainError("require-approval", "Action requires explicit approval.", "Inspect and approve or deny the request, then run again.", approval_id=request["id"])

    def assess_completion(self, session: dict, current_version: str) -> dict:
        evidence = [x for x in self.store.records("evidence", session["id"]) if x["revision"] == session["revision"] and x["version"] == current_version and x["result"] == "passed"]
        work = [x for x in self.store.records("work-item", session["id"]) if x["revision"] == session["revision"]]
        gaps = []
        if not work or any(x["status"] != "completed" for x in work):
            gaps.append("Not all work items completed.")
        for item in work:
            if not any(e.get("work_item") == item["id"] and e["kind"] == "review" for e in evidence):
                gaps.append(f"Missing independent review for {item['id']} at the current version.")
            for command in item["item"]["verification"]:
                if not any(e.get("work_item") == item["id"] and e.get("command") == command for e in evidence):
                    gaps.append(f"Missing current verification for {item['id']}.")
        for criterion in session["objective"]["criteria"]:
            if not any(criterion in e.get("criteria", []) for e in evidence):
                gaps.append(f"Criterion requires evidence: {criterion}")
        if any(x["status"] in {"pending", "uncertain", "running"} for k in ("effect", "attempt") for x in self.store.records(k, session["id"])):
            gaps.append("Uncertain operations require reconciliation.")
        return {"satisfied": not gaps, "gaps": gaps, "version": current_version, "evidence_ids": [e["id"] for e in evidence]}
