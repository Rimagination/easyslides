import unittest
from xml.etree import ElementTree as ET

from scripts.pptx_to_svg.emu_units import Xfrm
from scripts.pptx_to_svg.txbody_to_svg import convert_txbody


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class PptxToSvgTextboxMetadataTests(unittest.TestCase):
    def test_single_paragraph_text_preserves_source_textbox_and_vertical_anchor(self):
        tx_body = ET.fromstring(
            f"""<p:txBody xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
    xmlns:a="{A_NS}">
  <a:bodyPr lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr" wrap="square"/>
  <a:lstStyle/>
  <a:p>
    <a:pPr algn="ctr"/>
    <a:r><a:rPr sz="1800"/><a:t>Badge</a:t></a:r>
  </a:p>
</p:txBody>"""
        )

        result = convert_txbody(tx_body, Xfrm(x=10, y=20, w=120, h=44), None)

        self.assertIn('data-pptx-textbox="true"', result.svg)
        self.assertIn('data-pptx-box-x="10"', result.svg)
        self.assertIn('data-pptx-box-y="20"', result.svg)
        self.assertIn('data-pptx-box-w="120"', result.svg)
        self.assertIn('data-pptx-box-h="44"', result.svg)
        self.assertIn('data-pptx-valign="middle"', result.svg)


if __name__ == "__main__":
    unittest.main()
