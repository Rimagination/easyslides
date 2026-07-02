import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_template(root: Path) -> Path:
    template = root / "template"
    (template / "assets").mkdir(parents=True)
    (template / "assets" / "source.png").write_bytes(b"not-a-real-image")
    (template / "01_cover.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  <text x="90" y="150" data-pptx-textbox="true" data-pptx-box-x="90" data-pptx-box-y="104"
    data-pptx-box-w="760" data-pptx-box-h="64" data-pptx-valign="top" font-size="42">Original Source Title</text>
  <rect x="90" y="610" width="160" height="46" rx="23" fill="#751497"/>
  <text x="170" y="640" text-anchor="middle" data-pptx-textbox="true" data-pptx-box-x="105"
    data-pptx-box-y="616" data-pptx-box-w="130" data-pptx-box-h="34" data-pptx-valign="middle"
    font-size="22" fill="#FFFFFF">Original Lab</text>
  <image x="760" y="150" width="360" height="280" href="assets/source.png"/>
</svg>
""",
        encoding="utf-8",
    )
    (template / "02_content.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="60" y="80" width="1100" height="540" fill="#FFFFFF" stroke="#751497"/>
  <text x="100" y="140" data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="98"
    data-pptx-box-w="720" data-pptx-box-h="52" data-pptx-valign="top" font-size="34">Original Problem Statement</text>
  <text x="100" y="220" data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="184"
    data-pptx-box-w="500" data-pptx-box-h="120" data-pptx-valign="top" font-size="24">Original body evidence remains here.</text>
  <image x="720" y="180" width="360" height="280" href="assets/source.png"/>
</svg>
""",
        encoding="utf-8",
    )
    write_json(
        template / "layouts.json",
        {
            "template_id": "fixture",
            "pages": [
                {"id": "01_cover", "svg": "01_cover.svg", "story_role": "cover", "source_slide": 1},
                {"id": "02_content", "svg": "02_content.svg", "story_role": "content", "source_slide": 2},
            ],
        },
    )
    write_json(
        template / "geometry_contract.json",
        {
            "schema_version": "easyslides.template_geometry_contract.v1",
            "template_id": "fixture",
            "canvas": {"width": 1280, "height": 720},
            "pages": [
                {"id": "01_cover", "svg": "01_cover.svg", "protected_regions": [], "containers": []},
                {"id": "02_content", "svg": "02_content.svg", "protected_regions": [], "containers": []},
            ],
        },
    )
    write_json(
        template / "layout_roster.json",
        {
            "template_id": "fixture",
            "layouts": [
                {"page_id": "01_cover", "svg_path": "templates/layouts/fixture/01_cover.svg"},
                {"page_id": "02_content", "svg_path": "templates/layouts/fixture/02_content.svg"},
            ],
        },
    )
    return template


