import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def deck_plan() -> dict:
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "scenario_profile": "single_paper_report",
        "source_map": [{"id": "paper:main", "type": "pdf", "path": "paper.pdf", "title": "Paper"}],
        "slides": [
            {
                "page": "P01",
                "role": "cover",
                "action_title": "The paper asks a traceable question",
                "claim": "The paper asks a traceable question.",
                "evidence_sources": [{"source_id": "paper:main", "locator": "title", "kind": "metadata"}],
                "layout_id": "01_cover",
                "rhythm": "anchor",
                "speaker_note": "Introduce the question.",
            },
            {
                "page": "P02",
                "role": "result",
                "action_title": "The result is supported by the figure",
                "claim": "The result is supported by the figure.",
                "evidence_sources": [{"source_id": "paper:main", "locator": "Figure 1", "kind": "figure"}],
                "layout_id": "literature_minimal/result_with_figure",
                "rhythm": "dense",
                "speaker_note": "Explain the result.",
            },
        ],
    }


def content_plan(approved: bool = True) -> dict:
    return {
        "schema_version": "easyslides.content_plan.v1",
        "plan_status": "approved" if approved else "draft",
        "deck_message": "The evidence supports the result.",
        "audience": "research group",
        "delivery": "live",
        "slides": [
            {"page": "P01", "role": "cover", "question": "Why this paper?", "takeaway": "The paper asks a traceable question.", "content_units": ["The paper asks a traceable question."], "claim_ids": ["c1"]},
            {"page": "P02", "role": "result", "question": "What did it find?", "takeaway": "The result is supported by the figure.", "content_units": ["The result is supported by the figure."], "claim_ids": ["c2"]},
        ],
        "claim_ledger": [
            {"claim_id": "c1", "claim": "The paper asks a traceable question.", "type": "statement", "source": "paper.pdf:p.1", "verbatim": "The paper asks a traceable question.", "verified": True},
            {"claim_id": "c2", "claim": "The result is supported by the figure.", "type": "statement", "source": "paper.pdf:p.4", "verbatim": "The result is supported by the figure.", "verified": True},
        ],
        "source_coverage": [{"section_id": "paper:main", "label": "Paper", "disposition": "built-around", "reason": "supports the deck"}],
    }


def design_plan(approved: bool = True) -> dict:
    rows = []
    for page, form, family, runner, runner_family in (("P01", "statement", "statement", "split_compare", "comparison"), ("P02", "evidence_split", "evidence", "figure_focus", "figure")):
        rows.append({
            "page": page,
            "visual_protagonist": "the evidence",
            "candidate_forms": [{"form_id": form, "family": family}, {"form_id": runner, "family": runner_family}],
            "chosen_form": form,
            "runner_up": {"form_id": runner, "family": runner_family},
            "reasoning": "The chosen form carries the argument more clearly than the runner-up.",
            "layout_id": "01_cover" if page == "P01" else "literature_minimal/result_with_figure",
            "motion": "static: one-idea slide",
        })
    return {
        "schema_version": "easyslides.design_plan.v1",
        "plan_status": "approved" if approved else "draft",
        "design_language": {"palette": "semantic purple", "type_pairing": "Microsoft YaHei / Arial", "signature_motif": "quiet rule", "signature_move": "evidence dominates the result slide"},
        "density": {"median_words_per_slide": 24, "over_budget_count": 0, "non_text_protagonist_count": 1},
        "slides": rows,
        "form_ledger": [{"page": "P01", "format_family": "statement"}, {"page": "P02", "format_family": "evidence"}],
    }


