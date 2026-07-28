import json
import tempfile
import unittest
from pathlib import Path


class ConfirmUiTests(unittest.TestCase):
    def test_build_confirmation_package_from_project_artifacts(self):
        from scripts.confirm_ui import build_confirmation_package

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo_project"
            project.mkdir()
            (project / "sources").mkdir()
            (project / "sources" / "paper.md").write_text("source", encoding="utf-8")
            (project / "deck_plan.json").write_text(
                json.dumps(
                    {
                        "schema_version": "deck_plan.v1",
                        "title": "Demo Deck",
                        "canvas_format": "ppt169",
                        "scenario_profile": "single_paper_report",
                        "slides": [{"page": 1}, {"page": 2}],
                    }
                ),
                encoding="utf-8",
            )
            (project / "design_spec.md").write_text("# Demo Design\n", encoding="utf-8")
            (project / "spec_lock.md").write_text("# Demo Lock\n", encoding="utf-8")

            out = Path(tmp) / "confirm"
            manifest = build_confirmation_package(project, out, brand="academic-blue")

            self.assertEqual(manifest["schema_version"], "easyslides.confirm_ui.v1")
            self.assertEqual(manifest["status"], "needs_confirmation")
            self.assertEqual(manifest["deck_plan"]["slide_count"], 2)
            self.assertIn("paper.md", manifest["sources"])
            self.assertTrue((out / "confirm.json").is_file())
            self.assertTrue((out / "index.html").is_file())
            html = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("Demo Deck", html)
            self.assertIn("academic-blue", html)


if __name__ == "__main__":
    unittest.main()
