from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class BuildPluginBundleTests(unittest.TestCase):
    def test_bundle_is_physical_canonical_and_private_source_free(self) -> None:
        from scripts.build_plugin_bundle import build_bundle, WINDOWS_ABSOLUTE_PATH

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
            from scripts.easyslides_doctor import _template_checks
            from unittest.mock import patch
            with patch("scripts.easyslides_doctor.ROOT", output):
                checks = _template_checks()
            self.assertEqual(len(checks), 7)
            self.assertTrue(all(row["status"] == "pass" for row in checks), checks)
            policy = json.loads((output / "templates/template_policy.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["layouts"], sorted(policy["official_template_ids"]))
            image_library = output / "templates/image_references"
            catalog = json.loads((image_library / "registry.json").read_text(encoding="utf-8"))
            self.assertEqual(len(catalog["templates"]), 13)
            for entry in catalog["templates"]:
                for key in ("image", "preview"):
                    self.assertTrue((image_library / entry[key]).is_file())
            self.assertTrue((output / "templates/components/marketplace.json").is_file())
            self.assertTrue((output / "LICENSE").is_file())
            self.assertTrue((output / "INSTALL.md").is_file())
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
            self.assertIsNone(WINDOWS_ABSOLUTE_PATH.search(searchable_text))

            recorded = json.loads((output / "bundle_manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(recorded["privacy_policy"]["source_documents_included"])

    def test_existing_output_and_source_subdirectories_are_never_replaced(self):
        from scripts.build_plugin_bundle import build_bundle, ROOT
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                build_bundle(Path(tmp))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "user data")
        with self.assertRaises(ValueError):
            build_bundle(ROOT / "scripts" / "unsafe_bundle_output")


if __name__ == "__main__":
    unittest.main()
