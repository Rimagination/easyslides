import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def write_png(path: Path) -> None:
    path.write_bytes(PNG_1X1)


class ValidateImageReconstructionPptxTests(unittest.TestCase):
    def test_source_lines_override_ocr_fragments_and_allow_rich_runs(self):
        from scripts.validate_image_reconstruction_pptx import validate_image_reconstruction_pptx
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.pptx"
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            fragments = ["Aim 1:", "Source title"]
            boxes = [slide.shapes.add_textbox(0, 0, Inches(3), Inches(1)) for _ in fragments]
            for box, text in zip(boxes, fragments):
                box.text = text
            inventory = {"slides": [{"elements": [{"layer": "C", "text": text} for text in fragments],
                                     "source_text_lines": ["Aim 1: Source title"]}]}
            prs.save(path)
            report = validate_image_reconstruction_pptx(path, inventory=inventory)
            self.assertTrue(any(issue["code"] == "PPTX-TEXT-COVERAGE" for issue in report["issues"]))
            for box in boxes:
                box._element.getparent().remove(box._element)
            paragraph = slide.shapes.add_textbox(0, 0, Inches(5), Inches(1)).text_frame.paragraphs[0]
            for text, bold in zip(fragments, (False, True)):
                run = paragraph.add_run()
                run.text = text + " "
                run.font.bold = bold
            prs.save(path)
            self.assertEqual(validate_image_reconstruction_pptx(path, inventory=inventory)["status"], "pass")
            # Independent table cells remain separate logical lines, even on the same baseline.
            slide.shapes.add_table(1, 2, 0, Inches(2), Inches(4), Inches(1)).table.cell(0, 0).text = "Left"
            slide.shapes[-1].table.cell(0, 1).text = "Right"
            inventory["slides"][0]["source_text_lines"].extend(["Left", "Right"])
            prs.save(path)
            self.assertEqual(validate_image_reconstruction_pptx(path, inventory=inventory)["status"], "pass")

    def test_tiled_rasters_do_not_pass_editability(self):
        from scripts.validate_image_reconstruction_pptx import validate_image_reconstruction_pptx
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_png(root / "pixel.png")
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            for x in (0, prs.slide_width // 2):
                slide.shapes.add_picture(str(root / "pixel.png"), x, 0, width=prs.slide_width // 2, height=prs.slide_height)
            prs.save(root / "out.pptx")
            self.assertEqual(validate_image_reconstruction_pptx(root / "out.pptx")["status"], "fail")

    def test_partial_background_allowed_and_vector_pictures_rejected(self):
        from scripts.validate_image_reconstruction_pptx import validate_image_reconstruction_pptx
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_png(root / "pixel.png")
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_picture(str(root / "pixel.png"), 0, 0, width=prs.slide_width, height=prs.slide_height).name = "source_background"
            slide.shapes.add_textbox(0, 0, Inches(2), Inches(1)).text = "Title"
            prs.save(root / "out.pptx")
            self.assertEqual(validate_image_reconstruction_pptx(root / "out.pptx", production_scheme="image_partial_rebuild", reconstruction_mode="full_vector")["status"], "pass")
            self.assertEqual(validate_image_reconstruction_pptx(root / "out.pptx", reconstruction_mode="full_vector")["status"], "fail")

    def test_table_text_counts_and_fragmented_source_line_blocks(self):
        from scripts.validate_image_reconstruction_pptx import validate_image_reconstruction_pptx
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.pptx"
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_table(1, 1, 0, 0, Inches(3), Inches(1)).table.cell(0, 0).text = "Native table text"
            prs.save(path)
            inventory = {"slides": [{"elements": [{"layer": "C", "text": "Native table text"}]}]}
            self.assertEqual(validate_image_reconstruction_pptx(path, inventory=inventory)["status"], "pass")
            inventory["slides"][0]["elements"][0]["text"] = "A complete line"
            for text in ("A complete", "line"):
                slide.shapes.add_textbox(0, 0, Inches(2), Inches(1)).text = text
            prs.save(path)
            self.assertEqual(validate_image_reconstruction_pptx(path, inventory=inventory)["status"], "fail")

    def test_blocks_single_full_slide_picture(self):
        from scripts.validate_image_reconstruction_pptx import validate_image_reconstruction_pptx

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "pixel.png"
            pptx = root / "single_picture.pptx"
            write_png(image)

            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_picture(str(image), 0, 0, width=prs.slide_width, height=prs.slide_height)
            prs.save(pptx)

            report = validate_image_reconstruction_pptx(pptx)

        self.assertEqual(report["status"], "fail")
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("PPTX-FULL-SLIDE-PICTURE", codes)
        self.assertIn("PPTX-SINGLE-PICTURE-ONLY", codes)

    def test_text_and_native_shape_pass_without_blocking_issues(self):
        from scripts.validate_image_reconstruction_pptx import validate_image_reconstruction_pptx

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "pixel.png"
            pptx = root / "editable.pptx"
            write_png(image)

            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            textbox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(3), Inches(0.5))
            run = textbox.text_frame.paragraphs[0].add_run()
            run.text = "Editable title"
            run.font.size = Pt(24)
            slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1), Inches(3), Inches(2))
            slide.shapes.add_picture(str(image), Inches(4), Inches(1), width=Inches(1), height=Inches(1))
            prs.save(pptx)

            report = validate_image_reconstruction_pptx(pptx)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)
        self.assertEqual(report["slides"][0]["text_frame_count"], 1)
        self.assertEqual(report["slides"][0]["native_shape_count"], 1)

    def test_cli_help_is_printable(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_image_reconstruction_pptx.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validate PPTX structural editability", result.stdout)

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "pixel.png"
            pptx = root / "single_picture.pptx"
            report_path = root / "report.json"
            write_png(image)

            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_picture(str(image), 0, 0, width=prs.slide_width, height=prs.slide_height)
            prs.save(pptx)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_image_reconstruction_pptx.py",
                    str(pptx),
                    "--report",
                    str(report_path),
                    "--quiet",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "easyslides.image_reconstruction_pptx_report.v1")


if __name__ == "__main__":
    unittest.main()
