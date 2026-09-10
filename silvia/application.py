"""Composition root shared by CLI, interactive mode and TUI."""
from pathlib import Path

from silvia.agents import AgentRuntime
from silvia.agents.context import ContextBuilder
from silvia.config import data_home, load_config
from silvia.core import DomainError, now
from silvia.evidence import ArtifactStore, EvidenceStore
from silvia.git import fingerprint
from silvia.harness import HarnessEngine
from silvia.memory import MemoryStore
from silvia.reports import ProjectionEngine
from silvia.sandbox import SandboxRunner
from silvia.sessions import SessionRuntime
from silvia.skills import SkillRegistry
from silvia.storage import SQLiteStore


class Application:
    def __init__(self, *, home: Path | None = None, project: Path | None = None, migrate: bool = False):
        self.home = home or data_home()
        self.store = SQLiteStore(self.home / "silvia.db", migrate=migrate)
        self.sessions = SessionRuntime(self.store, self.home / "worktrees")
        self.harness = HarnessEngine(self.store)
        self.skills = SkillRegistry(self.store)
        self.memory = MemoryStore(self.store, self.harness)
        self.artifacts = ArtifactStore(self.store)
        self.sandbox = SandboxRunner(self.store, self.harness, self.skills, self.artifacts)
        self.evidence = EvidenceStore(self.store, self.artifacts)
        self.context = ContextBuilder(self.store, self.memory, self.skills)
        self.projections = ProjectionEngine(self.store, self.sessions, self.artifacts, self.harness)
        self.project = project
        self._agents = None

    @property
    def agents(self):
        if self._agents is None:
            self._agents = AgentRuntime(self.store, self.sessions, self.harness, self.context, self.artifacts, self.evidence, load_config(self.project), sandbox=self.sandbox)
        return self._agents

    def session_id(self, id: str | None = None) -> str:
        if id:
            self.sessions.inspect_session(id)
            return id
        values = self.sessions.list_sessions()
        if self.project:
            location = self.store.one("SELECT project_id FROM locations WHERE path=?", (str(self.project.resolve()),))
            if location:
                values = [v for v in values if v["project_id"] == location["project_id"]]
        active = [v for v in values if v["state"] not in {"completed", "cancelled", "archived"}]
        if len(active) == 1:
            return active[0]["id"]
        if len(values) == 1:
            return values[0]["id"]
        raise DomainError("ambiguous-session", "Specify a session ID.", "Use silvia session list to select a session.")

    async def cancel_session(self, id: str, reason: str = "user cancelled") -> dict:
        session = self.sessions.cancel_session(id, reason)
        await self.sandbox.request_stop(id, timeout=5)
        return session
    def confirm_completion(self, id: str) -> dict:
        with self.store.transaction():
            session = self.sessions.inspect_session(id)
            assessment = self.harness.assess_completion(session, fingerprint(Path(session["checkout"])))
            if not assessment["satisfied"]:
                raise DomainError("require-evidence", "Completion criteria are not satisfied.", gaps=assessment["gaps"])
            if session["runner"] or session["state"] != "waiting-for-action":
                raise DomainError("invalid-state", "Session must be stopped and waiting for human completion.")
            self.store.append(id, "gate.completion_assessed", assessment)
            self.sessions._transition(id, "waiting-for-action", "completed", "human confirmed completion")
        return self.sessions.inspect_session(id)

    def close(self):
        self.store.close()
