import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CapacityStressDemoTests(unittest.TestCase):
    def test_demo_generator_writes_capacity_report_and_svgs(self):
        from scripts.generate_capacity_stress_demo import CASE_LABELS, generate_demo

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "capacity_stress_demo"
            report = generate_demo(project, render_png=False)

            self.assertEqual(report["schema_version"], "easyslides.capacity_stress_report.v1")
            self.assertEqual(len(report["templates"]), 5)
            self.assertEqual(report["slide_count"], 15)
            self.assertEqual(report["overflow_count"], 0)
            self.assertTrue((project / "capacity_matrix.md").exists())
            self.assertTrue((project / "capacity_report.json").exists())
            self.assertEqual(len(list((project / "svg_output").glob("*.svg"))), 15)

            saved = json.loads((project / "capacity_report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["overflow_count"], 0)
            overload_body_checks = [
                check
                for check in saved["checks"]
                if check["case"] == "overload"
                and check["role"] == "body"
                and check["requested_chars"] > check["capacity_chars"]
            ]
            self.assertEqual(len(overload_body_checks), 5)
            self.assertTrue(all(check["requested_chars"] > check["capacity_chars"] for check in overload_body_checks))
            self.assertTrue(all(check["overflow"] is False for check in overload_body_checks))

            for svg_path in (project / "svg_output").glob("*.svg"):
                root = ET.parse(svg_path).getroot()
                page_titles = [
                    elem
                    for elem in root.iter()
                    if elem.tag.endswith("text") and elem.get("data-slot") == "PAGE_TITLE"
                ]
                key_messages = [
                    elem
                    for elem in root.iter()
                    if elem.tag.endswith("text") and elem.get("data-slot") == "KEY_MESSAGE"
                ]
                self.assertLessEqual(len(page_titles), 1)
                for title in page_titles:
                    title_text = "".join(title.itertext())
                    self.assertIn(title_text, set(CASE_LABELS.values()))
                    self.assertLessEqual(len(list(title)), 1)
                for message in key_messages:
                    self.assertLessEqual(len(list(message)), 2)

    def test_demo_generator_cli_can_run_as_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "capacity_stress_demo"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "generate_capacity_stress_demo.py"),
                    str(project),
                    "--no-render",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
