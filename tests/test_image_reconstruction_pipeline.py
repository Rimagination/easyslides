import tempfile
import unittest
from pathlib import Path

from PIL import Image


class ImageReconstructionPipelineTests(unittest.TestCase):
    def test_init_project_creates_canonical_scaffold(self):
        from scripts.image_reconstruction_pipeline import init_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (320, 180), "white").save(source)
            project = root / "image_project"

            report = init_project(project, [source])

            self.assertEqual(report["status"], "initialized")
            self.assertTrue((project / "sources" / "slide_001.png").exists())
            self.assertTrue((project / "analysis" / "_analysis.json").exists())
            self.assertTrue((project / "pages" / "page_001" / "assets" / "split").is_dir())
            self.assertTrue((project / "pptx").is_dir())
            self.assertTrue((project / "reports").is_dir())

    def test_practical_mode_treats_source_diff_as_advisory(self):
        from scripts.image_reconstruction_pipeline import qa_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "image_project"
            rendered = project / "reports" / "rendered_png"
            rendered.mkdir(parents=True)
            source = root / "source.png"
            Image.new("RGB", (320, 180), "white").save(source)
            Image.new("RGB", (320, 180), "black").save(rendered / "slide_001.png")

            report = qa_project(
                project,
                rendered_dir=rendered,
                source_images=[source],
                inventory=project / "analysis" / "missing.json",
                mode="faithful-practical",
            )

            self.assertEqual(report["status"], "pass")
            diff_gate = next(gate for gate in report["gates"] if gate["name"] == "source_render_diff")
            self.assertEqual(diff_gate["status"], "fail")
            self.assertTrue(diff_gate["advisory"])
            self.assertEqual(diff_gate["blocking_count"], 0)
            self.assertGreater(diff_gate["raw_blocking_count"], 0)

    def test_pixel_strict_mode_blocks_on_source_diff(self):
        from scripts.image_reconstruction_pipeline import qa_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "image_project"
            rendered = project / "reports" / "rendered_png"
            rendered.mkdir(parents=True)
            source = root / "source.png"
            Image.new("RGB", (320, 180), "white").save(source)
            Image.new("RGB", (320, 180), "black").save(rendered / "slide_001.png")

            report = qa_project(
                project,
                rendered_dir=rendered,
                source_images=[source],
                inventory=project / "analysis" / "missing.json",
                mode="pixel-strict",
            )

            self.assertEqual(report["status"], "fail")
            diff_gate = next(gate for gate in report["gates"] if gate["name"] == "source_render_diff")
            self.assertFalse(diff_gate["advisory"])
            self.assertGreater(diff_gate["blocking_count"], 0)


if __name__ == "__main__":
    unittest.main()
