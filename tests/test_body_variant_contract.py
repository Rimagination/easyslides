import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"


class BodyVariantComponentContractTests(unittest.TestCase):
    def test_legacy_component_names_normalize_to_stable_asset_ids(self):
        from scripts.body_variant_contract import normalize_component_refs

        refs = normalize_component_refs(
            {"components": ["key_point_bar", "evidence_triptych"]},
            "nsfc_defense",
        )

        self.assertEqual(
            [ref["asset_id"] for ref in refs],
            [
                "component/nsfc_defense/key_point_bar",
                "component/nsfc_defense/evidence_triptych",
            ],
        )
        self.assertEqual([ref["order"] for ref in refs], [1, 2])
        self.assertEqual(len({ref["instance_id"] for ref in refs}), 2)

    def test_nsfc_variants_resolve_all_template_component_refs(self):
        from scripts.body_variant_contract import validate_body_variant_contract

        report = validate_body_variant_contract(NSFC)

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["variant_count"], 9)
        self.assertEqual(report["component_ref_count"], 38)
        self.assertEqual(report["resolved_component_count"], 38)
        self.assertGreater(report["component_dependency_count"], 0)
        self.assertEqual(report["warning_count"], 0)

    def test_body_canvas_variant_cannot_escape_declared_content_area(self):
        from scripts.body_variant_contract import validate_body_variant_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            body_variants_path = template / "body_variants.json"
            payload = json.loads(body_variants_path.read_text(encoding="utf-8"))
            payload["variants"] = [payload["variants"][0]]
            payload["variants"][0]["regions"][0]["frame"]["x"] = -1
            body_variants_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            report = validate_body_variant_contract(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn(
            "BODY-VARIANT-REGION-OUTSIDE-CANVAS",
            {issue["code"] for issue in report["issues"]},
        )

    def test_required_unknown_component_fails_closed(self):
        from scripts.body_variant_contract import validate_body_variant_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "fixture"
            template.mkdir()
            (template / "body_variants.json").write_text(
                json.dumps(
                    {
                        "template_id": "fixture",
                        "variants": [
                            {
                                "variant_id": "content",
                                "slots": ["BODY"],
                                "component_refs": [
                                    {
                                        "asset_id": "component/fixture/missing",
                                        "instance_id": "missing",
                                        "role": "body",
                                        "order": 1,
                                        "required": True,
                                        "slot_bindings": {},
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report = validate_body_variant_contract(template, registry={"assets": []})

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["issues"][0]["code"], "BODY-VARIANT-COMPONENT-MISSING")

    def test_component_plan_expands_body_variant_dependencies(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_plan_contract import validate_component_plan
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        plan = build_component_plan(
            {
                "schema_version": "easyslides.deck_plan.v1",
                "template_id": "nsfc_defense",
                "slides": [
                    {
                        "page": "P01",
                        "role": "content",
                        "layout_id": "nsfc_defense/need_relationship_evidence",
                        "slot_payload": {},
                    }
                ],
            },
            registry=registry,
        )
        selected = plan["slides"][0]["selected_assets"][0]
        report = validate_component_plan(plan, registry=registry)

        self.assertEqual(selected["asset_id"], "body_variant/nsfc_defense/need_relationship_evidence")
        self.assertEqual(selected["composition_mode"], "ordered_component_refs")
        self.assertEqual(len(selected["component_refs"]), 5)
        self.assertEqual(len(selected["component_dependency_asset_ids"]), 5)
        self.assertIn("template_component_pack_contract", selected["required_gates"])
        self.assertIn("body_variant_component_contract", selected["required_gates"])
        self.assertEqual(report["status"], "pass", report["issues"])


if __name__ == "__main__":
    unittest.main()
