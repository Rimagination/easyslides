import json
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


class PptMasterTemplateLibraryTests(unittest.TestCase):
    def test_templates_root_keeps_layouts_and_shared_assets_separate(self):
        root_entries = {path.name for path in TEMPLATES.iterdir()}
        self.assertIn("layouts", root_entries)
        self.assertIn("charts", root_entries)
        self.assertIn("icons", root_entries)
        self.assertIn("reference", root_entries)
        self.assertNotIn("style_packs", root_entries)
        self.assertNotIn("academic", root_entries)
        self.assertNotIn("l001_notebook_defense", root_entries)
        self.assertNotIn("guizang_ppt", root_entries)

    def test_layout_library_contains_only_active_academic_templates(self):
        layouts_root = TEMPLATES / "layouts"
        index_path = layouts_root / "layouts_index.json"
        expected_templates = {
            "academic_general",
            "academic_scqa",
            "defense_leftnav",
            "defense_topnav",
            "literature_minimal",
            "nsfc_defense",
            "thu_speech",
        }
        retired_template_ids = {
            "academic01",
            "academic02",
            "literature02",
            "literature01",
            "defense01",
            "defense02",
            "cqu01",
            "medical01",
            "psychology01",
            "academic_defense",
            "defense_s01",
            "literature_s01",
            "literature_s02",
            "medical_university",
            "psychology_attachment",
            "重庆大学",
            "重庆大学",
        }

        self.assertTrue(index_path.exists(), "layouts_index.json is required")
        layouts_index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(set(layouts_index), expected_templates)
        self.assertEqual(len(layouts_index), 7)

        aliases = json.loads((layouts_root / "aliases.json").read_text(encoding="utf-8"))
        self.assertEqual(aliases["academic01"], "academic_general")
        self.assertEqual(aliases["academic02"], "academic_scqa")
        self.assertEqual(aliases["academic_defense"], "academic_general")
        self.assertEqual(aliases["defense01"], "defense_leftnav")
        self.assertEqual(aliases["defense02"], "defense_topnav")
        self.assertEqual(aliases["defense_s01"], "defense_leftnav")
        self.assertEqual(aliases["literature01"], "literature_minimal")
        self.assertEqual(aliases["literature_s01"], "literature_minimal")
        self.assertEqual(aliases["literature02"], "literature_minimal")
        self.assertNotIn("medical_university", aliases)
        self.assertNotIn("psychology_attachment", aliases)
        self.assertNotIn("重庆大学", aliases)
        for old_id in retired_template_ids:
            self.assertNotIn(old_id, layouts_index)
            self.assertFalse((layouts_root / old_id).exists(), f"retired template directory remains: {old_id}")
            if old_id in aliases:
                self.assertIn(aliases[old_id], expected_templates)

        for template_id in layouts_index:
            template_dir = layouts_root / template_id
            self.assertTrue(template_dir.is_dir(), f"{template_id} directory missing")
            self.assertTrue(
                (template_dir / "design_spec.md").exists(),
                f"{template_id}/design_spec.md missing",
            )
            self.assertGreaterEqual(
                len(list(template_dir.glob("*.svg"))),
                5,
                f"{template_id} should provide at least five SVG page shells",
            )

    def test_l001_left_nav_is_not_an_active_layout_template(self):
        layouts_root = TEMPLATES / "layouts"
        index = json.loads((layouts_root / "layouts_index.json").read_text(encoding="utf-8"))

        self.assertNotIn("l001_left_nav", index)
        self.assertFalse((layouts_root / "l001_left_nav").exists())

    def test_academic_scqa_distills_scqa_html_templates(self):
        layouts_root = TEMPLATES / "layouts"
        index = json.loads((layouts_root / "layouts_index.json").read_text(encoding="utf-8"))
        template_dir = layouts_root / "academic_scqa"

        self.assertIn("academic_scqa", index)
        self.assertNotIn("zjlab_academic_report01", index)
        self.assertTrue(template_dir.is_dir())
        self.assertFalse((layouts_root / "zjlab_academic_report01").exists())

        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
        template = json.loads((template_dir / "template.json").read_text(encoding="utf-8"))
        layouts = json.loads((template_dir / "layouts.json").read_text(encoding="utf-8"))
        body = json.loads((template_dir / "body_variants.json").read_text(encoding="utf-8"))
        story = json.loads((template_dir / "story_structure.json").read_text(encoding="utf-8"))
        rules_text = (template_dir / "rules.md").read_text(encoding="utf-8")

        self.assertEqual(template["template_id"], "academic_scqa")
        self.assertEqual(template["mode"], "classic")
        self.assertEqual(template["source_template"], "academic_report_html_slot_templates")
        self.assertEqual(layouts["distillation_model"], "five_shells_plus_scqa_body_variants")
        self.assertEqual(
            [shell["page_id"] for shell in layouts["shells"]],
            ["cover", "toc", "chapter", "content", "ending"],
        )
        for shell in layouts["shells"]:
            self.assertIn("LOGO", shell["slots"])
        self.assertEqual(
            sorted(path.name for path in template_dir.glob("*.svg")),
            ["01_cover.svg", "02_chapter.svg", "02_toc.svg", "03_content.svg", "04_ending.svg"],
        )
        self.assertIn("template_id: academic_scqa", spec_text)
        self.assertIn("replication_mode: classic", spec_text)
        self.assertIn("#0046A5", spec_text)
        self.assertIn("#0B2F6B", spec_text)
        self.assertIn("#00A6D6", spec_text)
        self.assertIn("#17A889", spec_text)
        self.assertNotIn("#003366", spec_text)
        self.assertNotIn("#CC0000", spec_text)
        self.assertNotIn("#10B981", spec_text)
        self.assertIn("SCQA", spec_text)
        for banned in ["zjlab", "ZJLab", "Zhejiang", "ZHEJIANG", "qianmo"]:
            for path in template_dir.iterdir():
                if path.suffix in {".md", ".json", ".svg"}:
                    self.assertNotIn(banned, path.read_text(encoding="utf-8"))
        for banned in ["ACADEMIC REPORT", "ORG_NAME", "ORG_NAME_EN"]:
            for path in template_dir.iterdir():
                if path.suffix in {".md", ".json", ".svg"}:
                    self.assertNotIn(banned, path.read_text(encoding="utf-8"))

        self.assertIn("LOGO", spec_text)
        self.assertIn("user-provided materials", spec_text)
        self.assertIn("degree-cap icon", spec_text)
        self.assertIn("degree-cap icon", rules_text)
        for svg_path in template_dir.glob("*.svg"):
            svg_text = svg_path.read_text(encoding="utf-8")
            self.assertIn('data-slot="LOGO"', svg_text)
            self.assertIn("{{LOGO}}", svg_text)

        variant_ids = {variant["variant_id"] for variant in body["variants"]}
        for variant_id in [
            "intro_policy",
            "research_method",
            "data_stats",
            "workflow_four_phase",
            "workflow_linear",
            "comparison",
            "image_grid",
            "key_finding",
        ]:
            self.assertIn(variant_id, variant_ids)
        self.assertEqual(story["narrative_model"], "AST_SCQA")
        self.assertEqual([phase["phase"] for phase in story["phases"]], ["S", "C", "Q", "A"])
        self.assertIn("title must be a conclusion sentence", rules_text)

        content_text = (template_dir / "03_content.svg").read_text(encoding="utf-8")
        for slot in ["PAGE_TITLE", "KEY_MESSAGE", "CONTENT_BODY", "SOURCE", "PAGE_NUM"]:
            self.assertIn(f"{{{{{slot}}}}}", content_text)
        self.assertIn('data-slot="CONTENT_AREA"', content_text)
        self.assertNotIn("stroke-dasharray", content_text)

    def test_academic_general_and_scqa_share_human_centered_academic_orchestration(self):
        reference = (ROOT / "references" / "academic-orchestration.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Audience-State-Transfer", reference)
        self.assertIn("SCQA", reference)
        self.assertIn("developer-facing language", reference)
        self.assertIn("one audience-state shift", reference)

        for template_id in ["academic_general", "academic_scqa"]:
            template_dir = TEMPLATES / "layouts" / template_id
            spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
            rules_text = (template_dir / "rules.md").read_text(encoding="utf-8")
            story = json.loads((template_dir / "story_structure.json").read_text(encoding="utf-8"))

            with self.subTest(template_id=template_id):
                self.assertIn("references/academic-orchestration.md", spec_text)
                self.assertIn("Audience-State-Transfer", spec_text)
                self.assertIn("SCQA", spec_text)
                self.assertIn("developer-facing language", rules_text)
                self.assertIn("one audience-state shift", rules_text)
                self.assertEqual(story["narrative_model"], "AST_SCQA")
                self.assertEqual(story["transfer_path"][0]["role"], "hook")
                self.assertEqual(story["transfer_path"][-1]["role"], "takeaway")

        academic_general_spec = (TEMPLATES / "layouts" / "academic_general" / "design_spec.md").read_text(
            encoding="utf-8"
        )
        for banned in [
            "Copy the template to the project directory",
            "Executor role",
            "Usage Instructions",
        ]:
            self.assertNotIn(banned, academic_general_spec)

    def test_defense_topnav_is_academic_blue_top_navigation_defense(self):
        layouts_root = TEMPLATES / "layouts"
        index = json.loads((layouts_root / "layouts_index.json").read_text(encoding="utf-8"))
        template_dir = layouts_root / "defense_topnav"
        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
        template = json.loads((template_dir / "template.json").read_text(encoding="utf-8"))
        layouts = json.loads((template_dir / "layouts.json").read_text(encoding="utf-8"))
        nav = json.loads((template_dir / "navigation_states.json").read_text(encoding="utf-8"))
        body = json.loads((template_dir / "body_variants.json").read_text(encoding="utf-8"))
        palettes = json.loads((template_dir / "theme_palettes.json").read_text(encoding="utf-8"))
        rules_text = (template_dir / "rules.md").read_text(encoding="utf-8")

        self.assertIn("defense_topnav", index)
        self.assertEqual(template["template_id"], "defense_topnav")
        self.assertEqual(template["mode"], "classic")
        self.assertEqual(template["files"]["theme_palettes"], "theme_palettes.json")
        self.assertIn("template_id: defense_topnav", spec_text)
        self.assertIn("replication_mode: classic", spec_text)
        self.assertIn("dynamic top navigation", spec_text)
        self.assertIn("theme_palettes.json", spec_text)
        self.assertIn("wine", spec_text)
        self.assertIn("academic_purple", spec_text)
        self.assertIn("academic_green", spec_text)
        self.assertEqual([shell["page_id"] for shell in layouts["shells"]], ["cover", "toc", "chapter", "content", "ending"])
        self.assertEqual(nav["variant_model"]["mode"], "single_svg_six_active_section_variants")
        self.assertEqual(nav["variant_model"]["base_shell"], "templates/layouts/defense_topnav/03_content.svg")
        self.assertEqual([section["index"] for section in nav["sections"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual([variant["variant_id"] for variant in nav["navigation_variants"]], ["D02-NAV-01", "D02-NAV-02", "D02-NAV-03", "D02-NAV-04", "D02-NAV-05", "D02-NAV-06"])

        content_text = (template_dir / "03_content.svg").read_text(encoding="utf-8")
        for token in [
            'data-component="top-navigation"',
            'id="top-nav-surface"',
            'id="nav-active-tab"',
            'data-active-index="1"',
            'data-slot="ACTIVE_SECTION_LABEL"',
            'data-slot="CONTENT_AREA"',
            'data-slot="CONTENT_BODY"',
            'data-slot="PAGE_NUM"',
        ]:
            self.assertIn(token, content_text)
        self.assertNotIn("FOOTER_KEYWORD", content_text)
        self.assertNotIn("FOOTER_SUMMARY", content_text)
        self.assertNotIn("{{SOURCE}}", content_text)
        self.assertNotIn('data-slot="SOURCE"', content_text)
        self.assertNotIn("补充说明", content_text)
        self.assertNotIn('data-slot="CARD_1_TITLE"', content_text)
        self.assertIn("three_card_summary", {variant["variant_id"] for variant in body["variants"]})
        self.assertIn("process_timeline", {variant["variant_id"] for variant in body["variants"]})
        self.assertIn("table_matrix", {variant["variant_id"] for variant in body["variants"]})
        self.assertEqual(body["primary_variant"], "flexible_canvas")
        self.assertEqual(body["selection_policy"]["default"], "match_claim_and_evidence_shape")
        self.assertEqual(palettes["schema_version"], "easyslides.theme_palettes.v1")
        self.assertEqual(palettes["template_id"], "defense_topnav")
        self.assertEqual(palettes["default_palette"], "academic_blue")
        self.assertEqual(
            sorted(palettes["palettes"]),
            ["academic_blue", "academic_green", "academic_purple", "wine"],
        )
        self.assertEqual(palettes["palettes"]["academic_blue"]["colors"]["primary"], "#183A6A")
        self.assertEqual(palettes["palettes"]["wine"]["colors"]["primary"], "#8B0012")
        self.assertEqual(palettes["palettes"]["academic_purple"]["colors"]["primary"], "#80308B")
        self.assertEqual(palettes["palettes"]["academic_green"]["colors"]["primary"], "#016F35")
        self.assertIn("恳请老师批评指正！", spec_text + rules_text)
        self.assertIn("English `listening` remains allowed", spec_text + rules_text)
        root = ET.fromstring(content_text)
        active_tab = next(node for node in root.iter() if node.attrib.get("id") == "nav-active-tab")
        self.assertEqual(active_tab.attrib["fill"], "#FFFFFF")
        self.assertEqual(active_tab.attrib["data-active-index"], "1")
        content_area = next(node for node in root.iter() if node.attrib.get("id") == "content-area")
        self.assertLessEqual(float(content_area.attrib["x"]), 56)
        self.assertLessEqual(float(content_area.attrib["y"]), 190)
        self.assertGreaterEqual(float(content_area.attrib["width"]), 1170)
        self.assertGreaterEqual(float(content_area.attrib["height"]), 430)
        self.assertEqual(content_area.attrib["fill"], "none")
        self.assertEqual(content_area.attrib["stroke"], "none")
        self.assertNotIn("stroke-dasharray", content_area.attrib)

        page_title = next(node for node in root.iter() if node.attrib.get("data-slot") == "PAGE_TITLE")
        key_message = next(node for node in root.iter() if node.attrib.get("data-slot") == "KEY_MESSAGE")
        key_message_backplate = next(
            node
            for node in root.iter()
            if node.tag.split("}")[-1] == "rect" and node.attrib.get("fill") == "#E7E6E6"
        )
        self.assertEqual(page_title.attrib["data-pptx-valign"], "middle")
        self.assertEqual(key_message.attrib["data-pptx-valign"], "middle")
        self.assertEqual(page_title.attrib["dominant-baseline"], "middle")
        self.assertEqual(key_message.attrib["dominant-baseline"], "middle")
        self.assertGreaterEqual(float(key_message.attrib["x"]) - float(key_message_backplate.attrib["x"]), 24)
        self.assertGreaterEqual(
            float(key_message.attrib["data-pptx-box-x"]) - float(key_message_backplate.attrib["x"]),
            24,
        )
        self.assertAlmostEqual(float(page_title.attrib["y"]), float(key_message.attrib["y"]), places=1)
        self.assertAlmostEqual(
            float(page_title.attrib["data-pptx-box-y"]) + float(page_title.attrib["data-pptx-box-h"]) / 2,
            float(key_message.attrib["data-pptx-box-y"]) + float(key_message.attrib["data-pptx-box-h"]) / 2,
            places=1,
        )
        self.assertNotIn('id="footer-summary"', content_text)
        self.assertNotIn("footer keyword plus summary", spec_text)

        ending_text = (template_dir / "04_ending.svg").read_text(encoding="utf-8")
        self.assertNotIn("聆听", ending_text)
        self.assertIn("专业：", ending_text)
        self.assertNotIn("联系方式：", ending_text)
        self.assertIn("third metadata item labels `CONTACT` as `专业：`", rules_text)
        self.assertIn(
            "timeline and process sequences must draw a visible connector line through every circular node center",
            rules_text,
        )

    def test_defense_leftnav_is_compact_classic_defense_with_active_navigation(self):
        layouts_root = TEMPLATES / "layouts"
        index = json.loads((layouts_root / "layouts_index.json").read_text(encoding="utf-8"))
        template_dir = layouts_root / "defense_leftnav"
        spec_path = template_dir / "design_spec.md"

        self.assertIn("defense_leftnav", index)
        self.assertTrue(template_dir.is_dir())
        self.assertTrue(spec_path.exists())

        template = json.loads((template_dir / "template.json").read_text(encoding="utf-8"))
        layouts = json.loads((template_dir / "layouts.json").read_text(encoding="utf-8"))
        nav = json.loads((template_dir / "navigation_states.json").read_text(encoding="utf-8"))
        body = json.loads((template_dir / "body_variants.json").read_text(encoding="utf-8"))
        components = json.loads((template_dir / "component_styles.json").read_text(encoding="utf-8"))
        palettes = json.loads((template_dir / "theme_palettes.json").read_text(encoding="utf-8"))
        spec_text = spec_path.read_text(encoding="utf-8")

        self.assertEqual(template["template_id"], "defense_leftnav")
        self.assertEqual(template["source_template"], "retired_full_defense_roster")
        self.assertEqual(template["mode"], "classic")
        self.assertEqual(template["files"]["theme_palettes"], "theme_palettes.json")
        self.assertEqual(layouts["replication_mode"], "classic")
        self.assertIn("template_id: defense_leftnav", spec_text)
        self.assertIn("replication_mode: classic", spec_text)
        self.assertIn("ACTIVE_SECTION", spec_text)
        self.assertIn("academic_blue", spec_text)
        self.assertIn("academic_purple", spec_text)
        self.assertIn("academic_green", spec_text)

        page_files = sorted(path.name for path in template_dir.glob("*.svg"))
        self.assertEqual(
            page_files,
            [
                "01_cover.svg",
                "02_chapter.svg",
                "02_toc.svg",
                "03_content.svg",
                "04_ending.svg",
            ],
        )
        for sidecar in ["page_catalog.json", "layout_roster.json", "slot_contracts.json", "story_structure.json", "links.json"]:
            self.assertFalse((template_dir / sidecar).exists(), sidecar)

        self.assertEqual([shell["page_id"] for shell in layouts["shells"]], ["cover", "toc", "chapter", "content", "ending"])
        content_shell = next(shell for shell in layouts["shells"] if shell["page_id"] == "content")
        for slot in ["ACTIVE_SECTION", "ACTIVE_SECTION_LABEL", "PAGE_TITLE", "KEY_MESSAGE", "CONTENT_AREA", "CONTENT_BODY", "PAGE_NUM"]:
            self.assertIn(slot, content_shell["slots"])
        self.assertNotIn("CITATION", content_shell["slots"])

        self.assertEqual(nav["active_section_slot"], "ACTIVE_SECTION")
        self.assertEqual(nav["active_label_slot"], "ACTIVE_SECTION_LABEL")
        expected_content_area = {"x": 310, "y": 210, "width": 910, "height": 440}
        self.assertEqual(nav["content_area"], expected_content_area)
        self.assertEqual(nav["navigation_surface"], {"x": 0, "y": 0, "width": 253.38, "height": 720, "fill": "#F2F2F2"})
        self.assertEqual(nav["variant_model"]["mode"], "single_svg_five_active_section_variants")
        self.assertEqual(nav["variant_model"]["shape_policy"], "preserve_navigation_shapes_switch_active_state")
        self.assertEqual([section["index"] for section in nav["sections"]], [1, 2, 3, 4, 5])
        self.assertEqual([section["title"] for section in nav["sections"]], layouts["default_sections"])
        self.assertEqual(len(nav["navigation_variants"]), 5)
        self.assertEqual([variant["variant_id"] for variant in nav["navigation_variants"]], layouts["navigation_variants"])
        self.assertEqual(
            [variant["active_section_index"] for variant in nav["navigation_variants"]],
            [1, 2, 3, 4, 5],
        )
        for variant in nav["navigation_variants"]:
            self.assertEqual(variant["svg_path"], "templates/layouts/defense_leftnav/03_content.svg")
            self.assertEqual(variant["shape_policy"], nav["variant_model"]["shape_policy"])
            self.assertIn("nav-active-band", variant["mutable_elements"])
            self.assertIn("nav-active-icon", variant["mutable_elements"])
        self.assertEqual(
            sorted(section["active_band"]["y"] for section in nav["sections"]),
            [section["active_band"]["y"] for section in nav["sections"]],
        )
        for section in nav["sections"]:
            self.assertIn("pointer_points", section)
            self.assertIn("icon_id", section)
            self.assertNotIn("transform", section["active_pointer"])
            self.assertEqual(section["active_band"]["width"], 291.05)
            self.assertEqual(section["active_label"]["x"], section["inactive_label"]["x"])
            self.assertEqual(section["active_label"]["anchor"], "start")
            self.assertEqual(section["active_label"]["box"]["x"], section["active_label"]["x"])
            self.assertEqual(section["active_label"]["box"]["y"], section["active_band"]["y"])
            self.assertEqual(section["active_label"]["box"]["height"], section["active_band"]["height"])
            self.assertEqual(section["active_label"]["box"]["vertical_anchor"], "middle")
            self.assertAlmostEqual(section["active_label"]["y"], section["active_band"]["y"] + 42.42)
            self.assertEqual(section["active_band"]["fill"], nav["colors"]["active_band"])
            self.assertEqual(section["active_pointer"]["fill"], nav["colors"]["active_pointer"])
            pointer_points = [
                tuple(float(value) for value in pair.split(","))
                for pair in section["active_pointer"]["points"].split()
            ]
            self.assertEqual(section["pointer_points"], section["active_pointer"]["points"])
            self.assertAlmostEqual(max(x for x, _ in pointer_points), section["active_band"]["width"] - 0.01, places=2)
            self.assertAlmostEqual(min(y for _, y in pointer_points), section["active_band"]["y"] + section["active_band"]["height"] - 0.01, places=2)

        self.assertGreaterEqual(len(body["variants"]), 5)
        self.assertEqual(body["content_area"], expected_content_area)
        self.assertEqual(body["component_spacing"]["min_gap"], 32)
        self.assertIn("independent body components", body["component_spacing"]["scope"])
        self.assertEqual(palettes["schema_version"], "easyslides.theme_palettes.v1")
        self.assertEqual(palettes["default_palette"], "wine")
        self.assertEqual(
            sorted(palettes["palettes"]),
            ["academic_blue", "academic_green", "academic_purple", "wine"],
        )
        self.assertEqual(palettes["palettes"]["academic_blue"]["colors"]["primary"], "#183A6A")
        self.assertEqual(palettes["palettes"]["academic_purple"]["colors"]["primary"], "#80308B")
        self.assertEqual(palettes["palettes"]["academic_green"]["colors"]["primary"], "#016F35")
        self.assertEqual(components["tokens"]["content_area"], expected_content_area)
        self.assertEqual(components["tokens"]["gap"], 32)
        self.assertEqual(components["navigation_styles"]["left_navigation"]["surface"], nav["navigation_surface"])
        self.assertEqual(components["navigation_styles"]["left_navigation"]["labels"]["active"]["x"], 72.54)
        self.assertEqual(components["navigation_styles"]["left_navigation"]["labels"]["active"]["text_anchor"], "start")

        content_text = (template_dir / "03_content.svg").read_text(encoding="utf-8")
        for token in [
            'data-component="left-navigation"',
            'id="nav-active-band"',
            'id="nav-active-fold"',
            'id="nav-active-pointer"',
            'id="nav-active-icon"',
            'id="nav-active-label"',
            'data-active-index="1"',
            'data-slot="ACTIVE_SECTION_LABEL"',
            'data-slot-token="{{ACTIVE_SECTION_LABEL}}"',
            'data-slot="CONTENT_BODY"',
        ]:
            self.assertIn(token, content_text)
        self.assertNotIn("{{CITATION}}", content_text)
        self.assertNotIn('data-slot="CITATION"', content_text)
        self.assertNotIn("#E7E6E6", content_text)
        self.assertIn('id="nav-surface" x="0" y="0" width="253.38" height="720" fill="#F2F2F2"', content_text)
        self.assertIn("PAGE_TITLE` as the short running title", spec_text)
        self.assertIn("KEY_MESSAGE` as the more detailed one-sentence claim", spec_text)
        self.assertIn("Do not use ad hoc gray fills", spec_text)
        self.assertIn("Flatten directional marker geometry before export", spec_text)
        self.assertIn("content-page header on a fixed grid", spec_text)
        self.assertIn("header-separator", spec_text)
        self.assertIn("Keep `PAGE_NUM` centered", spec_text)
        content_root = ET.fromstring(content_text)
        active_label = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "text" and node.attrib.get("id") == "nav-active-label"
        )
        active_fold = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "g" and node.attrib.get("id") == "nav-active-fold"
        )
        active_pointer = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "polygon" and node.attrib.get("id") == "nav-active-pointer"
        )
        self.assertNotIn("transform", active_fold.attrib)
        self.assertEqual(active_pointer.attrib["points"], nav["sections"][0]["active_pointer"]["points"])
        self.assertEqual(active_label.attrib["x"], "72.54")
        self.assertEqual(active_label.attrib["y"], "201.55")
        self.assertEqual(active_label.attrib["text-anchor"], "start")
        self.assertEqual(active_label.attrib["data-pptx-box-x"], "72.54")
        self.assertEqual(active_label.attrib["data-pptx-box-y"], "159.13")
        self.assertEqual(active_label.attrib["data-pptx-box-w"], "202")
        self.assertEqual(active_label.attrib["data-pptx-box-h"], "65.42")
        self.assertEqual(active_label.attrib["data-pptx-valign"], "middle")
        nav_labels = [
            "".join(node.itertext()).strip()
            for node in content_root.iter()
            if node.tag.split("}")[-1] == "text" and node.attrib.get("data-nav-label") == "inactive"
        ]
        self.assertEqual(nav_labels, layouts["default_sections"])
        nav_surface = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "rect" and node.attrib.get("id") == "nav-surface"
        )
        self.assertEqual(float(nav_surface.attrib["width"]), 253.38)
        page_number_group = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "g" and node.attrib.get("id") == "page-number"
        )
        page_number_rect = next(
            node for node in page_number_group.iter()
            if node.tag.split("}")[-1] == "rect"
        )
        page_number_text = next(
            node for node in page_number_group.iter()
            if node.tag.split("}")[-1] == "text" and node.attrib.get("data-slot") == "PAGE_NUM"
        )
        self.assertEqual(page_number_text.attrib["text-anchor"], "middle")
        self.assertEqual(page_number_text.attrib["data-pptx-valign"], "middle")
        self.assertEqual(float(page_number_text.attrib["data-pptx-box-x"]), float(page_number_rect.attrib["x"]))
        self.assertEqual(float(page_number_text.attrib["data-pptx-box-y"]), float(page_number_rect.attrib["y"]))
        self.assertEqual(float(page_number_text.attrib["data-pptx-box-w"]), float(page_number_rect.attrib["width"]))
        self.assertEqual(float(page_number_text.attrib["data-pptx-box-h"]), float(page_number_rect.attrib["height"]))
        title_marker = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "g" and node.attrib.get("id") == "title-marker"
        )
        self.assertNotIn("transform", title_marker.attrib)
        title_marker_polygon = next(
            node for node in title_marker.iter()
            if node.tag.split("}")[-1] == "polygon"
        )
        title_points = [
            tuple(float(value) for value in pair.split(","))
            for pair in title_marker_polygon.attrib["points"].split()
        ]
        self.assertEqual(max(title_points, key=lambda point: point[0]), title_points[0])
        page_title = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "text" and node.attrib.get("data-slot") == "PAGE_TITLE"
        )
        marker_right = max(point[0] for point in title_points)
        marker_center_y = (min(point[1] for point in title_points) + max(point[1] for point in title_points)) / 2
        page_title_box_center_y = float(page_title.attrib["data-pptx-box-y"]) + float(page_title.attrib["data-pptx-box-h"]) / 2
        self.assertGreaterEqual(float(page_title.attrib["x"]) - marker_right, 28)
        self.assertAlmostEqual(marker_center_y, page_title_box_center_y, places=1)
        self.assertEqual(page_title.attrib["data-pptx-valign"], "middle")
        header_separator = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "rect" and node.attrib.get("id") == "header-separator"
        )
        self.assertEqual(header_separator.attrib["fill"], "#8B0012")
        self.assertEqual(float(header_separator.attrib["x"]), 310)
        self.assertEqual(float(header_separator.attrib["width"]), 910)
        content_area = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "rect" and node.attrib.get("id") == "content-area"
        )
        self.assertEqual(float(content_area.attrib["x"]), expected_content_area["x"])
        self.assertEqual(float(content_area.attrib["y"]), expected_content_area["y"])
        self.assertEqual(float(content_area.attrib["width"]), expected_content_area["width"])
        self.assertEqual(float(content_area.attrib["height"]), expected_content_area["height"])
        self.assertEqual(content_area.attrib["fill"], "none")
        self.assertEqual(content_area.attrib["stroke"], "none")
        self.assertNotIn("stroke-dasharray", content_area.attrib)
        key_message = next(
            node for node in content_root.iter()
            if node.tag.split("}")[-1] == "g" and node.attrib.get("id") == "key-message"
        )
        key_rects = [
            node
            for node in key_message.iter()
            if node.tag.split("}")[-1] == "rect" and node.attrib.get("height")
        ]
        key_text = next(
            node for node in key_message.iter()
            if node.tag.split("}")[-1] == "text" and node.attrib.get("data-slot") == "KEY_MESSAGE"
        )
        self.assertEqual(key_text.attrib["data-pptx-valign"], "middle")
        key_top = min(float(node.attrib["y"]) for node in key_rects)
        key_bottom = max(float(node.attrib["y"]) + float(node.attrib["height"]) for node in key_rects)
        separator_bottom = float(header_separator.attrib["y"]) + float(header_separator.attrib["height"])
        self.assertGreaterEqual(key_top - separator_bottom, 16)
        self.assertGreaterEqual(float(content_area.attrib["y"]) - key_bottom, 32)

        toc_root = ET.fromstring((template_dir / "02_toc.svg").read_text(encoding="utf-8"))
        toc_marker = next(
            node for node in toc_root.iter()
            if node.tag.split("}")[-1] == "g" and node.attrib.get("id") == "shape-9"
        )
        self.assertNotIn("transform", toc_marker.attrib)

    def test_literature_minimal_is_classic_minimal_shell(self):
        layouts_root = TEMPLATES / "layouts"
        index = json.loads((layouts_root / "layouts_index.json").read_text(encoding="utf-8"))
        template_dir = layouts_root / "literature_minimal"
        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")

        self.assertIn("literature_minimal", index)
        self.assertIn("template_id: literature_minimal", spec_text)
        self.assertIn("replication_mode: classic", spec_text)
        self.assertNotIn("slot_guided_mirror", spec_text)

        page_files = sorted(path.name for path in template_dir.glob("*.svg"))
        self.assertEqual(
            page_files,
            [
                "01_cover.svg",
                "02_chapter.svg",
                "02_toc.svg",
                "03_content.svg",
                "04_ending.svg",
            ],
        )

        layouts_contract = json.loads((template_dir / "layouts.json").read_text(encoding="utf-8"))
        self.assertEqual(
            layouts_contract["text_fit_policy"]["schema_version"],
            "easyslides.template_text_fit_policy.v1",
        )
        self.assertIn("slot_models", layouts_contract)

        for sidecar in [
            "page_catalog.json",
            "rules.md",
            "story_structure.json",
            "template.json",
            "layout_roster.json",
            "slot_contracts.json",
            "links.json",
        ]:
            self.assertFalse((template_dir / sidecar).exists(), sidecar)

        content_text = (template_dir / "03_content.svg").read_text(encoding="utf-8")
        for slot in ("PAGE_TITLE", "CHAPTER_TITLE", "KEY_MESSAGE", "CONTENT_BODY", "SOURCE", "PAGE_NUM"):
            self.assertIn(f"{{{{{slot}}}}}", content_text)
        toc_text = (template_dir / "02_toc.svg").read_text(encoding="utf-8")
        for index in range(1, 6):
            self.assertIn(f"{{{{TOC_ITEM_{index}_TITLE}}}}", toc_text)
            self.assertIn(f"{{{{TOC_ITEM_{index}_DESC}}}}", toc_text)
        cover_text = (template_dir / "01_cover.svg").read_text(encoding="utf-8")
        ending_text = (template_dir / "04_ending.svg").read_text(encoding="utf-8")
        self.assertIn('id="cover-chrome"', cover_text)
        self.assertIn('M 0 594 C 220 582', cover_text)
        for slot in ("TITLE", "SUBTITLE", "AUTHOR", "DATE"):
            self.assertIn(f"{{{{{slot}}}}}", cover_text)
        self.assertNotIn("{{INSTITUTION}}", cover_text)
        self.assertIn("日期：", cover_text)
        self.assertIn('y="194.13" width="1280" height="299.73" fill="#0D5DBE"', ending_text)
        self.assertIn("{{THANK_YOU}}", ending_text)
        self.assertIn("English `Thank you for listening!` is acceptable", spec_text)
        root = ET.fromstring(content_text)
        body_nodes = [
            node
            for node in root.iter()
            if node.tag.split("}")[-1] == "text" and node.attrib.get("data-slot") == "CONTENT_BODY"
        ]
        self.assertEqual(len(body_nodes), 1)
        self.assertEqual(body_nodes[0].attrib.get("data-pptx-textbox"), "true")

    def test_literature_minimal_pptx_text_boxes_respect_visual_frames(self):
        template_dir = TEMPLATES / "layouts" / "literature_minimal"

        def slot_text(root: ET.Element, slot: str) -> ET.Element:
            for group in root.iter():
                if group.attrib.get("data-slot") == slot:
                    for node in group.iter():
                        if node.tag.split("}")[-1] == "text":
                            return node
            self.fail(f"{slot} text node missing")

        chapter_root = ET.fromstring((template_dir / "02_chapter.svg").read_text(encoding="utf-8"))
        chapter_desc = slot_text(chapter_root, "CHAPTER_DESC")
        self.assertGreaterEqual(float(chapter_desc.attrib["data-pptx-box-x"]), 512)

        content_root = ET.fromstring((template_dir / "03_content.svg").read_text(encoding="utf-8"))
        key_message = slot_text(content_root, "KEY_MESSAGE")
        self.assertEqual(key_message.attrib.get("data-pptx-valign"), "middle")
        self.assertEqual(float(key_message.attrib["data-pptx-box-y"]), 116)
        self.assertEqual(float(key_message.attrib["data-pptx-box-h"]), 74)

    def test_defense_leftnav_forbids_meta_slide_labels_in_generated_copy(self):
        template_dir = TEMPLATES / "layouts" / "defense_leftnav"
        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
        rules_text = (template_dir / "rules.md").read_text(encoding="utf-8")
        style_text = (template_dir / "component_styles.json").read_text(encoding="utf-8")

        banned_examples = [
            "\u672c\u9875\u843d\u70b9",
            "\u672c\u9875\u5c0f\u7ed3",
            "\u672c\u9875\u91cd\u70b9",
            "\u8fd9\u4e00\u9875\u60f3\u8bf4\u660e",
        ]
        academic_replacements = [
            "\u5173\u952e\u5224\u65ad",
            "\u673a\u5236\u89e3\u91ca",
            "\u7814\u7a76\u8d21\u732e",
            "\u65b9\u6cd5\u4f9d\u636e",
            "\u7ed3\u679c\u542f\u793a",
        ]

        self.assertIn("## Hard Generation Rules", spec_text)
        self.assertIn("meta-slide labels", spec_text)
        self.assertIn("presentation-internal writing process", spec_text)
        for phrase in banned_examples:
            self.assertIn(phrase, spec_text)
            self.assertNotIn(phrase, rules_text)
            self.assertNotIn(phrase, style_text)
        for phrase in academic_replacements:
            self.assertIn(phrase, spec_text)

    def test_defense_leftnav_closing_page_avoids_listening_wording(self):
        template_dir = TEMPLATES / "layouts" / "defense_leftnav"
        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
        rules_text = (template_dir / "rules.md").read_text(encoding="utf-8")
        ending_text = (template_dir / "04_ending.svg").read_text(encoding="utf-8")

        listening_word = "\u8046\u542c"
        banned_closing_phrases = [
            "\u611f\u8c22\u8046\u542c",
            "\u8c22\u8c22\u8046\u542c",
            "\u611f\u8c22\u5404\u4f4d\u8001\u5e08\u8046\u542c",
        ]
        approved_closing_phrases = [
            "\u656c\u8bf7\u5404\u4f4d\u8001\u5e08\u6279\u8bc4\u6307\u6b63",
            "\u611f\u8c22\u5404\u4f4d\u8001\u5e08\u6307\u5bfc",
            "\u8c22\u8c22",
        ]

        self.assertNotIn(listening_word, ending_text)
        self.assertIn("## Hard Generation Rules", spec_text)
        self.assertIn("closing-page wording", spec_text)
        self.assertIn("closing page", spec_text)
        for phrase in banned_closing_phrases:
            self.assertIn(phrase, spec_text)
            self.assertNotIn(phrase, rules_text)
            self.assertNotIn(phrase, ending_text)
        for phrase in approved_closing_phrases:
            self.assertIn(phrase, spec_text)

    def test_defense_leftnav_rules_md_points_to_design_spec_hard_rules(self):
        template_dir = TEMPLATES / "layouts" / "defense_leftnav"
        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
        rules_text = (template_dir / "rules.md").read_text(encoding="utf-8")
        non_empty_rule_lines = [
            line for line in rules_text.splitlines()
            if line.strip() and not line.startswith("#")
        ]

        self.assertIn("## Hard Generation Rules", spec_text)
        self.assertIn(
            "Authoritative hard generation rules live in `design_spec.md#hard-generation-rules`.",
            rules_text,
        )
        self.assertLessEqual(len(non_empty_rule_lines), 4)
        for duplicated_rule_phrase in [
            "PAGE_TITLE",
            "\u672c\u9875\u843d\u70b9",
            "\u611f\u8c22\u8046\u542c",
            "CONTENT_AREA",
        ]:
            self.assertNotIn(duplicated_rule_phrase, rules_text)

    def test_defense_leftnav_template_has_no_default_school_brand(self):
        template_dir = TEMPLATES / "layouts" / "defense_leftnav"
        spec_text = (template_dir / "design_spec.md").read_text(encoding="utf-8")
        layouts_contract = json.loads((template_dir / "layouts.json").read_text(encoding="utf-8"))
        template_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in template_dir.iterdir()
            if path.is_file() and path.suffix in {".svg", ".json", ".md"}
        )

        self.assertIn("specific school logo must never be baked into the template", spec_text)
        self.assertIn("logo-free deck", spec_text)
        self.assertIn("chapter transition pages", spec_text)
        self.assertIn("upper-left", spec_text)
        self.assertIn("other non-content page brand placements unchanged", spec_text)
        brand_slots = layouts_contract["optional_brand_slots"]
        self.assertEqual(brand_slots["enabled"], "source_matched_only")
        self.assertTrue(brand_slots["no_default_school_brand"])
        self.assertEqual(brand_slots["chapter"]["placement"], "upper_left")
        self.assertEqual(brand_slots["chapter"]["box"], {"x": 54, "y": 42, "width": 178, "height": 32})
        self.assertEqual(brand_slots["content"]["placement"], "upper_right_header")
        self.assertEqual(brand_slots["content"]["box"], {"x": 1038, "y": 38, "width": 188, "height": 34})
        self.assertEqual(brand_slots["emblem_top_right"]["placement"], "upper_right")
        self.assertEqual(brand_slots["emblem_top_right"]["box"], {"x": 1048, "y": 44, "width": 178, "height": 32})
        for forbidden in [
            "华东师范大学",
            "East China Normal University",
            "ECNU",
            "ecnu_logo",
            "school_brand_wordmark",
        ]:
            self.assertNotIn(forbidden, template_text)

    def test_chart_library_matches_ppt_master_catalog(self):
        charts_root = TEMPLATES / "charts"
        index = json.loads((charts_root / "charts_index.json").read_text(encoding="utf-8"))

        self.assertEqual(index["meta"]["total"], 71)
        chart_files = {path.stem for path in charts_root.glob("*.svg")}
        self.assertEqual(chart_files, set(index["charts"]))

    def test_icon_library_contains_all_ppt_master_families(self):
        icons_root = TEMPLATES / "icons"
        expected_counts = {
            "chunk-filled": 640,
            "lucide": 4,
            "phosphor-duotone": 1248,
            "simple-icons": 3651,
            "tabler-filled": 1053,
            "tabler-outline": 5039,
        }

        actual_counts = {
            family: len(list((icons_root / family).glob("*.svg")))
            for family in expected_counts
        }
        self.assertEqual(actual_counts, expected_counts)
        self.assertEqual(sum(actual_counts.values()), 11635)


if __name__ == "__main__":
    unittest.main()
