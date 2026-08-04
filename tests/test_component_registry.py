import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class ComponentRegistryTests(unittest.TestCase):
    def test_registry_builds_from_existing_assets(self):
        from scripts.component_registry import build_component_registry, validate_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        report = validate_component_registry(registry)

        self.assertEqual(registry["schema_version"], "easyslides.component_registry.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertIn("card_component", registry["counts_by_granularity"])
        self.assertNotIn("component_package", registry["counts_by_granularity"])
        self.assertIn("page_recipe", registry["counts_by_granularity"])
        self.assertIn("body_variant", registry["counts_by_granularity"])
        self.assertIn("template_component", registry["counts_by_granularity"])
        self.assertEqual(registry["counts_by_granularity"]["chart_asset"], 71)
        self.assertEqual(registry["counts_by_granularity"]["icon_family"], 6)

    def test_registry_includes_stable_asset_ids(self):
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        asset_ids = {asset["asset_id"] for asset in registry["assets"]}

        self.assertIn("card/three_card_summary", asset_ids)
        self.assertNotIn("component_package/three_card_summary", asset_ids)
        self.assertIn("body_variant/academic_general/comparison_synthesis", asset_ids)
        self.assertIn("component/academic_general/comparison_column", asset_ids)
        self.assertIn("visual_recipe/pm_flow_strip", asset_ids)
        self.assertIn("page_recipe/pm_causal_map", asset_ids)
        self.assertIn("body_variant/defense_topnav/three_card_summary", asset_ids)
        self.assertIn("component/nsfc_defense/statement_panel", asset_ids)
        self.assertIn("chart/bar_chart", asset_ids)
        self.assertIn("icon_family/tabler-outline", asset_ids)

    def test_body_variant_assets_retain_ordered_component_dependencies(self):
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        variant = next(
            asset
            for asset in registry["assets"]
            if asset["asset_id"] == "body_variant/nsfc_defense/evidence_chain"
        )

        refs = variant["metadata"]["component_refs"]
        dependencies = variant["metadata"]["component_dependency_asset_ids"]
        self.assertEqual(variant["metadata"]["composition_mode"], "ordered_component_refs")
        self.assertEqual(
            [ref["asset_id"] for ref in refs],
            [
                "component/nsfc_defense/statement_panel",
                "component/nsfc_defense/vertical_key_tag",
                "component/nsfc_defense/evidence_tile",
                "component/nsfc_defense/evidence_tile",
                "component/nsfc_defense/evidence_tile",
                "component/nsfc_defense/evidence_tile",
            ],
        )
        self.assertEqual(
            dependencies,
            [
                "component/nsfc_defense/statement_panel",
                "component/nsfc_defense/vertical_key_tag",
                "component/nsfc_defense/evidence_tile",
            ],
        )

    def test_legacy_registry_is_hydrated_with_chart_assets(self):
        from scripts.component_registry import load_component_registry

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy_registry.json"
            path.write_text(
                json.dumps({"schema_version": "easyslides.component_registry.v1", "assets": []}),
                encoding="utf-8",
            )
            registry = load_component_registry(path)

        self.assertIn("chart/bar_chart", {asset["asset_id"] for asset in registry["assets"]})
        self.assertEqual(registry["counts_by_granularity"]["chart_asset"], 71)

    def test_academic_general_component_preserves_centered_caption_contract(self):
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        package_asset = next(
            asset
            for asset in registry["assets"]
            if asset["asset_id"] == "component/academic_general/media_panel"
        )
        root = ET.parse(
            ROOT / "templates" / "layouts" / "academic_general" / "assets" / "components" / "media_panel.svg"
        ).getroot()
        caption = next(node for node in root.iter() if node.get("data-slot-id") == "CAPTION")

        self.assertEqual(package_asset["metadata"]["template_id"], "academic_general")
        self.assertIn("vertical_center_alignment", package_asset["required_gates"])
        self.assertEqual(caption.get("data-pptx-valign"), "middle")
        self.assertEqual(caption.get("data-center-lock"), "true")

    def test_cli_build_writes_registry(self):
        from scripts.component_registry import main

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "component_registry.json"
            code = main(["build", "--output", str(output), "--no-template-asset-bank"])

            self.assertEqual(code, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "easyslides.component_registry.v1")


if __name__ == "__main__":
    unittest.main()
