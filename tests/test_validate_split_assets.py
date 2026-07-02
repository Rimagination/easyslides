import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


class ValidateSplitAssetsTests(unittest.TestCase):
    def _write_circle(self, path: Path, *, clipped: bool) -> None:
        image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        bbox = (0, 0, 31, 31) if clipped else (4, 4, 27, 27)
        draw.ellipse(bbox, outline=(0, 0, 0, 255), width=3)
        image.save(path)

    def test_closed_circle_touching_edge_fails(self):
        from scripts.validate_split_assets import validate_split_assets

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            asset = root / "ecosystem_circle.png"
            manifest = root / "split_manifest.json"
            self._write_circle(asset, clipped=True)
            manifest.write_text(
                json.dumps({"assets": [{"name": "ecosystem_circle", "path": str(asset)}]}),
                encoding="utf-8",
            )

            report = validate_split_assets(manifest, min_transparent_margin_px=2)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["blocking_count"], 1)
        self.assertEqual(report["issues"][0]["code"], "ASSET-CLOSED-SHAPE-CLIPPED")

    def test_padded_closed_circle_passes(self):
        from scripts.validate_split_assets import validate_split_assets

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            asset = root / "ecosystem_circle.png"
            manifest = root / "split_manifest.json"
            self._write_circle(asset, clipped=False)
            manifest.write_text(
                json.dumps({"assets": [{"name": "ecosystem_circle", "path": str(asset)}]}),
                encoding="utf-8",
            )

            report = validate_split_assets(manifest, min_transparent_margin_px=2)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)

    def test_preserved_source_frame_can_touch_edges(self):
        from scripts.validate_split_assets import validate_split_assets

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            asset = root / "source_frame.png"
            manifest = root / "split_manifest.json"
            Image.new("RGBA", (32, 24), (40, 120, 180, 255)).save(asset)
            manifest.write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "name": "large_mangrove",
                                "path": str(asset),
                                "source_type": "preserve_source_frame",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = validate_split_assets(manifest, min_transparent_margin_px=2)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["warning_count"], 0)


if __name__ == "__main__":
    unittest.main()
