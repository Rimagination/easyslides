import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ComponentMarketplaceTests(unittest.TestCase):
    def test_builtin_marketplace_is_valid_and_searchable(self):
        from scripts.component_marketplace import search_marketplace, validate_marketplace

        report = validate_marketplace()
        result = search_marketplace("research", tags=["academic"])

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["matches"][0]["pack_id"], "research-core")

    def test_builtin_pack_can_be_installed_from_marketplace(self):
        from scripts.component_marketplace import install_marketplace_pack

        with tempfile.TemporaryDirectory() as temp_dir:
            report = install_marketplace_pack("research-core", target=Path(temp_dir) / "installed")

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["installation"]["status"], "pass", report)


if __name__ == "__main__":
    unittest.main()
