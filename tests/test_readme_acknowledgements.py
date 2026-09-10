import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReadmeAcknowledgementsTests(unittest.TestCase):
    def test_acknowledgements_retain_source_links_and_license_boundary(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        for project in [
            "hugohe3/ppt-master",
            "Gabberflast/academic-pptx-skill",
            "LearnPrompt/humanize-ppt",
            "op7418/guizang-ppt-skill",
            "xiao634zhang/paper-ppt-skill",
            "fangyuanopus/literature-report-ppt-builder",
        ]:
            with self.subTest(project=project):
                self.assertIn(f"https://github.com/{project}", text)

        self.assertIn("[LICENSE](LICENSE)", text)
        self.assertIn("third-party templates and images require their own permissions", text)


if __name__ == "__main__":
    unittest.main()
