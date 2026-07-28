import tempfile
import unittest
from pathlib import Path

from PIL import Image


class CrossRendererVisualRegressionTests(unittest.TestCase):
    def test_two_identical_backend_outputs_pass(self):
        from scripts.cross_renderer_visual_regression import run_cross_renderer_visual_regression

        def renderer(_pptx, output, **kwargs):
            output = Path(output)
            output.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40, 30), "white").save(output / "slide_001.png")
            return {"status": "pass", "backend": kwargs["renderer_backend"]}

        with tempfile.TemporaryDirectory() as temp_dir:
            pptx = Path(temp_dir) / "deck.pptx"
            pptx.write_bytes(b"pptx")
            report = run_cross_renderer_visual_regression(pptx, Path(temp_dir) / "out", renderer=renderer)

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["comparison"]["status"], "pass")

    def test_missing_second_backend_requires_review(self):
        from scripts.cross_renderer_visual_regression import run_cross_renderer_visual_regression

        def renderer(_pptx, output, **kwargs):
            if kwargs["renderer_backend"] == "soffice":
                raise FileNotFoundError("LibreOffice unavailable")
            output = Path(output)
            output.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40, 30), "white").save(output / "slide_001.png")
            return {"status": "pass"}

        with tempfile.TemporaryDirectory() as temp_dir:
            pptx = Path(temp_dir) / "deck.pptx"
            pptx.write_bytes(b"pptx")
            report = run_cross_renderer_visual_regression(pptx, Path(temp_dir) / "out", renderer=renderer)

        self.assertEqual(report["status"], "review_required", report)


if __name__ == "__main__":
    unittest.main()
