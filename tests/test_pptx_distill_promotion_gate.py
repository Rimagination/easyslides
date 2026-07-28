import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PptxDistillPromotionGateTests(unittest.TestCase):
    def test_promotion_status_fails_before_review_and_pass(self):
        from scripts.pptx_distill_promotion_gate import resolve_promotion_status

        self.assertEqual(resolve_promotion_status([{"status": "pass"}, {"status": "review_required"}]), "review_required")
        self.assertEqual(resolve_promotion_status([{"status": "fail"}, {"status": "review_required"}]), "fail")
        self.assertEqual(resolve_promotion_status([{"status": "pass"}, {"status": "pass"}]), "pass")

    def test_projection_review_is_not_silently_promotable(self):
        from scripts.pptx_distill_promotion_gate import validate_projection

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source_svg = workspace / "svg-flat" / "slide_01.svg"
            source_svg.parent.mkdir()
            source_svg.write_text("<svg />", encoding="utf-8")
            (workspace / "projection_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.pptx_projection_manifest.v1",
                        "renderer_mappings": [{"renderer_id": "source_template_projection"}],
                        "pages": [
                            {
                                "slide_id": "slide-01",
                                "status": "ready",
                                "source_svg": str(source_svg),
                                "source_svg_exists": True,
                            }
                        ],
                        "components": [
                            {
                                "component_id": "component-unknown",
                                "classification": "unknown",
                                "status": "review_required",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = validate_projection(workspace)

        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["blocking_count"], 0)
        self.assertEqual(report["review_count"], 1)

    def test_projection_missing_source_geometry_is_blocking(self):
        from scripts.pptx_distill_promotion_gate import validate_projection

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "projection_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.pptx_projection_manifest.v1",
                        "renderer_mappings": [{"renderer_id": "source_template_projection"}],
                        "pages": [
                            {
                                "slide_id": "slide-01",
                                "status": "ready",
                                "source_svg": str(workspace / "missing.svg"),
                                "source_svg_exists": False,
                            }
                        ],
                        "components": [],
                    }
                ),
                encoding="utf-8",
            )

            report = validate_projection(workspace)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_count"], 1)
        self.assertEqual(report["issues"][0]["code"], "PROJECTION-SOURCE-SVG-MISSING")

    def test_distill_artifact_manifest_is_checked(self):
        from scripts.pptx_distill_promotion_gate import REQUIRED_DISTILL_ARTIFACTS, validate_distill_artifacts

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            artifacts = {key: f"{key}.json" for key in REQUIRED_DISTILL_ARTIFACTS}
            for filename in artifacts.values():
                (workspace / filename).write_text("{}", encoding="utf-8")
            (workspace / "distill_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.distill_manifest.v1",
                        "stage": "phase_5_qa_and_promotion",
                        "artifacts": artifacts,
                    }
                ),
                encoding="utf-8",
            )

            report = validate_distill_artifacts(workspace)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)

    def test_cross_material_gate_checks_native_pptx_outputs(self):
        from scripts import pptx_distill_promotion_gate as gate

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_dir = root / "template"
            report_dir = root / "reports"
            template_dir.mkdir()

            def fake_smoke(_template_dir, smoke_dir, **_kwargs):
                smoke_dir.mkdir(parents=True, exist_ok=True)
                (smoke_dir / "material_smoke_manifest.json").write_text("{}", encoding="utf-8")
                return {
                    "status": "pass",
                    "failures": [],
                    "page_count": 1,
                    "text_replacement_ratio": 1.0,
                    "image_replaced_count": 1,
                }

            def fake_export(*_args, **_kwargs):
                (report_dir / "material_smoke.pptx").parent.mkdir(parents=True, exist_ok=True)
                (report_dir / "material_smoke.pptx").write_bytes(b"pptx")
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            clean = {"status": "pass", "blocking_count": 0, "warning_count": 0, "issues": []}
            with (
                patch.object(gate.template_material_smoke_test, "run_material_smoke_test", side_effect=fake_smoke),
                patch.object(gate.template_geometry_qa, "validate_template_geometry", return_value=clean),
                patch.object(gate.template_geometry_qa, "validate_pptx_against_contract", return_value=clean),
                patch.object(gate.validate_pptx_text_layout, "validate_pptx_text_layout", return_value=clean),
                patch.object(gate.subprocess, "run", side_effect=fake_export),
            ):
                report = gate.run_cross_material_gate(
                    template_dir=template_dir,
                    report_dir=report_dir,
                    forbidden_keywords=[],
                    max_pages=1,
                )

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["native_pptx"].endswith("material_smoke.pptx"))
        self.assertTrue(report["native_text_report"])
        self.assertTrue(report["native_geometry_report"])


if __name__ == "__main__":
    unittest.main()
