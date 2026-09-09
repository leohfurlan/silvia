import unittest

from workflow.contracts import parse_plan, parse_pr_draft, parse_review


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
