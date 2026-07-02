import contextlib
import io
import json
import unittest

from scripts import page_recipe


class PageRecipeTests(unittest.TestCase):
    def test_registry_loads_page_recipes(self):
        registry = page_recipe.load_page_recipes()

        self.assertGreaterEqual(page_recipe.recipe_count(registry), 8)
        self.assertIn("recipes", registry)

    def test_query_causal_content_prefers_causal_map(self):
        matches = page_recipe.select_page_recipes(content_shape="causal_chain", item_count=4)

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["recipe_id"], "pm_causal_map")

    def test_payload_capacity_validation_fails_for_long_slot(self):
        payload = {
            "title": "机制链路",
            "items": [
                {"node_title": "外部压力", "node_body": "这是一段明显超过卡片槽位容量的长解释文本，应该在进入 SVG 执行前被压缩或拆页"},
                {"node_title": "中介过程", "node_body": "短解释"},
                {"node_title": "系统响应", "node_body": "短解释"},
                {"node_title": "管理结果", "node_body": "短解释"},
            ],
        }

        result = page_recipe.validate_page_payload("pm_causal_map", payload)

        self.assertFalse(result["passed"])
        self.assertTrue(any(v["slot_id"] == "node_body" for v in result["violations"]), result)

    def test_prompt_contains_whole_page_and_slot_gate_contract(self):
        prompt = page_recipe.build_page_prompt("pm_causal_map")

        self.assertIn("whole 1280x720 SVG page", prompt)
        self.assertIn("data-pptx-textbox", prompt)
        self.assertIn("validate_svg_text_slots.py", prompt)

    def test_cli_query_json_is_parseable(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = page_recipe.main(["query", "--content-shape", "causal_chain", "--item-count", "4", "--json"])

        self.assertEqual(code, 0)
        rows = json.loads(stdout.getvalue())
        self.assertEqual(rows[0]["recipe_id"], "pm_causal_map")


if __name__ == "__main__":
    unittest.main()
