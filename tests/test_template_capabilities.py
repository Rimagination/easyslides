from __future__ import annotations

import unittest


class TemplateCapabilityTests(unittest.TestCase):
    def test_every_layout_directory_has_a_valid_capability_profile(self):
        from scripts.template_capabilities import build_capability_registry

        report = build_capability_registry()
        by_id = {row["template_id"]: row for row in report["templates"]}

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(by_id["nsfc_defense"]["composition_mode"], "template_composable")
        self.assertEqual(by_id["defense_topnav"]["composition_mode"], "body_variant_only")
        self.assertEqual(by_id["academic_general"]["composition_mode"], "shell_only")
        self.assertFalse(by_id["nsfc_defense_distilled"]["generation_enabled"])

    def test_named_template_rejects_global_and_cross_template_assets(self):
        from scripts.component_registry import build_component_registry
        from scripts.template_capabilities import asset_allowed_for_template, load_template_capability

        assets = {
            asset["asset_id"]: asset
            for asset in build_component_registry(include_template_asset_bank=False)["assets"]
        }
        capability = load_template_capability("defense_topnav")

        allowed, _ = asset_allowed_for_template(
            assets["body_variant/defense_topnav/three_card_summary"], capability
        )
        global_allowed, _ = asset_allowed_for_template(assets["card/three_card_summary"], capability)
        cross_template_allowed, _ = asset_allowed_for_template(
            assets["body_variant/defense_leftnav/card_grid"], capability
        )

        self.assertTrue(allowed)
        self.assertFalse(global_allowed)
        self.assertFalse(cross_template_allowed)

    def test_missing_named_template_profile_fails_closed(self):
        from scripts.template_capabilities import load_template_capability

        capability = load_template_capability("not_a_real_template")

        self.assertEqual(capability["status"], "fail")


if __name__ == "__main__":
    unittest.main()
