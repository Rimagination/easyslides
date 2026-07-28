import unittest


class ChartLibraryTests(unittest.TestCase):
    def test_ppt_master_catalog_is_normalized_into_productized_assets(self):
        from scripts.chart_library import load_chart_library, validate_chart_library

        library = load_chart_library()
        report = validate_chart_library(library)

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(library["chart_count"], 71)
        bar = next(chart for chart in library["charts"] if chart["chart_id"] == "bar_chart")
        self.assertEqual(bar["asset_id"], "chart/bar_chart")
        self.assertEqual(bar["family"], "quantitative")
        self.assertIn("chart", bar["selection"]["content_shapes"])
        self.assertEqual(bar["data_model"], "category_series")
        self.assertEqual(bar["upstream"]["project"], "hugohe3/ppt-master")

    def test_search_uses_selection_rules_as_product_metadata(self):
        from scripts.chart_library import search_charts

        matches = search_charts("trend", limit=10)
        ids = {chart["chart_id"] for chart in matches}

        self.assertIn("line_chart", ids)
        self.assertIn("area_chart", ids)

    def test_chart_payload_requires_a_data_envelope_when_present(self):
        from scripts.chart_library import validate_chart_payload

        invalid = validate_chart_payload("bar_chart", {"title": "No data"})
        valid = validate_chart_payload("bar_chart", {"data": {"categories": ["A"], "series": [1]}})

        self.assertFalse(invalid["passed"])
        self.assertTrue(valid["passed"])


if __name__ == "__main__":
    unittest.main()
