import contextlib
import io
import json
import unittest


class CardRecipeTests(unittest.TestCase):
    def test_visual_recipe_registry_loads(self):
        from scripts.card_recipe import load_visual_recipes, recipe_count

        registry = load_visual_recipes()

        self.assertEqual(registry["schema_version"], "easyslides.card_visual_recipes.v1")
        self.assertGreaterEqual(recipe_count(registry), 9)

    def test_query_finds_flow_strip_for_sequence(self):
        from scripts.card_recipe import load_visual_recipes, select_recipes

        matches = select_recipes(content_shape="sequence", item_count=3, registry=load_visual_recipes())

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["recipe_id"], "pm_flow_strip")

    def test_payload_capacity_passes_and_fails(self):
        from scripts.card_recipe import load_visual_recipes, validate_recipe_payload

        registry = load_visual_recipes()
        good = {
            "title": "文本层面",
            "items": [
                {"label": "鸠摩罗什译本", "detail": "后秦弘始年间译出"},
                {"label": "三十二分之首", "detail": "用于组织经典结构"},
                {"label": "六种成就具足", "detail": "信闻时主处众"},
            ],
        }
        bad = {
            "title": "文本层面",
            "items": [
                {"label": "鸠摩罗什译本", "detail": "这段说明故意写得很长" * 30},
            ],
        }

        self.assertTrue(validate_recipe_payload("pm_text_panel_with_header", good, registry)["passed"])
        self.assertFalse(validate_recipe_payload("pm_text_panel_with_header", bad, registry)["passed"])

    def test_prompt_contains_svg_contract(self):
        from scripts.card_recipe import build_recipe_prompt, load_visual_recipes

        prompt = build_recipe_prompt("pm_text_panel_with_header", load_visual_recipes())

        self.assertIn("<g id=", prompt)
        self.assertIn("All elements must stay inside", prompt)
        self.assertIn("pm_text_panel_with_header", prompt)

    def test_cli_query_json_is_parseable(self):
        from scripts.card_recipe import main

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["query", "--content-shape", "sequence", "--item-count", "3", "--json"])

        self.assertEqual(code, 0)
        rows = json.loads(stdout.getvalue())
        self.assertEqual(rows[0]["recipe_id"], "pm_flow_strip")


if __name__ == "__main__":
    unittest.main()
