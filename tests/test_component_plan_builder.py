import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "component_plan_builder.py"


def sample_deck_plan() -> dict:
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "template_id": "defense_topnav",
        "slides": [
            {
                "page": "P01",
                "role": "result",
                "action_title": "Three checks keep the generated slide readable",
                "claim": "Parallel checks should be shown as peer cards.",
                "content_shape": "parallel_points",
                "item_count": 3,
                "rhythm": "breathing",
                "component_requirements": {"preferred_granularity": "card_component"},
                "component_payload": {
                    "items": [
                        {"title": "Need", "body": "Use source-linked claims."},
                        {"title": "Fit", "body": "Check content against capacity."},
                        {"title": "Gate", "body": "Validate before rendering."},
                    ]
                },
            },
            {
                "page": "P02",
                "role": "result",
                "action_title": "The selected template card layout remains exact",
                "claim": "Explicit body variants should stay inside the distilled template.",
                "content_shape": "cards",
                "layout_id": "defense_topnav/three_card_summary",
                "slot_payload": {
                    "CARD_1_TITLE": "Need",
                    "CARD_1_BODY": "Readers need source-linked claims.",
                    "CARD_2_TITLE": "Method",
                    "CARD_2_BODY": "The planner selects a verified body variant.",
                    "CARD_3_TITLE": "Gate",
                    "CARD_3_BODY": "Slot payload is checked before rendering.",
                },
                "rhythm": "dense",
            },
            {
                "page": "P03",
                "role": "mechanism",
                "action_title": "Exposure creates a chain of measurable responses",
                "claim": "A causal chain should use a full-page recipe.",
                "content_shape": "causal_chain",
                "item_count": 4,
                "rhythm": "breathing",
                "component_requirements": {"preferred_granularity": "page_recipe"},
            },
        ],
    }


