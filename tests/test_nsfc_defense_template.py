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
        self.assertEqual(
            template["content_organization"],
            [
                "significance_and_scientific_question",
                "research_content_and_technical_route",
                "innovation_feasibility_and_implementation",
            ],
        )
        self.assertEqual(len(layouts["layouts"]), 5)
        self.assertEqual(len(layouts["shells"]), 5)
        self.assertEqual(len(projection["pages"]), 5)
        self.assertEqual(len(slots["slots"]), 18)
        self.assertEqual(template["layout_count"], 5)
        self.assertEqual(template["variant_count"], 9)
        self.assertEqual(len(variants["variants"]), 9)
        self.assertEqual(primitives["tokens"], {})
        self.assertEqual(primitives["primitives"], [])
        self.assertEqual(len(recipes["recipes"]), 9)
        for recipe in recipes["recipes"]:
            if recipe["variant_id"] == "grant_text_evidence_stack":
                self.assertEqual(recipe["primitives"], [])
                self.assertEqual(recipe["scene_component"], "grant_text_evidence_stack")
            else:
                self.assertTrue(recipe["primitives"])
        self.assertEqual(len(roster["pages"]), 17)
        self.assertEqual(roster["canonical_shell_count"], 5)
        self.assertEqual(roster["body_variant_count"], 9)
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
        self.assertEqual(content["slots"], ["PAGE_TITLE", "KEY_MESSAGE", "PAGE_NUMBER"])
        self.assertEqual(content["content_shell_policy"], "source_guided_body_variant_required")
        self.assertEqual(content["body_canvas"], {"x": 64.0, "y": 204.0, "width": 1152.0, "height": 458.0})
        self.assertEqual(len(content["legacy_shadow_slots"]), 13)
        self.assertEqual(
            layouts["content_shell_contract"]["public_slots"],
            ["PAGE_TITLE", "KEY_MESSAGE", "PAGE_NUMBER"],
        )
        content_svg = ET.parse(TEMPLATE / "04_content.svg").getroot()
        self.assertFalse(
            any(node.attrib.get("data-easyslides-open-body-canvas") for node in content_svg.iter()),
            "body_canvas must remain a logical template constraint, not a visible SVG rectangle",
        )
        ending = next(row for row in layouts["layouts"] if row["page_id"] == "ending")
        self.assertEqual(
            ending["slots"],
            ["CLOSING_TITLE", "AFFILIATION", "PRESENTER", "DATE"],
        )
        self.assertEqual(
            {row["variant_id"] for row in variants["variants"]},
            {
                "need_relationship_evidence",
                "dual_track_evidence",
                "evidence_chain",
                "metric_dashboard",
                "three_evidence_track",
                "comparison_evidence",
                "application_system",
                "literature_transfer",
                "grant_text_evidence_stack",
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
        self.assertEqual(len({variant["composition_scene"] for variant in variants["variants"]}), 9)
        story = json.loads((TEMPLATE / "story_structure.json").read_text(encoding="utf-8"))
        self.assertEqual(story["default_scenario"], "nsfc_grant_cn")
        grant_profile = story["grant_cn_profile"]
        self.assertEqual(grant_profile["scenario_label"], "中国国家自然科学基金申请答辩")
        self.assertEqual(len(grant_profile["sections"]), 3)
        self.assertIn("research_content_3", grant_profile["full_deck_roles"])
        self.assertIn("work_plan_and_expected_outcomes", grant_profile["full_deck_roles"])
        self.assertTrue(grant_profile["variant_bindings"])
        self.assertEqual(story["generation_contract"]["body_component_policy"], "forbidden")
        self.assertEqual(len(story["canonical_content_sequence"]), 9)
        self.assertTrue((TEMPLATE / "compiled" / "template_ir.json").is_file())
        self.assertTrue((TEMPLATE / "compiled" / "template.lock.json").is_file())

    def test_source_derived_leaf_components_keep_the_source_style_locked(self) -> None:
        catalog = json.loads((TEMPLATE / "component_catalog.json").read_text(encoding="utf-8"))
        components = {row["component_id"]: row for row in catalog["components"]}
        self.assertEqual(len(components), 14)
        leaf_components = {
            component_id: component
            for component_id, component in components.items()
            if component["classification"] == "template_scoped_source_derived_leaf"
        }
        self.assertEqual(len(leaf_components), 13)
        for component_id, component in leaf_components.items():
            slot_ids = {slot["slot_id"] for slot in component["slots"]}
            self.assertNotIn("BODY", slot_ids, component_id)
            self.assertEqual(component["classification"], "template_scoped_source_derived_leaf")
            self.assertIn("source_derived", component["asset_path"])
            self.assertEqual(
                component["provenance"]["style_mutation_policy"],
                "forbid_color_font_size_geometry_crop_and_layer_order_changes",
            )
            root = ET.fromstring((TEMPLATE / component["asset_path"]).read_text(encoding="utf-8"))
            declared_slots = {
                node.attrib.get("data-slot-id")
                for node in root.iter()
                if node.attrib.get("data-slot-id")
            }
            self.assertEqual(
                declared_slots,
                {slot["slot_id"] for slot in component["slots"]},
                component_id,
            )
            self.assertEqual(root.attrib.get("data-easyslides-style-policy"), "source_locked")
            for node in root.iter():
                if node.attrib.get("data-slot-kind") == "text":
                    self.assertEqual(node.attrib.get("data-pptx-valign"), "middle")
                    self.assertEqual(node.attrib.get("data-center-lock"), "true")

        imported = components["grant_text_evidence_stack"]
        self.assertEqual(imported["classification"], "template_scoped_imported_page_scene")
        self.assertIn("assets/components/imported/", imported["asset_path"])
        self.assertEqual(imported["provenance"]["source_component_id"], "component/research_core/evidence_stack")
        self.assertEqual(
            imported["provenance"]["style_mutation_policy"],
            "preserve_source_structure_geometry_and_fonts_map_visual_tokens_to_nsfc_purple",
        )
        imported_root = ET.fromstring((TEMPLATE / imported["asset_path"]).read_text(encoding="utf-8"))
        self.assertEqual(imported_root.attrib.get("data-easyslides-import-kind"), "adapted_page_scene_not_leaf_component")
        self.assertEqual(imported_root.attrib.get("data-easyslides-style-policy"), "template_token_adapted")
        imported_paints = {
            value.upper()
            for node in imported_root.iter()
            for value in (node.attrib.get("fill"), node.attrib.get("stroke"))
            if value
        }
        self.assertTrue({"#751497", "#F8EAFC", "#4A2C59"}.issubset(imported_paints))
        self.assertTrue(imported_paints.isdisjoint({"#172033", "#1C75BC", "#4B5B6D"}))
        self.assertEqual(
            {
                node.attrib.get("data-slot-id")
                for node in imported_root.iter()
                if node.attrib.get("data-slot-id")
            },
            {slot["slot_id"] for slot in imported["slots"]},
        )

        for component_id, expected_lines in {
            "vertical_key_tag": 3,
            "vertical_feature_image_panel": 4,
        }.items():
            component = components[component_id]
            slot = next(row for row in component["slots"] if row["kind"] == "text")
            self.assertEqual(slot["text_layout"], "balanced_cjk_stack")
            self.assertEqual(slot["capacity"]["max_chars_per_line"], 2)
            self.assertEqual(slot["capacity"]["max_lines"], expected_lines)
            root = ET.parse(TEMPLATE / component["asset_path"]).getroot()
            node = next(item for item in root.iter() if item.attrib.get("data-slot-id") == slot["slot_id"])
            self.assertEqual(node.attrib.get("data-easyslides-layout"), "balanced_cjk_stack")
            self.assertEqual(node.attrib.get("data-pptx-no-wrap"), "true")

        feature = ET.parse(
            TEMPLATE / "assets" / "components" / "source_derived" / "vertical_feature_image_panel.svg"
        ).getroot()
        vx, vy, width, height = [
            float(value) for value in feature.attrib["viewBox"].replace(",", " ").split()
        ]
        feature_background = next(
            node
            for node in feature.iter()
            if node.tag.rsplit("}", 1)[-1] == "rect"
            and node.attrib.get("fill") == "#FFFFFF"
            and float(node.attrib.get("width", "0")) > width * 0.9
        )
        self.assertGreaterEqual(float(feature_background.attrib["x"]), vx - 0.01)
        self.assertLessEqual(
            float(feature_background.attrib["x"]) + float(feature_background.attrib["width"]),
            vx + width + 0.01,
        )
        self.assertGreaterEqual(float(feature_background.attrib["y"]), vy - 0.01)
        self.assertLessEqual(
            float(feature_background.attrib["y"]) + float(feature_background.attrib["height"]),
            vy + height + 0.01,
        )

        from scripts.template_production_gate import validate_component_catalog

        catalog_gate = validate_component_catalog(TEMPLATE)
        self.assertEqual(catalog_gate["status"], "pass", catalog_gate["issues"])

        variants = json.loads((TEMPLATE / "body_variants.json").read_text(encoding="utf-8"))["variants"]
        for variant in variants:
            if variant["variant_id"] == "grant_text_evidence_stack":
                self.assertEqual(len(variant["component_refs"]), 1)
            else:
                self.assertGreaterEqual(len(variant["component_refs"]), 2, variant["variant_id"])
            self.assertEqual(
                set(variant["slots"][index]["slot_id"] for index in range(len(variant["slots"]))),
                {
                    target
                    for component_ref in variant["component_refs"]
                    for target in component_ref["slot_bindings"].values()
                },
                variant["variant_id"],
            )

    def test_shell_pages_have_named_slots_and_hard_vertical_alignment_metadata(self) -> None:
        slot_contract = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))
        declared = {slot["slot_id"] for slot in slot_contract["slots"]}
        self.assertEqual(len(slot_contract["slots"]), 18)
        self.assertEqual(len(declared), 15)
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

    def test_content_page_title_is_a_hard_single_line_slot(self) -> None:
        contracts = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))["slots"]
        page_title = next(
            slot
            for slot in contracts
            if slot["slot_id"] == "PAGE_TITLE" and slot["shell_id"] == "content"
        )

        self.assertEqual(page_title["capacity"]["max_lines"], 1)
        self.assertEqual(page_title["capacity"]["max_chars_per_line"], 10)
        self.assertTrue(page_title["capacity"]["single_line_required"])
        self.assertEqual(page_title["capacity"]["overflow_action"], "shorten_title_required")

        root = ET.fromstring((TEMPLATE / "04_content.svg").read_text(encoding="utf-8"))
        title = next(node for node in root.iter() if node.attrib.get("data-slot-id") == "PAGE_TITLE")
        self.assertEqual(title.attrib.get("data-easyslides-single-line"), "required")
        self.assertEqual(title.attrib.get("data-pptx-no-wrap"), "true")

    def test_content_shell_has_running_title_key_message_and_automatic_page_number(self) -> None:
        contracts = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))["slots"]
        content_slots = {
            slot["slot_id"]: slot
            for slot in contracts
            if slot["shell_id"] == "content"
        }
        self.assertEqual(set(content_slots), {"PAGE_TITLE", "KEY_MESSAGE", "PAGE_NUMBER"})
        self.assertEqual(content_slots["PAGE_TITLE"]["role"], "running_title")
        self.assertEqual(content_slots["KEY_MESSAGE"]["role"], "central_message")
        self.assertEqual(content_slots["KEY_MESSAGE"]["capacity"]["max_lines"], 2)
        self.assertEqual(content_slots["KEY_MESSAGE"]["rendering"], "square_bullets")
        self.assertEqual(content_slots["PAGE_NUMBER"]["value_policy"], "automatic_slide_index")

        root = ET.fromstring((TEMPLATE / "04_content.svg").read_text(encoding="utf-8"))
        message = next(node for node in root.iter() if node.attrib.get("data-slot-id") == "KEY_MESSAGE")
        page_number = next(node for node in root.iter() if node.attrib.get("data-slot-id") == "PAGE_NUMBER")
        self.assertEqual(message.attrib.get("data-easyslides-layout"), "square_bullets")
        self.assertEqual(message.attrib.get("data-pptx-no-wrap"), "true")
        self.assertEqual(page_number.attrib.get("data-pptx-text-anchor"), "end")

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

    def test_toc_and_chapter_corner_flourishes_use_one_exact_rotation_source(self) -> None:
        for shell in ("02_toc.svg", "03_chapter.svg"):
            root = ET.fromstring((TEMPLATE / shell).read_text(encoding="utf-8"))
            groups = {node.attrib.get("id"): node for node in root.iter() if node.attrib.get("id")}
            top_left = groups["chapter-corner-top-left"]
            bottom_right = groups["chapter-corner-bottom-right"]
            top_paths = [node for node in top_left if node.tag.split("}")[-1] == "path"]
            bottom_paths = [node for node in bottom_right if node.tag.split("}")[-1] == "path"]

            self.assertEqual(bottom_right.attrib.get("transform"), "rotate(180 640 360)", shell)
            self.assertEqual(bottom_right.attrib.get("data-easyslides-symmetry-source"), "chapter-corner-top-left", shell)
            self.assertEqual(
                [node.attrib.get("d") for node in bottom_paths],
                [node.attrib.get("d") for node in top_paths],
                shell,
            )

    def test_projection_exposes_only_content_chrome_and_requires_body_variant_for_body(self) -> None:
        from scripts.pptx_projection import project_slide

        contract = json.loads((TEMPLATE / "slot_contracts.json").read_text(encoding="utf-8"))
        page_slots = [slot for slot in contract["slots"] if slot["source_slide_id"] == "slide-03"]
        self.assertEqual([slot["slot_id"] for slot in page_slots], ["PAGE_TITLE", "KEY_MESSAGE", "PAGE_NUMBER"])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "projected.svg"
            result = project_slide(
                source_workspace=TEMPLATE,
                slide_id="content",
                values={"PAGE_TITLE": "Title", "KEY_MESSAGE": "Point", "PAGE_NUMBER": "03"},
                output_svg=output,
            )
            self.assertEqual(result["status"], "pass")
            self.assertEqual(set(result["replaced_slots"]), {"PAGE_TITLE", "KEY_MESSAGE", "PAGE_NUMBER"})
            rendered = output.read_text(encoding="utf-8")
            self.assertIn(">Title<", rendered)
            self.assertIn(">Point<", rendered)
            self.assertIn(">03<", rendered)
            self.assertIn('data-pptx-valign="middle"', rendered)


if __name__ == "__main__":
    unittest.main()
