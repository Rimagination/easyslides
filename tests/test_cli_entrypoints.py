import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONIOENCODING", None)
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


class CliEntrypointTests(unittest.TestCase):
    def test_project_manager_help_imports_shared_project_utils(self):
        result = run_cli("scripts/project_manager.py", "help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("project_manager.py init", result.stdout)

    def test_thumbnail_help_imports_office_soffice_helper(self):
        result = run_cli("scripts/thumbnail.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Create thumbnail grids", result.stdout)

    def test_svg_quality_checker_help_is_printable_on_windows(self):
        result = run_cli("scripts/svg_quality_checker.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SVG Quality Check Tool", result.stdout)
        self.assertNotIn("Unable to import dependency modules", result.stdout + result.stderr)

    def test_ppt_master_pipeline_help_is_printable(self):
        result = run_cli("scripts/ppt_master_pipeline.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PPT Master-compatible workflow gates", result.stdout)

    def test_render_pptx_png_help_is_printable(self):
        result = run_cli("scripts/render_pptx_png.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Render a PPTX deck to per-slide PNG files", result.stdout)

    def test_image_reconstruction_pipeline_help_is_printable(self):
        result = run_cli("scripts/image_reconstruction_pipeline.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("slide-image-to-editable PPTX reconstruction", result.stdout)

    def test_validate_svg_text_slots_help_is_printable(self):
        result = run_cli("scripts/validate_svg_text_slots.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validate SVG text against fixed PPTX text slots", result.stdout)

    def test_page_recipe_help_is_printable(self):
        result = run_cli("scripts/page_recipe.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PPT Master whole-page layout recipes", result.stdout)

    def test_page_recipe_preview_help_is_printable(self):
        result = run_cli("scripts/page_recipe_preview.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Generate a PPT Master page recipe preview project", result.stdout)

    def test_project_manager_setup_pdf_tools_can_run_check_without_installing(self):
        result = run_cli("scripts/project_manager.py", "setup-pdf-tools", "--skip-python")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mineru", result.stdout.lower())
        self.assertIn("pdffigures2", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
