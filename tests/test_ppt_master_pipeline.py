import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path


class PptMasterPipelineTests(unittest.TestCase):
    def make_project(self) -> tempfile.TemporaryDirectory:
        temp = tempfile.TemporaryDirectory()
        project = Path(temp.name)
        for rel in ("sources", "images", "templates", "svg_output", "notes", "exports"):
            (project / rel).mkdir()
        return temp

    def test_phase_a_reports_missing_contract_files(self):
        from scripts.ppt_master_pipeline import validate_phase_a

        with self.make_project() as temp_dir:
            gate = validate_phase_a(temp_dir)

        self.assertFalse(gate.passed)
        self.assertIn("design_spec.md", gate.missing)
        self.assertIn("spec_lock.md", gate.missing)

    def test_phase_a_passes_with_design_and_spec_lock(self):
        from scripts.ppt_master_pipeline import validate_phase_a

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "design_spec.md").write_text("# Design\n", encoding="utf-8")
            (project / "spec_lock.md").write_text("# Spec Lock\n", encoding="utf-8")

            gate = validate_phase_a(project)

        self.assertTrue(gate.passed)
        self.assertEqual(gate.missing, [])
        self.assertTrue(any("deck_execution_lock.json" in warning for warning in gate.warnings))

    def test_executor_phase_requires_svg_and_total_notes(self):
        from scripts.ppt_master_pipeline import validate_executor_phase

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "design_spec.md").write_text("# Design\n", encoding="utf-8")
            (project / "spec_lock.md").write_text("# Spec Lock\n", encoding="utf-8")

            missing_gate = validate_executor_phase(project)
            (project / "notes" / "total.md").write_text("# 01\nNotes\n", encoding="utf-8")
            (project / "svg_output" / "01.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>',
                encoding="utf-8",
            )
            passed_gate = validate_executor_phase(project)

        self.assertFalse(missing_gate.passed)
        self.assertIn("notes/total.md", missing_gate.missing)
        self.assertIn("svg_output/*.svg", missing_gate.missing)
        self.assertTrue(passed_gate.passed)

    def test_status_returns_next_action(self):
        from scripts.ppt_master_pipeline import project_status

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "design_spec.md").write_text("# Design\n", encoding="utf-8")
            (project / "spec_lock.md").write_text("# Spec Lock\n", encoding="utf-8")
            status = project_status(project)

        self.assertEqual(status["next_action"], "run_executor_svg_generation")
        self.assertEqual(status["svg_count"], 0)

    def test_export_dry_run_returns_canonical_order(self):
        from scripts.ppt_master_pipeline import run_export

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "notes" / "total.md").write_text("# 01\nNotes\n", encoding="utf-8")
            (project / "svg_output" / "01.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>',
                encoding="utf-8",
            )
            result = run_export(project, dry_run=True)

        commands = [" ".join(command) for command in result["commands"]]
        self.assertTrue(result["passed"])
        self.assertIn("validate_svg_text_slots.py", commands[0])
        self.assertIn("--strict-unboxed", commands[0])
        self.assertIn("--require-valign", commands[0])
        self.assertIn("--check-canvas", commands[0])
        self.assertIn("total_md_split.py", commands[1])
        self.assertIn("finalize_svg.py", commands[2])
        self.assertIn("svg_to_pptx.py", commands[3])
        self.assertIn("validate-latest-visual-measure", commands[4])

    def test_export_is_blocked_by_unconfirmed_clarification(self):
        from scripts.clarification_gate import build_clarification_request
        from scripts.ppt_master_pipeline import run_export

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "notes" / "total.md").write_text("# 01\nNotes\n", encoding="utf-8")
            (project / "svg_output" / "01.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>',
                encoding="utf-8",
            )
            (project / "clarification_request.json").write_text(
                json.dumps(build_clarification_request("new_deck"), ensure_ascii=False),
                encoding="utf-8",
            )
            result = run_export(project, dry_run=True)

        self.assertFalse(result["passed"])
        self.assertIn("clarification_request.json (confirmed)", result["gate"]["missing"][0])

    def test_export_dry_run_includes_template_geometry_when_lock_names_template(self):
        from scripts.ppt_master_pipeline import run_export

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "notes" / "total.md").write_text("# 01\nNotes\n", encoding="utf-8")
            (project / "svg_output" / "01.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>',
                encoding="utf-8",
            )
            (project / "deck_execution_lock.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.deck_execution_lock.v1",
                        "template_id": "nsfc_defense_distilled",
                    }
                ),
                encoding="utf-8",
            )
            template_dir = project / "templates" / "nsfc_defense_distilled"
            template_dir.mkdir(parents=True)
            (template_dir / "geometry_contract.json").write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.template_geometry_contract.v1",
                        "template_id": "nsfc_defense_distilled",
                        "canvas": {"width": 1280, "height": 720},
                        "pages": [],
                    }
                ),
                encoding="utf-8",
            )
            result = run_export(project, dry_run=True)

        commands = [" ".join(command) for command in result["commands"]]
        self.assertTrue(result["passed"])
        self.assertIn("validate_svg_text_slots.py", commands[0])
        self.assertIn("--require-valign", commands[0])
        self.assertIn("visual_measure_gate.py", commands[1])
        self.assertIn("--template-dir", commands[1])
        self.assertIn("templates\\nsfc_defense_distilled", commands[1].replace("/", "\\"))
        self.assertIn("total_md_split.py", commands[2])
        self.assertIn("finalize_svg.py", commands[3])
        self.assertIn("svg_to_pptx.py", commands[4])
        self.assertIn("validate-latest-visual-measure", commands[5])

    def test_export_dry_run_can_disable_svg_slot_gate(self):
        from scripts.ppt_master_pipeline import run_export

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "notes" / "total.md").write_text("# 01\nNotes\n", encoding="utf-8")
            (project / "svg_output" / "01.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>',
                encoding="utf-8",
            )
            result = run_export(project, dry_run=True, validate_svg_slots=False)

        commands = [" ".join(command) for command in result["commands"]]
        self.assertTrue(result["passed"])
        self.assertNotIn("validate_svg_text_slots.py", commands[0])
        self.assertIn("total_md_split.py", commands[0])

    def test_export_dry_run_can_insert_render_png_preview(self):
        from scripts.ppt_master_pipeline import run_export

        with self.make_project() as temp_dir:
            project = Path(temp_dir)
            (project / "notes" / "total.md").write_text("# 01\nNotes\n", encoding="utf-8")
            (project / "svg_output" / "01.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>',
                encoding="utf-8",
            )
            result = run_export(project, dry_run=True, render_png=True)

        commands = [" ".join(command) for command in result["commands"]]
        self.assertTrue(result["passed"])
        self.assertIn("svg_to_pptx.py", commands[-3])
        self.assertIn("render-latest-pptx", commands[-2])
        self.assertIn("validate-latest-visual-measure", commands[-1])

    def test_cli_status_json_is_parseable(self):
        from scripts.ppt_master_pipeline import main

        with self.make_project() as temp_dir:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["status", temp_dir, "--json"])

        self.assertEqual(code, 0)
        status = json.loads(stdout.getvalue())
        self.assertEqual(status["next_action"], "complete_phase_a")


if __name__ == "__main__":
    unittest.main()
