"""Fail-closed skill capability execution behind one sandbox seam."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import url2pathname

from silvia.core import ActionRequest, DomainError, digest, encode, now, uid
from silvia.git import safe_path


@dataclass(frozen=True)
class SandboxRequest:
    session_id: str
    revision: int
    source_id: str
    skill_path: str
    skill_digest: str
    capability: str
    executable: str
    argv: tuple[str, ...]
    filesystem: dict
    network: tuple[str, ...]
    platforms: tuple[str, ...]
    timeout: int = 900


@dataclass(frozen=True)
class SandboxResult:
    status: str
    exit_code: int | None
    output: str
    isolation: dict


class SandboxAdapter(Protocol):
    def prepare(self, request: SandboxRequest) -> dict: ...
    async def run(self, request: SandboxRequest) -> SandboxResult: ...
    async def request_stop(self, request: SandboxRequest) -> bool: ...


class UnavailableSandboxAdapter:
    """Production default: absence of containment is a denial, never host fallback."""
    def prepare(self, request: SandboxRequest) -> dict:
        raise DomainError("sandbox-unavailable", "No compatible sandbox adapter is configured.", "Install or configure a supported sandbox adapter; direct host execution is disabled.")

    async def run(self, request: SandboxRequest) -> SandboxResult:
        raise AssertionError("Unavailable sandbox must fail during preflight")
    async def request_stop(self, request: SandboxRequest) -> bool:
        return False


class SandboxRunner:
    def __init__(self, store, harness, skills, artifacts, adapter: SandboxAdapter | None = None):
        self.store, self.harness, self.skills, self.artifacts = store, harness, skills, artifacts
        self.adapter = adapter or UnavailableSandboxAdapter()
        self.active: dict[str, tuple[SandboxAdapter, SandboxRequest]] = {}

    @staticmethod
    def _skill_root(identity: dict) -> Path:
        parsed = urlparse(identity["source_uri"])
        if parsed.scheme != "file":
            raise DomainError("sandbox-incompatible", "Only registered local skill sources can execute capabilities.")
        source = Path(url2pathname(parsed.path)).resolve()
        return safe_path(source, identity["path"])

    @staticmethod
    def _platform_supported(platforms: tuple[str, ...]) -> bool:
        current = {sys.platform.casefold(), os.name.casefold(), "windows" if os.name == "nt" else "posix"}
        return not platforms or bool(current.intersection(value.casefold() for value in platforms))

    @staticmethod
    def _policy_digest(request: SandboxRequest) -> str:
        return digest(encode({
            "executable": request.executable,
            "argv": request.argv,
            "filesystem": request.filesystem,
            "network": request.network,
            "platforms": request.platforms,
            "timeout": request.timeout,
        }))

    async def request_stop(self, session_id: str, timeout: float = 5) -> bool:
        active = self.active.get(session_id)
        if not active:
            return False
        adapter, request = active
        stop = getattr(adapter, "request_stop", None)
        if not stop:
            return False
        try:
            return bool(await asyncio.wait_for(stop(request), timeout=max(0, timeout)))
        except (asyncio.TimeoutError, OSError, DomainError):
            return False
    async def run(self, session_id: str, source_id: str, skill_path: str, capability: str) -> dict:
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not session:
            raise DomainError("not-found", "Skill capability requires an existing session.")
        skill = self.skills.resolve(source_id, skill_path)
        matches = [value for value in skill["capabilities"] if value["name"] == capability]
        if len(matches) != 1:
            raise DomainError("capability-denied", "Capability is absent, duplicated or denied by an invalid sidecar.")
        declared = matches[0]
        platforms = tuple(declared["platforms"])
        if not self._platform_supported(platforms):
            raise DomainError("sandbox-incompatible", "Capability does not support this platform.")
        executable = safe_path(self._skill_root(skill["identity"]), declared["executable"])
        request = SandboxRequest(
            session_id=session_id,
            revision=session["revision"],
            source_id=source_id,
            skill_path=skill_path,
            skill_digest=skill["identity"]["digest"],
            capability=capability,
            executable=str(executable),
            argv=(str(executable), *declared["argv"]),
            filesystem=declared["filesystem"],
            network=tuple(declared["network"]),
            platforms=platforms,
        )
        policy_digest = self._policy_digest(request)
        preflight = self.adapter.prepare(request)
        if not isinstance(preflight, dict) or preflight.get("status") != "ready" or preflight.get("containment") is not True or preflight.get("policy_digest") != policy_digest:
            raise DomainError("sandbox-incompatible", "Sandbox adapter cannot prove enforcement of the requested policy.")
        parameters = json.loads(encode({"request": asdict(request), "preflight": preflight}))
        action = ActionRequest("skill.execute", session_id, session["revision"], f"{source_id}:{skill_path}:{capability}", parameters=parameters)
        self.harness.authorize(action)
        effect = {"id": uid(), "session_id": session_id, "revision": session["revision"], "kind": "skill.execute", "status": "pending", "target": action.target, "skill_digest": request.skill_digest, "preflight": preflight, "started_at": now()}
        with self.store.transaction():
            self.store.put("effect", effect["id"], effect, session_id, session["revision"])
            self.store.append(session_id, "skill.execution_started", {"effect_id": effect["id"], "target": action.target, "skill_digest": request.skill_digest, "preflight": preflight}, actor="user")
        self.active[session_id] = (self.adapter, request)
        try:
            result = await asyncio.wait_for(self.adapter.run(request), timeout=request.timeout)
            valid_exit = (
                (result.status == "completed" and result.exit_code == 0)
                or (result.status == "failed" and result.exit_code not in {None, 0})
                or result.status == "uncertain"
            )
            if not valid_exit or result.isolation.get("policy_digest") != policy_digest:
                raise DomainError("sandbox-invalid", "Sandbox adapter returned an invalid result or policy evidence.")
        except asyncio.TimeoutError:
            result = SandboxResult("uncertain", None, "Sandbox execution timed out.", preflight)
        except asyncio.CancelledError:
            result = SandboxResult("uncertain", None, "Sandbox execution was interrupted.", preflight)
        except (DomainError, OSError, UnicodeError) as error:
            result = SandboxResult("uncertain", None, f"Sandbox result is uncertain: {error}", preflight)
        finally:
            self.active.pop(session_id, None)
        state = self.store.one("SELECT state FROM sessions WHERE id=?", (session_id,))
        if state and state["state"] in {"cancelled", "archived"} and result.status != "uncertain":
            result = SandboxResult("uncertain", result.exit_code, "Session became terminal while the sandbox effect was active.", result.isolation)
        output = self.store.redactor.text(result.output[:131072])
        artifact = self.artifacts.store_artifact(session_id, output) if output else None
        effect.update(status=result.status, exit_code=result.exit_code, artifact=artifact, isolation=result.isolation, finished_at=now(), output_truncated=len(result.output) > 131072)
        with self.store.transaction():
            self.store.put("effect", effect["id"], effect, session_id, session["revision"])
            self.store.append(session_id, "skill.execution_finished", {"effect_id": effect["id"], "status": effect["status"], "exit_code": effect["exit_code"], "artifact": artifact}, actor="user")
        if result.status == "uncertain":
            raise DomainError("reconciliation-required", "Sandbox execution has an uncertain result.", effect_id=effect["id"])
        if result.status == "failed":
            raise DomainError("skill-failed", "Sandboxed skill capability failed.", effect_id=effect["id"], exit_code=result.exit_code)
        return effect