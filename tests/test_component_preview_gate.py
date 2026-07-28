import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "component_preview_gate.py"


class ComponentPreviewGateTests(unittest.TestCase):
    def test_center_locked_preview_passes_gate(self):
        from scripts.component_preview_gate import validate_component_preview_dir

        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp) / "previews"
            preview_root.mkdir()
            (preview_root / "ok.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
  <text data-pptx-textbox="true" data-pptx-box-y="20" data-pptx-box-h="40"
        data-pptx-valign="middle" data-center-lock="true" data-slot-id="title"
        x="100" y="40"><tspan x="100" y="40">OK</tspan></text>
</svg>
""",
                encoding="utf-8",
            )
            report = validate_component_preview_dir(preview_root)

        self.assertEqual(report["schema_version"], "easyslides.component_preview_gate_report.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["svg_count"], 1)
        self.assertGreater(report["checked_text_count"], 0)

    def test_off_center_text_fails(self):
        from scripts.component_preview_gate import validate_component_preview_dir

        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp)
            (preview_root / "bad.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
  <text data-pptx-textbox="true" data-pptx-box-y="20" data-pptx-box-h="40"
        data-pptx-valign="middle" data-center-lock="true" data-slot-id="title"
        x="100" y="26"><tspan x="100" y="26">Bad</tspan></text>
</svg>
""",
                encoding="utf-8",
            )

            report = validate_component_preview_dir(preview_root)

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PREVIEW-CENTER", {item["code"] for item in report["issues"]})

    def test_missing_middle_valign_fails(self):
        from scripts.component_preview_gate import validate_component_preview_dir

        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp)
            (preview_root / "bad.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
  <text data-pptx-textbox="true" data-pptx-box-y="20" data-pptx-box-h="40"
        data-center-lock="true" data-slot-id="title"
        x="100" y="40"><tspan x="100" y="40">Bad</tspan></text>
</svg>
""",
                encoding="utf-8",
            )

            report = validate_component_preview_dir(preview_root)

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PREVIEW-VALIGN", {item["code"] for item in report["issues"]})

    def test_cli_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp) / "previews"
            preview_root.mkdir()
            (preview_root / "ok.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
  <text data-pptx-textbox="true" data-pptx-box-y="20" data-pptx-box-h="40"
        data-pptx-valign="middle" data-center-lock="true" data-slot-id="title"
        x="100" y="40"><tspan x="100" y="40">OK</tspan></text>
</svg>
""",
                encoding="utf-8",
            )
            report_path = Path(tmp) / "report.json"

            result = subprocess.run(
                [sys.executable, str(GATE), str(preview_root), "--report", str(report_path), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            stdout_report = json.loads(result.stdout)
            file_report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(stdout_report["status"], "pass")
        self.assertEqual(file_report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
