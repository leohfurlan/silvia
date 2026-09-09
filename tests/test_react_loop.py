import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workflow.config import WorkflowConfig
from workflow.contracts import WorkItem
from workflow.engine import WorkflowPaused, WorkflowRunner, _parallel_coders
from workflow.observability import NullObserver


class RetryHandler:
    def __init__(self, decision="retry"):
        self.decision = decision
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        return self.decision


class ReactLoopTest(unittest.IsolatedAsyncioTestCase):
    def _runner(self, root, handler=None):
        return WorkflowRunner(
            WorkflowConfig(repo=root, api_key="test"),
            NullObserver(),
            intervention_handler=handler,
        )

    async def test_agent_error_retries_only_after_authorization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            handler = RetryHandler()
            runner = self._runner(root, handler)
            calls = 0

            async def fake_invoke(config, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("temporary tool failure")
                return "ok"

            with patch("workflow.engine.invoke_agent", fake_invoke):
                result = await runner._invoke_resilient(
                    model_name="qwen3.8-flash",
                    system_prompt="",
                    user_prompt="",
                    tools=[],
                    role="coder",
                    task_id="item-a",
                    phase="coding",
                )

            self.assertEqual(result, "ok")
            self.assertEqual(calls, 2)
            self.assertEqual(len(handler.requests), 1)
            self.assertEqual(runner.session.state["status"], "running")
            self.assertIsNone(runner.session.state["pending_intervention"])

    async def test_agent_error_pauses_without_handler(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = self._runner(Path(temporary))

            async def fake_invoke(config, **kwargs):
                raise RuntimeError("requires human action")

            with patch("workflow.engine.invoke_agent", fake_invoke):
                with self.assertRaises(WorkflowPaused):
                    await runner._invoke_resilient(
                        model_name="qwen3.8-flash",
                        system_prompt="",
                        user_prompt="",
                        tools=[],
                        role="coder",
                        task_id="item-a",
                        phase="coding",
                    )

            self.assertEqual(runner.session.state["status"], "waiting_user")
            self.assertIsNotNone(runner.session.state["pending_intervention"])

    async def test_parallel_coders_keep_independent_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            handler = RetryHandler()
            runner = self._runner(root, handler)
            attempts = {}

            async def fake_agent(config, **kwargs):
                task_id = kwargs["task_id"]
                attempts[task_id] = attempts.get(task_id, 0) + 1
                await asyncio.sleep(0)
                if task_id == "a" and attempts[task_id] == 1:
                    raise RuntimeError("one coder failed")
                return f"done-{task_id}"

            items = (
                WorkItem("a", "first", ("a.py",)),
                WorkItem("b", "second", ("b.py",)),
            )
            with patch("workflow.engine.invoke_agent", fake_agent), patch("workflow.engine.tools_for", return_value=[]):
                result = await _parallel_coders(
                    WorkflowConfig(repo=root, api_key="test", max_parallel=2),
                    items,
                    "context",
                    NullObserver(),
                    runner._invoke_resilient,
                    runner.session,
                )

            self.assertEqual(result, {"a": "done-a", "b": "done-b"})
            self.assertEqual(attempts, {"a": 2, "b": 1})



    async def test_paused_session_can_be_reloaded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner = self._runner(root)

            async def fake_invoke(config, **kwargs):
                raise RuntimeError("requires human action")

            with patch("workflow.engine.invoke_agent", fake_invoke):
                with self.assertRaises(WorkflowPaused):
                    await runner._invoke_resilient(
                        model_name="qwen3.8-flash",
                        system_prompt="",
                        user_prompt="",
                        tools=[],
                        role="coder",
                        task_id="item-a",
                        phase="coding",
                    )

            resumed = WorkflowRunner(
                WorkflowConfig(repo=root, api_key="test"),
                NullObserver(),
                session_id=runner.session.session_id,
                resume=True,
            )
            self.assertEqual(resumed.session.session_id, runner.session.session_id)
            self.assertEqual(resumed.session.state["status"], "waiting_user")
            self.assertIsNotNone(resumed.session.state["pending_intervention"])

if __name__ == "__main__":
    unittest.main()
