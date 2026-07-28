import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class VisualReviewTests(unittest.TestCase):
    def test_build_review_package_from_prerendered_pngs(self):
        from scripts.visual_review import build_review_package

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rendered = tmp_path / "rendered"
            rendered.mkdir()
            Image.new("RGB", (320, 180), "#2454A6").save(rendered / "slide_001.png")
            Image.new("RGB", (320, 180), "#E9B44C").save(rendered / "slide_002.png")

            out = tmp_path / "review"
            manifest = build_review_package(
                tmp_path / "deck.pptx",
                out,
                rendered_dir=rendered,
                skip_render=True,
                title="Demo Review",
            )

            self.assertEqual(manifest["schema_version"], "easyslides.visual_review.v1")
            self.assertEqual(manifest["status"], "needs_review")
            self.assertEqual(manifest["slide_count"], 2)
            self.assertEqual(manifest["slides"][0]["image"], "slides/slide_001.png")
            self.assertTrue((out / "slides" / "slide_001.png").is_file())
            self.assertTrue((out / "contact_sheet.png").is_file())
            self.assertTrue((out / "index.html").is_file())
            self.assertTrue((out / "visual_review.json").is_file())

            saved = json.loads((out / "visual_review.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["title"], "Demo Review")
            self.assertEqual(saved["slides"][0]["checks"], ["readable", "aligned", "complete"])


if __name__ == "__main__":
    unittest.main()
