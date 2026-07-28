from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "layouts" / "nsfc_defense"


class NsfcDefenseTemplateTests(unittest.TestCase):
    def test_canonical_template_uses_five_shells_and_preserves_source_roster(self) -> None:
        template = json.loads((TEMPLATE / "template.json").read_text(encoding="utf-8"))
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))
        slots = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))
        projection = json.loads((TEMPLATE / "projection_manifest.json").read_text(encoding="utf-8"))
        variants = json.loads((TEMPLATE / "body_variants.json").read_text(encoding="utf-8"))
        primitives = json.loads((TEMPLATE / "component_primitives.json").read_text(encoding="utf-8"))
        recipes = json.loads((TEMPLATE / "body_variant_recipes.json").read_text(encoding="utf-8"))
        roster = json.loads((TEMPLATE / "source_page_roster.json").read_text(encoding="utf-8"))
        registry = json.loads((ROOT / "templates" / "template_registry.json").read_text(encoding="utf-8"))

        self.assertEqual(template["template_id"], "nsfc_defense")
        self.assertEqual(template["source_template_id"], "nsfc_defense_distilled")
        self.assertEqual(template["content_organization"], ["national_need", "technical_innovation", "application_benefits"])
        self.assertEqual(len(layouts["layouts"]), 5)
        self.assertEqual(len(layouts["shells"]), 5)
        self.assertEqual(len(projection["pages"]), 5)
        self.assertEqual(len(slots["slots"]), 17)
        self.assertEqual(template["layout_count"], 5)
        self.assertEqual(template["variant_count"], 12)
        self.assertEqual(len(variants["variants"]), 12)
        self.assertEqual(primitives["tokens"]["grid"], 8)
        self.assertEqual(len(primitives["primitives"]), 10)
        for primitive in primitives["primitives"]:
            asset = TEMPLATE / primitive["asset_path"]
            self.assertTrue(asset.is_file(), primitive["primitive_id"])
            root = ET.fromstring(asset.read_text(encoding="utf-8"))
            slot_nodes = {
                node.attrib.get("data-slot-id")
                for node in root.iter()
                if node.attrib.get("data-slot-id")
            }
            self.assertEqual(slot_nodes, {slot["slot_id"] for slot in primitive["slots"]})
        self.assertEqual(len(recipes["recipes"]), 12)
        self.assertTrue(all(recipe["primitives"] for recipe in recipes["recipes"]))
        self.assertEqual(len(roster["pages"]), 17)
        self.assertEqual(roster["canonical_shell_count"], 5)
        self.assertEqual(roster["body_variant_count"], 12)
        self.assertIn("nsfc_defense", {row["template_id"] for row in registry["packages"]})
        self.assertIn("academic_general", {row["template_id"] for row in registry["templates"]})
        self.assertEqual(
            {row["page_id"] for row in layouts["layouts"]},
            {"cover", "toc", "chapter", "content", "ending"},
        )
        chapter = next(row for row in layouts["layouts"] if row["page_id"] == "chapter")
        self.assertEqual(chapter["slots"], ["CHAPTER_TITLE", "CHAPTER_DESC"])
        cover = next(row for row in layouts["layouts"] if row["page_id"] == "cover")
        self.assertEqual(
            cover["slots"],
            [
                "TITLE",
                "PROJECT_TYPE",
                "SUBTITLE",
                "AFFILIATION",
                "PRESENTER",
                "DATE",
            ],
        )
        self.assertNotIn("PROJECT_TITLE", cover["slots"])
        self.assertFalse(any(slot.startswith("DATE_") for slot in cover["slots"]))
        toc = next(row for row in layouts["layouts"] if row["page_id"] == "toc")
        self.assertEqual(toc["slots"], ["TOC_ITEM_01_TITLE", "TOC_ITEM_02_TITLE", "TOC_ITEM_03_TITLE"])
        content = next(row for row in layouts["layouts"] if row["page_id"] == "content")
        self.assertEqual(content["slots"], ["PAGE_TITLE"])
        self.assertEqual(content["content_shell_policy"], "source_guided_body_variant_required")
        self.assertEqual(content["body_canvas"], {"x": 64.0, "y": 116.0, "width": 1152.0, "height": 548.0})
        self.assertEqual(len(content["legacy_shadow_slots"]), 13)
        self.assertEqual(layouts["content_shell_contract"]["public_slots"], ["PAGE_TITLE"])
        ending = next(row for row in layouts["layouts"] if row["page_id"] == "ending")
        self.assertEqual(
            ending["slots"],
            ["CLOSING_TITLE", "CLOSING_SUBTITLE", "AFFILIATION", "PRESENTER", "DATE"],
        )
        self.assertEqual(
            {row["variant_id"] for row in variants["variants"]},
            {
                "evidence_triptych",
                "two_track_evidence",
                "bottleneck_chain",
                "hotspot_metrics",
                "hotspot_panels",
                "innovation_evidence",
                "ann_snn_comparison",
                "plasticity_training",
                "network_architecture",
                "sensor_application",
                "literature_result",
                "application_benefits",
            },
        )
        for variant in variants["variants"]:
            self.assertEqual(variant["composition_mode"], "ordered_component_refs")
            self.assertNotIn("components", variant)
            self.assertTrue(variant["component_refs"])
            self.assertEqual(
                [ref["order"] for ref in variant["component_refs"]],
                list(range(1, len(variant["component_refs"]) + 1)),
            )
            self.assertTrue(
                all(ref["asset_id"].startswith("component/nsfc_defense/") for ref in variant["component_refs"])
            )
            self.assertTrue(all(ref.get("region") for ref in variant["component_refs"]))
            self.assertTrue(all(ref.get("slot_bindings") for ref in variant["component_refs"]))
            self.assertTrue(variant["story_roles"])
            self.assertTrue(variant["section"])
            self.assertTrue(variant["source_page_purpose"])
            self.assertTrue(variant["regions"])
            self.assertEqual(variant["coordinate_space"], "body_canvas")
            self.assertTrue(variant["composition_scene"])
        self.assertEqual(len({variant["composition_scene"] for variant in variants["variants"]}), 12)
        story = json.loads((TEMPLATE / "story_structure.json").read_text(encoding="utf-8"))
        self.assertEqual(story["generation_contract"]["body_component_policy"], "forbidden")
        self.assertEqual(len(story["canonical_content_sequence"]), 12)
        self.assertTrue((TEMPLATE / "compiled" / "template_ir.json").is_file())
        self.assertTrue((TEMPLATE / "compiled" / "template.lock.json").is_file())

    def test_source_like_body_components_have_semantic_figure_slots_and_no_generic_body_box(self) -> None:
        catalog = json.loads((TEMPLATE / "component_catalog.json").read_text(encoding="utf-8"))
        components = {row["component_id"]: row for row in catalog["components"]}
        self.assertEqual(len(components), 12)
        for component_id, component in components.items():
            slot_ids = {slot["slot_id"] for slot in component["slots"]}
            self.assertNotIn("BODY", slot_ids, component_id)
            self.assertFalse(any(slot_id.startswith("PRIMARY_") for slot_id in slot_ids), component_id)
            self.assertGreaterEqual(
                len([slot for slot in component["slots"] if slot["kind"] == "image"]),
                2,
                component_id,
            )
            root = ET.fromstring((TEMPLATE / component["asset_path"]).read_text(encoding="utf-8"))
            image_slots = {
                node.attrib.get("data-slot-id")
                for node in root.iter()
                if node.tag.split("}")[-1] == "image"
            }
            self.assertEqual(
                image_slots,
                {slot["slot_id"] for slot in component["slots"] if slot["kind"] == "image"},
                component_id,
            )

        variants = json.loads((TEMPLATE / "body_variants.json").read_text(encoding="utf-8"))["variants"]
        for variant in variants:
            self.assertEqual(len(variant["component_refs"]), 1, variant["variant_id"])
            self.assertEqual(
                set(variant["slots"][index]["slot_id"] for index in range(len(variant["slots"]))),
                set(variant["component_refs"][0]["slot_bindings"].values()),
                variant["variant_id"],
            )

    def test_shell_pages_have_named_slots_and_hard_vertical_alignment_metadata(self) -> None:
        slot_contract = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))
        declared = {slot["slot_id"] for slot in slot_contract["slots"]}
        self.assertEqual(len(slot_contract["slots"]), 17)
        self.assertEqual(len(declared), 14)
        for svg_path in sorted(TEMPLATE.glob("*.svg")):
            root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
            text_nodes = [node for node in root.iter() if node.tag.split("}")[-1] == "text"]
            image_nodes = [node for node in root.iter() if node.tag.split("}")[-1] == "image"]
            self.assertTrue(text_nodes, svg_path.name)
            self.assertTrue(image_nodes, svg_path.name)
            for node in text_nodes:
                slot_id = node.attrib.get("data-slot-id")
                if slot_id:
                    self.assertIn(slot_id, declared, svg_path.name)
                else:
                    self.assertTrue(
                        node.attrib.get("data-easyslides-static-text") == "true"
                        or node.attrib.get("data-pptx-fixed-chrome") == "true",
                        svg_path.name,
                    )
                if node.attrib.get("data-easyslides-static-geometry") == "source_fidelity":
                    continue
                self.assertEqual(node.attrib.get("data-pptx-textbox"), "true", svg_path.name)
                self.assertEqual(node.attrib.get("data-pptx-valign"), "middle", svg_path.name)
                self.assertEqual(node.attrib.get("data-center-lock"), "true", svg_path.name)
                for key in ("data-pptx-box-x", "data-pptx-box-y", "data-pptx-box-w", "data-pptx-box-h"):
                    self.assertIn(key, node.attrib, f"{svg_path.name}: {slot_id}")
            for node in image_nodes:
                slot_id = node.attrib.get("data-slot-id")
                if slot_id:
                    self.assertIn(slot_id, declared, svg_path.name)

    def test_cover_keeps_field_labels_static_and_exposes_only_their_values(self) -> None:
        root = ET.fromstring((TEMPLATE / "01_cover.svg").read_text(encoding="utf-8"))
        text_nodes = [node for node in root.iter() if node.tag.split("}")[-1] == "text"]
        editable = {node.attrib.get("data-slot-id") for node in text_nodes if node.attrib.get("data-slot-id")}
        static = {
            node.attrib.get("data-easyslides-static-role")
            for node in text_nodes
            if node.attrib.get("data-easyslides-static-text") == "true"
        }

        self.assertEqual(
            editable,
            {
                "TITLE",
                "PROJECT_TYPE",
                "SUBTITLE",
                "AFFILIATION",
                "PRESENTER",
                "DATE",
            },
        )
        self.assertEqual(static, {"affiliation_label", "presenter_label", "presentation_date_label"})
        title_nodes = {
            node.attrib.get("data-slot-id"): node
            for node in text_nodes
            if node.attrib.get("data-slot-id") in {"TITLE", "PROJECT_TYPE", "SUBTITLE"}
        }
        self.assertEqual(set(title_nodes), {"TITLE", "PROJECT_TYPE", "SUBTITLE"})
        self.assertTrue(
            all(node.attrib.get("data-pptx-text-anchor") == "middle" for node in title_nodes.values())
        )
        placeholder_text = {
            node.attrib.get("data-slot-id"): "".join(node.itertext()).strip()
            for node in text_nodes
            if node.attrib.get("data-slot-id")
        }
        self.assertEqual(
            placeholder_text,
            {
                "TITLE": "项目名称",
                "PROJECT_TYPE": "项目类别",
                "SUBTITLE": "答辩主题",
                "AFFILIATION": "单位名称",
                "PRESENTER": "汇报人",
                "DATE": "汇报日期",
            },
        )

    def test_projection_exposes_only_content_chrome_and_requires_body_variant_for_body(self) -> None:
        from scripts.pptx_projection import project_slide

        contract = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))
        page_slots = [slot for slot in contract["slots"] if slot["source_slide_id"] == "slide-03"]
        self.assertEqual([slot["slot_id"] for slot in page_slots], ["PAGE_TITLE"])
        text_slot = page_slots[0]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "projected.svg"
            result = project_slide(
                source_workspace=TEMPLATE,
                slide_id="content",
                values={text_slot["slot_id"]: "Title"},
                output_svg=output,
            )
            self.assertEqual(result["status"], "pass")
            self.assertIn(text_slot["slot_id"], result["replaced_slots"])
            rendered = output.read_text(encoding="utf-8")
            self.assertIn(">Title<", rendered)
            self.assertIn('data-pptx-valign="middle"', rendered)


if __name__ == "__main__":
    unittest.main()
