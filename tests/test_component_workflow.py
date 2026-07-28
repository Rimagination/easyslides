import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DECK_PLAN = ROOT / "tests" / "fixtures" / "component_workflow_deck_plan.json"


class ComponentWorkflowTests(unittest.TestCase):
    def test_workflow_builds_plan_gallery_and_pptx(self):
        from scripts.component_workflow import run_component_workflow

        with self.subTest("temporary output"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                report = run_component_workflow(deck_plan_path=FIXTURE_DECK_PLAN, output_dir=tmp_path / "workflow")
                component_plan = json.loads((tmp_path / "workflow" / "component_plan.json").read_text(encoding="utf-8"))

                self.assertTrue((tmp_path / "workflow" / "gallery" / "component_gallery.html").exists())
                self.assertFalse((tmp_path / "workflow" / "component_gallery.pptx").exists())
                self.assertTrue((tmp_path / "workflow" / "component_workflow_report.json").exists())

        self.assertEqual(report["schema_version"], "easyslides.component_workflow_report.v1")
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["component_plan_status"], "pass")
        self.assertEqual(report["gallery_status"], "pass")
        self.assertEqual(report["pptx_status"], "not_applicable")
        self.assertEqual(component_plan["slides"][0]["selected_assets"][0]["asset_id"], "card/kpi_row_3")
        self.assertEqual(component_plan["slides"][1]["selected_assets"][0]["asset_id"], "card/evidence_stack")


if __name__ == "__main__":
    unittest.main()
