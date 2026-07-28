import tempfile
import unittest
from pathlib import Path


class WorkflowManifestTests(unittest.TestCase):
    def test_update_manifest_records_current_route_and_history(self):
        from scripts.workflow_manifest import load_manifest, update_manifest

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            first = update_manifest(
                project,
                route="template-fill-pptx",
                stage="analyze",
                status="running",
                artifacts={"source_pptx": "sources/template.pptx"},
                command=["python", "scripts/template_fill_pptx.py", "analyze"],
            )
            second = update_manifest(
                project,
                route="template-fill-pptx",
                stage="apply",
                status="completed",
                artifacts={"output_pptx": "exports/filled.pptx"},
                command=["python", "scripts/template_fill_pptx.py", "apply"],
            )

            loaded = load_manifest(project)
            self.assertEqual(first["schema_version"], "easyslides.workflow_manifest.v1")
            self.assertEqual(second["current"]["route"], "template-fill-pptx")
            self.assertEqual(second["current"]["stage"], "apply")
            self.assertEqual(second["current"]["status"], "completed")
            self.assertEqual(loaded["artifacts"]["source_pptx"], "sources/template.pptx")
            self.assertEqual(loaded["artifacts"]["output_pptx"], "exports/filled.pptx")
            self.assertEqual(len(loaded["history"]), 2)
            self.assertEqual(loaded["history"][0]["stage"], "analyze")
            self.assertEqual(loaded["history"][1]["stage"], "apply")


if __name__ == "__main__":
    unittest.main()
