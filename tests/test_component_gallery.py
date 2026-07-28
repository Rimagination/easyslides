import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / "scripts" / "component_gallery.py"


class ComponentGalleryTests(unittest.TestCase):
    def test_public_gallery_excludes_template_migration_sources(self):
        from scripts.component_gallery import build_component_gallery

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "gallery"
            manifest = build_component_gallery(output_dir=output)
            html = output / "component_gallery.html"

            self.assertEqual(manifest["schema_version"], "easyslides.component_gallery.v1")
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["preview_gate_status"], "not_applicable")
            self.assertEqual(manifest["package_count"], 0)
            self.assertEqual(manifest["story_count"], 0)
            self.assertEqual(manifest["fail_story_count"], 0)
            self.assertTrue(html.exists())
            self.assertEqual(manifest["preview_gate_report"]["reason"], "no_public_component_packages")

    def test_gallery_manifest_keeps_template_migration_sources_out_of_public_packages(self):
        from scripts.component_gallery import build_component_gallery

        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_component_gallery(output_dir=Path(tmp) / "gallery")

        self.assertEqual(manifest["packages"], [])
        self.assertEqual(manifest["preview_gate_report"]["svg_count"], 0)

    def test_cli_writes_gallery(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "gallery"
            result = subprocess.run(
                [sys.executable, str(GALLERY), "--out", str(output), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(result.stdout)
            self.assertTrue((output / "component_gallery.html").exists())

        self.assertEqual(manifest["status"], "pass")
        self.assertEqual(manifest["preview_gate_status"], "not_applicable")
        self.assertEqual(manifest["story_count"], 0)


if __name__ == "__main__":
    unittest.main()