class PresentationContractTests(unittest.TestCase):
    def test_form_candidates_are_divergent(self):
        from scripts.component_selector import select_form_candidates

        result = select_form_candidates(content_shape="parallel_points")
        self.assertEqual(result["status"], "found")
        self.assertGreaterEqual(len({row["family"] for row in result["candidates"]}), 2)
        self.assertNotEqual(result["chosen"]["family"], result["runner_up"]["family"])

    def test_content_and_design_contracts_require_approval(self):
        from scripts.content_plan_contract import validate_content_plan
        from scripts.design_plan_contract import validate_design_plan

        self.assertEqual(validate_content_plan(content_plan())["status"], "pass")
        self.assertEqual(validate_design_plan(design_plan(), content_plan=content_plan())["status"], "pass")
        self.assertEqual(validate_content_plan(content_plan(False))["status"], "fail")
        self.assertEqual(validate_design_plan(design_plan(False))["status"], "fail")

    def test_review_contracts_reject_unresolved_reports(self):
        from scripts.review_contract import validate_arbiter_report, validate_critic_report

        critic = {
            "schema_version": "easyslides.critic_report.v1", "deck_id": "demo", "review_effort": "standard",
            "coverage": {"slide_count": 2, "slides_opened": [1, 2]}, "findings": [], "verdict": "pass",
        }
        arbiter = {"schema_version": "easyslides.arbiter_report.v1", "deck_id": "demo", "verdicts": [], "escalated_unreviewed": [], "verdict": "pass"}
        self.assertEqual(validate_critic_report(critic)["status"], "pass")
        self.assertEqual(validate_arbiter_report(arbiter)["status"], "pass")
        arbiter["escalated_unreviewed"] = [{"slide": 2, "issue": "bad"}]
        self.assertEqual(validate_arbiter_report(arbiter)["status"], "fail")

    def test_template_package_can_be_registered_and_validated(self):
        from scripts.template_package import build_package_manifest, validate_package

        template_dir = ROOT / "templates" / "layouts" / "nsfc_purple_semantic"
        manifest = build_package_manifest(template_dir)
        report = validate_package(template_dir, manifest=manifest)
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(manifest["layout_count"], 17)

    def test_draft_plan_builder_is_explicitly_not_production_ready(self):
        from scripts.presentation_plan_builder import build_content_plan, build_design_plan
        from scripts.content_plan_contract import validate_content_plan
        from scripts.design_plan_contract import validate_design_plan

        content = build_content_plan(deck_plan())
        design = build_design_plan(deck_plan())
        self.assertEqual(content["plan_status"], "draft")
        self.assertEqual(design["plan_status"], "draft")
        self.assertEqual(validate_content_plan(content)["status"], "fail")
        self.assertEqual(validate_design_plan(design)["status"], "fail")

    def test_deck_gates_join_all_contracts_and_hash_artifacts(self):
        from scripts.component_plan_builder import build_component_plan
        from scripts.clarification_gate import answer_clarification_request, build_clarification_request
        from scripts.deck_gates import run_deck_gates

        with tempfile.TemporaryDirectory() as tmp:
            deck_dir = Path(tmp)
            plan = deck_plan()
            (deck_dir / "deck_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            (deck_dir / "content_plan.json").write_text(json.dumps(content_plan(), ensure_ascii=False), encoding="utf-8")
            (deck_dir / "design_plan.json").write_text(json.dumps(design_plan(), ensure_ascii=False), encoding="utf-8")
            component = build_component_plan(plan)
            (deck_dir / "component_plan.json").write_text(json.dumps(component, ensure_ascii=False), encoding="utf-8")
            clarification = build_clarification_request("new_deck")
            clarification = answer_clarification_request(
                clarification,
                {str(row["id"]): str(row["recommended_option_id"]) for row in clarification["question_bank"]},
            )
            (deck_dir / "clarification_request.json").write_text(json.dumps(clarification, ensure_ascii=False), encoding="utf-8")
            (deck_dir / "critic_report.json").write_text(json.dumps({
                "schema_version": "easyslides.critic_report.v1", "deck_id": "demo", "review_effort": "standard",
                "coverage": {"slide_count": 2, "slides_opened": [1, 2]}, "findings": [], "verdict": "pass",
            }), encoding="utf-8")
            (deck_dir / "arbiter_report.json").write_text(json.dumps({
                "schema_version": "easyslides.arbiter_report.v1", "deck_id": "demo", "verdicts": [], "escalated_unreviewed": [], "verdict": "pass",
            }), encoding="utf-8")
            (deck_dir / "render_report.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            (deck_dir / "geometry_report.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            report = run_deck_gates(deck_dir, repo_root=ROOT)
            self.assertEqual(report["status"], "pass", report["failed_gates"])
            self.assertTrue(all(row.get("sha256") for row in report["artifacts"] if row["status"] == "present"))
            self.assertEqual(report["gates"][-1]["id"], "handoff")


if __name__ == "__main__":
    unittest.main()
