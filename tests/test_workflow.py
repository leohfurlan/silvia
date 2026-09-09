import unittest
from pathlib import Path

from workflow.config import WorkflowConfig
from workflow.contracts import parse_plan, parse_pr_draft, parse_review
from workflow.engine import _validate_plan


class WorkflowContractsTest(unittest.TestCase):
    def test_plan_requires_disjoint_scoped_items(self):
        plan = parse_plan(
            '{"summary":"x","acceptance_criteria":["works"],"work_items":['
            '{"id":"a","purpose":"one","owned_paths":["a.py"],"dependencies":[]},'
            '{"id":"b","purpose":"two","owned_paths":["b.py"],"dependencies":["a"]}'
            ']}'
        )
        self.assertEqual(plan.work_items[1].dependencies, ("a",))
        self.assertEqual(plan.work_items[0].owned_paths, ("a.py",))
        self.assertEqual(plan.work_items[0].context_class, "standard")
        self.assertEqual(plan.work_items[0].model, "qwen3.8-flash")

    def test_large_context_is_routed_to_deepseek(self):
        plan = parse_plan(
            '{"summary":"x","work_items":['
            '{"id":"a","purpose":"broad task","owned_paths":["a.py"],'
            '"context_class":"large","model":"deepseek-v4-flash"}]}'
        )
        self.assertEqual(plan.work_items[0].context_class, "large")
        _validate_plan(plan, WorkflowConfig(repo=Path.cwd(), api_key="test"))

    def test_large_context_rejects_non_deepseek(self):
        plan = parse_plan(
            '{"summary":"x","work_items":['
            '{"id":"a","purpose":"broad task","owned_paths":["a.py"],'
            '"context_class":"large","model":"qwen3.8-flash"}]}'
        )
        with self.assertRaisesRegex(ValueError, "must use deepseek-v4-flash"):
            _validate_plan(plan, WorkflowConfig(repo=Path.cwd(), api_key="test"))

    def test_deepseek_is_rejected_for_standard_context(self):
        plan = parse_plan(
            '{"summary":"x","work_items":['
            '{"id":"a","purpose":"small task","owned_paths":["a.py"],'
            '"model":"deepseek-v4-flash"}]}'
        )
        with self.assertRaisesRegex(ValueError, "reserved for large-context"):
            _validate_plan(plan, WorkflowConfig(repo=Path.cwd(), api_key="test"))

    def test_plan_rejects_unknown_dependency(self):
        with self.assertRaises(ValueError):
            parse_plan(
                '{"summary":"x","work_items":['
                '{"id":"a","purpose":"one","owned_paths":["a.py"],"dependencies":["missing"]}'
                ']}'
            )

    def test_review_is_fail_closed(self):
        review = parse_review('{"status":"changes_requested","findings":["bug"],"required_changes":["fix"]}')
        self.assertEqual(review.status, "changes_requested")
        with self.assertRaises(ValueError):
            parse_review('{"status":"approved"}')

    def test_pr_draft_requires_title_and_body(self):
        draft = parse_pr_draft('{"title":"Change","body":"Evidence"}')
        self.assertEqual(draft.title, "Change")
        with self.assertRaises(ValueError):
            parse_pr_draft('{"title":"Change","body":""}')


if __name__ == "__main__":
    unittest.main()