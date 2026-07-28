import json
import tempfile
import unittest
from pathlib import Path


def valid_component_plan() -> dict:
    return {
        "schema_version": "easyslides.component_plan.v1",
        "slides": [
            {
                "page": "P01",
                "selected_assets": [
                    {
                        "asset_id": "card/three_card_summary",
                        "payload": {
                            "items": [
                                {"title": "Need", "body": "Readers need source-linked claims."},
                                {"title": "Method", "body": "The planner selects a verified component."},
                                {"title": "Gate", "body": "Payload capacity is checked before rendering."},
                            ]
                        },
                    }
                ],
            }
        ],
    }


def legacy_component_package_registry() -> dict:
    """Keep validating the legacy source schema without publishing its pack."""
    component_path = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "components"
        / "packages"
        / "research-core"
        / "components"
        / "three_card_summary"
        / "component.json"
    )
    component = json.loads(component_path.read_text(encoding="utf-8"))
    return {
        "assets": [
            {
                "asset_id": component["asset_id"],
                "granularity": component["granularity"],
                "metadata": {
                    "source_asset_id": component["source_asset_id"],
                    "input_schema": component["input_schema"],
                },
                "required_gates": component["qa"]["required_gates"],
            }
        ]
    }


class ComponentPlanContractTests(unittest.TestCase):

    def test_component_package_input_schema_blocks_unknown_payload_fields(self):
        from scripts.component_plan_contract import validate_component_plan

        registry = legacy_component_package_registry()
        plan = {
            "schema_version": "easyslides.component_plan.v1",
            "slides": [
                {
                    "page": "P01",
                    "selected_assets": [
                        {
                            "asset_id": "component_package/three_card_summary",
                            "payload": {
                                "items": [
                                    {"title": "A", "body": "One", "unexpected": "no"},
                                    {"title": "B", "body": "Two"},
                                    {"title": "C", "body": "Three"}
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        report = validate_component_plan(plan, registry=registry)

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PLAN-PAYLOAD", {issue["code"] for issue in report["issues"]})
    def test_valid_component_plan_passes(self):
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        report = validate_component_plan(
            valid_component_plan(),
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(report["schema_version"], "easyslides.component_plan_report.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertIn("component_selector", report["required_gates"])

    def test_unknown_asset_fails(self):
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        plan = valid_component_plan()
        plan["slides"][0]["selected_assets"][0]["asset_id"] = "card/missing"

        report = validate_component_plan(
            plan,
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PLAN-ASSET-ID", {item["code"] for item in report["issues"]})

    def test_named_template_rejects_unscoped_global_asset(self):
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        plan = valid_component_plan()
        plan["template_id"] = "defense_topnav"
        report = validate_component_plan(
            plan,
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(report["status"], "fail")
        self.assertIn("template_capability_profile", report["required_gates"])
        self.assertIn("COMPONENT-PLAN-TEMPLATE-ASSET", {item["code"] for item in report["issues"]})

    def test_over_capacity_payload_fails_before_rendering(self):
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        plan = valid_component_plan()
        plan["slides"][0]["selected_assets"][0]["payload"]["items"][0]["body"] = "too long " * 80

        report = validate_component_plan(
            plan,
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PLAN-PAYLOAD", {item["code"] for item in report["issues"]})

    def test_component_package_payload_uses_source_asset_capacity(self):
        from scripts.component_plan_contract import validate_component_plan

        plan = valid_component_plan()
        plan["slides"][0]["selected_assets"][0]["asset_id"] = "component_package/three_card_summary"
        plan["slides"][0]["selected_assets"][0]["payload"]["items"][0]["body"] = "too long " * 80

        report = validate_component_plan(
            plan,
            registry=legacy_component_package_registry(),
        )

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PLAN-PAYLOAD", {item["code"] for item in report["issues"]})

    def test_deck_plan_coverage_requires_component_for_each_page(self):
        from scripts.component_plan_contract import validate_component_plan_file
        from scripts.component_registry import build_component_registry

        deck_plan = {
            "schema_version": "easyslides.deck_plan.v1",
            "slides": [{"page": "P01"}, {"page": "P02"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            component_plan_path = tmp_path / "component_plan.json"
            deck_plan_path = tmp_path / "deck_plan.json"
            registry_path = tmp_path / "component_registry.json"
            component_plan_path.write_text(json.dumps(valid_component_plan(), ensure_ascii=False), encoding="utf-8")
            deck_plan_path.write_text(json.dumps(deck_plan, ensure_ascii=False), encoding="utf-8")
            registry_path.write_text(
                json.dumps(build_component_registry(include_template_asset_bank=False), ensure_ascii=False),
                encoding="utf-8",
            )

            report = validate_component_plan_file(
                component_plan_path,
                registry_path=registry_path,
                deck_plan_path=deck_plan_path,
            )

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PLAN-DECK-COVERAGE", {item["code"] for item in report["issues"]})


if __name__ == "__main__":
    unittest.main()
