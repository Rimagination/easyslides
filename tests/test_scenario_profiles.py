import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScenarioProfileTests(unittest.TestCase):
    def test_active_academic_scenarios_are_declared(self):
        from scripts.scenario_profiles import load_profiles, validate_profiles

        catalog = load_profiles()
        validate_profiles(catalog)

        self.assertEqual(catalog["schema_version"], "easyslides.scenario_profiles.v1")
        self.assertEqual(
            set(catalog["profiles"]),
            {
                "single_paper_report",
                "multi_paper_review",
                "thesis_defense",
                "proposal_or_fund",
                "lab_progress",
                "workshop_training",
                "conference_talk",
            },
        )

    def test_template_policy_keeps_visual_overrides_separate_from_hard_rules(self):
        from scripts.scenario_profiles import get_profile, load_profiles

        catalog = load_profiles()
        profile = get_profile("single_paper_report", catalog)
        policy = profile["template_policy"]

        self.assertTrue(policy["template_controls_visuals"])
        self.assertIn("palette", policy["template_may_override"])
        self.assertIn("title_treatment", policy["template_may_override"])
        self.assertIn("source_traceability", policy["template_must_not_override"])
        self.assertIn("text_fit", policy["template_must_not_override"])
        self.assertNotIn("source_traceability", policy["template_may_override"])

    def test_workshop_has_looser_structure_than_literature_and_defense_profiles(self):
        from scripts.scenario_profiles import get_profile, load_profiles, structure_rank

        catalog = load_profiles()
        workshop = get_profile("workshop_training", catalog)
        single = get_profile("single_paper_report", catalog)
        defense = get_profile("thesis_defense", catalog)

        self.assertLess(
            structure_rank(workshop["structure_strength"]),
            structure_rank(single["structure_strength"]),
        )
        self.assertLess(
            structure_rank(workshop["structure_strength"]),
            structure_rank(defense["structure_strength"]),
        )
        self.assertIn("interaction_checkpoints", workshop["required_rules"])
        self.assertIn("action_titles", workshop["recommended_rules"])
        self.assertNotIn("action_titles", workshop["required_rules"])

    def test_thesis_defense_v4_variant_declares_duration_and_visual_policies(self):
        from scripts.scenario_profiles import (
            duration_page_band,
            get_scenario_variant,
            load_profiles,
        )

        catalog = load_profiles()
        variant = get_scenario_variant("thesis_defense", catalog=catalog)

        self.assertEqual(variant["display_name"], "中文硕博士毕业答辩 v4")
        self.assertFalse(variant["visual_exploration"]["default_enabled"])
        self.assertTrue(variant["visual_exploration"]["explicit_opt_in"])
        self.assertEqual(
            duration_page_band("thesis_defense", 20, catalog=catalog)["min_pages"],
            24,
        )
        self.assertEqual(
            duration_page_band("thesis_defense", 20, catalog=catalog)["max_pages"],
            32,
        )

    def test_cli_lists_profiles_as_json(self):
        from scripts.scenario_profiles import main

        output = main(["--list", "--json"])
        payload = json.loads(output)

        self.assertIn("single_paper_report", payload["profiles"])
        self.assertIn("workshop_training", payload["profiles"])
        self.assertEqual(payload["schema_version"], "easyslides.scenario_profiles.v1")


if __name__ == "__main__":
    unittest.main()
