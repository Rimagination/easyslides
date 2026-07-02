import json
import tempfile
import unittest
from pathlib import Path


class CardLibraryTests(unittest.TestCase):
    def test_library_declares_thirteen_styles(self):
        from scripts.card_library import count_card_styles, load_card_library

        library = load_card_library()

        self.assertEqual(library["schema_version"], "easyslides.card_library.v1")
        self.assertEqual(count_card_styles(library), 13)
        self.assertEqual(library["style_count"], 13)

    def test_query_finds_three_card_summary_for_parallel_points(self):
        from scripts.card_library import load_card_library, select_cards

        matches = select_cards(
            content_shape="parallel_points",
            item_count=3,
            library=load_card_library(),
        )

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["card_id"], "three_card_summary")

    def test_payload_within_capacity_passes(self):
        from scripts.card_library import load_card_library, validate_card_payload

        payload = {
            "items": [
                {"title": "机制清晰", "body": "变量之间存在稳定路径，适合用图示表达主链路。"},
                {"title": "证据充分", "body": "多源数据给出一致方向，局部差异作为补充说明。"},
                {"title": "应用可迁移", "body": "指标定义简单，后续可复用到相邻区域。"},
            ]
        }

        result = validate_card_payload("three_card_summary", payload, load_card_library())

        self.assertTrue(result["passed"], result)
        self.assertEqual(result["checked_slots"], 6)

    def test_payload_over_capacity_fails(self):
        from scripts.card_library import load_card_library, validate_card_payload

        long_text = "这个说明故意写得很长" * 40
        payload = {
            "items": [
                {"title": "机制清晰", "body": long_text},
                {"title": "证据充分", "body": "短说明"},
                {"title": "应用可迁移", "body": "短说明"},
            ]
        }

        result = validate_card_payload("three_card_summary", payload, load_card_library())

        self.assertFalse(result["passed"])
        self.assertEqual(result["violations"][0]["slot_id"], "body")
        self.assertIn("overflow_action", result["violations"][0])

    def test_preview_export_writes_pptx(self):
        from scripts.card_library import export_preview_pptx, load_card_library

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "card_library_preview.pptx"
            export_preview_pptx(output, load_card_library())

            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 10_000)

    def test_cli_validate_emits_json_result(self):
        from scripts.card_library import main

        payload = {"metric": "42%", "label": "解释度提升"}
        code = main(["validate", "--card-id", "stat_card", "--payload-json", json.dumps(payload, ensure_ascii=False)])

        self.assertEqual(code, 0)

    def test_cli_validate_accepts_payload_file(self):
        from scripts.card_library import main

        payload = {"metric": "42%", "label": "解释度提升"}
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = Path(temp_dir) / "payload.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            code = main(["validate", "--card-id", "stat_card", "--payload-file", str(payload_path)])

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
