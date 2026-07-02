import tempfile
import unittest
from pathlib import Path

from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes


PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGP4"
    "DwABAQEAGP+J8QAAAABJRU5ErkJggg=="
)


class SvgToPptxImageEffectsTests(unittest.TestCase):
    def test_svg_image_opacity_exports_as_blip_alpha_mod_fix(self):
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<image href="{PNG_DATA_URI}" x="0" y="0" width="1280" height="720" opacity="0.22"/>
</svg>"""

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image_opacity.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertIn('<a:alphaModFix amt="22000"/>', slide_xml)

    def test_cropped_nested_svg_opacity_exports_as_blip_alpha_mod_fix(self):
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<svg x="0" y="0" width="1280" height="720" viewBox="0.2 0 0.8 0.8" opacity="0.22" preserveAspectRatio="none">
  <image href="{PNG_DATA_URI}" x="0" y="0" width="1" height="1" preserveAspectRatio="none"/>
</svg>
</svg>"""

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cropped_image_opacity.svg"
            path.write_text(svg, encoding="utf-8")
            slide_xml, _, _, _ = convert_svg_to_slide_shapes(path)

        self.assertIn('<a:alphaModFix amt="22000"/>', slide_xml)
        self.assertIn('<a:srcRect l="20000" t="0" r="0" b="20000"/>', slide_xml)


if __name__ == "__main__":
    unittest.main()
