import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class VisualMeasureGateTests(unittest.TestCase):
    def test_template_slot_contract_requires_preserve_geometry_replacement(self):
        from scripts.visual_measure_gate import validate_template_slot_contract

        with tempfile.TemporaryDirectory() as temp_dir:
            template_dir = Path(temp_dir)
            (template_dir / "slot_contracts.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.template_slot_contracts.v1",
                        "template_id": "demo",
                        "replacement_rule": "freeform_rebuild",
                        "layouts": [
                            {
                                "layout_id": "L1",
                                "slots": ["TITLE"],
                                "text_slots": ["TITLE"],
                                "image_slots": [],
                                "replacement": "freeform_rebuild",
                                "slot_details": [{"slot_id": "TITLE", "kind": "text"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = validate_template_slot_contract(template_dir)

        self.assertEqual(report["schema_version"], "easyslides.template_slot_contract_report.v1")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_count"], 2)
        self.assertEqual(
            [issue["code"] for issue in report["issues"]],
            ["SLOT-CONTRACT-REPLACEMENT-RULE", "SLOT-CONTRACT-LAYOUT-REPLACEMENT"],
        )

    def test_build_visual_measure_report_combines_gate_status_and_issues(self):
        from scripts.visual_measure_gate import GateReport, build_visual_measure_report

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            geometry_path = root / "geometry_report.json"
            text_path = root / "text_layout_report.json"
            diff_path = root / "visual_diff" / "metrics.json"

            geometry = {
                "schema_version": "easyslides.template_geometry_qa_report.v1",
                "status": "fail",
                "blocking_count": 1,
                "warning_count": 0,
                "issues": [
                    {
                        "code": "SVG-TEXT-CONTAINER-OVERFLOW",
                        "severity": "blocking",
                        "svg": "03_content.svg",
                        "message": "Text exceeds declared container body.",
                    }
                ],
            }
            text = {
                "schema_version": "easyslides.pptx_text_layout_report.v1",
                "status": "pass",
                "blocking_count": 0,
                "warning_count": 1,
                "issues": [
                    {
                        "code": "TEXT-LABEL-TOO-LONG",
                        "severity": "warning",
                        "slide_number": 2,
                        "shape_name": "subtitle",
                        "message": "A small label-like slot contains sentence-length text.",
                    }
                ],
            }
            visual_diff = {
                "schema_version": "easyslides.pptx_visual_diff_report.v1",
                "status": "pass",
                "slide_count": 3,
                "avg_mae": 0.25,
                "avg_changed_pct": 1.2,
                "worst_slide": {"slide": 2, "mae": 0.7},
                "slides": [],
            }

            report = build_visual_measure_report(
                [
                    GateReport("template_geometry_svg", geometry, geometry_path),
                    GateReport("pptx_text_layout", text, text_path),
                    GateReport("render_diff", visual_diff, diff_path),
                ]
            )

        self.assertEqual(report["schema_version"], "easyslides.visual_measure_report.v1")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_count"], 1)
        self.assertEqual(report["warning_count"], 1)
        self.assertEqual([gate["name"] for gate in report["gates"]], ["template_geometry_svg", "pptx_text_layout", "render_diff"])
        self.assertEqual(report["gates"][0]["status"], "fail")
        self.assertEqual(report["gates"][2]["summary"]["avg_mae"], 0.25)
        self.assertEqual(report["issues"][0]["gate"], "template_geometry_svg")
        self.assertEqual(report["issues"][0]["code"], "SVG-TEXT-CONTAINER-OVERFLOW")
        self.assertIn("suggestion", report["issues"][0])
        self.assertTrue(report["issues"][0]["suggestion"])
        self.assertEqual(report["issues"][1]["gate"], "pptx_text_layout")

    def test_cli_combines_existing_json_reports(self):
        from scripts.visual_measure_gate import main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            blocking_report = root / "geometry.json"
            warning_report = root / "text.json"
            output_report = root / "visual_measure_report.json"
            blocking_report.write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.template_geometry_qa_report.v1",
                        "status": "fail",
                        "blocking_count": 1,
                        "warning_count": 0,
                        "issues": [{"code": "PPTX-TEXT-PROTECTED-OVERLAP", "severity": "blocking"}],
                    }
                ),
                encoding="utf-8",
            )
            warning_report.write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.pptx_text_layout_report.v1",
                        "status": "pass",
                        "blocking_count": 0,
                        "warning_count": 1,
                        "issues": [{"code": "TEXT-LABEL-TOO-LONG", "severity": "warning"}],
                    }
                ),
                encoding="utf-8",
            )

            code = main(
                [
                    "--existing-report",
                    f"template_geometry_pptx={blocking_report}",
                    "--existing-report",
                    f"pptx_text_layout={warning_report}",
                    "--report",
                    str(output_report),
                    "--quiet",
                ]
            )

            payload = json.loads(output_report.read_text(encoding="utf-8"))

        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["blocking_count"], 1)
        self.assertEqual(payload["warning_count"], 1)

    def test_cli_can_include_source_render_diff_gate(self):
        from scripts.visual_measure_gate import main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            rendered_dir = root / "rendered"
            rendered_dir.mkdir()
            rendered = rendered_dir / "slide_001.png"
            output_report = root / "visual_measure_report.json"
            Image.new("RGB", (160, 90), "#336699").save(source)
            Image.new("RGB", (160, 90), "#336699").save(rendered)

            code = main(
                [
                    "--source-image",
                    str(source),
                    "--rendered-slide-dir",
                    str(rendered_dir),
                    "--report",
                    str(output_report),
                    "--quiet",
                ]
            )

            payload = json.loads(output_report.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["gate_count"], 1)
        self.assertEqual(payload["gates"][0]["name"], "source_render_diff")
        self.assertEqual(payload["gates"][0]["summary"]["avg_mae"], 0.0)

    def test_cli_can_include_split_assets_gate(self):
        from scripts.visual_measure_gate import main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            asset = root / "plain_asset.png"
            manifest = root / "split_manifest.json"
            output_report = root / "visual_measure_report.json"
            Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(asset)
            image = Image.open(asset)
            pixels = image.load()
            for y in range(8, 24):
                for x in range(8, 24):
                    pixels[x, y] = (0, 0, 0, 255)
            image.save(asset)
            manifest.write_text(json.dumps({"assets": [{"name": "plain_asset", "path": str(asset)}]}), encoding="utf-8")

            code = main(
                [
                    "--split-assets-manifest",
                    str(manifest),
                    "--report",
                    str(output_report),
                    "--quiet",
                ]
            )

            payload = json.loads(output_report.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["gate_count"], 1)
        self.assertEqual(payload["gates"][0]["name"], "split_assets")
        self.assertEqual(payload["gates"][0]["summary"]["asset_count"], 1)


if __name__ == "__main__":
    unittest.main()
