import tempfile
import unittest
from pathlib import Path

from workflow.harness import HarnessConflict, initialize_standard_harness


class HarnessInitializationTest(unittest.TestCase):
    def test_creates_standard_scaffold_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = initialize_standard_harness(root, project_name="Example")
            self.assertIn("DEVELOPMENT.md", first.created)
            self.assertIn("docs/product/PRD.md", first.created)
            self.assertEqual((root / "docs/specs/_template/plan.md").is_file(), True)

            second = initialize_standard_harness(root, project_name="Example")
            self.assertEqual(second.created, ())
            self.assertIn("DEVELOPMENT.md", second.preserve_compatible)
            self.assertEqual(second.integration_required, ())

    def test_preserves_divergent_file_for_explicit_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "DEVELOPMENT.md").write_text("local rules\n", encoding="utf-8")

            report = initialize_standard_harness(root)
            self.assertEqual((root / "DEVELOPMENT.md").read_text(encoding="utf-8"), "local rules\n")
            self.assertIn("DEVELOPMENT.md", report.integration_required)
            self.assertIn("AGENTS.md", report.created)

    def test_rejects_controlled_symlink_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            try:
                (root / "DEVELOPMENT.md").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            with self.assertRaises(HarnessConflict):
                initialize_standard_harness(root)
            self.assertFalse((root / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
