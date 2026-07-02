import tempfile
import unittest
from pathlib import Path

from scripts import page_recipe_preview
from scripts.validate_svg_text_slots import validate_svg_text_slots


class PageRecipePreviewTests(unittest.TestCase):
    def test_build_preview_project_writes_one_svg_per_recipe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = page_recipe_preview.build_preview_project(Path(temp_dir) / "preview")

            svg_files = sorted((project / "svg_output").glob("*.svg"))

            self.assertEqual(len(svg_files), 8)
            self.assertTrue((project / "notes" / "total.md").exists())
            self.assertTrue((project / "design_spec.md").exists())
            self.assertTrue((project / "spec_lock.md").exists())

    def test_preview_svgs_pass_text_slot_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = page_recipe_preview.build_preview_project(Path(temp_dir) / "preview")

            report = validate_svg_text_slots(
                project / "svg_output",
                strict_unboxed=True,
                unboxed_char_threshold=12,
            )

            self.assertEqual(report["status"], "pass", report["issues"])
            self.assertEqual(report["blocking_count"], 0)

    def test_render_text_slot_contains_declared_box(self):
        slot = page_recipe_preview.TextSlot(
            slot_id="demo",
            x=100,
            y=120,
            w=240,
            h=60,
            lines=["固定槽位", "显式换行"],
            size=20,
            weight="700",
        )

        markup = page_recipe_preview.render_text_slot(slot)

        self.assertIn('data-pptx-textbox="true"', markup)
        self.assertIn('data-pptx-box-w="240"', markup)
        self.assertIn("<tspan", markup)


if __name__ == "__main__":
    unittest.main()
