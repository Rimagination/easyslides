import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / "scripts" / "component_gallery.py"


class ComponentGalleryTests(unittest.TestCase):
    def test_builds_gallery_with_svg_previews(self):
        from scripts.component_gallery import build_component_gallery

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "gallery"
            manifest = build_component_gallery(output_dir=output)
            html = output / "component_gallery.html"
            svg = output / "previews" / "three_card_summary__default.svg"

            self.assertEqual(manifest["schema_version"], "easyslides.component_gallery.v1")
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["preview_gate_status"], "pass")
            self.assertEqual(manifest["package_count"], 6)
            self.assertEqual(manifest["story_count"], 18)
            self.assertEqual(manifest["fail_story_count"], 6)
            self.assertTrue(html.exists())
            self.assertTrue(svg.exists())
            svg_text = svg.read_text(encoding="utf-8")
            self.assertIn('data-pptx-valign="middle"', svg_text)
            self.assertIn('data-center-lock="true"', svg_text)

    def test_gallery_manifest_records_expected_overflow_failures(self):
        from scripts.component_gallery import build_component_gallery

        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_component_gallery(output_dir=Path(tmp) / "gallery")

        overflow_stories = [
            story
            for package in manifest["packages"]
            for story in package["stories"]
            if story["story_id"] == "overflow"
        ]

        self.assertEqual(len(overflow_stories), 6)
        self.assertTrue(all(story["status"] == "fail" for story in overflow_stories))
        self.assertTrue(all(story["violations"] for story in overflow_stories))

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
        self.assertEqual(manifest["preview_gate_status"], "pass")
        self.assertEqual(manifest["story_count"], 18)


if __name__ == "__main__":
    unittest.main()
