import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = ROOT / "templates" / "icons"
BUILDER = ROOT / "scripts" / "build_icon_gallery.py"


def parse_manifest_js(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    prefix = "window.ICON_MANIFEST = "
    suffix = ";\n"
    if not text.startswith(prefix) or not text.endswith(suffix):
        raise AssertionError("manifest must be a browser-ready JS assignment")
    return json.loads(text[len(prefix) : -len(suffix)])


class IconGalleryTests(unittest.TestCase):
    def test_manifest_builder_generates_browser_ready_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sample_icons = tmp_path / "icons"
            (sample_icons / "chunk-filled").mkdir(parents=True)
            (sample_icons / "simple-icons").mkdir()
            (sample_icons / "chunk-filled" / "home.svg").write_text(
                '<svg viewBox="0 0 16 16"></svg>',
                encoding="utf-8",
            )
            (sample_icons / "simple-icons" / "openai.svg").write_text(
                '<svg viewBox="0 0 24 24"></svg>',
                encoding="utf-8",
            )
            manifest_path = tmp_path / "icons_manifest.js"

            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--icons-dir",
                    str(sample_icons),
                    "--manifest",
                    str(manifest_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = parse_manifest_js(manifest_path)
            self.assertEqual(manifest["total"], 2)
            self.assertEqual(
                [family["id"] for family in manifest["families"]],
                ["chunk-filled", "simple-icons"],
            )
            self.assertEqual(manifest["families"][0]["icons"][0]["token"], "chunk-filled/home")
            self.assertEqual(manifest["families"][0]["icons"][0]["path"], "chunk-filled/home.svg")

    def test_icon_gallery_assets_cover_full_local_library(self):
        html_path = ICONS_DIR / "index.html"
        manifest_path = ICONS_DIR / "icons_manifest.js"

        self.assertTrue(html_path.exists(), "templates/icons/index.html is required")
        self.assertTrue(manifest_path.exists(), "templates/icons/icons_manifest.js is required")

        html = html_path.read_text(encoding="utf-8")
        self.assertIn("icons_manifest.js", html)
        self.assertIn("data-gallery-root", html)

        manifest = parse_manifest_js(manifest_path)
        expected_counts = {
            "chunk-filled": 640,
            "lucide": 4,
            "phosphor-duotone": 1248,
            "simple-icons": 3651,
            "tabler-filled": 1053,
            "tabler-outline": 5039,
        }
        actual_counts = {
            family["id"]: len(family["icons"])
            for family in manifest["families"]
        }
        self.assertEqual(actual_counts, expected_counts)
        self.assertEqual(manifest["total"], 11635)


if __name__ == "__main__":
    unittest.main()
