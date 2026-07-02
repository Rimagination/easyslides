import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectBackedSkillDocsTests(unittest.TestCase):
    def test_architecture_doc_declares_layered_project_backed_skill(self):
        text = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")

        self.assertIn("project-backed Codex skill", text)
        self.assertIn("Skill = task router and operating guide", text)
        self.assertIn("Workflows = task-specific protocols", text)
        self.assertIn("Scripts = local execution engine", text)
        self.assertIn("one production PPTX backend", text)
        self.assertIn("Path E: Slide Image Reconstruction", text)

    def test_install_doc_declares_installation_levels(self):
        text = (ROOT / "INSTALL.md").read_text(encoding="utf-8")

        self.assertIn("Minimal Skill Install", text)
        self.assertIn("Full Local Runtime", text)
        self.assertIn("Developer Mode", text)
        self.assertIn("Real PPTX generation requires the full repository", text)
        self.assertIn("EasySlides is a project-backed skill", text)

    def test_readme_and_skill_link_architecture_and_install(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        for text in (readme, skill):
            self.assertIn("project-backed", text)
            self.assertIn("ARCHITECTURE.md", text)
            self.assertIn("INSTALL.md", text)


if __name__ == "__main__":
    unittest.main()
