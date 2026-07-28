from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"


class TemplateFeedbackContractTests(unittest.TestCase):
    def test_nsfc_feedback_contract_passes_and_is_a_production_gate(self) -> None:
        from scripts.template_feedback_contract import validate_template_feedback_contract
        from scripts.template_production_gate import run_gate
        from scripts.template_compiler import compile_template

        report = validate_template_feedback_contract(NSFC)
        gate = run_gate(NSFC, run_cross_material=False)
        template_ir = compile_template(NSFC)["template_ir"]

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertTrue((NSFC / "feedback_contract.json").is_file())
        self.assertIn("feedback_contract", template_ir["source_hashes"])
        self.assertEqual(
            template_ir["feedback_contract"]["template_id"],
            "nsfc_defense",
        )
        self.assertIn(
            "feedback_contract",
            {item["id"] for item in gate["gates"]},
        )

    def test_feedback_contract_rejects_a_wrapping_title_box(self) -> None:
        from scripts.template_feedback_contract import validate_template_feedback_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "04_content.svg"
            root = ET.parse(path).getroot()
            title = next(node for node in root.iter() if node.get("data-slot-id") == "PAGE_TITLE")
            title.set("data-pptx-no-wrap", "false")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_feedback_contract(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("FEEDBACK-TITLE-NO-WRAP", {item["code"] for item in report["issues"]})

    def test_feedback_contract_rejects_directional_corner_effect(self) -> None:
        from scripts.template_feedback_contract import validate_template_feedback_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "02_toc.svg"
            root = ET.parse(path).getroot()
            corner = next(node for node in root.iter() if node.get("id") == "chapter-corner-top-left")
            next(iter(corner)).set("filter", "url(#directional-shadow)")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_feedback_contract(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("FEEDBACK-CORNER-DIRECTIONAL-EFFECT", {item["code"] for item in report["issues"]})

    def test_feedback_contract_rejects_toc_text_off_its_container_center(self) -> None:
        from scripts.template_feedback_contract import validate_template_feedback_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "02_toc.svg"
            root = ET.parse(path).getroot()
            title = next(node for node in root.iter() if node.get("data-slot-id") == "TOC_ITEM_01_TITLE")
            title.set("data-pptx-box-y", "183.48")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_feedback_contract(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("FEEDBACK-TOC-CONTROL-VERTICAL-CENTER", {item["code"] for item in report["issues"]})

    def test_feedback_contract_rejects_a_conclusion_container(self) -> None:
        from scripts.template_feedback_contract import validate_template_feedback_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "assets" / "components" / "source_derived" / "comparison_matrix.svg"
            root = ET.parse(path).getroot()
            conclusion = next(node for node in root.iter() if node.get("data-slot-id") == "CONCLUSION")
            root.append(
                ET.Element(
                    "rect",
                    {
                        "x": conclusion.get("data-pptx-box-x"),
                        "y": conclusion.get("data-pptx-box-y"),
                        "width": conclusion.get("data-pptx-box-w"),
                        "height": conclusion.get("data-pptx-box-h"),
                        "fill": "#751497",
                    },
                )
            )
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_feedback_contract(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("FEEDBACK-CONCLUSION-CONTAINER", {item["code"] for item in report["issues"]})

    def test_feedback_contract_rejects_key_message_without_template_owned_bullets(self) -> None:
        from scripts.template_feedback_contract import validate_template_feedback_contract

        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "nsfc_defense"
            shutil.copytree(NSFC, template)
            path = template / "04_content.svg"
            root = ET.parse(path).getroot()
            message = next(node for node in root.iter() if node.get("data-slot-id") == "KEY_MESSAGE")
            message.set("data-easyslides-layout", "plain_text")
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

            report = validate_template_feedback_contract(template)

        self.assertEqual(report["status"], "fail")
        self.assertIn("FEEDBACK-KEY-MESSAGE-BULLETS", {item["code"] for item in report["issues"]})


if __name__ == "__main__":
    unittest.main()
