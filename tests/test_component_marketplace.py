import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ComponentMarketplaceTests(unittest.TestCase):
    def test_builtin_marketplace_is_valid_with_no_builtin_pack(self):
        from scripts.component_marketplace import search_marketplace, validate_marketplace

        report = validate_marketplace()
        result = search_marketplace("research", tags=["academic"])

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["matches"], [])


if __name__ == "__main__":
    unittest.main()