class ComponentPlanBuilderTests(unittest.TestCase):
    def test_named_template_requires_declared_local_body_variants(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        plan = build_component_plan(sample_deck_plan(), registry=registry, limit=1)
        report = validate_component_plan(plan, registry=registry)

        self.assertEqual(plan["schema_version"], "easyslides.component_plan.v1")
        self.assertEqual(plan["source_schema_version"], "easyslides.deck_plan.v1")
        self.assertEqual([slide["selection_status"] for slide in plan["slides"]], ["blocked", "found", "blocked"])
        self.assertEqual(report["status"], "fail")
        self.assertIn("declared body variant", plan["slides"][0]["selection_block_reason"])
        self.assertEqual(
            plan["slides"][1]["selected_assets"][0]["asset_id"],
            "body_variant/defense_topnav/three_card_summary",
        )

    def test_named_template_blocks_explicit_global_component(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = sample_deck_plan()
        deck_plan["slides"] = [
            {
                "page": "P01",
                "role": "result",
                "component_requirements": {"selected_asset_id": "card/three_card_summary"},
            }
        ]
        plan = build_component_plan(
            deck_plan,
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(plan["slides"][0]["selection_status"], "blocked")
        self.assertIn("not allowed by this template profile", plan["slides"][0]["selection_block_reason"])

    def test_content_shape_aliases_support_card_body_variants(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = sample_deck_plan()
        deck_plan["slides"] = [deck_plan["slides"][1]]
        registry = build_component_registry(include_template_asset_bank=False)

        plan = build_component_plan(deck_plan, registry=registry, limit=1)

        self.assertEqual(plan["slides"][0]["content_shape"], "parallel_points")
        self.assertEqual(
            plan["slides"][0]["selected_assets"][0]["asset_id"],
            "body_variant/defense_topnav/three_card_summary",
        )

    def test_explicit_chart_id_selects_the_chart_asset_directly(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = {
            "schema_version": "easyslides.deck_plan.v1",
            "slides": [
                {
                    "page": "P01",
                    "role": "result",
                    "action_title": "The trend changes after intervention",
                    "chart_id": "line_chart",
                    "chart_payload": {"data": {"categories": ["2024", "2025"], "series": [1, 2]}},
                }
            ],
        }
        registry = build_component_registry(include_template_asset_bank=False)
        plan = build_component_plan(deck_plan, registry=registry, limit=1)
        report = validate_component_plan(plan, registry=registry)

        self.assertEqual(plan["slides"][0]["content_shape"], "chart")
        self.assertEqual(plan["slides"][0]["selected_assets"][0]["asset_id"], "chart/line_chart")
        self.assertEqual(report["status"], "pass", report["issues"])

    def test_explicit_icon_family_selects_and_validates_icon_payload(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = {
            "schema_version": "easyslides.deck_plan.v1",
            "slides": [
                {
                    "page": "P01",
                    "role": "content",
                    "action_title": "The method uses a consistent symbol",
                    "icon_family": "lucide",
                    "icon_name": "lucide/calendar-days",
                }
            ],
        }
        registry = build_component_registry(include_template_asset_bank=False)
        plan = build_component_plan(deck_plan, registry=registry, limit=1)
        report = validate_component_plan(plan, registry=registry)

        self.assertEqual(plan["slides"][0]["content_shape"], "icon")
        self.assertEqual(plan["slides"][0]["selected_assets"][0]["asset_id"], "icon_family/lucide")
        self.assertEqual(report["status"], "pass", report["issues"])

    def test_untemplated_plan_uses_generic_card_not_migrated_template_scene(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = sample_deck_plan()
        deck_plan.pop("template_id")
        deck_plan["slides"] = [
            {
                "page": "P01",
                "role": "result",
                "content_shape": "parallel_points",
                "item_count": 3,
                "component_payload": {
                    "items": [
                        {"title": "Need", "body": "Source-linked claims."},
                        {"title": "Fit", "body": "Capacity is checked."},
                        {"title": "Gate", "body": "Review before render."},
                    ]
                },
            }
        ]
        registry = build_component_registry(include_template_asset_bank=False)

        plan = build_component_plan(deck_plan, registry=registry, limit=1)

        self.assertEqual(plan["slides"][0]["selection_query"]["preferred_granularity"], "card_component")
        self.assertEqual(
            plan["slides"][0]["selected_assets"][0]["asset_id"],
            "card/three_card_summary",
        )

    def test_builder_passes_evidence_selection_metadata(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = {
            "schema_version": "easyslides.deck_plan.v1",
            "slides": [
                {
                    "page": "P01",
                    "role": "result",
                    "content_shape": "supporting_points",
                    "item_count": 3,
                    "component_requirements": {
                        "evidence_type": "text_evidence",
                        "editable_target": "evidence_items",
                        "visual_complexity": "high",
                    },
                    "component_payload": {
                        "claim": "Multiple sources support the conclusion.",
                        "items": [
                            {"evidence": "Records show the same trend."},
                            {"evidence": "Independent checks localize error."},
                            {"evidence": "Sensitivity tests keep rank order."},
                        ],
                    },
                }
            ],
        }
        registry = build_component_registry(include_template_asset_bank=False)

        plan = build_component_plan(deck_plan, registry=registry, limit=1)

        self.assertEqual(plan["slides"][0]["selection_query"]["evidence_type"], "text_evidence")
        self.assertEqual(plan["slides"][0]["selection_query"]["editable_target"], "evidence_items")
        self.assertEqual(plan["slides"][0]["selection_query"]["visual_complexity"], "high")
        self.assertFalse(plan["slides"][0]["selected_assets"][0]["asset_id"].startswith("component_package/"))

    def test_untemplated_selection_does_not_borrow_template_assets(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry

        deck_plan = sample_deck_plan()
        deck_plan.pop("template_id")
        deck_plan["slides"] = [
            {
                "page": "P01",
                "role": "argument",
                "action_title": "A single claim needs emphasis",
                "claim": "Generic plans should not borrow a template body variant.",
                "content_shape": "argument",
                "item_count": 1,
                "rhythm": "anchor",
            }
        ]

        registry = build_component_registry(include_template_asset_bank=False)
        plan = build_component_plan(deck_plan, registry=registry, limit=1)
        asset_id = plan["slides"][0]["selected_assets"][0]["asset_id"]

        self.assertFalse(asset_id.startswith("body_variant/"), asset_id)
        self.assertFalse(asset_id.startswith("page_module/"), asset_id)

    def test_cli_writes_and_validates_component_plan(self):
        from scripts.component_registry import build_component_registry

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            deck_path = tmp_path / "deck_plan.json"
            registry_path = tmp_path / "component_registry.json"
            output_path = tmp_path / "component_plan.json"
            deck_plan = sample_deck_plan()
            deck_plan["slides"] = [deck_plan["slides"][1]]
            deck_path.write_text(json.dumps(deck_plan, ensure_ascii=False, indent=2), encoding="utf-8")
            registry_path.write_text(
                json.dumps(build_component_registry(include_template_asset_bank=False), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    str(deck_path),
                    "--registry",
                    str(registry_path),
                    "--write",
                    str(output_path),
                    "--validate",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            plan = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["validation_status"], "pass")
        self.assertEqual(plan["slide_count"], 1)


if __name__ == "__main__":
    unittest.main()
