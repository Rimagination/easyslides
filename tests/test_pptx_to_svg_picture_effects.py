import base64
import unittest
from io import BytesIO
from xml.etree import ElementTree as ET

from PIL import Image

from scripts.pptx_to_svg.emu_units import Xfrm
from scripts.pptx_to_svg.pic_to_svg import convert_blip_fill


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNoaGgAAAMEAYFL09IQAAAAAElFTkSuQmCC"
)


class DummySlidePart:
    path = "ppt/slides/slide1.xml"

    def resolve_rel(self, rid):
        return "../media/image1.png" if rid == "rId1" else None


class DummyPackage:
    def read_media(self, target):
        return PNG_1X1 if target == "../media/image1.png" else None

    def media_filename(self, target):
        return "image1.png"


class PptxToSvgPictureEffectsTests(unittest.TestCase):
    def test_alpha_mod_fix_becomes_svg_image_opacity(self):
        blip_fill = ET.fromstring(
            f"""<p:blipFill xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
    xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <a:blip r:embed="rId1">
    <a:alphaModFix amt="22000"/>
  </a:blip>
  <a:stretch><a:fillRect/></a:stretch>
</p:blipFill>"""
        )

        result = convert_blip_fill(
            blip_fill,
            Xfrm(x=10, y=20, w=300, h=200),
            DummySlidePart(),
            DummyPackage(),
        )

        self.assertIn('opacity="0.22"', result.svg)
        self.assertIn('href="../assets/image1.png"', result.svg)
        self.assertEqual(result.media["image1.png"], PNG_1X1)

    def test_duotone_effect_is_baked_into_extracted_image(self):
        blip_fill = ET.fromstring(
            f"""<p:blipFill xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
    xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <a:blip r:embed="rId1">
    <a:duotone>
      <a:srgbClr val="000000"/>
      <a:srgbClr val="BF4BE7"/>
    </a:duotone>
  </a:blip>
  <a:stretch><a:fillRect/></a:stretch>
</p:blipFill>"""
        )

        result = convert_blip_fill(
            blip_fill,
            Xfrm(x=10, y=20, w=300, h=200),
            DummySlidePart(),
            DummyPackage(),
        )

        filename, data = next(iter(result.media.items()))
        pixel = Image.open(BytesIO(data)).convert("RGB").getpixel((0, 0))

        self.assertIn("_fx_", filename)
        self.assertNotEqual(data, PNG_1X1)
        self.assertGreater(pixel[2], pixel[1])
        self.assertGreater(pixel[0], pixel[1])


if __name__ == "__main__":
    unittest.main()
