import json
import tempfile
import unittest
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_template(root: Path) -> Path:
    template = root / "fixture"
    (template / "assets").mkdir(parents=True)
    (template / "01_cover.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  <text x="90" y="150" data-pptx-textbox="true" data-pptx-box-x="90" data-pptx-box-y="104"
    data-pptx-box-w="760" data-pptx-box-h="64" data-pptx-valign="top" font-size="42">Original Title</text>
</svg>
""",
        encoding="utf-8",
    )
    write_json(
        template / "layouts.json",
        {
            "template_id": "fixture",
            "pages": [{"id": "01_cover", "svg": "01_cover.svg", "story_role": "cover", "source_slide": 1}],
            "slot_models": {"cover": [{"slot_id": "TITLE", "kind": "text"}]},
        },
    )
    write_json(
        template / "page_catalog.json",
        {
            "schema_version": "easyslides.page_catalog.v1",
            "template_id": "fixture",
            "pages": [{"id": "01_cover", "source_slide": 1, "story_role": "cover"}],
        },
    )
    write_json(
        template / "geometry_contract.json",
        {
            "schema_version": "easyslides.template_geometry_contract.v1",
            "template_id": "fixture",
            "canvas": {"width": 1280, "height": 720},
            "pages": [{"id": "01_cover", "svg": "01_cover.svg", "protected_regions": [], "containers": []}],
        },
    )
    return template


class TemplateDistillAcceptanceTests(unittest.TestCase):
    def test_dry_run_plans_faithful_and_cross_material_gates(self):
        from scripts.template_distill_acceptance import run_acceptance

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(root)
            out = root / "acceptance"

            report = run_acceptance(
                template_dir=template,
                output_dir=out,
                forbidden_keywords=["Original"],
                render_contact=False,
                dry_run=True,
            )

        gate_ids = {gate["id"] for gate in report["gates"]}
        self.assertEqual(report["status"], "planned")
        self.assertIn("svg_geometry", gate_ids)
        self.assertIn("native_pptx_export", gate_ids)
        self.assertIn("pptx_text_layout", gate_ids)
        self.assertIn("material_smoke_build", gate_ids)
        self.assertIn("material_smoke_pptx_geometry", gate_ids)

    def test_optional_render_is_explicitly_skipped_when_renderer_missing(self):
        import scripts.template_distill_acceptance as acceptance

        original = acceptance.renderer_available
        acceptance.renderer_available = lambda: False
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                template = make_template(root)
                report = acceptance.run_acceptance(
                    template_dir=template,
                    output_dir=root / "acceptance",
                    dry_run=True,
                )
        finally:
            acceptance.renderer_available = original

        render_gate = next(gate for gate in report["gates"] if gate["id"] == "render_contact_sheet")
        self.assertFalse(render_gate["required"])
        self.assertEqual(render_gate["status"], "skipped")

    def test_required_render_stays_required_even_when_renderer_missing(self):
        import scripts.template_distill_acceptance as acceptance

        original = acceptance.renderer_available
        acceptance.renderer_available = lambda: False
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                template = make_template(root)
                report = acceptance.run_acceptance(
                    template_dir=template,
                    output_dir=root / "acceptance",
                    require_render=True,
                    dry_run=True,
                )
        finally:
            acceptance.renderer_available = original

        render_gate = next(gate for gate in report["gates"] if gate["id"] == "render_contact_sheet")
        self.assertTrue(render_gate["required"])
        self.assertEqual(render_gate["status"], "planned")


if __name__ == "__main__":
    unittest.main()
