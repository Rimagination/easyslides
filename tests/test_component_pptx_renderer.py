import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from pptx import Presentation


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "component_pptx_renderer.py"


class ComponentPptxRendererTests(unittest.TestCase):
    def test_builds_native_pptx_preview_with_center_anchors(self):
        from scripts.component_pptx_renderer import build_component_pptx

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "component_gallery.pptx"
            report = build_component_pptx(output_path=output, validate_text_layout=True)
            prs = Presentation(str(output))
            with zipfile.ZipFile(output) as archive:
                slide_xml = "\n".join(
                    archive.read(name).decode("utf-8")
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                )

        self.assertEqual(report["schema_version"], "easyslides.component_pptx_renderer_report.v1")
        self.assertEqual(report["status"], "pass", report["text_layout_report"])
        self.assertEqual(report["slide_count"], 18)
        self.assertEqual(report["text_layout_status"], "pass")
        self.assertEqual(report["text_layout_report"]["warning_count"], 0)
        self.assertEqual(len(prs.slides), 18)
        self.assertIn('anchor="ctr"', slide_xml)
        self.assertGreater(report["center_anchor_textbox_count"], 0)

    def test_cli_writes_pptx(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "component_gallery.pptx"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "--out",
                    str(output),
                    "--validate-text-layout",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.exists())
            report = json.loads(result.stdout)

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["slide_count"], 18)


if __name__ == "__main__":
    unittest.main()
