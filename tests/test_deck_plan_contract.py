import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "deck_plan_contract.py"


def valid_deck_plan() -> dict:
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "scenario_profile": "single_paper_report",
        "source_map": [
            {
                "id": "paper:main",
                "type": "pdf",
                "path": "sources/paper.pdf",
                "title": "Example Paper",
            },
            {
                "id": "fig:1",
                "type": "figure",
                "path": "sources/figures/fig1.png",
                "title": "Figure 1",
                "parent_source": "paper:main",
            },
        ],
        "slides": [
            {
                "page": "P01",
                "role": "cover",
                "action_title": "Example Paper tests whether evidence-first slides help readers",
                "claim": "The deck introduces the paper identity and main question.",
                "evidence_sources": [
                    {"source_id": "paper:main", "locator": "title page", "kind": "paper_metadata"}
                ],
                "layout_id": "01_cover",
                "rhythm": "anchor",
                "speaker_note": "Open with the paper identity and why the question matters.",
            },
            {
                "page": "P02",
                "role": "result",
                "action_title": "The main result improves accuracy without raising latency",
                "claim": "The reported method improves the target metric while staying practical.",
                "evidence_sources": [
                    {
                        "source_id": "fig:1",
                        "locator": "Figure 1",
                        "kind": "figure",
                        "figure_id": "fig1",
                    }
                ],
                "layout_id": "literature_minimal/result_with_figure",
                "rhythm": "dense",
                "chart_id": "none",
                "speaker_note": "Walk through the figure and state the so-what explicitly.",
            },
        ],
    }


class DeckPlanContractTests(unittest.TestCase):
    def test_valid_deck_plan_passes_and_preserves_page_contract(self):
        from scripts.deck_plan_contract import validate_deck_plan

        report = validate_deck_plan(valid_deck_plan(), repo_root=ROOT)

        self.assertEqual(report["schema_version"], "easyslides.deck_plan_report.v1")
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["slide_count"], 2)
        self.assertEqual(report["pages"], ["P01", "P02"])

    def test_unknown_evidence_source_and_missing_action_title_fail(self):
        from scripts.deck_plan_contract import validate_deck_plan

        plan = valid_deck_plan()
        plan["slides"][1]["evidence_sources"][0]["source_id"] = "fig:missing"
        plan["slides"][1]["action_title"] = ""

        report = validate_deck_plan(plan, repo_root=ROOT)
        codes = {item["code"] for item in report["issues"]}

        self.assertEqual(report["status"], "fail")
        self.assertIn("DECK-PLAN-ACTION-TITLE", codes)
        self.assertIn("DECK-PLAN-SOURCE-REF", codes)

    def test_template_body_variant_payload_contract_is_enforced(self):
        from scripts.deck_plan_contract import validate_deck_plan

        plan = valid_deck_plan()
        plan["template_id"] = "defense_topnav"
        plan["slides"] = [plan["slides"][1]]
        plan["slides"][0]["page"] = "P01"
        plan["slides"][0]["layout_id"] = "defense_topnav/three_card_summary"
        plan["slides"][0]["slot_payload"] = {
            "CARD_1_TITLE": "Need",
            "CARD_1_BODY": "Readers need source-linked claims.",
            "CARD_2_TITLE": "Method",
            "CARD_2_BODY": "The deck plan selects a verified body variant.",
            "CARD_3_TITLE": "Gate",
            "CARD_3_BODY": "The slot payload is checked before rendering.",
        }

        report = validate_deck_plan(plan, repo_root=ROOT)

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["body_variant_status"], "pass")
        self.assertEqual(report["body_variant_reports"][0]["variant_id"], "three_card_summary")
        self.assertIn("template_tokens", report["body_variant_reports"][0]["required_gates"])

    def test_template_body_variant_payload_contract_rejects_freeform_svg(self):
        from scripts.deck_plan_contract import validate_deck_plan

        plan = valid_deck_plan()
        plan["template_id"] = "defense_topnav"
        plan["slides"] = [plan["slides"][1]]
        plan["slides"][0]["page"] = "P01"
        plan["slides"][0]["layout_id"] = "defense_topnav/three_card_summary"
        plan["slides"][0]["slot_payload"] = {
            "CARD_1_TITLE": "Need",
            "FREEFORM_SVG": "<rect />",
        }

        report = validate_deck_plan(plan, repo_root=ROOT)
        codes = {item["code"] for item in report["issues"]}

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["body_variant_status"], "fail")
        self.assertIn("DECK-PLAN-BODY-VARIANT", codes)
        self.assertTrue(
            any("FREEFORM_SVG" in item["message"] for item in report["issues"]),
            report["issues"],
        )

    def test_cli_validates_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "deck_plan.json"
            plan_path.write_text(
                json.dumps(valid_deck_plan(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(plan_path), "--repo-root", str(ROOT), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["slide_count"], 2)

    def test_workflow_docs_require_deck_plan_before_spec_lock(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (ROOT / "references" / "workflow-create.md").read_text(encoding="utf-8")
        strategist = (ROOT / "references" / "strategist.md").read_text(encoding="utf-8")

        for text in (skill, workflow, strategist):
            self.assertIn("deck_plan.json", text)
            self.assertIn("scripts/deck_plan_contract.py", text)
            self.assertIn("body_variant_contract", text)
            self.assertIn("scripts/body_variant_adapter.py", text)
            self.assertIn("action_title", text)
            self.assertIn("evidence_sources", text)


if __name__ == "__main__":
    unittest.main()
