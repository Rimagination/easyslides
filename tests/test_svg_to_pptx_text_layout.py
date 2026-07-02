import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from svg_to_pptx.drawingml_utils import estimate_text_width  # noqa: E402
from svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes  # noqa: E402


class SvgToPptxTextLayoutTests(unittest.TestCase):
    def test_digit_one_keeps_enough_width_for_page_numbers(self):
        font_size = 24

        self.assertGreater(estimate_text_width("11", font_size), font_size)
        self.assertAlmostEqual(
            estimate_text_width("11", font_size),
            estimate_text_width("10", font_size),
        )

    def test_tagged_multiline_text_exports_as_one_textbox(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<text x="100" y="120" data-pptx-textbox="true" data-pptx-box-x="90" data-pptx-box-y="90" data-pptx-box-w="400" data-pptx-box-h="120" font-family="Arial, sans-serif" font-size="24" fill="#000000">
  <tspan>第一行</tspan><tspan x="100" dy="32">第二行</tspan>
</text>
</svg>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "textbox.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertEqual(slide_xml.count("<p:sp>"), 1)
        self.assertEqual(slide_xml.count("<a:p>"), 2)
        self.assertIn("<a:bodyPr wrap=\"square\"", slide_xml)

    def test_tagged_textbox_can_vertically_center_text(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<text x="100" y="120" data-pptx-textbox="true" data-pptx-box-x="90" data-pptx-box-y="90" data-pptx-box-w="400" data-pptx-box-h="120" data-pptx-valign="middle" font-family="Arial, sans-serif" font-size="24" fill="#000000">
  <tspan>居中文字</tspan>
</text>
</svg>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "centered_textbox.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertIn('anchor="ctr"', slide_xml)

    def test_flipped_tagged_textbox_exports_positive_extent(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<g transform="translate(150 100) scale(-1 1) translate(-150 -100)">
  <text x="120" y="120" data-pptx-textbox="true" data-pptx-box-x="120" data-pptx-box-y="90" data-pptx-box-w="80" data-pptx-box-h="40" data-pptx-valign="middle" font-family="Arial, sans-serif" font-size="24" fill="#000000">01-</text>
</g>
</svg>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flipped_textbox.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertIn('flipH="1"', slide_xml)
        self.assertNotIn('cx="-', slide_xml)
        self.assertNotIn('cy="-', slide_xml)


if __name__ == "__main__":
    unittest.main()
