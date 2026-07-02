import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QA_GATE = ROOT / "scripts" / "academic_qa_gate.py"


def valid_academic_plan() -> dict:
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "scenario_profile": "single_paper_report",
        "source_map": [
            {
                "id": "paper:main",
                "type": "pdf",
                "path": "sources/paper.pdf",
                "title": "Evidence First Paper",
            },
            {
                "id": "fig:1",
                "type": "figure",
                "path": "images/fig1.png",
                "title": "Figure 1. Main result",
                "parent_source": "paper:main",
            },
        ],
        "slides": [
            {
                "page": "P01",
                "role": "paper_identity",
                "action_title": "The paper frames evidence-first slide generation as a traceability problem",
                "claim": "The report is based on Evidence First Paper.",
                "evidence_sources": [
                    {"source_id": "paper:main", "locator": "title page", "kind": "paper_metadata"}
                ],
                "layout_id": "auto/paper_identity",
                "rhythm": "anchor",
                "speaker_note": "Introduce the paper identity.",
            },
            {
                "page": "P02",
                "role": "key_results",
                "action_title": "The main result shows traceable plans reduce unsupported slide claims",
                "claim": "The result section uses figure evidence.",
                "evidence_sources": [
                    {"source_id": "fig:1", "locator": "Figure 1", "kind": "figure"}
                ],
                "layout_id": "auto/key_results",
                "rhythm": "dense",
                "speaker_note": "Explain the result from the figure.",
            },
            {
                "page": "P03",
                "role": "references",
                "action_title": "Source provenance remains visible for review and reuse",
                "claim": "References are retained for traceability.",
                "evidence_sources": [
                    {"source_id": "paper:main", "locator": "references", "kind": "reference"}
                ],
                "layout_id": "auto/references",
                "rhythm": "dense",
                "speaker_note": "Show citation and source provenance.",
            },
            {
                "page": "P04",
                "role": "conclusions",
                "action_title": "Traceable planning turns the paper into an auditable deck",
                "claim": "The final slide ends on conclusions rather than a generic thank-you.",
                "evidence_sources": [
                    {"source_id": "paper:main", "locator": "conclusion", "kind": "paper_section"}
                ],
                "layout_id": "auto/conclusions",
                "rhythm": "breathing",
                "speaker_note": "Close with the verified takeaway.",
            },
        ],
    }


class AcademicQaGateTests(unittest.TestCase):
    def test_valid_plan_passes_academic_qa(self):
        from scripts.academic_qa_gate import run_academic_qa

        report = run_academic_qa(valid_academic_plan(), repo_root=ROOT)

        self.assertEqual(report["schema_version"], "easyslides.academic_qa_report.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)

    def test_topic_title_and_unsupported_result_slide_fail(self):
        from scripts.academic_qa_gate import run_academic_qa

        plan = valid_academic_plan()
        plan["slides"][1]["action_title"] = "Results"
        plan["slides"][1]["evidence_sources"] = [
            {"source_id": "paper:main", "locator": "results section", "kind": "paper_section"}
        ]

        report = run_academic_qa(plan, repo_root=ROOT)
        codes = {item["code"] for item in report["issues"]}

        self.assertEqual(report["status"], "fail")
        self.assertIn("AQA-ACTION-TITLE", codes)
        self.assertIn("AQA-RESULT-EVIDENCE", codes)

    def test_body_variant_contract_failures_stop_academic_qa(self):
        from scripts.academic_qa_gate import run_academic_qa

        plan = valid_academic_plan()
        plan["template_id"] = "defense_topnav"
        plan["slides"] = [plan["slides"][1]]
        plan["slides"][0]["page"] = "P01"
        plan["slides"][0]["layout_id"] = "defense_topnav/three_card_summary"
        plan["slides"][0]["slot_payload"] = {
            "CARD_1_TITLE": "Result",
            "FREEFORM_SVG": "<rect />",
        }

        report = run_academic_qa(plan, repo_root=ROOT)
        codes = {item["code"] for item in report["issues"]}

        self.assertEqual(report["status"], "fail")
        self.assertIn("AQA-BODY-VARIANT", codes)
        self.assertEqual(report["body_variant_status"], "fail")

    def test_missing_references_and_non_conclusion_last_slide_warn(self):
        from scripts.academic_qa_gate import run_academic_qa

        plan = valid_academic_plan()
        plan["slides"] = [plan["slides"][0], plan["slides"][1]]
        plan["slides"].append(
            {
                "page": "P03",
                "role": "thank_you",
                "action_title": "Thank you and questions",
                "claim": "The deck closes with Q&A.",
                "evidence_sources": [
                    {"source_id": "paper:main", "locator": "presentation close", "kind": "paper_section"}
                ],
                "layout_id": "auto/thank_you",
                "rhythm": "anchor",
                "speaker_note": "Invite questions.",
            }
        )

        report = run_academic_qa(plan, repo_root=ROOT)
        codes = {item["code"] for item in report["issues"]}

        self.assertEqual(report["status"], "warn")
        self.assertIn("AQA-REFERENCES", codes)
        self.assertIn("AQA-CONCLUSION-LAST", codes)

    def test_cli_validates_deck_plan_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "deck_plan.json"
            plan_path.write_text(
                json.dumps(valid_academic_plan(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(QA_GATE), str(plan_path), "--repo-root", str(ROOT), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")

    def test_docs_explain_academic_qa_gate(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (ROOT / "references" / "workflow-create.md").read_text(encoding="utf-8")
        strategist = (ROOT / "references" / "strategist.md").read_text(encoding="utf-8")

        for text in (skill, workflow, strategist):
            self.assertIn("Academic QA Gate", text)
            self.assertIn("scripts/academic_qa_gate.py", text)
            self.assertIn("action_title", text)
            self.assertIn("References", text)
            self.assertIn("Conclusions", text)


if __name__ == "__main__":
    unittest.main()
