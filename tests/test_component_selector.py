import unittest


class ComponentSelectorTests(unittest.TestCase):
    def test_selects_card_for_parallel_points_when_card_preferred(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="parallel_points",
            item_count=3,
            preferred_granularity="card_component",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "card/three_card_summary")

    def test_selects_page_recipe_for_causal_chain(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            page_role="mechanism",
            content_shape="causal_chain",
            item_count=4,
            preferred_granularity="page_recipe",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "page_recipe/pm_causal_map")

    def test_template_affinity_prefers_matching_body_variant(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="parallel_points",
            item_count=3,
            preferred_granularity="body_variant",
            template_id="defense_topnav",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "body_variant/defense_topnav/three_card_summary")

    def test_component_package_can_be_selected_as_asset_granularity(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="parallel_points",
            item_count=3,
            preferred_granularity="component_package",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "component_package/three_card_summary")

    def test_evidence_type_and_complexity_help_rank_component_packages(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="supporting_points",
            item_count=3,
            evidence_type="text_evidence",
            editable_target="evidence_items",
            visual_complexity="high",
            preferred_granularity="component_package",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["query"]["evidence_type"], "text_evidence")
        self.assertEqual(result["matches"][0]["asset_id"], "component_package/evidence_stack")
        self.assertIn("evidence type match", result["matches"][0]["reason"])

    def test_recent_asset_reuse_is_penalized_for_content_arrangement(self):
        from scripts.component_selector import select_components

        registry = {
            "assets": [
                {
                    "asset_id": "component/a",
                    "granularity": "component_package",
                    "render_backend": "component_package",
                    "selection": {"content_shapes": ["parallel_points"], "item_count_min": 3, "item_count_max": 3},
                },
                {
                    "asset_id": "component/b",
                    "granularity": "component_package",
                    "render_backend": "component_package",
                    "selection": {"content_shapes": ["parallel_points"], "item_count_min": 3, "item_count_max": 3},
                },
            ]
        }
        result = select_components(
            content_shape="parallel_points",
            item_count=3,
            recent_asset_ids=["component/a"],
            registry=registry,
        )

        self.assertEqual(result["matches"][0]["asset_id"], "component/b")
        self.assertIn("recent asset reuse penalty", result["matches"][1]["reason"])


if __name__ == "__main__":
    unittest.main()
