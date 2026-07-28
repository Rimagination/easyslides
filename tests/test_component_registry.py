import json
import tempfile
import unittest
from pathlib import Path


class ComponentRegistryTests(unittest.TestCase):
    def test_registry_builds_from_existing_assets(self):
        from scripts.component_registry import build_component_registry, validate_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        report = validate_component_registry(registry)

        self.assertEqual(registry["schema_version"], "easyslides.component_registry.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertIn("card_component", registry["counts_by_granularity"])
        self.assertIn("component_package", registry["counts_by_granularity"])
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
        self.assertIn("component_package/three_card_summary", asset_ids)
        self.assertIn("visual_recipe/pm_flow_strip", asset_ids)
        self.assertIn("page_recipe/pm_causal_map", asset_ids)
        self.assertIn("body_variant/defense_topnav/three_card_summary", asset_ids)
        self.assertIn("component/nsfc_defense/claim_bar", asset_ids)
        self.assertIn("chart/bar_chart", asset_ids)
        self.assertIn("icon_family/tabler-outline", asset_ids)

    def test_body_variant_assets_retain_ordered_component_dependencies(self):
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        variant = next(
            asset
            for asset in registry["assets"]
            if asset["asset_id"] == "body_variant/nsfc_defense/evidence_triptych"
        )

        refs = variant["metadata"]["component_refs"]
        dependencies = variant["metadata"]["component_dependency_asset_ids"]
        self.assertEqual(variant["metadata"]["composition_mode"], "ordered_component_refs")
        self.assertEqual(
            [ref["asset_id"] for ref in refs],
            ["component/nsfc_defense/evidence_triptych"],
        )
        self.assertEqual(
            dependencies,
            [
                "component/nsfc_defense/evidence_triptych",
                "component/nsfc_defense/claim_bar",
                "component/nsfc_defense/info_panel",
                "component/nsfc_defense/evidence_figure",
                "component/nsfc_defense/caption_bar",
                "component/nsfc_defense/callout_panel",
                "component/nsfc_defense/synthesis_bar",
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

    def test_component_package_assets_preserve_story_and_alignment_metadata(self):
        from scripts.component_registry import build_component_registry

        registry = build_component_registry(include_template_asset_bank=False)
        package_asset = next(
            asset
            for asset in registry["assets"]
            if asset["asset_id"] == "component_package/three_card_summary"
        )
        invariants = package_asset["metadata"]["qa"]["alignment_invariants"]

        self.assertEqual(package_asset["metadata"]["source_asset_id"], "card/three_card_summary")
        self.assertTrue(package_asset["metadata"]["stories"])
        self.assertEqual(invariants[0]["rule"], "text_center_y_matches_container_center_y")
        self.assertEqual(package_asset["slots"][0]["alignment"]["vertical"], "middle")

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
