import tempfile
import unittest
from pathlib import Path


class ProjectManagerImageReconstructionTests(unittest.TestCase):
    def test_slide_image_reconstruction_kind_creates_extra_dirs(self):
        from scripts.project_manager import ProjectManager

        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(base_dir=tmp)
            project_path = Path(
                manager.init_project(
                    "screenshot_case",
                    "ppt169",
                    project_kind="slide_image_reconstruction",
                )
            )

            self.assertTrue((project_path / "analysis").is_dir())
            self.assertTrue((project_path / "pages" / "page_001" / "assets" / "split").is_dir())
            self.assertTrue((project_path / "pptx").is_dir())
            self.assertTrue((project_path / "reports").is_dir())
            self.assertIn("Project kind: slide_image_reconstruction", (project_path / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
