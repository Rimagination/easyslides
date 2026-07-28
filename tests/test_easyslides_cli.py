import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


class EasySlidesCliTests(unittest.TestCase):
    def test_help_is_printable_and_lists_product_commands(self):
        result = run_cli("scripts/easyslides.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EasySlides command hub", result.stdout)
        self.assertIn("source-to-md", result.stdout)
        self.assertIn("distill", result.stdout)
        self.assertIn("semantic-render", result.stdout)
        self.assertIn("template-gate", result.stdout)
        self.assertIn("template-fill", result.stdout)
        self.assertIn("beautify", result.stdout)
        self.assertIn("clarify", result.stdout)
        self.assertIn("component", result.stdout)
        self.assertIn("chart", result.stdout)
        self.assertIn("icon", result.stdout)

    def test_component_pack_help_delegates_to_pack_manager(self):
        result = run_cli("scripts/easyslides.py", "component", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("declarative EasySlides component packs", result.stdout)

    def test_chart_help_delegates_to_chart_library(self):
        result = run_cli("scripts/easyslides.py", "chart", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Inspect the EasySlides chart asset library", result.stdout)

    def test_icon_help_delegates_to_icon_library(self):
        result = run_cli("scripts/easyslides.py", "icon", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Inspect, search, validate, and sync EasySlides icon assets", result.stdout)

    def test_source_to_md_help_delegates_to_dispatcher(self):
        result = run_cli("scripts/easyslides.py", "source-to-md", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Convert files, directories, or URLs to Markdown", result.stdout)

    def test_distill_help_delegates_to_fail_closed_distiller(self):
        result = run_cli("scripts/easyslides.py", "distill", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Distill a source PPTX", result.stdout)
        self.assertIn("--promote-assets", result.stdout)

    def test_semantic_render_and_template_gate_help_are_available(self):
        render = run_cli("scripts/easyslides.py", "semantic-render", "--help")
        gate = run_cli("scripts/easyslides.py", "template-gate", "--help")

        self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
        self.assertIn("named-slot semantic", render.stdout)
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("fail-closed semantic template", gate.stdout)

    def test_workflow_write_manifest_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            result = run_cli(
                "scripts/easyslides.py",
                "workflow",
                "write-manifest",
                str(project),
                "--route",
                "template-fill-pptx",
                "--stage",
                "scaffold",
                "--status",
                "ready",
                "--artifact",
                "fill_plan=analysis/fill_plan.json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((project / "workflow_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["current"]["route"], "template-fill-pptx")
            self.assertEqual(manifest["current"]["stage"], "scaffold")
            self.assertEqual(manifest["artifacts"]["fill_plan"], "analysis/fill_plan.json")


if __name__ == "__main__":
    unittest.main()
