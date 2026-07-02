import tempfile
import unittest
from pathlib import Path

from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes


class SvgToPptxGroupTransformTests(unittest.TestCase):
    def test_rotate_180_group_preserves_drawingml_rotation(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<g transform="rotate(180 1157.6 644.18)">
  <path d="M 1033.84 571 L 1281.35 571 L 1033.84 713.28 Z" fill="#751497"/>
  <path d="M 1033.84 568.36 L 1281.35 568.36 L 1033.84 690.86 Z" fill="#751497"/>
</g>
</svg>"""

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rotate_group.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertIn('rot="10800000"', slide_xml)


if __name__ == "__main__":
    unittest.main()
