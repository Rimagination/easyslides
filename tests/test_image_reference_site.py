import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_image_reference_site import build, LIBRARY


class ImageReferenceSiteTests(unittest.TestCase):
    def test_public_catalog_contains_only_portable_metadata_and_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            public = build(output)
            source = json.loads((LIBRARY / "registry.json").read_text(encoding="utf-8"))["templates"]
            self.assertEqual([item["id"] for item in public], [item["id"] for item in source])
            for item in public:
                self.assertEqual(set(item), {"id", "name", "style_summary", "slide_count", "version", "image", "preview"})
                for key in ("image", "preview"):
                    self.assertEqual((output / item[key]).stat().st_size, (LIBRARY / item[key]).stat().st_size)
            script = (output / "catalog.js").read_text(encoding="utf-8")
            self.assertNotIn("source_pptx", script)
            self.assertNotIn("previous_image", script)

    def test_rejects_asset_paths_outside_library(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            entry = dict(json.loads((LIBRARY / "registry.json").read_text(encoding="utf-8"))["templates"][0])
            entry["image"] = "../private.png"
            (source / "registry.json").write_text(json.dumps({"templates": [entry]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                build(source / "public", source)


if __name__ == "__main__":
    unittest.main()