class TemplateMaterialSmokeTestTests(unittest.TestCase):
    def test_smoke_test_replaces_cross_domain_material_and_preserves_geometry_metadata(self):
        from scripts.template_material_smoke_test import run_material_smoke_test

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_template(root)
            target = root / "out"

            report = run_material_smoke_test(
                source,
                target,
                forbidden_keywords=["Original Source", "Original Problem", "Original body"],
                min_text_replacement_ratio=0.75,
            )

            cover_svg = (target / "01_cover.svg").read_text(encoding="utf-8")
            manifest = json.loads((target / "material_smoke_manifest.json").read_text(encoding="utf-8"))
            root_xml = ET.fromstring(cover_svg)
            texts = [node for node in root_xml.iter() if node.tag.rsplit("}", 1)[-1] == "text"]

        self.assertEqual(report["status"], "pass")
        self.assertEqual(manifest["status"], "pass")
        self.assertGreaterEqual(report["text_replaced_count"], 4)
        self.assertGreaterEqual(report["image_replaced_count"], 2)
        self.assertEqual(report["ellipsized_heading_count"], 0)
        self.assertNotIn("Original Source Title", cover_svg)
        self.assertNotIn("...", cover_svg)
        self.assertIn("smoke_heat_map.png", cover_svg)
        self.assertEqual(texts[0].attrib["data-pptx-box-w"], "760")
        self.assertEqual(texts[0].attrib["data-pptx-box-h"], "64")
        self.assertEqual(texts[1].attrib["data-pptx-valign"], "middle")

    def test_selected_pages_filter_page_sidecars(self):
        from scripts.template_material_smoke_test import run_material_smoke_test

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_template(root)
            target = root / "out"

            report = run_material_smoke_test(source, target, selected_pages=["02_content.svg"])
            geometry = json.loads((target / "geometry_contract.json").read_text(encoding="utf-8"))
            roster = json.loads((target / "layout_roster.json").read_text(encoding="utf-8"))

        self.assertEqual(report["selected_pages"], ["02_content.svg"])
        self.assertEqual([page["id"] for page in geometry["pages"]], ["02_content"])
        self.assertEqual([page["page_id"] for page in roster["layouts"]], ["02_content"])

    def test_toc_chrome_and_number_markers_are_not_material_slots(self):
        from scripts.template_material_smoke_test import run_material_smoke_test

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "template"
            source.mkdir()
            (source / "01_toc.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <text x="716" y="126" data-pptx-textbox="true" data-pptx-box-x="707" data-pptx-box-y="60" data-pptx-box-w="170" data-pptx-box-h="96" data-pptx-valign="top" font-size="72">目录</text>
  <text x="-314" y="385" data-pptx-textbox="true" data-pptx-box-x="-324" data-pptx-box-y="290" data-pptx-box-w="720" data-pptx-box-h="138" data-pptx-valign="top" font-size="106" fill-opacity="0.5">CONTENTS</text>
  <text x="728" y="243" data-pptx-textbox="true" data-pptx-box-x="728" data-pptx-box-y="202" data-pptx-box-w="90" data-pptx-box-h="52" data-pptx-valign="middle" font-size="42">01-</text>
  <text x="825" y="216" data-pptx-textbox="true" data-pptx-box-x="815" data-pptx-box-y="184" data-pptx-box-w="266" data-pptx-box-h="48" data-pptx-valign="middle" font-size="32">添加章节标题</text>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                source / "layouts.json",
                {
                    "template_id": "chrome_fixture",
                    "pages": [
                        {"id": "01_toc", "svg": "01_toc.svg", "story_role": "toc", "source_slide": 1},
                    ],
                },
            )
            write_json(
                source / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "chrome_fixture",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [{"id": "01_toc", "svg": "01_toc.svg", "protected_regions": [], "containers": []}],
                },
            )
            write_json(
                source / "layout_roster.json",
                {"template_id": "chrome_fixture", "layouts": [{"page_id": "01_toc", "svg_path": "01_toc.svg"}]},
            )

            target = root / "out"
            report = run_material_smoke_test(source, target, min_text_replacement_ratio=0.75)
            svg = (target / "01_toc.svg").read_text(encoding="utf-8")

        self.assertEqual(report["status"], "pass", report["failures"])
        self.assertIn("目录", svg)
        self.assertIn("CONTENTS", svg)
        self.assertIn("01-", svg)
        self.assertNotIn("38.6", svg)
        self.assertNotIn("Ba...", svg)

    def test_flipped_images_are_not_treated_as_safe_material_slots(self):
        from scripts.template_material_smoke_test import run_material_smoke_test

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "template"
            (source / "assets").mkdir(parents=True)
            (source / "assets" / "source.png").write_bytes(b"not-a-real-image")
            (source / "01_content.svg").write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <text x="100" y="140" data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="98" data-pptx-box-w="720" data-pptx-box-h="52" font-size="34">Original Problem Statement</text>
  <g transform="translate(500 300) scale(-1 1) translate(-500 -300)">
    <image x="300" y="160" width="400" height="280" href="assets/source.png"/>
  </g>
</svg>
""",
                encoding="utf-8",
            )
            write_json(
                source / "layouts.json",
                {
                    "template_id": "flipped_image_fixture",
                    "pages": [
                        {"id": "01_content", "svg": "01_content.svg", "story_role": "content", "source_slide": 1},
                    ],
                },
            )
            write_json(
                source / "geometry_contract.json",
                {
                    "schema_version": "easyslides.template_geometry_contract.v1",
                    "template_id": "flipped_image_fixture",
                    "canvas": {"width": 1280, "height": 720},
                    "pages": [{"id": "01_content", "svg": "01_content.svg", "protected_regions": [], "containers": []}],
                },
            )
            write_json(
                source / "layout_roster.json",
                {"template_id": "flipped_image_fixture", "layouts": [{"page_id": "01_content", "svg_path": "01_content.svg"}]},
            )

            target = root / "out"
            report = run_material_smoke_test(source, target)
            svg = (target / "01_content.svg").read_text(encoding="utf-8")

        self.assertEqual(report["status"], "pass", report["failures"])
        self.assertEqual(report["image_replaced_count"], 0)
        self.assertIn("assets/source.png", svg)
        self.assertNotIn("smoke_heat_map.png", svg)

    def test_forbidden_replacement_term_fails(self):
        from scripts.template_material_smoke_test import run_material_smoke_test

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_template(root)
            target = root / "out"

            report = run_material_smoke_test(source, target, forbidden_keywords=["Urban Heat"])

        self.assertEqual(report["status"], "fail")
        self.assertIn("forbidden_source_terms_remaining", report["failures"])


if __name__ == "__main__":
    unittest.main()
