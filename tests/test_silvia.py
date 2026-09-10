"""Public integration tests: real SQLite, filesystem, Git, CLI and hostile exports."""
import asyncio
import inspect
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from silvia.application import Application
from silvia.core import ActionRequest, DomainError, ObjectiveInput, digest, encode, uid
from silvia.git import fingerprint, owned_path
from silvia.providers import ProviderReply
from silvia.sandbox import SandboxResult
from silvia.security import Redactor
from silvia.storage import InProcessStore, SQLiteStore


def _sandbox_policy_digest(request):
    return digest(encode({
        "executable": request.executable,
        "argv": request.argv,
        "filesystem": request.filesystem,
        "network": request.network,
        "platforms": request.platforms,
        "timeout": request.timeout,
    }))


class FakeSandboxAdapter:
    def __init__(self, handler=None):
        self.handler = handler
        self.requests = []
        self.stop_requested = False

    def prepare(self, request):
        return {
            "status": "ready",
            "adapter": "fake",
            "containment": True,
            "policy_digest": _sandbox_policy_digest(request),
        }

    async def run(self, request):
        self.requests.append(request)
        value = self.handler(request) if self.handler else SandboxResult(
            "completed",
            0,
            "",
            {"adapter": "fake", "isolation": "test-double", "policy_digest": _sandbox_policy_digest(request)},
        )
        return await value if inspect.isawaitable(value) else value

    async def request_stop(self, request):
        self.stop_requested = True
        return True

class LocalCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.app = Application(home=self.root / "home", project=self.project)
        self.addCleanup(self.app.close)
        project = self.app.sessions.register_project(self.project)
        self.session = self.app.sessions.new_session(project["id"], "Test", ObjectiveInput("Implement a greeting", ("greeting returns hello",)), "direct")
        self.id = self.session["id"]

    def tearDown(self):
        pass

    def approve(self, operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except DomainError as error:
            self.assertEqual(error.code, "require-approval")
            self.app.harness.grant(error.details["approval_id"])
            return operation(*args, **kwargs)

    def test_revision_is_immutable_and_compare_and_swap(self):
        self.app.sessions.revise_objective(self.id, 1, ObjectiveInput("New", ("verified",)))
        with self.assertRaises(DomainError):
            self.app.sessions.revise_objective(self.id, 1, ObjectiveInput("Conflict", ("verified",)))
        with self.assertRaises(sqlite3.IntegrityError):
            self.app.store.db.execute("UPDATE objectives SET data='{}'")
        self.assertEqual(self.app.sessions.inspect_session(self.id)["revision"], 2)

    def test_state_and_event_rollback_together(self):
        before = self.app.projections.events(self.id)
        with self.assertRaises(RuntimeError):
            with self.app.store.transaction():
                self.app.store.db.execute("UPDATE sessions SET name='bad' WHERE id=?", (self.id,))
                self.app.store.append(self.id, "session.changed", {})
                raise RuntimeError("interrupted")
        self.assertEqual(self.app.sessions.inspect_session(self.id)["name"], "Test")
        self.assertEqual(before, self.app.projections.events(self.id))

    def test_event_idempotency_and_conflict(self):
        with self.app.store.transaction():
            event = self.app.store.append(self.id, "session.observed", {"x": 1})
            duplicate = self.app.store.append(self.id, "session.observed", {"x": 1}, event_id=event["event_id"])
            self.assertEqual(event, duplicate)
            with self.assertRaises(DomainError):
                self.app.store.append(self.id, "session.observed", {"x": 2}, event_id=event["event_id"])

    def test_authorization_target_revision_replay(self):
        action = ActionRequest("git.push", self.id, 1, "origin/main")
        approval = self.app.harness.request(action)
        grant = self.app.harness.grant(approval["id"])
        with self.assertRaises(DomainError):
            self.app.harness.consume(grant["id"], ActionRequest("git.push", self.id, 1, "other/main"))
        self.app.harness.consume(grant["id"], action)
        with self.assertRaises(DomainError):
            self.app.harness.consume(grant["id"], action)
        self.assertEqual(self.app.harness.evaluate(ActionRequest("invented", self.id, 1, ".")).outcome, "deny")

    def test_expired_grant_fails(self):
        action = ActionRequest("git.commit", self.id, 1, "HEAD")
        grant = self.app.harness.grant(self.app.harness.request(action)["id"])
        with self.app.store.transaction():
            grant["expires_at"] = "2000-01-01T00:00:00+00:00"
            self.app.store.put("grant", grant["id"], grant, self.id, 1)
        with self.assertRaises(DomainError):
            self.app.harness.consume(grant["id"], action)

    def test_resume_does_not_execute_and_marks_uncertainty(self):
        self.app.sessions.transition(self.id, "created", "planning", "test")
        self.app.sessions.transition(self.id, "planning", "running", "test")
        with self.app.store.transaction():
            self.app.store.put("attempt", "lost", {"id": "lost", "session_id": self.id, "revision": 1, "status": "running"}, self.id, 1)
        result = self.app.sessions.resume_session(self.id)
        self.assertEqual(result["uncertain_attempts"], ["lost"])
        self.assertTrue(result["confirmation_required"])
        self.assertEqual(result["session"]["state"], "waiting-for-action")

    def test_second_writer_rejected(self):
        with self.assertRaisesRegex(DomainError, "owns this checkout"):
            self.app.sessions.new_session(self.session["project_id"], "Other", ObjectiveInput("Other", ("ok",)), "direct")

    def test_memory_conflict_budget_and_forget(self):
        for text in ("Greeting is hello", "Greeting is goodbye"):
            memory = self.app.memory.propose(text, session_id=self.id, key="greeting")
            self.approve(self.app.memory.promote, memory["id"])
        self.assertEqual(self.app.memory.recall(session_id=self.id)["items"], [])
        self.assertTrue(self.app.memory.recall(session_id=self.id)["conflicts"])
        self.approve(self.app.memory.forget, memory["id"], session_id=self.id)
        self.assertEqual(len(self.app.memory.recall(session_id=self.id)["items"]), 1)
        self.assertEqual(self.app.memory.recall(session_id=self.id, budget=0)["items"], [])
        self.assertNotIn("goodbye", encode(self.app.projections.events(self.id)))

    def test_memory_forget_rejects_cross_project_scope(self):
        memory = self.app.memory.propose("Project secret", session_id=self.id)
        other_project = self.root / "other-project"
        other_project.mkdir()
        project = self.app.sessions.register_project(other_project)
        other = self.app.sessions.new_session(project["id"], "Other", ObjectiveInput("Other", ("verified",)), "direct")
        with self.assertRaisesRegex(DomainError, "selected session or project"):
            self.app.memory.forget(memory["id"], session_id=other["id"])

    def test_routes_exports_and_artifacts_do_not_leak_local_paths(self):
        config = self.project / ".silvia/config.toml"
        config.parent.mkdir()
        config.write_text('[providers.default]\nendpoint="http://127.0.0.1:9999/v1"\nmodel="test"\ncredential_ref="env:PRIVATE_TOKEN"\ncost_policy="local"\nadapter="openai-compatible"\n')
        routes = self.app.agents.available_routes()
        self.assertNotIn("credential_ref", routes[0])
        artifact = self.app.artifacts.store_artifact(self.id, "portable")
        with self.app.store.transaction():
            self.app.store.put("context", "portable-context", {"id": "portable-context", "session_id": self.id, "revision": 1, "source_uri": self.project.as_uri(), "command": "inspect " + str(self.project / "local.py")}, self.id, 1)
        self.assertEqual(self.app.artifacts.root(self.id).name, self.id)
        path = self.root / "portable.zip"
        with self.assertRaises(DomainError) as error:
            self.app.projections.export_session(self.id, path)
        self.app.harness.grant(error.exception.details["approval_id"])
        self.app.projections.export_session(self.id, path)
        with zipfile.ZipFile(path) as archive:
            state = json.loads(archive.read("state.json"))
            self.assertIn("artifacts/" + artifact["digest"], archive.namelist())
            exported_text = "\n".join(archive.read(name).decode("utf-8", errors="replace") for name in archive.namelist())
        self.assertNotIn("checkout", state["session"])
        self.assertNotIn(str(self.project), exported_text)
        self.assertNotIn(str(self.root), exported_text)
        self.assertNotIn(self.project.as_uri(), exported_text)
        self.assertIn("[local-path-redacted]", exported_text)

    def test_secrets_never_enter_events_or_memory(self):
        secret = "sk-" + "q" * 24
        with self.app.store.transaction():
            self.app.store.append(self.id, "agent.failed", {"output": secret, "password": "hidden"})
        self.assertNotIn(secret, encode(self.app.projections.events(self.id)))
        with self.assertRaises(DomainError):
            self.app.memory.propose(secret, session_id=self.id)

    def test_skill_provenance_change_and_traversal(self):
        source = self.root / "skills"
        skill = source / "greet"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: greet\ndescription: Greetings\ncustom: extension\n---\nUse hello.")
        registered = self.app.skills.register_source(source, "local")
        resolved = self.app.skills.resolve(registered["id"], "greet")
        self.assertEqual(resolved["metadata"]["custom"], "extension")
        self.assertEqual(resolved["capabilities"], [])
        with self.assertRaises(DomainError):
            self.app.skills.resolve(registered["id"], "../project")
        (skill / "SKILL.md").write_text("Changed")
        with self.assertRaises(DomainError):
            self.app.skills.build_context([{**resolved["identity"]}], 10000)

    def test_skill_capability_is_fail_closed_without_sandbox(self):
        source = self.root / "sandbox-skills"
        skill = source / "greet"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: greet\ndescription: Greetings\n---\nReadable.")
        (skill / "run.py").write_text('print("host execution must not happen")\n')
        (skill / "silvia.yaml").write_text(
            "schema_version: 1\ncapabilities:\n"
            "  - name: greet\n    executable: run.py\n    argv: [hello]\n"
            "    filesystem: {read: ['.'], write: []}\n    network: []\n"
            "    platforms: [windows]\n    requires_approval: true\n    extension: preserved\n"
        )
        registered = self.app.skills.register_source(source, "sandbox")
        with self.assertRaises(DomainError) as error:
            asyncio.run(self.app.agents.execute_skill_capability(self.id, registered["id"], "greet", "greet"))
        self.assertEqual(error.exception.code, "sandbox-unavailable")
        self.assertEqual(self.app.store.records("approval", self.id), [])
        self.assertEqual(self.app.store.records("effect", self.id), [])

    def test_skill_capability_crosses_sandbox_and_f02(self):
        source = self.root / "sandbox-fake-skills"
        skill = source / "greet"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: greet\ndescription: Greetings\n---\nReadable.")
        (skill / "run.py").write_text('print("not executed by fake")\n')
        (skill / "silvia.yaml").write_text(
            "schema_version: 1\ncapabilities:\n"
            "  - name: greet\n    executable: run.py\n    argv: [hello, world]\n"
            "    filesystem: {read: ['.'], write: []}\n    network: []\n"
            "    platforms: [windows]\n    requires_approval: true\n"
        )
        registered = self.app.skills.register_source(source, "sandbox-fake")
        adapter = FakeSandboxAdapter(lambda request: SandboxResult("completed", 0, "isolated", {"adapter": "fake", "policy_applied": True, "policy_digest": _sandbox_policy_digest(request)}))
        self.app.sandbox.adapter = adapter
        operation = lambda: asyncio.run(self.app.agents.execute_skill_capability(self.id, registered["id"], "greet", "greet"))
        with self.assertRaises(DomainError) as error:
            operation()
        self.assertEqual(error.exception.code, "require-approval")
        self.assertEqual(adapter.requests, [])
        self.app.harness.grant(error.exception.details["approval_id"])
        effect = operation()
        self.assertEqual(effect["status"], "completed")
        self.assertTrue(effect["isolation"]["policy_applied"])
        self.assertEqual(adapter.requests[0].argv[-2:], ("hello", "world"))
        self.assertEqual(len(self.app.store.records("authorization-use", self.id)), 1)

    def test_skill_capability_rejects_unproven_preflight(self):
        source = self.root / "sandbox-incompatible-skills"
        skill = source / "greet"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: greet\ndescription: Greetings\n---\nReadable.")
        (skill / "run.py").write_text("print('no')\n")
        (skill / "silvia.yaml").write_text(
            "schema_version: 1\ncapabilities:\n"
            "  - name: greet\n    executable: run.py\n    argv: []\n"
            "    filesystem: {read: ['.'], write: []}\n    network: []\n"
            "    platforms: [windows]\n    requires_approval: true\n"
        )
        registered = self.app.skills.register_source(source, "sandbox-incompatible")

        class IncompatibleAdapter:
            def prepare(self, request):
                return {"status": "ready", "containment": False, "policy_digest": "unproven"}

            async def run(self, request):
                raise AssertionError("incompatible adapter must never run")

        self.app.sandbox.adapter = IncompatibleAdapter()
        with self.assertRaises(DomainError) as error:
            asyncio.run(self.app.agents.execute_skill_capability(self.id, registered["id"], "greet", "greet"))
        self.assertEqual(error.exception.code, "sandbox-incompatible")
        self.assertEqual(self.app.store.records("approval", self.id), [])
        self.assertEqual(self.app.store.records("effect", self.id), [])

    def test_interrupted_sandbox_execution_requires_reconciliation(self):
        source = self.root / "sandbox-interrupted-skills"
        skill = source / "wait"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: wait\ndescription: Wait\n---\nReadable.")
        (skill / "run.py").write_text("print('not executed by fake')\n")
        (skill / "silvia.yaml").write_text(
            "schema_version: 1\ncapabilities:\n"
            "  - name: wait\n    executable: run.py\n    argv: []\n"
            "    filesystem: {read: ['.'], write: []}\n    network: []\n"
            "    platforms: [windows]\n    requires_approval: true\n"
        )
        registered = self.app.skills.register_source(source, "sandbox-interrupted")

        async def blocked(request):
            await asyncio.Event().wait()

        self.app.sandbox.adapter = FakeSandboxAdapter(blocked)
        operation = lambda: self.app.agents.execute_skill_capability(self.id, registered["id"], "wait", "wait")
        with self.assertRaises(DomainError) as error:
            asyncio.run(operation())
        self.app.harness.grant(error.exception.details["approval_id"])

        async def interrupt():
            task = asyncio.create_task(operation())
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(DomainError) as interrupted:
                await task
            return interrupted.exception

        interrupted = asyncio.run(interrupt())
        self.assertEqual(interrupted.code, "reconciliation-required")
        effects = self.app.store.records("effect", self.id)
        self.assertEqual(effects[-1]["status"], "uncertain")
    def test_direct_capability_cancel_requests_stop_and_stays_uncertain(self):
        source = self.root / "sandbox-cancelled-skills"
        skill = source / "wait"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: wait\ndescription: Wait\n---\nReadable.")
        (skill / "run.py").write_text("print('not executed by fake')\n")
        (skill / "silvia.yaml").write_text(
            "schema_version: 1\ncapabilities:\n"
            "  - name: wait\n    executable: run.py\n    argv: []\n"
            "    filesystem: {read: ['.'], write: []}\n    network: []\n"
            "    platforms: [windows]\n    requires_approval: true\n"
        )
        registered = self.app.skills.register_source(source, "sandbox-cancelled")
        adapter = FakeSandboxAdapter()

        async def finish_after_stop(request):
            while not adapter.stop_requested:
                await asyncio.sleep(0)
            return SandboxResult("completed", 0, "late success", {
                "adapter": "fake",
                "policy_digest": _sandbox_policy_digest(request),
            })

        adapter.handler = finish_after_stop
        self.app.sandbox.adapter = adapter
        operation = lambda: self.app.agents.execute_skill_capability(self.id, registered["id"], "wait", "wait")
        with self.assertRaises(DomainError) as error:
            asyncio.run(operation())
        self.app.harness.grant(error.exception.details["approval_id"])

        async def execute_and_cancel():
            task = asyncio.create_task(operation())
            while not adapter.requests:
                await asyncio.sleep(0)
            await self.app.cancel_session(self.id)
            with self.assertRaises(DomainError) as interrupted:
                await task
            return interrupted.exception

        interrupted = asyncio.run(execute_and_cancel())
        self.assertTrue(adapter.stop_requested)
        self.assertEqual(interrupted.code, "reconciliation-required")
        self.assertEqual(self.app.store.records("effect", self.id)[-1]["status"], "uncertain")
    def test_invalid_sidecar_remains_readable_but_not_executable(self):
        source = self.root / "invalid-sidecar-skills"
        skill = source / "invalid"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: invalid\ndescription: Invalid\n---\nStill readable.")
        (skill / "run.py").write_text("print('no')\n")
        (skill / "silvia.yaml").write_text("schema_version: 99\ncapabilities: []\n")
        registered = self.app.skills.register_source(source, "invalid-sidecar")
        resolved = self.app.skills.resolve(registered["id"], "invalid")
        self.assertIn("Still readable", resolved["instructions"])
        self.assertEqual(resolved["capabilities"], [])
        with self.assertRaisesRegex(DomainError, "absent, duplicated or denied"):
            asyncio.run(self.app.agents.execute_skill_capability(self.id, registered["id"], "invalid", "run"))
    def test_export_roundtrip_and_corruption(self):
        artifact = self.app.artifacts.store_artifact(self.id, "Evidence")
        path = self.root / "session.zip"
        with self.assertRaises(DomainError) as error:
            self.app.projections.export_session(self.id, path)
        self.app.harness.grant(error.exception.details["approval_id"])
        result = self.app.projections.export_session(self.id, path)
        self.assertTrue(result["verification"]["valid"])
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(bad, "w") as dst:
            for name in src.namelist():
                dst.writestr(name, b"corrupt" if name.endswith(artifact["digest"]) else src.read(name))
        with self.assertRaises(DomainError):
            self.app.projections.verify_import(bad)

    def test_zip_traversal_rejected(self):
        path = self.root / "hostile.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../escape", "unsafe")
        with self.assertRaises(DomainError):
            self.app.projections.verify_import(path)
        self.assertFalse((self.root / "escape").exists())

    def test_completion_without_evidence_rejected(self):
        with self.assertRaises(DomainError):
            self.app.confirm_completion(self.id)

    def test_report_is_deterministic(self):
        self.assertEqual(self.app.projections.render(self.id), self.app.projections.render(self.id))

    def test_cli_json_and_reopen(self):
        result = subprocess.run([sys.executable, "-m", "silvia", "--home", str(self.app.home), "status", self.id, "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["session"]["id"], self.id)
        self.assertEqual(result.stderr, "")

    def test_future_schema_fails_closed(self):
        path = self.root / "future.db"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE schema_migrations(version INTEGER)")
            db.execute("INSERT INTO schema_migrations VALUES(99)")
        db.close()
        with self.assertRaises(DomainError):
            SQLiteStore(path)


class AgentIntegration(unittest.TestCase):
    setUp = LocalCase.setUp
    tearDown = LocalCase.tearDown
    def test_real_files_checks_review_and_completion(self):
        asyncio.run(self.flow())

    async def flow(self):
        config = self.project / ".silvia/config.toml"
        config.parent.mkdir()
        config.write_text('[providers.default]\nendpoint="http://127.0.0.1:9999/v1"\nmodel="test"\ncost_policy="local"\nadapter="openai-compatible"\n')
        runtime = self.app.agents
        class BoundaryProvider:
            async def invoke(inner, messages, tools, max_tokens):
                review = "read-only reviewer" in messages[0]["content"]
                if messages[-1]["role"] == "tool":
                    return ProviderReply('{"status":"pass","findings":[]}' if review else "Implemented greeting", (), {"total_tokens": 20})
                name, args = ("read_file", {"path": "greeting.py"}) if review else ("write_file", {"path": "greeting.py", "content": 'def greet():\n    return "hello"\n'})
                return ProviderReply("", ({"id": "call", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}},), {"total_tokens": 20})
        runtime.provider_factory = lambda *_: BoundaryProvider()
        command = [sys.executable, "-B", "-c", "from greeting import greet; assert greet() == 'hello'"]
        proposal = runtime.propose_plan(self.id, [{"id": "greeting", "purpose": "Implement greeting", "owned_paths": ["greeting.py"], "verification": [command]}])
        self.app.harness.grant(proposal["approval"]["id"])
        with self.assertRaises(DomainError) as error:
            await runtime.run(self.id)
        self.app.harness.grant(error.exception.details["approval_id"])
        await runtime.run(self.id)
        self.assertEqual((self.project / "greeting.py").read_text(), 'def greet():\n    return "hello"\n')
        result = self.app.confirm_completion(self.id)
        self.assertEqual(result["state"], "completed")


class TUITest(unittest.IsolatedAsyncioTestCase):
    async def test_agent_stop_waits_before_forcing_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = Application(home=root / "home", project=root)
            try:
                stop_signal = asyncio.Event()
                class CooperativeProvider:
                    async def request_stop(inner):
                        stop_signal.set()
                        return True
                async def cooperative():
                    await stop_signal.wait()
                    return "stopped"
                app.agents.tasks["cooperative"] = asyncio.create_task(cooperative())
                app.agents.active_providers["cooperative"] = CooperativeProvider()
                result = await app.agents.stop("cooperative", deadline=1)
                self.assertTrue(result["cooperative_signal"])
                self.assertTrue(result["cooperative"])
                self.assertFalse(result["reconciliation_required"])
                async def stuck():
                    await asyncio.sleep(60)
                task = asyncio.create_task(stuck())
                app.agents.tasks["stuck"] = task
                result = await app.agents.stop("stuck", deadline=0)
                self.assertTrue(result["reconciliation_required"])
                self.assertTrue(task.cancelled())
            finally:
                app.close()
    async def test_headless_mount(self):
        from silvia.tui import SilviaTUI
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = Application(home=root / "home", project=root)
            try:
                tui = SilviaTUI(app)
                async with tui.run_test(size=(100, 40)) as pilot:
                    await pilot.pause()
                    self.assertEqual(tui.title, "SilvIA")
            finally:
                app.close()
