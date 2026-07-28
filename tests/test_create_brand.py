import json
import tempfile
import unittest
from pathlib import Path


class CreateBrandTests(unittest.TestCase):
    def test_builtin_academic_blue_brand_is_registered(self):
        from scripts.create_brand import DEFAULT_BRAND_ROOT, show_brand

        payload = show_brand("academic-blue", DEFAULT_BRAND_ROOT)

        self.assertEqual(payload["schema_version"], "easyslides.brand.v1")
        self.assertEqual(payload["id"], "academic-blue")
        self.assertEqual(payload["palette"]["primary"], "#2454A6")

    def test_create_brand_writes_preset_and_registry(self):
        from scripts.create_brand import create_brand, list_brands, show_brand

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "brands"
            brand_path = create_brand(
                "Lab Brand",
                name="Lab Brand",
                root=root,
                primary="#123456",
                accent="#ABCDEF",
            )

            self.assertEqual(brand_path, root / "lab-brand" / "brand.json")
            payload = json.loads(brand_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "easyslides.brand.v1")
            self.assertEqual(payload["palette"]["primary"], "#123456")
            self.assertEqual(payload["palette"]["accent"], "#ABCDEF")

            registry = json.loads((root / "registry.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["schema_version"], "easyslides.brand_registry.v1")
            self.assertEqual(registry["brands"][0]["id"], "lab-brand")
            self.assertEqual(list_brands(root)[0]["name"], "Lab Brand")
            self.assertEqual(show_brand("Lab Brand", root)["id"], "lab-brand")

    def test_create_brand_rejects_invalid_color(self):
        from scripts.create_brand import create_brand

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                create_brand("bad", root=Path(tmp) / "brands", primary="blue")


if __name__ == "__main__":
    unittest.main()
