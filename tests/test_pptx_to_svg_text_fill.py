import unittest
from xml.etree import ElementTree as ET

from scripts.pptx_to_svg.txbody_to_svg import _build_run


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class PptxToSvgTextFillTests(unittest.TestCase):
    def test_gradient_text_fill_uses_first_resolved_stop_instead_of_default_black(self):
        rpr = ET.fromstring(
            f"""<a:rPr xmlns:a="{A_NS}" sz="3600">
  <a:gradFill>
    <a:gsLst>
      <a:gs pos="0"><a:srgbClr val="EBA967"/></a:gs>
      <a:gs pos="100000"><a:srgbClr val="FBECDD"/></a:gs>
    </a:gsLst>
    <a:lin ang="0"/>
  </a:gradFill>
</a:rPr>"""
        )

        run = _build_run("Title", rpr, None, None, {}, default_fill="#000000")

        self.assertEqual(run.fill, "#EBA967")
        self.assertEqual(run.fill_opacity, 1.0)


if __name__ == "__main__":
    unittest.main()
