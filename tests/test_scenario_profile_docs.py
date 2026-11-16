import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScenarioProfileDocsTests(unittest.TestCase):
    def test_main_skill_points_agents_to_scenario_profiles(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("references/scenario_profiles.json", text)
        self.assertIn("scripts/scenario_profiles.py --list", text)
        self.assertIn("single_paper_report", text)
        self.assertIn("workshop_training", text)
        self.assertIn("required_rules", text)
        self.assertIn("recommended_rules", text)

    def test_create_workflow_loads_profile_before_confirmations(self):
        text = (ROOT / "references" / "workflow-create.md").read_text(encoding="utf-8")

        self.assertIn("Scenario profile", text)
        self.assertIn("python scripts/scenario_profiles.py --profile", text)
        self.assertIn("template_may_override", text)
        self.assertIn("template_must_not_override", text)

    def test_strategist_explains_rule_layers_and_template_boundary(self):
        text = (ROOT / "references" / "strategist.md").read_text(encoding="utf-8")

        self.assertIn("hard_rules", text)
        self.assertIn("required_rules", text)
        self.assertIn("recommended_rules", text)
        self.assertIn("relaxable_rules", text)
        self.assertIn("Templates control visual containers", text)
        self.assertIn("scenario profiles control content organization", text)

    def test_skill_is_scenario_first_and_template_extensible(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Academic Scenario-First Template Contract", text)
        self.assertIn("scenario first, template second", text)
        self.assertIn("template route is not a scenario", text)
        self.assertIn("seed profiles", text)
        self.assertIn("scenario_variant", text)
        self.assertIn("do not force a defense or literature-report template", text)

    def test_create_workflow_does_not_pin_all_decks_to_academic_general(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Template and Design Foundation", text)
        self.assertIn("If the user provides an explicit template path", text)
        self.assertIn("If no matching template exists", text)
        self.assertIn("academic_classic` remains an available neutral pack when explicitly selected", text)
        self.assertIn("academic_scqa` is the structured academic/technical report variant", text)


if __name__ == "__main__":
    unittest.main()
