import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "templates" / "template_policy.json"
LAYOUTS = ROOT / "templates" / "layouts"


class TemplatePolicyTests(unittest.TestCase):
    def test_official_template_set_is_exact(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        expected = {
            "academic_general",
            "academic_scqa",
            "defense_leftnav",
            "defense_topnav",
            "literature_minimal",
            "nsfc_defense",
            "thu_speech",
        }
        self.assertEqual(set(policy["official_template_ids"]), expected)

    def test_only_official_templates_are_in_the_project_layout_root(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        official = set(policy["official_template_ids"])
        actual = {
            path.name
            for path in LAYOUTS.iterdir()
            if path.is_dir() and path.name != "assets" and (path / "layouts.json").is_file()
        }
        self.assertEqual(actual, official)

    def test_generated_index_contains_only_official_templates(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        index = json.loads((LAYOUTS / "layouts_index.json").read_text(encoding="utf-8"))
        self.assertEqual(set(index), set(policy["official_template_ids"]))


if __name__ == "__main__":
    unittest.main()
