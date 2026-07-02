import math
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class LayoutMetricsTests(unittest.TestCase):
    def test_units_box_transform_and_text_measurement_share_one_api(self):
        from scripts.layout_metrics import (
            Box,
            emu_to_px,
            estimate_text_width_px,
            parse_transform_matrix,
            px_to_emu,
            transform_box,
        )

        self.assertEqual(px_to_emu(1), 9525)
        self.assertAlmostEqual(emu_to_px(9525), 1.0)

        box = Box(10, 20, 100, 40)
        matrix = parse_transform_matrix("translate(5 10) scale(2 1)")
        transformed = transform_box(box, matrix)

        self.assertEqual(transformed, Box(25, 30, 200, 40))
        self.assertGreater(estimate_text_width_px("11", 24), 24)
        self.assertAlmostEqual(
            estimate_text_width_px("11", 24),
            estimate_text_width_px("10", 24),
        )

    def test_svg_text_box_uses_declared_slot_before_heuristics(self):
        from scripts.layout_metrics import Box, measure_svg_text_box

        elem = ET.fromstring(
            """<text x="10" y="50" text-anchor="middle" font-size="24"
  data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="200"
  data-pptx-box-w="300" data-pptx-box-h="40">Declared</text>"""
        )

        self.assertEqual(
            measure_svg_text_box(elem, "Declared"),
            Box(100, 200, 300, 40),
        )

    def test_svg_text_box_estimate_respects_anchor_and_multiline_tspans(self):
        from scripts.layout_metrics import measure_svg_text_box

        elem = ET.fromstring(
            """<text x="640" y="250" text-anchor="middle" font-size="30">
  <tspan>First line</tspan><tspan x="640" dy="36">Second line</tspan>
</text>"""
        )

        box = measure_svg_text_box(elem, "First line Second line")

        self.assertLess(box.x, 640)
        self.assertGreater(box.right, 640)
        self.assertGreaterEqual(box.height, 30 * 1.22 * 2)

    def test_nested_svg_image_wrapper_measures_outer_box(self):
        from scripts.layout_metrics import Box, iter_svg_image_boxes

        root = ET.fromstring(
            """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <svg x="120" y="80" width="300" height="180" viewBox="0.1 0.2 0.8 0.6">
    <image href="assets/photo.png" x="0" y="0" width="1" height="1" preserveAspectRatio="none"/>
  </svg>
</svg>"""
        )

        images = list(iter_svg_image_boxes(root))

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].href, "assets/photo.png")
        self.assertEqual(images[0].box, Box(120, 80, 300, 180))

    def test_root_svg_with_single_image_uses_image_box_not_canvas_box(self):
        from scripts.layout_metrics import Box, iter_svg_image_boxes

        root = ET.fromstring(
            """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <image href="assets/photo.png" x="300" y="200" width="400" height="240"/>
</svg>"""
        )

        images = list(iter_svg_image_boxes(root))

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].box, Box(300, 200, 400, 240))

    def test_transform_box_handles_rotation_as_axis_aligned_bounds(self):
        from scripts.layout_metrics import Box, parse_transform_matrix, transform_box

        box = Box(0, 0, 100, 50)
        rotated = transform_box(box, parse_transform_matrix("rotate(90 0 0)"))

        self.assertTrue(math.isclose(rotated.x, -50, abs_tol=1e-9))
        self.assertTrue(math.isclose(rotated.y, 0, abs_tol=1e-9))
        self.assertTrue(math.isclose(rotated.width, 50, abs_tol=1e-9))
        self.assertTrue(math.isclose(rotated.height, 100, abs_tol=1e-9))

    def test_core_layout_tools_depend_on_shared_metrics_module(self):
        paths = [
            ROOT / "scripts" / "validate_svg_text_slots.py",
            ROOT / "scripts" / "validate_pptx_text_layout.py",
            ROOT / "scripts" / "template_geometry_qa.py",
            ROOT / "scripts" / "svg_to_pptx" / "drawingml_utils.py",
        ]

        for path in paths:
            self.assertIn("layout_metrics", path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
