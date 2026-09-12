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
        self.assertTrue(
            all(
                {"conclusion", "evidence", "explanation", "status"}
                <= set(slide["content_contract"])
                for slide in plan["slides"]
            )
        )
        self.assertTrue(any(slide["content_quality"]["source_text_chars"] > 0 for slide in plan["slides"]))
        self.assertTrue(all(slide.get("preferred_form") for slide in plan["slides"]))

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

    def test_cli_accepts_defense_duration_and_explicit_visual_exploration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "sample_project"
            write_sample_project(project)
            (project / "sources" / "example_paper.md").write_text(
                "# 示例论文\n\n## 第一章 研究背景\n## 第二章 核心结果",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(INTAKE),
                    str(project),
                    "--repo-root",
                    str(ROOT),
                    "--scenario-profile",
                    "thesis_defense",
                    "--duration-minutes",
                    "15",
                    "--visual-exploration",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            plan = json.loads((project / "deck_plan.json").read_text(encoding="utf-8"))
            report = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(plan["scenario_variant"], "cn_degree_defense_v4")
        self.assertEqual(plan["defense"]["page_budget"]["duration_band"], "15分钟")
        self.assertEqual(plan["intake"]["workflow_stages"][1], "visual_exploration")

    def test_thesis_defense_variant_emits_chapter_figure_and_workflow_contract(self):
        from scripts.academic_qa_gate import run_academic_qa
        from scripts.deck_plan_contract import validate_deck_plan
        from scripts.paper_intake import build_paper_report_deck_plan

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "sample_project"
            write_sample_project(project)
            (project / "sources" / "example_paper.md").write_text(
                "\n".join(
                    [
                        "# Evidence-First Thesis",
                        "",
                        "## 第一章 研究背景",
                        "### 研究现状",
                        "## 第二章 核心结果",
                        "### 结果分析",
                        "![Figure 1. Main result](../images/fig1.png)",
                    ]
                ),
                encoding="utf-8",
            )

            plan = build_paper_report_deck_plan(
                project,
                repo_root=ROOT,
                scenario_profile="thesis_defense",
                duration_minutes=10,
            )
            deck_report = validate_deck_plan(plan, repo_root=ROOT)
            qa = run_academic_qa(plan, repo_root=ROOT)

        self.assertEqual(plan["scenario_profile"], "thesis_defense")
        self.assertEqual(plan["scenario_variant"], "cn_degree_defense_v4")
        self.assertEqual(plan["template_id"], "defense_topnav")
        self.assertEqual(plan["palette_id"], "thesis_navy_v4")
        self.assertEqual(deck_report["status"], "pass", deck_report["issues"])
        self.assertFalse(plan["intake"]["visual_exploration"])
        self.assertNotIn("visual_exploration", plan["intake"]["workflow_stages"])
        self.assertEqual(
            [chapter["id"] for chapter in plan["defense"]["chapters"]],
            ["chapter_01", "chapter_02"],
        )
        figure = next(source for source in plan["source_map"] if source["type"] == "figure")
        self.assertEqual(figure["figure_class"], "A")
        self.assertTrue(figure["quality"]["needs_high_res"])
        self.assertGreaterEqual(
            sum(slide["defense_section"] == "研究背景与问题" for slide in plan["slides"]),
            4,
        )
        self.assertEqual(qa["status"], "warn", qa["issues"])
        self.assertEqual(qa["error_count"], 0, qa["issues"])
        self.assertIn("AQA-FIGURE-HIGH-RES", {item["code"] for item in qa["issues"]})
        self.assertIn("content_quality_summary", qa)

    def test_richer_source_selects_semantic_defense_variants(self):
        from scripts.paper_intake import build_paper_report_deck_plan

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "sample_project"
            write_sample_project(project)
            (project / "sources" / "example_paper.md").write_text(
                "\n".join(
                    [
                        "# Evidence-First Thesis",
                        "",
                        "## 第一章 研究背景",
                        "### 研究现状",
                        "Existing studies explain the trend but leave the mechanism unresolved.",
                        "### 研究问题",
                        "This thesis tests whether the proposed mechanism explains the observed pattern.",
                        "### 研究目标",
                        "The study compares two settings and evaluates three measurable outcomes.",
                        "### 研究方法",
                        "- Collect observations from the two settings.",
                        "- Compare the response across matched samples.",
                        "### 样本",
                        "The sample covers sites with comparable baseline conditions.",
                        "## 第二章 核心结果",
                        "### 结果分析",
                        "The treatment changes the response consistently across the sampled sites.",
                        "![Figure 1. Main result](../images/fig1.png)",
                    ]
                ),
                encoding="utf-8",
            )

            plan = build_paper_report_deck_plan(
                project,
                repo_root=ROOT,
                scenario_profile="thesis_defense",
            )

        content_slides = [
            slide
            for slide in plan["slides"]
            if slide["role"] not in {"cover", "toc", "chapter", "ending"}
        ]
        self.assertTrue(all(slide["content_quality"]["evidence_count"] > 0 for slide in content_slides))
        self.assertGreaterEqual(
            len({slide["layout_id"].rsplit("/", 1)[-1] for slide in content_slides}),
            3,
        )
        self.assertTrue(any(slide["preferred_form"] == "timeline" for slide in content_slides))

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
