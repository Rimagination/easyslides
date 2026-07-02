import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "scripts" / "paper_intake.py"


def write_sample_project(project: Path) -> None:
    sources = project / "sources"
    images = project / "images"
    sources.mkdir(parents=True)
    images.mkdir(parents=True)

    (sources / "example_paper.pdf").write_bytes(b"%PDF-1.4\n% test fixture\n")
    (sources / "example_paper.md").write_text(
        "\n".join(
            [
                "# Evidence-First Slide Generation",
                "",
                "This paper evaluates whether traceable slide plans improve academic review.",
                "",
                "![Figure 1. Intake architecture](../images/fig1.png)",
                "",
                "The figure shows the source map and deck plan handoff.",
            ]
        ),
        encoding="utf-8",
    )
    (sources / "mineru_manifest.json").write_text(
        json.dumps(
            {
                "source_pdf": "sources/example_paper.pdf",
                "method": "mineru_precision",
                "figures": ["fig1.png"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (images / "fig1.png").write_bytes(b"\x89PNG\r\n\x1a\n")


class PaperIntakeTests(unittest.TestCase):
    def test_builds_single_paper_deck_plan_from_project_sources(self):
        from scripts.academic_qa_gate import run_academic_qa
        from scripts.deck_plan_contract import validate_deck_plan
        from scripts.paper_intake import build_paper_report_deck_plan

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "sample_project"
            write_sample_project(project)

            plan = build_paper_report_deck_plan(project, repo_root=ROOT)
            report = validate_deck_plan(plan, repo_root=ROOT)
            qa = run_academic_qa(plan, repo_root=ROOT)

        self.assertEqual(plan["schema_version"], "easyslides.deck_plan.v1")
        self.assertEqual(plan["scenario_profile"], "single_paper_report")
        self.assertEqual(plan["template_id"], "academic_scqa")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["body_variant_status"], "pass")
        self.assertEqual(qa["status"], "pass", qa["issues"])
        self.assertEqual(plan["paper"]["title"], "Evidence-First Slide Generation")
        source_ids = {item["id"] for item in plan["source_map"]}
        self.assertIn("paper:main", source_ids)
        self.assertIn("fig:1", source_ids)
        self.assertTrue(all("slot_payload" in slide for slide in plan["slides"]))
        self.assertTrue(all("content_shape" in slide for slide in plan["slides"]))
        self.assertTrue(any(slide["role"] == "key_results" for slide in plan["slides"]))
        self.assertTrue(any(slide["role"] == "references" for slide in plan["slides"]))
        self.assertTrue(
            any(
                evidence["source_id"] == "fig:1"
                for slide in plan["slides"]
                for evidence in slide["evidence_sources"]
            )
        )

    def test_cli_writes_deck_plan_json_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "sample_project"
            write_sample_project(project)

            result = subprocess.run(
                [sys.executable, str(INTAKE), str(project), "--repo-root", str(ROOT), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            output_path = project / "deck_plan.json"

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output_path.exists())
            report = json.loads(result.stdout)
            plan = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["output"], str(output_path))
        self.assertEqual(plan["scenario_profile"], "single_paper_report")

    def test_docs_explain_paper_report_intake(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (ROOT / "references" / "workflow-create.md").read_text(encoding="utf-8")

        for text in (skill, workflow):
            self.assertIn("paper-report intake", text)
            self.assertIn("scripts/paper_intake.py", text)
            self.assertIn("source_map", text)
            self.assertIn("deck_plan.json", text)


if __name__ == "__main__":
    unittest.main()
