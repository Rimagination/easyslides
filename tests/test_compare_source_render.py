import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class CompareSourceRenderTests(unittest.TestCase):
    def test_identical_source_and_render_passes(self):
        from scripts.compare_source_render import compare_source_images_to_render_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            rendered_dir = root / "rendered"
            rendered_dir.mkdir()
            rendered = rendered_dir / "slide_001.png"
            out = root / "diff"
            Image.new("RGB", (320, 180), "#cc3344").save(source)
            Image.new("RGB", (320, 180), "#cc3344").save(rendered)

            report = compare_source_images_to_render_dir([source], rendered_dir, out, fail_mae=0.1, fail_changed_pct=0.1)
            contact_exists = Path(report["contact_sheet"]).exists()

        self.assertEqual(report["schema_version"], "easyslides.source_render_compare_report.v1")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)
        self.assertEqual(report["avg_mae"], 0.0)
        self.assertTrue(contact_exists)

    def test_large_difference_fails_with_hotspots(self):
        from scripts.compare_source_render import compare_source_images_to_render_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            rendered_dir = root / "rendered"
            rendered_dir.mkdir()
            rendered = rendered_dir / "slide_001.png"
            out = root / "diff"
            Image.new("RGB", (320, 180), "white").save(source)
            Image.new("RGB", (320, 180), "black").save(rendered)

            report = compare_source_images_to_render_dir([source], rendered_dir, out, fail_mae=1, fail_changed_pct=1)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_count"], 1)
        self.assertEqual(report["issues"][0]["code"], "SOURCE-RENDER-DIFF-THRESHOLD")
        self.assertTrue(report["slides"][0]["worst_regions"])

    def test_cli_writes_metrics_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            rendered_dir = root / "rendered"
            rendered_dir.mkdir()
            rendered = rendered_dir / "slide_001.png"
            out = root / "diff"
            Image.new("RGB", (160, 90), "#224466").save(source)
            Image.new("RGB", (160, 90), "#224466").save(rendered)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/compare_source_render.py",
                    str(source),
                    "--rendered-dir",
                    str(rendered_dir),
                    "--out",
                    str(out),
                    "--quiet",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((out / "metrics.json").read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
