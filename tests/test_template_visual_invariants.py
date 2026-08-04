from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"
ACADEMIC_GENERAL = ROOT / "templates" / "layouts" / "academic_general"


class TemplateVisualInvariantTests(unittest.TestCase):
    def test_production_templates_pass_declared_visual_invariants(self) -> None:
        from scripts.template_visual_invariants import validate_template_visual_invariants

        for template in (NSFC, ACADEMIC_GENERAL):
            report = validate_template_visual_invariants(template)
            self.assertEqual(report["status"], "pass", report["issues"])

    def test_production_gate_includes_visual_invariants(self) -> None:
        from scripts.template_production_gate import run_gate

        report = run_gate(NSFC, run_cross_material=False)
        gates = {gate["id"]: gate for gate in report["gates"]}

        self.assertEqual(gates["template_visual_invariants"]["status"], "pass")

    def test_declared_container_text_cannot_move_off_the_centre_line(self) -> None:
        from scripts.template_visual_invariants import validate_template_visual_invariants

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "02_toc.svg"
            root = ET.parse(path).getroot()
            title = next(node for node in root.iter() if node.get("data-slot-id") == "TOC_ITEM_01_TITLE")
            title.set("data-pptx-box-y", "183.48")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_visual_invariants(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("VISUAL-CENTER-CONTAINER-ALIGNMENT", {item["code"] for item in report["issues"]})

    def test_center_lock_requires_native_middle_alignment(self) -> None:
        from scripts.template_visual_invariants import validate_template_visual_invariants

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "02_toc.svg"
            root = ET.parse(path).getroot()
            title = next(node for node in root.iter() if node.get("data-slot-id") == "TOC_ITEM_01_TITLE")
            title.set("data-pptx-valign", "top")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_visual_invariants(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("VISUAL-CENTER-LOCK-VALIGN", {item["code"] for item in report["issues"]})

    def test_mirror_pair_rejects_directional_filters(self) -> None:
        from scripts.template_visual_invariants import validate_template_visual_invariants

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "03_chapter.svg"
            root = ET.parse(path).getroot()
            corner = next(node for node in root.iter() if node.get("id") == "chapter-corner-top-left")
            next(iter(corner)).set("filter", "url(#directional-shadow)")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_visual_invariants(template)

        self.assertEqual(report["status"], "fail")
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("VISUAL-SYMMETRY-DIRECTIONAL-EFFECT", codes)
        self.assertIn("VISUAL-SYMMETRY-GEOMETRY", codes)


if __name__ == "__main__":
    unittest.main()
