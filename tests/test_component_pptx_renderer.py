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
    def test_reports_no_public_component_packages_after_template_migration(self):
        from scripts.component_pptx_renderer import build_component_pptx

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "component_gallery.pptx"
            report = build_component_pptx(output_path=output, validate_text_layout=True)

        self.assertEqual(report["schema_version"], "easyslides.component_pptx_renderer_report.v1")
        self.assertEqual(report["status"], "not_applicable")
        self.assertEqual(report["reason"], "no_public_component_packages")
        self.assertEqual(report["slide_count"], 0)
        self.assertEqual(report["text_layout_status"], "not_applicable")
        self.assertFalse(output.exists())

    def test_cli_reports_no_public_component_packages(self):
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
            self.assertFalse(output.exists())
            report = json.loads(result.stdout)

        self.assertEqual(report["status"], "not_applicable", report)
        self.assertEqual(report["slide_count"], 0)


if __name__ == "__main__":
    unittest.main()
