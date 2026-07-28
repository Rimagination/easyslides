import unittest


class ComponentSelectionReviewTests(unittest.TestCase):
    def test_review_retains_recommended_component_and_alternatives(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry
        from scripts.component_selection_review import build_component_selection_review

        registry = build_component_registry(include_template_asset_bank=False)
        plan = build_component_plan(
            {
                "schema_version": "easyslides.deck_plan.v1",
                "slides": [{"page": "P01", "role": "overview", "content_shape": "parallel_points", "item_count": 3}],
            },
            registry=registry,
        )
        review = build_component_selection_review(plan, registry=registry)

        self.assertEqual(review["status"], "pass", review)
        self.assertTrue(review["slides"][0]["recommended"])
        self.assertIn("component_requirements.selected_asset_id", review["slides"][0]["approval_contract"]["deck_plan_field"])

    def test_explicit_approved_asset_is_used_when_template_is_compatible(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.component_registry import build_component_registry

        plan = build_component_plan(
            {
                "schema_version": "easyslides.deck_plan.v1",
                "slides": [
                    {
                        "page": "P01",
                        "role": "overview",
                        "content_shape": "parallel_points",
                        "item_count": 3,
                        "component_requirements": {"selected_asset_id": "component_package/three_card_summary"},
                    }
                ],
            },
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(plan["slides"][0]["selected_assets"][0]["asset_id"], "component_package/three_card_summary")


if __name__ == "__main__":n+    unittest.main()
