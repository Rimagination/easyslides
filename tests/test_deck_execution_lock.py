import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOCKER = ROOT / "scripts" / "deck_execution_lock.py"


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


def variant_plan() -> dict:
    plan = valid_deck_plan()
    plan["template_id"] = "defense_topnav"
    plan["slides"] = [plan["slides"][1]]
    slide = plan["slides"][0]
    slide["page"] = "P01"
    slide["layout_id"] = "defense_topnav/three_card_summary"
    slide["content_shape"] = "cards"
    slide["slot_payload"] = {
        "CARD_1_TITLE": "Need",
        "CARD_1_BODY": "Readers need source-linked claims.",
        "CARD_2_TITLE": "Method",
        "CARD_2_BODY": "The deck plan selects a verified body variant.",
        "CARD_3_TITLE": "Gate",
        "CARD_3_BODY": "The slot payload is checked before rendering.",
    }
    return plan


class DeckExecutionLockTests(unittest.TestCase):
    def test_builds_execution_lock_from_deck_plan_and_body_variant_contract(self):
        from scripts.deck_execution_lock import build_deck_execution_lock

        lock = build_deck_execution_lock(variant_plan(), repo_root=ROOT)

        self.assertEqual(lock["schema_version"], "easyslides.deck_execution_lock.v1")
        self.assertEqual(lock["source_schema_version"], "easyslides.deck_plan.v1")
        self.assertEqual(lock["template_id"], "defense_topnav")
        self.assertEqual(lock["slide_count"], 1)
        self.assertIn("deck_plan_contract", lock["required_gates"])
        self.assertIn("body_variant_contract", lock["required_gates"])
        self.assertIn("preview_render", lock["required_gates"])
        page = lock["pages"]["P01"]
        self.assertEqual(page["layout_id"], "defense_topnav/three_card_summary")
        self.assertEqual(page["rhythm"], "dense")
        self.assertEqual(page["body_variant"]["variant_id"], "three_card_summary")
        self.assertEqual(page["body_variant"]["status"], "pass")
        self.assertEqual(page["body_variant"]["palette_id"], "academic_blue")
        self.assertEqual(
            page["body_variant"]["declared_slots"],
            [
                "CARD_1_TITLE",
                "CARD_1_BODY",
                "CARD_2_TITLE",
                "CARD_2_BODY",
                "CARD_3_TITLE",
                "CARD_3_BODY",
            ],
        )

    def test_validation_rejects_lock_when_deck_plan_drifts(self):
        from scripts.deck_execution_lock import build_deck_execution_lock, validate_deck_execution_lock

        plan = variant_plan()
        lock = build_deck_execution_lock(plan, repo_root=ROOT)
        plan["slides"][0]["rhythm"] = "breathing"

        report = validate_deck_execution_lock(plan, lock, repo_root=ROOT)
        codes = {item["code"] for item in report["issues"]}

        self.assertEqual(report["status"], "fail")
        self.assertIn("EXEC-LOCK-RHYTHM", codes)

    def test_deck_plan_report_includes_execution_lock_preview(self):
        from scripts.deck_plan_contract import validate_deck_plan

        report = validate_deck_plan(variant_plan(), repo_root=ROOT)

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["execution_lock_status"], "pass")
        self.assertEqual(report["execution_lock"]["pages"]["P01"]["body_variant"]["variant_id"], "three_card_summary")

    def test_cli_writes_execution_lock_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "deck_plan.json"
            lock_path = Path(tmp) / "deck_execution_lock.json"
            plan_path.write_text(json.dumps(variant_plan(), ensure_ascii=False, indent=2), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(LOCKER),
                    str(plan_path),
                    "--repo-root",
                    str(ROOT),
                    "--write",
                    str(lock_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(lock["schema_version"], "easyslides.deck_execution_lock.v1")
            self.assertIn("P01", lock["pages"])

    def test_workflow_docs_require_execution_lock_after_deck_plan(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (ROOT / "references" / "workflow-create.md").read_text(encoding="utf-8")
        strategist = (ROOT / "references" / "strategist.md").read_text(encoding="utf-8")
        resume = (ROOT / "workflows" / "resume-execute.md").read_text(encoding="utf-8")

        for text in (skill, workflow, strategist, resume):
            self.assertIn("deck_execution_lock.json", text)
            self.assertIn("scripts/deck_execution_lock.py", text)
            self.assertIn("execution_lock", text)


if __name__ == "__main__":
    unittest.main()
