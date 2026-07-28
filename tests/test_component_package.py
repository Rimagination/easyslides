import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "component_package.py"


class ComponentPackageTests(unittest.TestCase):
    def test_component_packages_validate(self):
        from scripts.component_package import validate_component_packages

        report = validate_component_packages(ROOT / "templates" / "components" / "packages")

        self.assertEqual(report["schema_version"], "easyslides.component_package_report.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertGreaterEqual(report["package_count"], 6)

    def test_missing_vertical_center_invariant_fails(self):
        from scripts.component_package import validate_component_package

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = Path(tmp)
            package = {
                "schema_version": "easyslides.component_package.v1",
                "component_id": "bad_component",
                "asset_id": "component_package/bad_component",
                "source_asset_id": "card/three_card_summary",
                "granularity": "component_package",
                "render_backend": "component_package",
                "selection": {"content_shapes": ["parallel_points"]},
                "input_schema": {
                    "schema_version": "easyslides.component_input_schema.v1",
                    "type": "object",
                    "required": ["title"],
                    "additional_properties": False,
                    "properties": {"title": {"type": "string", "min_length": 1, "max_length": 20}},
                },
                "slots": [
                    {
                        "slot_id": "title",
                        "kind": "text",
                        "capacity": {
                            "font_size_px": 20,
                            "min_font_size_px": 16,
                            "line_height": 1.2,
                            "max_chars_per_line_zh": 10,
                            "max_lines": 1,
                            "overflow_action": "shorten",
                        },
                    }
                ],
                "qa": {"required_gates": ["component_package_contract"]},
                "stories": [
                    {
                        "story_id": "default",
                        "payload": "stories/default.json",
                    }
                ],
            }
            story_dir = package_dir / "stories"
            story_dir.mkdir()
            (story_dir / "default.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.component_story.v1",
                        "story_id": "default",
                        "payload": {"title": "Bad"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = validate_component_package(package_dir, package)

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PACKAGE-VERTICAL-CENTER", {item["code"] for item in report["issues"]})

    def test_cli_validates_component_packages(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass", report["issues"])


if __name__ == "__main__":
    unittest.main()
