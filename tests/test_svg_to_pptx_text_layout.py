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

    def test_explicit_table_exports_as_native_graphic_frame_with_merges(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<g id="comparison-table" data-pptx-table="true" data-pptx-table-x="100" data-pptx-table-y="120" data-pptx-table-w="500" data-pptx-table-h="140" data-pptx-table-rows="2" data-pptx-table-cols="2" data-pptx-table-col-widths="200 300" data-pptx-table-row-heights="60 80">
  <g data-pptx-table-cell="true" data-pptx-table-row="1" data-pptx-table-col="1" data-pptx-table-row-span="2" data-pptx-table-align="center">
    <rect x="100" y="120" width="200" height="140" fill="#E4F1FC" stroke="#B8D8ED" stroke-width="1"/>
    <text x="150" y="190" data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="120" data-pptx-box-w="200" data-pptx-box-h="140" data-pptx-valign="middle" font-family="Arial, sans-serif" font-size="20" fill="#0869C0">A</text>
  </g>
  <g data-pptx-table-cell="true" data-pptx-table-row="1" data-pptx-table-col="2">
    <rect x="300" y="120" width="300" height="60" fill="#FFFFFF" stroke="#B8D8ED" stroke-width="1"/>
    <text x="310" y="150" data-pptx-textbox="true" data-pptx-box-x="300" data-pptx-box-y="120" data-pptx-box-w="300" data-pptx-box-h="60" data-pptx-valign="middle" font-family="Arial, sans-serif" font-size="20" fill="#182437">B</text>
  </g>
  <g data-pptx-table-cell="true" data-pptx-table-row="2" data-pptx-table-col="2">
    <rect x="300" y="180" width="300" height="80" fill="#FFFFFF" stroke="#B8D8ED" stroke-width="1"/>
    <text x="310" y="210" data-pptx-textbox="true" data-pptx-box-x="300" data-pptx-box-y="180" data-pptx-box-w="300" data-pptx-box-h="80" data-pptx-valign="middle" font-family="Arial, sans-serif" font-size="20" fill="#182437">C</text>
  </g>
</g>
</svg>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertEqual(slide_xml.count("<p:graphicFrame>"), 1)
        self.assertIn('uri="http://schemas.openxmlformats.org/drawingml/2006/table"', slide_xml)
        self.assertIn('<a:gridCol w="1905000"/>', slide_xml)
        self.assertIn('<a:gridCol w="2857500"/>', slide_xml)
        self.assertIn('<a:tc><a:txBody>', slide_xml)
        self.assertNotIn('<a:tc><p:txBody>', slide_xml)
        self.assertIn('<a:tcPr anchor="ctr"', slide_xml)
        self.assertIn('rowSpan="2"', slide_xml)
        self.assertIn('vMerge="1"', slide_xml)
        self.assertIn('<a:t>A</a:t>', slide_xml)


if __name__ == "__main__":
    unittest.main()
