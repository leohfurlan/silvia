"""Portable repository checks for the bundled Astra skill."""
from __future__ import annotations

import re
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill" / "astra"


class AstraSkillContract(unittest.TestCase):
    def test_required_files_and_entrypoint_mode(self):
        for relative in ("SKILL.md", "scripts/ask_astra.sh", "scripts/ask_astra.py", "agents/openai.yaml"):
            self.assertTrue((SKILL / relative).is_file(), relative)
        stage = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--stage", "skill/astra/scripts/ask_astra.sh"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertTrue(stage.startswith("100755 "), stage)

    def test_routing_contract_and_manifest(self):
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in (SKILL / "SKILL.md", SKILL / "scripts/ask_astra.py", ROOT / "README.md"))
        for required in ("GPT-6 Astra", "gpt-6-astra", "Qwen3.8-Flash", "GLM 5.3 Flash", "glm-5.3-flash", "BAI_API_KEY", "APIKEY_B_AI", "https://api.b.ai/v1", "B.AI Responses API"):
            self.assertIn(required, corpus)
        manifest = yaml.safe_load((SKILL / "agents/openai.yaml").read_text(encoding="utf-8"))
        self.assertTrue(all(manifest.get("interface", {}).get(key) for key in ("display_name", "short_description", "default_prompt")))

    def test_svg_is_local_and_structurally_valid(self):
        path = ROOT / "assets/astra-orchestrator.svg"
        ET.parse(path)
        text = path.read_text(encoding="utf-8")
        for required in ('viewBox="0 0 1200 600"', "ASTRA", "QWEN3.8-FLASH", "GLM 5.3 FLASH"):
            self.assertIn(required, text)
        self.assertIsNone(re.search(r"gradient|<filter(?:\s|>)|<image(?:\s|>)|url\(|@font-face|@import|fonts\.(?:googleapis|gstatic)|href=[^\s]*(?:https?:|//)", text, re.I))

    def test_repository_has_no_credential_shaped_content(self):
        patterns = [
            re.compile(value) for value in (
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}",
                r"gh[pousr]_[A-Za-z0-9]{20,}", r"sk-(?:ant-)?[A-Za-z0-9_-]{20,}",
                r"xox[baprs]-[A-Za-z0-9-]{20,}",
            )
        ]
        excluded = {Path("tests/test_skill.py"), Path("tests/test_skill.sh")}
        for path in ROOT.rglob("*"):
            relative = path.relative_to(ROOT)
            if not path.is_file() or ".git" in relative.parts or "__pycache__" in relative.parts or relative in excluded:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            self.assertFalse(any(pattern.search(text) for pattern in patterns), str(relative))


if __name__ == "__main__":
    unittest.main()