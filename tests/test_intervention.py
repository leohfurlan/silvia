import tempfile
import unittest
from pathlib import Path

from workflow.engine import _validate_source_truth
from workflow.tools import workspace_tools


class InterventionRegressionTest(unittest.TestCase):
    def test_file_ownership_allows_listing_ancestor_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owned = root / "docs/specs/F02-permissoes/evidencia-verificacao.md"
            owned.parent.mkdir(parents=True)
            owned.write_text("evidence", encoding="utf-8")
            tools = workspace_tools(
                root,
                ("docs/specs/F02-permissoes/evidencia-verificacao.md",),
                writable=False,
            )
            list_tool = next(tool for tool in tools if tool.name == "list_files")
            self.assertEqual(
                list_tool.invoke({"path": "docs/specs/F02-permissoes"}),
                "docs/specs/F02-permissoes/evidencia-verificacao.md",
            )

    def test_workspace_exposes_read_only_git_metadata_tools(self):
        names = {
            tool.name
            for tool in workspace_tools(Path.cwd(), (".",), writable=False)
        }
        self.assertIn("git_status", names)
        self.assertIn("git_branch", names)


    def test_source_truth_allows_consistent_unimplemented_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "docs/specs/F01"
            directory.mkdir(parents=True)
            (directory / "contract.md").write_text(
                "Status: proposed. Not approved, not implemented.",
                encoding="utf-8",
            )
            (directory / "spec.md").write_text(
                "Status: proposal; nothing implemented or verified.",
                encoding="utf-8",
            )
            (directory / "plan.md").write_text(
                "Status: proposed; no step executed.",
                encoding="utf-8",
            )
            _validate_source_truth(Path(temporary))

    def test_source_truth_rejects_conflicting_artifact_statuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "docs/specs/F02"
            directory.mkdir(parents=True)
            (directory / "contract.md").write_text(
                "**Status**: proposed. Not approved, not implemented.",
                encoding="utf-8",
            )
            (directory / "spec.md").write_text(
                "**Status**: implemented on 2026-09-09.",
                encoding="utf-8",
            )
            (directory / "plan.md").write_text(
                "**Status**: executed.",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Source-of-truth conflict"):
                _validate_source_truth(Path(temporary))


if __name__ == "__main__":
    unittest.main()
