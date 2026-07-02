import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TemplateGeometryQaTests(unittest.TestCase):
    def test_pptx_text_visual_box_is_tighter_than_autofit_shape_extents(self):
        from scripts.template_geometry_qa import Box, pptx_visual_text_box

        sp = ET.fromstring(
            """<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:spPr>
    <a:xfrm>
      <a:off x="4599845" y="1848277"/>
      <a:ext cx="744478" cy="812800"/>
    </a:xfrm>
  </p:spPr>
  <p:txBody>
    <a:bodyPr lIns="0" tIns="0" rIns="0" bIns="0"/>
    <a:p>
      <a:pPr algn="ctr"/>
      <a:r><a:rPr sz="4000"/><a:t>01</a:t></a:r>
    </a:p>
  </p:txBody>
</p:sp>"""
        )
        shape_box = Box(x=482.77, y=194.13, width=78.13, height=85.33)

        visual_box = pptx_visual_text_box(sp, shape_box)

        self.assertLess(visual_box.width, shape_box.width)
        self.assertLess(visual_box.height, shape_box.height)
        self.assertGreater(visual_box.x, shape_box.x)
        self.assertLessEqual(visual_box.bottom, 270.76)

    def test_pptx_visual_text_box_does_not_expand_beyond_declared_shape(self):
        from scripts.template_geometry_qa import Box, pptx_visual_text_box

        sp = ET.fromstring(
            """<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:spPr>
    <a:xfrm>
      <a:off x="9800000" y="1200000"/>
      <a:ext cx="1533528" cy="713740"/>
    </a:xfrm>
  </p:spPr>
  <p:txBody>
    <a:bodyPr lIns="0" tIns="0" rIns="0" bIns="0"/>
    <a:p>
      <a:pPr algn="l"/>
      <a:r><a:rPr sz="2000"/><a:t>尖峰神经网络(SNN)的构建</a:t></a:r>
    </a:p>
  </p:txBody>
</p:sp>"""
        )
        shape_box = Box(x=1029.7, y=132.88, width=161.03, height=74.9)

        visual_box = pptx_visual_text_box(sp, shape_box)

        self.assertLessEqual(visual_box.width, shape_box.width)
        self.assertLessEqual(visual_box.height, shape_box.height)
        self.assertLessEqual(visual_box.right, shape_box.right)

    def test_pptx_visual_text_box_uses_vertical_middle_anchor(self):
        from scripts.template_geometry_qa import Box, pptx_visual_text_box

        sp = ET.fromstring(
            """<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:spPr>
    <a:xfrm>
      <a:off x="914400" y="914400"/>
      <a:ext cx="1828800" cy="914400"/>
    </a:xfrm>
  </p:spPr>
  <p:txBody>
    <a:bodyPr lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"/>
    <a:p>
      <a:pPr algn="ctr"/>
      <a:r><a:rPr sz="2000"/><a:t>Unit</a:t></a:r>
    </a:p>
  </p:txBody>
</p:sp>"""
        )
        shape_box = Box(x=96, y=96, width=192, height=96)

        visual_box = pptx_visual_text_box(sp, shape_box)

        self.assertGreater(visual_box.y, shape_box.y)
        self.assertAlmostEqual(visual_box.cy, shape_box.cy, delta=0.01)

    def test_container_assignment_prefers_largest_overlap(self):
        from scripts.template_geometry_qa import Box, best_container_for_text

        containers = [
            ("left", Box(x=0, y=0, width=120, height=100)),
            ("right", Box(x=100, y=0, width=220, height=100)),
        ]
        text_box = Box(x=90, y=20, width=180, height=30)

        assigned = best_container_for_text(containers, text_box)

        self.assertIsNotNone(assigned)
        self.assertEqual(assigned[0], "right")

    def test_container_assignment_prefers_smallest_center_container(self):
        from scripts.template_geometry_qa import Box, best_container_for_text

        containers = [
            ("outer", Box(x=50.95, y=103.72, width=1177.63, height=67.24)),
            ("label", Box(x=51.33, y=103.72, width=131.34, height=67.24)),
        ]
        text_box = Box(x=39.72, y=119.47, width=154.57, height=38.78)

        assigned = best_container_for_text(containers, text_box)

        self.assertIsNotNone(assigned)
        self.assertEqual(assigned[0], "label")

    def test_center_anchored_text_inside_container_passes(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="100" y="100" width="220" height="90" fill="#EEEEEE"/>
  <text x="210" y="150" text-anchor="middle" font-size="24">Centered</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {"id": "card_1", "x": 100, "y": 100, "width": 220, "height": 90}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_container_assignment_requires_text_center_inside_container(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="100" y="100" width="120" height="70" fill="#EEEEEE"/>
  <text x="90" y="140" text-anchor="middle" font-size="24">Edge</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {"id": "card_1", "x": 100, "y": 100, "width": 120, "height": 70}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertNotIn("TEXT-CONTAINER-OVERFLOW", {issue["code"] for issue in report["issues"]})

    def test_text_inside_snug_pill_container_does_not_fail_for_virtual_padding(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="452.37" y="183.48" width="639.57" height="87.28" fill="#FFFFFF"/>
  <text x="521.83" y="239.46" text-anchor="middle" font-size="53.33">01</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {
                                    "id": "pill_1",
                                    "x": 452.37,
                                    "y": 183.48,
                                    "width": 639.57,
                                    "height": 87.28,
                                }
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_compact_control_text_requires_middle_valign(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="100" y="200" width="160" height="44" rx="22" ry="22" fill="#751497"/>
  <text x="180" y="230" text-anchor="middle" data-pptx-textbox="true"
    data-pptx-box-x="120" data-pptx-box-y="205" data-pptx-box-w="120"
    data-pptx-box-h="34" data-pptx-valign="top" font-size="22">Badge</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("CONTROL-TEXT-VERTICAL-MISALIGN", {issue["code"] for issue in report["issues"]})

    def test_compact_control_text_center_lock_passes(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="100" y="200" width="160" height="44" rx="22" ry="22" fill="#751497"/>
  <text x="180" y="230" text-anchor="middle" data-pptx-textbox="true"
    data-pptx-box-x="120" data-pptx-box-y="205" data-pptx-box-w="120"
    data-pptx-box-h="34" data-pptx-valign="middle" font-size="22">Badge</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_rectangular_control_text_requires_vertical_center_alignment(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="100" y="100" width="220" height="48" fill="#751497"/>
  <text x="120" y="122" data-pptx-textbox="true"
    data-pptx-box-x="120" data-pptx-box-y="104" data-pptx-box-w="160"
    data-pptx-box-h="24" data-pptx-valign="top" font-size="20">Unit</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {"id": "unit_badge", "x": 100, "y": 100, "width": 220, "height": 48}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("CONTROL-TEXT-VERTICAL-MISALIGN", {issue["code"] for issue in report["issues"]})

    def test_rectangular_control_text_vertical_center_alignment_passes(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="100" y="100" width="220" height="48" fill="#751497"/>
  <text x="120" y="134" data-pptx-textbox="true"
    data-pptx-box-x="120" data-pptx-box-y="112" data-pptx-box-w="160"
    data-pptx-box-h="24" data-pptx-valign="middle" font-size="20">Unit</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {"id": "unit_badge", "x": 100, "y": 100, "width": 220, "height": 48}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_dark_path_label_text_alignment_is_checked_without_body_overflow(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="50.95" y="103.72" width="1177.63" height="67.24" fill="#FFFFFF" stroke="#751497"/>
  <path d="M 51.33 103.72 L 182.67 103.72 L 182.67 170.96 L 51.33 170.96 Z" fill="#751497"/>
  <text x="39.72" y="146.67" data-pptx-textbox="true"
    data-pptx-box-x="39.72" data-pptx-box-y="119.47"
    data-pptx-box-w="154.57" data-pptx-box-h="38.78"
    data-pptx-valign="top" font-size="32" fill="#FFFFFF">(MFSN)</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {"id": "outer", "x": 50.95, "y": 103.72, "width": 1177.63, "height": 67.24}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        codes = {issue["code"] for issue in report["issues"]}
        self.assertEqual(report["status"], "fail")
        self.assertIn("CONTROL-TEXT-VERTICAL-MISALIGN", codes)
        self.assertNotIn("TEXT-CONTAINER-OVERFLOW", codes)

    def test_small_edge_bleed_from_container_is_not_blocking(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="50" y="100" width="400" height="100" fill="#FFFFFF"/>
  <text x="44" y="140" font-size="20">Edge label</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [
                                {"id": "card_1", "x": 50, "y": 100, "width": 400, "height": 100}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_same_line_tspans_do_not_inflate_text_height(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="80" fill="#751497"/>
  <text x="48" y="53" font-size="48" fill="#FFFFFF"><tspan>01  </tspan><tspan>国家重大需求</tspan></text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [
                                {"id": "top_chrome", "x": 0, "y": 0, "width": 1280, "height": 80, "fill": "#751497"}
                            ],
                            "containers": [],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_multiline_tspans_use_widest_display_line_not_joined_text(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <text x="640" y="250" text-anchor="middle" font-size="30"><tspan>这是一个很长但仍然可以放在画布内的第一行文本内容</tspan><tspan x="640" dy="36">这是一个很长但仍然可以放在画布内的第二行文本内容</tspan></text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [],
                            "containers": [],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        self.assertEqual(report["status"], "pass")

    def test_detects_text_over_protected_region_card_overflow_and_missing_image(self):
        from scripts.template_geometry_qa import validate_template_geometry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            template.mkdir()
            (template / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="220" height="720" fill="#9D1B22"/>
  <rect x="300" y="180" width="160" height="70" fill="#EEEEEE"/>
  <text x="190" y="120" font-size="30" fill="#000000">This text crosses the nav rail</text>
  <text x="310" y="220" font-size="30">This card text is far too long</text>
  <image x="500" y="260" width="200" height="120" href="assets/missing.png"/>
  <text x="500" y="420" font-size="18">image?</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                template / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "template",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [
                        {
                            "id": "01_content",
                            "svg": "01_content.svg",
                            "protected_regions": [
                                {
                                    "id": "left_nav",
                                    "x": 0,
                                    "y": 0,
                                    "width": 220,
                                    "height": 720,
                                    "fill": "#9D1B22",
                                }
                            ],
                            "containers": [
                                {"id": "card_1", "x": 300, "y": 180, "width": 160, "height": 70}
                            ],
                        }
                    ],
                },
            )

            report = validate_template_geometry(template)

        codes = {issue["code"] for issue in report["issues"]}
        self.assertEqual(report["status"], "fail")
        self.assertIn("TEXT-PROTECTED-OVERLAP", codes)
        self.assertIn("TEXT-CONTAINER-OVERFLOW", codes)
        self.assertIn("IMAGE-MISSING-ASSET", codes)
        self.assertIn("IMAGE-MISSING-PLACEHOLDER", codes)


if __name__ == "__main__":
    unittest.main()
