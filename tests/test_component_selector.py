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

    def test_academic_general_selects_its_declared_comparison_variant(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="comparison",
            item_count=2,
            preferred_granularity="body_variant",
            template_id="academic_general",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "body_variant/academic_general/comparison_synthesis")

    def test_academic_general_evidence_variant_is_template_affine(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="argument",
            item_count=3,
            preferred_granularity="body_variant",
            template_id="academic_general",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "body_variant/academic_general/evidence_argument")
        self.assertIn("template match", result["matches"][0]["reason"])

    def test_academic_general_selects_process_variant_from_nested_selection(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="process",
            item_count=3,
            preferred_granularity="body_variant",
            template_id="academic_general",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "body_variant/academic_general/process_outcome")

    def test_academic_general_selects_a_local_leaf_component_for_explicit_assembly(self):
        from scripts.component_registry import build_component_registry
        from scripts.component_selector import select_components

        result = select_components(
            content_shape="process",
            item_count=3,
            preferred_granularity="template_component",
            template_id="academic_general",
            registry=build_component_registry(include_template_asset_bank=False),
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["matches"][0]["asset_id"], "component/academic_general/process_step")
        self.assertIn("template match", result["matches"][0]["reason"])

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
