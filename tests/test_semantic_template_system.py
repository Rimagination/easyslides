import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "layouts" / "nsfc_purple_semantic"


class SemanticTemplateSystemTests(unittest.TestCase):
    def test_clean_nsfc_template_contract_and_variant_resolution(self):
        from scripts.semantic_template_renderer import load_template, resolve_layout
        from scripts.template_production_gate import validate_contract

        report = validate_contract(TEMPLATE)
        self.assertEqual(report["status"], "pass", report["issues"])
        template = load_template(TEMPLATE)
        selected = resolve_layout(
            template,
            {"role": "content", "content_shape": "architecture", "item_count": 3},
        )
        self.assertEqual(selected["layout_id"], "figure_left")
        comparison = resolve_layout(
            template,
            {"role": "content", "content_shape": "comparison", "item_count": 6},
        )
        self.assertEqual(comparison["layout_id"], "comparison_focus")

    def test_expanded_layout_variants_are_routable_and_renderable(self):
        from scripts.semantic_template_renderer import load_template, render_deck, resolve_layout

        template = load_template(TEMPLATE)
        cases = {
            "timeline": ("timeline", 4),
            "quote": ("quote", 1),
            "metric_set": ("metrics", 4),
            "table": ("table", 4),
            "four_findings": ("four_cards", 4),
        }
        for content_shape, (expected_layout, item_count) in cases.items():
            selected = resolve_layout(
                template,
                {"role": "content", "content_shape": content_shape, "item_count": item_count},
            )
            self.assertEqual(selected["layout_id"], expected_layout)

        slides = []
        for layout_id in ("timeline", "quote", "metrics", "table", "four_cards"):
            layout = template.layouts[layout_id]
            payload = {}
            for declared in layout["slots"]:
                slot_id = declared["slot_id"]
                if declared["kind"] == "image":
                    continue
                if declared["kind"] == "list":
                    payload[slot_id] = ["Evidence point one", "Evidence point two"]
                elif slot_id.endswith("_VALUE") or "_VALUE_" in slot_id:
                    payload[slot_id] = "12.3%"
                elif slot_id == "PAGE_NUM":
                    payload[slot_id] = "1"
                else:
                    payload[slot_id] = "Sample"
            slides.append(
                {
                    "role": "content",
                    "layout_id": layout_id,
                    "content_shape": "expanded",
                    "item_count": 4,
                    "slot_payload": payload,
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "expanded_plan.json"
            plan_path.write_text(json.dumps({"slides": slides}), encoding="utf-8")
            manifest = render_deck(TEMPLATE, plan_path, root / "out")

        self.assertEqual(manifest["slide_count"], 5)
        self.assertEqual(
            [row["layout_id"] for row in manifest["assignments"]],
            ["timeline", "quote", "metrics", "table", "four_cards"],
        )

    def test_named_slot_rendering_rejects_overflow_and_unknown_slots(self):
        from scripts.semantic_template_renderer import (
            SemanticTemplateError,
            SlotCapacityError,
            load_template,
            render_deck,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {
                "slides": [
                    {
                        "role": "content",
                        "content_shape": "text_focus",
                        "item_count": 1,
                        "slot_payload": {
                            "PAGE_TITLE": "Short title",
                            "KEY_MESSAGE": "One clear claim",
                            "BODY": ["This line is intentionally short."],
                            "PAGE_NUM": "1",
                        },
                    }
                ]
            }
            path = root / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            manifest = render_deck(TEMPLATE, path, root / "out")
            self.assertEqual(manifest["assignments"][0]["layout_id"], "text_focus")
            rendered = (root / "out" / "01_text_focus.svg").read_text(encoding="utf-8")
            self.assertNotIn("{{", rendered)
            stale = root / "out" / "99_stale.svg"
            stale.write_text("<svg/>", encoding="utf-8")
            render_deck(TEMPLATE, path, root / "out")
            self.assertFalse(stale.exists())
            self.assertTrue((root / "out" / "assets" / "transparent.svg").is_file())

            plan["slides"][0]["slot_payload"]["BODY"] = ["x" * 800]
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(SlotCapacityError):
                render_deck(TEMPLATE, path, root / "overflow")

            plan["slides"][0]["slot_payload"] = {
                "PAGE_TITLE": "Short",
                "KEY_MESSAGE": "Claim",
                "BODY": ["Body"],
                "PAGE_NUM": "1",
                "UNKNOWN": "forbidden",
            }
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(SemanticTemplateError):
                render_deck(TEMPLATE, path, root / "unknown")

    def test_cover_static_background_is_copied_for_svg_consumers(self):
        from scripts.semantic_template_renderer import render_deck

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {
                "slides": [
                    {
                        "role": "cover",
                        "content_shape": "cover",
                        "item_count": 1,
                        "slot_payload": {
                            "TITLE": "Template title",
                            "SUBTITLE": "Template subtitle",
                            "AUTHOR": "Author",
                            "DATE": "2026",
                        },
                    }
                ]
            }
            path = root / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            render_deck(TEMPLATE, path, root / "out")
            rendered = (root / "out" / "01_cover.svg").read_text(encoding="utf-8")
            self.assertIn("assets/nsfc_purple_dark_pattern.png", rendered)
            self.assertTrue((root / "out" / "assets" / "nsfc_purple_dark_pattern.png").is_file())

    def test_production_gate_is_review_required_without_rendered_evidence(self):
        from scripts.template_production_gate import run_gate

        report = run_gate(TEMPLATE)
        self.assertEqual(report["status"], "review_required")
        self.assertFalse(report["production_eligible"])
        self.assertEqual(report["blocking_count"], 0)

    def test_production_gate_exposes_hard_text_geometry_and_cross_material_gates(self):
        from scripts.template_production_gate import run_gate

        report = run_gate(TEMPLATE)
        gates = {gate["id"]: gate for gate in report["gates"]}

        self.assertEqual(gates["template_capability_profile"]["status"], "pass")
        self.assertEqual(gates["template_slot_contract"]["status"], "pass")
        self.assertEqual(gates["component_catalog"]["status"], "pass")
        self.assertEqual(gates["svg_text_slots"]["status"], "pass")
        self.assertEqual(gates["template_geometry_svg"]["status"], "pass")
        self.assertEqual(gates["cross_material_smoke"]["status"], "review_required")
        self.assertIn("template_geometry_pptx", gates)
        self.assertFalse(report["production_eligible"])

    def test_component_catalog_must_point_to_indexed_materialized_assets(self):
        from scripts.template_production_gate import validate_component_catalog

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            (root / "assets" / "asset_manifest.json").write_text(
                json.dumps({"assets": [], "asset_count": 0}),
                encoding="utf-8",
            )
            (root / "component_catalog.json").write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "component_id": "missing",
                                "asset_path": "assets/components/missing.svg",
                            }
                        ],
                        "symbols": [],
                        "unknown_component_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            report = validate_component_catalog(root)

        self.assertEqual(report["status"], "fail")
        self.assertTrue({item["code"] for item in report["issues"]} & {"COMPONENT-CATALOG-ASSET-MISSING"})

    def test_partial_visual_diff_inputs_fail_closed(self):
        from scripts.template_production_gate import run_gate

        report = run_gate(TEMPLATE, source_render_dir=Path("tmp/source-only"))
        gates = {gate["id"]: gate for gate in report["gates"]}

        self.assertEqual(gates["render_diff"]["status"], "fail")
        self.assertEqual(report["status"], "fail")

    def test_invalid_compact_valign_cannot_be_green(self):
        from scripts.template_production_gate import run_gate

        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / TEMPLATE.name
            shutil.copytree(TEMPLATE, clone)
            toc = clone / "02_toc.svg"
            toc.write_text(
                toc.read_text(encoding="utf-8").replace(
                    'data-pptx-valign="middle"', 'data-pptx-valign="mid"', 1
                ),
                encoding="utf-8",
            )
            report = run_gate(clone)

        gates = {gate["id"]: gate for gate in report["gates"]}
        self.assertEqual(report["status"], "fail")
        self.assertEqual(gates["svg_text_slots"]["status"], "fail")

    def test_source_promotion_requires_passed_gate(self):
        from scripts.pptx_distill_promote import require_passed_promotion_report

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            with self.assertRaises(ValueError):
                require_passed_promotion_report(
                    workspace,
                    {"status": "review_required", "promotable": False},
                )
            report = require_passed_promotion_report(
                workspace,
                {"status": "pass", "promotable": True},
            )
            self.assertTrue(report["promotable"])


if __name__ == "__main__":
    unittest.main()
