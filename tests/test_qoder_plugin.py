"""Qoder imports need their own manifest and a flat, complete Plugin ZIP."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_plugin_bundle import ROOT, build_bundle
from scripts.build_qoder_plugin import build_qoder_plugin


class QoderPluginTests(unittest.TestCase):
    def test_zip_keeps_shared_runtime_and_only_qoder_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "easyslides"
            archive_path = Path(tmp) / "plugin.zip"
            result = build_qoder_plugin(output, archive_path)
            self.assertEqual(result["host"], "qoder")
            manifest = json.loads((output / ".qoder-plugin/plugin.json").read_text(encoding="utf-8"))
            npm = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
            self.assertEqual((manifest["name"], manifest["version"]), (npm["name"], npm["version"]))
            self.assertEqual(manifest["skills"], "./skills/")
            self.assertTrue((output / manifest["logo"]).is_file())
            self.assertTrue((output / "qoder.md").is_file())
            self.assertIn("references/qoder.md", (output / "qoder.md").read_text(encoding="utf-8"))
            policy = json.loads((output / "templates/template_policy.json").read_text(encoding="utf-8"))
            self.assertEqual(policy["default_native_template_id"], "academic_general")
            self.assertEqual(len(result["layouts"]), 8)
            self.assertEqual(len(list((output / "templates/layouts/academic_general/cover_banners").glob("*.png"))), 14)
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                self.assertIn(".qoder-plugin/plugin.json", names)
                self.assertIn("scripts/easyslides.py", names)
                self.assertIn("references/default-academic-template.md", names)
                for name in result["skills"]:
                    self.assertIn(f"skills/{name}/SKILL.md", names)
                self.assertFalse(any(name.startswith((".codex-plugin/", ".zcode-plugin/", "projects/", "easyslides/")) for name in names))
                self.assertFalse(any(Path(name).suffix.lower() in {".pdf", ".pptx", ".docx"} for name in names))
            with self.assertRaises(FileExistsError):
                build_qoder_plugin(output, archive_path)

    def test_output_guards_reject_invalid_targets_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "easyslides"
            with self.assertRaises(ValueError):
                build_qoder_plugin(output, output / "nested.zip")
            with self.assertRaises(ValueError):
                build_qoder_plugin(output, Path(tmp) / "wrong.tgz")
            with self.assertRaises(ValueError):
                build_qoder_plugin(Path(tmp) / "wrong-name", Path(tmp) / "plugin.zip")
            with self.assertRaises(ValueError):
                build_bundle(output, host="unknown")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
