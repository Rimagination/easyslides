from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"
FIXTURE = ROOT / "tests" / "fixtures" / "nsfc_composable_deck_plan.json"


class SlideCompilerTests(unittest.TestCase):
    def _compile_fixture(self) -> dict:
        from scripts.slide_compiler import compile_slides
        from scripts.template_compiler import compile_template

        deck_plan = json.loads(FIXTURE.read_text(encoding="utf-8"))
        template_ir = compile_template(NSFC)["template_ir"]
        return compile_slides(deck_plan, template_ir)

    def test_compiles_source_like_scene_with_semantic_slots(self) -> None:
        slide_ir = self._compile_fixture()
        slide = slide_ir["slides"][0]
        component_layers = [layer for layer in slide["layers"] if layer["layer_type"] == "component"]

        self.assertEqual(slide_ir["schema_version"], "easyslides.slide_ir.v1")
        self.assertEqual(slide["shell_id"], "content")
        self.assertEqual(slide["body_variant_id"], "evidence_triptych")
        self.assertEqual([layer["instance_id"] for layer in component_layers], ["evidence_triptych"])
        self.assertIn("CLAIM", component_layers[0]["payload"])
        self.assertIn("RELATION_LEFT", component_layers[0]["payload"])
        self.assertNotIn("PRIMARY_BODY", component_layers[0]["payload"])
        for layer in component_layers:
            self.assertGreater(layer["frame"]["width"], 0)
            self.assertGreater(layer["frame"]["height"], 0)

    def test_cover_uses_shared_title_and_date_payload_names_without_duplicate_dates(self) -> None:
        from scripts.slide_compiler import SlideCompileError, compile_slides
        from scripts.template_compiler import compile_template

        template_ir = compile_template(NSFC)["template_ir"]
        payload = {
            "TITLE": "Memristive neural computing circuits",
            "PROJECT_TYPE": "National Natural Science Foundation project",
            "SUBTITLE": "Final defense presentation",
            "AFFILIATION": "Research University",
            "PRESENTER": "Liang",
            "DATE": "2026-07-28",
        }
        slide_ir = compile_slides(
            {"template_id": "nsfc_defense", "slides": [{"page": "C01", "role": "cover", "shell_payload": payload}]},
            template_ir,
        )

        self.assertEqual(slide_ir["slides"][0]["shell_id"], "cover")
        self.assertEqual(slide_ir["slides"][0]["shell_payload"], payload)
        with self.assertRaises(SlideCompileError):
            compile_slides(
                {
                    "template_id": "nsfc_defense",
                    "slides": [{"page": "C01", "role": "cover", "shell_payload": {"DATE_02": "duplicate"}}],
                },
                template_ir,
            )

    def test_renders_source_like_scene_to_svg_and_native_pptx(self) -> None:
        from scripts.slide_compiler import render_slide_ir_to_pptx, render_slide_ir_to_svg

        slide_ir = self._compile_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg_report = render_slide_ir_to_svg(slide_ir, root / "svg")
            svg = Path(svg_report["svg_files"][0])
            svg_root = ET.parse(svg).getroot()
            instances = [
                node.attrib["data-easyslides-instance"]
                for node in svg_root.iter()
                if node.attrib.get("data-easyslides-instance")
            ]
            pptx_path = root / "compiled.pptx"
            pptx_report = render_slide_ir_to_pptx(slide_ir, pptx_path, svg_output_dir=root / "pptx-svg")
            presentation = Presentation(pptx_path)
            synthesis = next(
                layer["payload"]["SYNTHESIS"]
                for layer in slide_ir["slides"][0]["layers"]
                if layer.get("instance_id") == "evidence_triptych"
            )

            def iter_shapes(shapes):
                for shape in shapes:
                    yield shape
                    if hasattr(shape, "shapes"):
                        yield from iter_shapes(shape.shapes)

            synthesis_shape = next(
                shape
                for shape in iter_shapes(presentation.slides[0].shapes)
                if getattr(shape, "has_text_frame", False) and shape.text.strip() == synthesis
            )

            self.assertEqual(svg_report["status"], "pass")
            self.assertEqual(instances, ["evidence_triptych"])
            self.assertIn('data-easyslides-instance="evidence_triptych"', svg.read_text(encoding="utf-8"))
            self.assertEqual(pptx_report["status"], "pass")
            self.assertEqual(len(presentation.slides), 1)
            self.assertGreater(synthesis_shape.width, Inches(5))
            self.assertGreater(synthesis_shape.height, Inches(0.3))
            self.assertLess(synthesis_shape.height, Inches(1))
            self.assertEqual(synthesis_shape.text_frame.vertical_anchor, MSO_ANCHOR.MIDDLE)

    def test_source_guided_content_rejects_direct_body_components(self) -> None:
        from scripts.slide_compiler import SlideCompileError, compile_slides
        from scripts.template_compiler import compile_template

        template_ir = compile_template(NSFC)["template_ir"]
        with self.assertRaisesRegex(SlideCompileError, "forbids direct body_components"):
            compile_slides(
                {
                    "template_id": "nsfc_defense",
                    "slides": [
                        {
                            "page": "P01",
                            "role": "content",
                            "section": "01",
                            "story_role": "national_need_evidence",
                            "body_variant_id": "evidence_triptych",
                            "shell_payload": {"PAGE_TITLE": "National need"},
                            "slot_payload": {},
                            "body_components": [{"component_id": "evidence_triptych", "frame": {"x": 92, "y": 170, "width": 510, "height": 360}, "slot_payload": {}}],
                        }
                    ],
                },
                template_ir,
            )

    def test_source_guided_content_requires_matching_section_and_story_role(self) -> None:
        from scripts.slide_compiler import SlideCompileError, compile_slides
        from scripts.template_compiler import compile_template

        template_ir = compile_template(NSFC)["template_ir"]
        with self.assertRaisesRegex(SlideCompileError, "does not permit story_role"):
            compile_slides(
                {
                    "template_id": "nsfc_defense",
                    "slides": [
                        {
                            "page": "P01",
                            "role": "content",
                            "section": "02",
                            "story_role": "method_comparison",
                            "body_variant_id": "evidence_triptych",
                            "shell_payload": {"PAGE_TITLE": "Method contrast"},
                            "slot_payload": {},
                        }
                    ],
                },
                template_ir,
            )

    def test_ambiguous_content_requires_an_explicit_choice(self) -> None:
        from scripts.slide_compiler import SlideCompileError, compile_slides
        from scripts.template_compiler import compile_template

        template_ir = compile_template(NSFC)["template_ir"]
        with self.assertRaisesRegex(SlideCompileError, "ambiguous"):
            compile_slides(
                {
                    "template_id": "nsfc_defense",
                    "slides": [{"page": "P01", "role": "content", "shell_payload": {"PAGE_TITLE": "Undefined content"}, "slot_payload": {}}],
                },
                template_ir,
            )


if __name__ == "__main__":
    unittest.main()
