import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_reference_workspace(root: Path) -> Path:
    workspace = root / "source"
    (workspace / "svg-flat").mkdir(parents=True)
    (workspace / "assets").mkdir()
    write_json(
        workspace / "manifest.json",
        {
            "source": {"pptx": str(root / "source.pptx"), "name": "source.pptx"},
            "slideSize": {"width": 1280, "height": 720},
            "theme": {
                "colors": {"accent1": "#8B0012", "lt1": "#FFFFFF"},
                "fonts": {"majorLatin": "Aptos Display", "minorLatin": "Aptos"},
            },
            "assets": {"commonAssets": [], "allAssets": [], "assetMap": {}},
            "pageTypeCandidates": {
                "cover_candidate": [1],
                "content_candidate": [2],
                "ending_candidate": [3],
            },
            "layouts": [],
            "masters": [],
            "slides": [
                {
                    "index": 1,
                    "flatSvgFile": "slide_01.svg",
                    "pageType": "cover_candidate",
                    "textSamples": ["A Study Title", "Presenter"],
                    "textCount": 2,
                    "shapeCount": 8,
                    "imageAssets": [],
                    "backgroundAsset": None,
                },
                {
                    "index": 2,
                    "flatSvgFile": "slide_02.svg",
                    "pageType": "content_candidate",
                    "textSamples": ["Key finding", "Body evidence"],
                    "textCount": 2,
                    "shapeCount": 14,
                    "imageAssets": ["figure.png"],
                    "backgroundAsset": None,
                },
                {
                    "index": 3,
                    "flatSvgFile": "slide_03.svg",
                    "pageType": "ending_candidate",
                    "textSamples": ["Thank You"],
                    "textCount": 1,
                    "shapeCount": 5,
                    "imageAssets": [],
                    "backgroundAsset": None,
                },
            ],
        },
    )
    for index, title in ((1, "A Study Title"), (2, "Key finding"), (3, "Thank You")):
        (workspace / "svg-flat" / f"slide_{index:02d}.svg").write_text(
            f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <linearGradient id="accentFade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#8B0012"/>
      <stop offset="1" stop-color="#8B0012" stop-opacity="0"/>
    </linearGradient>
    <filter id="softShadow"><feDropShadow dx="0" dy="4" stdDeviation="2" flood-color="#8B0012" flood-opacity="0.35"/></filter>
  </defs>
  <rect x="0" y="0" width="1280" height="80" fill="url(#accentFade)" filter="url(#softShadow)"/>
  <text x="80" y="60" font-size="32">{title}</text>
  <text x="80" y="140" font-size="20">Body evidence</text>
  <image x="720" y="160" width="420" height="300" href="assets/figure.png"/>
</svg>
""",
            encoding="utf-8",
        )
    return workspace


class PptxTemplateDistillTests(unittest.TestCase):
    def test_element_geometry_uses_roundtrip_textbox_dimensions(self):
        from scripts.pptx_template_distill import element_geometry

        node = ET.fromstring(
            """<text x="0" y="0" data-pptx-box-x="12" data-pptx-box-y="24"
              data-pptx-box-w="320" data-pptx-box-h="44" font-size="20">Label</text>"""
        )

        geometry = element_geometry(node)

        self.assertEqual(geometry["x"], 12)
        self.assertEqual(geometry["y"], 24)
        self.assertEqual(geometry["width"], 320)
        self.assertEqual(geometry["height"], 44)

    def test_compact_control_textboxes_are_center_locked(self):
        from scripts.pptx_template_distill import normalize_compact_control_text_alignment, tag_name

        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">
  <rect x="100" y="200" width="160" height="44" rx="22" ry="22" fill="#751497"/>
  <text x="180" y="230" text-anchor="middle" data-pptx-textbox="true"
    data-pptx-box-x="120" data-pptx-box-y="205" data-pptx-box-w="120"
    data-pptx-box-h="34" data-pptx-valign="top" font-size="22">Badge</text>
  <text x="80" y="90" data-pptx-textbox="true" data-pptx-box-x="70"
    data-pptx-box-y="60" data-pptx-box-w="600" data-pptx-box-h="54"
    data-pptx-valign="top" font-size="32">Title</text>
  <text x="420" y="120" data-pptx-textbox="true" data-pptx-box-x="410"
    data-pptx-box-y="92" data-pptx-box-w="120" data-pptx-box-h="32"
    data-pptx-valign="top" font-size="24">Status</text>
</svg>"""

        root = ET.fromstring(normalize_compact_control_text_alignment(svg))
        texts = [node for node in root.iter() if tag_name(node) == "text"]
        badge, title, status = texts

        self.assertEqual(badge.attrib["data-pptx-valign"], "middle")
        center = float(badge.attrib["data-pptx-box-y"]) + float(badge.attrib["data-pptx-box-h"]) / 2
        self.assertAlmostEqual(center, 222.0)
        self.assertEqual(title.attrib["data-pptx-valign"], "top")
        self.assertEqual(status.attrib["data-pptx-valign"], "middle")

    def test_small_badge_rectangles_are_not_inferred_as_text_containers(self):
        from scripts.pptx_template_distill import infer_containers

        rects = [
            {
                "x": 150,
                "y": 460,
                "width": 128,
                "height": 44,
                "fill": "url(#accent)",
                "stroke": "#FFFFFF",
            },
            {
                "x": 90,
                "y": 150,
                "width": 620,
                "height": 220,
                "fill": "#FFFFFF",
                "stroke": "#751497",
            },
        ]

        containers = infer_containers(rects, protected=[], width=1280, height=720)

        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0]["x"], 90)
        self.assertEqual(containers[0]["height"], 220)

    def test_top_chrome_gradient_strip_is_protected_not_container(self):
        from scripts.pptx_template_distill import infer_containers, infer_protected_regions

        rects = [
            {
                "x": 0,
                "y": 0,
                "width": 1280,
                "height": 79.18,
                "fill": "url(#ggrad2)",
                "stroke": "none",
            },
            {
                "x": 50,
                "y": 110,
                "width": 1100,
                "height": 140,
                "fill": "#FFFFFF",
                "stroke": "#751497",
            },
        ]

        protected = infer_protected_regions(rects, width=1280, height=720)
        containers = infer_containers(rects, protected=protected, width=1280, height=720)

        self.assertEqual([region["id"] for region in protected], ["top_chrome"])
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0]["y"], 110)

    def test_writes_distilled_spec_and_slot_guided_template_pack(self):
        from scripts.pptx_template_distill import build_from_reference_workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_workspace = make_reference_workspace(root)
            template_dir = root / "fixture_distilled"

            result = build_from_reference_workspace(
                source_workspace=source_workspace,
                template_dir=template_dir,
                template_id="fixture_distilled",
                source_pptx=root / "source.pptx",
            )

            distilled = json.loads((source_workspace / "distilled_spec.json").read_text(encoding="utf-8"))
            rebuild_plan = json.loads((source_workspace / "editable_rebuild_plan.json").read_text(encoding="utf-8"))
            adaptation = json.loads((source_workspace / "adaptation_strategy.json").read_text(encoding="utf-8"))
            source_geometry = json.loads((source_workspace / "source_geometry_risks.json").read_text(encoding="utf-8"))
            design_spec = (template_dir / "design_spec.md").read_text(encoding="utf-8")
            layouts = json.loads((template_dir / "layouts.json").read_text(encoding="utf-8"))
            catalog = json.loads((template_dir / "page_catalog.json").read_text(encoding="utf-8"))
            geometry = json.loads((template_dir / "geometry_contract.json").read_text(encoding="utf-8"))
            template = json.loads((template_dir / "template.json").read_text(encoding="utf-8"))
            language_report_exists = (source_workspace / "template_language.md").exists()

        self.assertEqual(result["template_id"], "fixture_distilled")
        self.assertEqual(distilled["source"]["slide_size"], [1280, 720])
        self.assertTrue(distilled["identity_must_preserve"])
        self.assertIn("forbidden_drift", distilled)
        language = distilled["template_language"]
        self.assertEqual(language["visual_system"]["primary_color"], "#8B0012")
        self.assertIn("content", {item["role"] for item in language["layout_grammar"]})
        self.assertIn("gradient_or_filter_effects", {risk["risk"] for risk in language["fidelity_risks"]})
        self.assertEqual(language["editable_rebuild_plan"][0]["surface"], "source_rendered_raster_baseline")
        self.assertTrue(language_report_exists)
        self.assertEqual(rebuild_plan["baseline"]["surface"], "source_rendered_raster_baseline")
        self.assertIn("atmosphere_background", {item["primitive"] for item in rebuild_plan["primitive_candidates"]})
        self.assertIn("visual_diff_gate", {phase["id"] for phase in rebuild_plan["phases"]})
        self.assertIn("research_problem", {item["id"] for item in adaptation["material_types"]})
        self.assertIn("evidence_result", {item["id"] for item in adaptation["material_types"]})
        self.assertEqual(adaptation["selection_policy"]["default_route"], "classify_material_then_match_role_density_slots")
        self.assertIn("split_across_multiple_pages", adaptation["overflow_policy"]["actions"])
        self.assertIn("visual_diff_gate", {gate["id"] for gate in adaptation["validation_gates"]})
        self.assertIn("cross_material_smoke_test", {gate["id"] for gate in adaptation["validation_gates"]})
        smoke_gate = next(gate for gate in adaptation["validation_gates"] if gate["id"] == "cross_material_smoke_test")
        self.assertIn("scripts/template_material_smoke_test.py", smoke_gate["command"])
        self.assertTrue(distilled["qa_expectations"]["requires_cross_material_smoke_test"])
        self.assertEqual(source_geometry["schema_version"], "easyslides.source_geometry_risks.v1")
        self.assertIn("blocking_count", source_geometry)
        self.assertEqual(result["source_geometry_risks"], str(source_workspace / "source_geometry_risks.json"))
        self.assertEqual(layouts["global_contract"]["replication_mode"], "slot_guided_mirror")
        self.assertEqual(len(layouts["pages"]), 3)
        self.assertEqual(layouts["pages"][0]["story_role"], "cover")
        self.assertEqual(layouts["pages"][1]["story_role"], "content")
        self.assertIn("PAGE_TITLE", {slot["slot_id"] for slot in layouts["slot_models"]["content"]})
        self.assertIn("placeholders:", design_spec)
        self.assertIn("{{PAGE_TITLE}}", design_spec)
        frontmatter = design_spec.split("\n---\n", 1)[0]
        self.assertIn('"02_content": ["{{PAGE_TITLE}}", "{{BODY_TEXT_01}}", "{{IMAGE_01}}"]', frontmatter)
        self.assertEqual(catalog["pages"][1]["source_slide"], 2)
        self.assertEqual(geometry["schema_version"], "easyslides.template_geometry_contract.v1")
        self.assertEqual(len(geometry["pages"]), 3)
        self.assertIn("containers", geometry["pages"][1])
        self.assertEqual(template["template_id"], "fixture_distilled")

    def test_sanitizes_template_id_for_paths_and_frontmatter(self):
        from scripts.pptx_template_distill import sanitize_template_id

        self.assertEqual(sanitize_template_id("Academic Red Nav 6!"), "academic_red_nav_6")
        self.assertEqual(sanitize_template_id("___"), "pptx_distilled_template")


if __name__ == "__main__":
    unittest.main()
