from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class BuildPluginBundleTests(unittest.TestCase):
    def test_bundle_is_physical_canonical_and_private_source_free(self) -> None:
        from scripts.build_plugin_bundle import build_bundle

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "easyslides"
            manifest = build_bundle(output)

            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(
                sorted(manifest["skills"]),
                ["easyslides", "easyslides-clarify", "easyslides-distill"],
            )
            self.assertTrue((output / "skills" / "easyslides" / "SKILL.md").is_file())
            self.assertTrue((output / "scripts" / "semantic_template_renderer.py").is_file())
            self.assertTrue((output / "templates" / "layouts" / "nsfc_defense" / "layouts.json").is_file())
            self.assertFalse((output / "templates" / "layouts" / "nsfc_purple_semantic").exists())
            self.assertFalse((output / "projects").exists())
            self.assertFalse((output / "templates" / "reference").exists())
            self.assertFalse((output / "skills" / "easyslides-template-reuse").exists())
            self.assertFalse(any(path.suffix.lower() in {".pptx", ".pdf"} for path in output.rglob("*")))
            self.assertFalse(
                (output / "templates" / "layouts" / "nsfc_defense" / "production_gate.json").exists()
            )
            self.assertFalse(
                (output / "templates" / "layouts" / "nsfc_defense" / "human_review.json").exists()
            )
            for path in output.rglob("*.json"):
                json.loads(path.read_text(encoding="utf-8"))
            searchable_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output.rglob("*")
                if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml", ".md"}
            )
            self.assertNotIn("attention_all_you_need_thu_env_ppt169_20260525", searchable_text)
            self.assertNotIn("D:\\scansci\\easyslides", searchable_text)

            recorded = json.loads((output / "bundle_manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(recorded["privacy_policy"]["source_documents_included"])


if __name__ == "__main__":
    unittest.main()
