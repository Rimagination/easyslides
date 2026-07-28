import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.template_text_fit_check import validate_template_text_fit  # noqa: E402


ACTIVE_ACADEMIC_TEMPLATES = (
    "academic_general",
    "academic_scqa",
    "defense_leftnav",
    "defense_topnav",
    "literature_minimal",
)

BOX_ATTRS = (
    "data-pptx-box-x",
    "data-pptx-box-y",
    "data-pptx-box-w",
    "data-pptx-box-h",
)


class ActiveAcademicTemplateTextFitTests(unittest.TestCase):
    def test_active_academic_templates_have_text_fit_contracts(self):
        failures = {}
        for template_id in ACTIVE_ACADEMIC_TEMPLATES:
            report = validate_template_text_fit(ROOT / "templates" / "layouts" / template_id)
            if report["status"] != "pass":
                failures[template_id] = report["issues"]

        self.assertEqual(failures, {})

    def test_placeholder_text_elements_have_pptx_box_bounds(self):
        failures = []
        layouts_root = ROOT / "templates" / "layouts"
        for template_id in ACTIVE_ACADEMIC_TEMPLATES:
            for svg_path in sorted((layouts_root / template_id).glob("*.svg")):
                root = ET.parse(svg_path).getroot()
                for elem in root.iter():
                    if elem.tag.split("}", 1)[-1] != "text":
                        continue
                    text = "".join(elem.itertext())
                    if "{{" not in text:
                        continue
                    missing = [attr for attr in BOX_ATTRS if elem.get(attr) is None]
                    if missing:
                        failures.append(
                            f"{template_id}/{svg_path.name}: {text.strip()[:60]} missing {', '.join(missing)}"
                        )

        self.assertEqual(failures, [])

    def test_pptx_text_boxes_stay_inside_canvas(self):
        failures = []
        layouts_root = ROOT / "templates" / "layouts"
        for template_id in ACTIVE_ACADEMIC_TEMPLATES:
            for svg_path in sorted((layouts_root / template_id).glob("*.svg")):
                root = ET.parse(svg_path).getroot()
                for elem in root.iter():
                    if elem.tag.split("}", 1)[-1] != "text":
                        continue
                    if elem.get("data-pptx-box-x") is None:
                        continue
                    x = float(elem.get("data-pptx-box-x"))
                    y = float(elem.get("data-pptx-box-y"))
                    w = float(elem.get("data-pptx-box-w"))
                    h = float(elem.get("data-pptx-box-h"))
                    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1280 or y + h > 720:
                        failures.append(
                            f"{template_id}/{svg_path.name}: box {x},{y},{w},{h} leaves 1280x720 canvas"
                        )

        self.assertEqual(failures, [])

    def test_pptx_text_boxes_declare_vertical_alignment(self):
        failures = []
        layouts_root = ROOT / "templates" / "layouts"
        valid = {"top", "t", "middle", "center", "ctr", "bottom", "b"}
        for template_id in ACTIVE_ACADEMIC_TEMPLATES:
            for svg_path in sorted((layouts_root / template_id).glob("*.svg")):
                root = ET.parse(svg_path).getroot()
                for elem in root.iter():
                    if elem.tag.split("}", 1)[-1] != "text" or elem.get("data-pptx-textbox") != "true":
                        continue
                    valign = (elem.get("data-pptx-valign") or "").strip().lower()
                    if valign not in valid:
                        failures.append(f"{template_id}/{svg_path.name}: missing or invalid valign {valign!r}")
                    if elem.get("text-anchor") == "middle" and valign not in {"middle", "center", "ctr"}:
                        failures.append(f"{template_id}/{svg_path.name}: centered text is not vertically centered")

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
