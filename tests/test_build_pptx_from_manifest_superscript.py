import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = (
    ROOT
    / "tmp"
    / "ppt_skill_compare"
    / "image-to-editable-ppt-skill"
    / "skills"
    / "image-to-editable-ppt"
    / "cli"
    / "editppt"
    / "runtime"
    / "build_pptx_from_manifest.py"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("editppt_build_pptx_from_manifest", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BuildPptxSuperscriptTests(unittest.TestCase):
    def test_caret_exponent_becomes_native_superscript_runs(self):
        builder = load_builder()

        runs = builder.caret_superscript_runs("10^-1", 12)

        self.assertEqual(
            runs,
            [
                {"text": "10"},
                {"text": "-1", "baseline": 30000, "font_size": 7.8},
            ],
        )

    def test_write_pptx_emits_drawingml_baseline_for_caret_exponent(self):
        builder = load_builder()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            pptx_path = root / "out.pptx"
            manifest = {
                "slide": {"width": 13.333, "height": 7.5, "background": "#FFFFFF"},
                "source": {"width_px": 1600, "height_px": 900},
                "text_boxes": [
                    {
                        "text": "10^-1",
                        "box_px": [100, 100, 80, 30],
                        "font": "Arial",
                        "font_size": 12,
                        "color": "#000000",
                        "implementation": "native_text",
                    }
                ],
            }
            manifest_path.write_text("{}", encoding="utf-8")

            builder.write_pptx(manifest, pptx_path, manifest_path)
            with zipfile.ZipFile(pptx_path) as archive:
                slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")

        self.assertIn('baseline="30000"', slide_xml)
        self.assertIn("<a:t>10</a:t>", slide_xml)
        self.assertIn("<a:t>-1</a:t>", slide_xml)
        self.assertNotIn("10^-1", slide_xml)


if __name__ == "__main__":
    unittest.main()
