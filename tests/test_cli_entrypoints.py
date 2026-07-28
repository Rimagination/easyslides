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

    def test_source_to_md_dispatcher_help_is_printable(self):
        result = run_cli("scripts/source_to_md.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Convert files, directories, or URLs to Markdown", result.stdout)

    def test_template_fill_pptx_help_is_printable(self):
        result = run_cli("scripts/template_fill_pptx.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Analyze and fill native PPTX templates", result.stdout)

    def test_native_enhance_pptx_help_is_printable(self):
        result = run_cli("scripts/native_enhance_pptx.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Native append-only enhancement", result.stdout)

    def test_visual_review_help_is_printable(self):
        result = run_cli("scripts/visual_review.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Create a deck visual review package", result.stdout)

    def test_create_brand_help_is_printable(self):
        result = run_cli("scripts/create_brand.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Create and inspect EasySlides brand presets", result.stdout)

    def test_confirm_ui_help_is_printable(self):
        result = run_cli("scripts/confirm_ui.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Build a local EasySlides confirmation page", result.stdout)

    def test_clarification_gate_help_is_printable(self):
        result = run_cli("scripts/clarification_gate.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("clarification gate", result.stdout.lower())

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

    def test_component_registry_help_is_printable(self):
        result = run_cli("scripts/component_registry.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unified EasySlides component registry", result.stdout)

    def test_body_variant_contract_help_is_printable(self):
        result = run_cli("scripts/body_variant_contract.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("body-variant component composition contracts", result.stdout)

    def test_component_package_help_is_printable(self):
        result = run_cli("scripts/component_package.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validate EasySlides component package", result.stdout)

    def test_component_gallery_help_is_printable(self):
        result = run_cli("scripts/component_gallery.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Build a static EasySlides component package review gallery", result.stdout)

    def test_component_preview_gate_help_is_printable(self):
        result = run_cli("scripts/component_preview_gate.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validate component preview SVG center-alignment gates", result.stdout)

    def test_component_pptx_renderer_help_is_printable(self):
        result = run_cli("scripts/component_pptx_renderer.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Render EasySlides component package stories to a native PPTX preview deck", result.stdout)

    def test_component_selector_help_is_printable(self):
        result = run_cli("scripts/component_selector.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Select EasySlides components", result.stdout)

    def test_component_plan_contract_help_is_printable(self):
        result = run_cli("scripts/component_plan_contract.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validate EasySlides component_plan.json", result.stdout)

    def test_component_plan_builder_help_is_printable(self):
        result = run_cli("scripts/component_plan_builder.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Build EasySlides component_plan.json", result.stdout)

    def test_component_workflow_help_is_printable(self):
        result = run_cli("scripts/component_workflow.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Run the EasySlides component asset workflow", result.stdout)

    def test_project_manager_setup_pdf_tools_can_run_check_without_installing(self):
        result = run_cli("scripts/project_manager.py", "setup-pdf-tools", "--skip-python")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mineru", result.stdout.lower())
        self.assertIn("pdffigures2", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
