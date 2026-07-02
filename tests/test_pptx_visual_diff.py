import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class PptxVisualDiffTests(unittest.TestCase):
    def test_compares_rendered_png_dirs_and_writes_report(self):
        from scripts.pptx_visual_diff import compare_render_dirs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            generated = root / "generated"
            out = root / "diff"
            source.mkdir()
            generated.mkdir()

            Image.new("RGB", (16, 9), "#000000").save(source / "slide1.png")
            Image.new("RGB", (16, 9), "#000000").save(generated / "slide1.png")
            Image.new("RGB", (16, 9), "#FFFFFF").save(source / "slide2.png")
            Image.new("RGB", (16, 9), "#FDFDFD").save(generated / "slide2.png")

            report = compare_render_dirs(source, generated, out)
            saved = json.loads((out / "metrics.json").read_text(encoding="utf-8"))

        self.assertEqual(report["slide_count"], 2)
        self.assertEqual(saved["slide_count"], 2)
        self.assertEqual(report["slides"][0]["mae"], 0.0)
        self.assertGreater(report["slides"][1]["mae"], 0.0)
        self.assertTrue(report["contact_sheet"].endswith("visual_diff_contact.png"))


if __name__ == "__main__":
    unittest.main()
