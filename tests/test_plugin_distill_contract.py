import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginDistillContractTests(unittest.TestCase):
    def test_plugin_metadata_discovers_distill_skill_and_declared_assets(self):
        metadata = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(metadata["skills"], "./skills/")
        for key in ("composerIcon", "logo", "logoDark"):
            declared = metadata["interface"][key]
            self.assertTrue((ROOT / declared.removeprefix("./")).exists(), declared)
        self.assertIn("Distill PPTX templates", metadata["interface"]["capabilities"])
        self.assertIn("PPTX distillation", metadata["keywords"])
        self.assertLessEqual(len(metadata["interface"]["defaultPrompt"]), 3)
        self.assertIn("无内容", metadata["interface"]["defaultPrompt"][0])

        skill_path = ROOT / "skills" / "easyslides-distill" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        frontmatter, body = skill_path.read_text(encoding="utf-8").split("\n---\n", 1)
        self.assertTrue(frontmatter.startswith("---\n"))
        self.assertIn("name: easyslides-distill", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("scripts/pptx_template_distill.py", body)
        self.assertIn("scripts/pptx_source_graph.py", body)
        self.assertIn("component_catalog.json", body)
        self.assertIn("design_system_pack.json", body)
        self.assertIn("projection_manifest.json", body)
        self.assertIn("source_graph.json", body)

    def test_distill_skill_has_agent_metadata_and_hard_geometry_contract(self):
        agent = ROOT / "skills" / "easyslides-distill" / "agents" / "openai.yaml"
        agent_text = agent.read_text(encoding="utf-8")
        self.assertIn('display_name: "EasySlides PPTX Distill"', agent_text)
        self.assertIn("$easyslides-distill", agent_text)
        self.assertIn("allow_implicit_invocation: true", agent_text)

        body = (ROOT / "skills" / "easyslides-distill" / "SKILL.md").read_text(encoding="utf-8")
        for token in (
            "data-pptx-box-x",
            "data-pptx-box-y",
            "data-pptx-box-w",
            "data-pptx-box-h",
            "data-pptx-valign",
            "PPTX-CONTROL-TEXT-VERTICAL-MISALIGN",
            "template_material_smoke_test.py",
            "source_geometry_risks.json",
            "pptx_distill_promotion_gate.py",
            "promotion_report.json",
            "evidence-driven shell profile",
            "body_variants.json",
            "body_variant_contract.py",
            "component_refs",
            "source_page_roster.json",
            "canonical_shell_limit",
        ):
            self.assertIn(token, body)

    def test_easyslides_adapter_and_route_delegate_to_plugin_distill(self):
        adapter = (ROOT / "skills" / "easyslides" / "SKILL.md").read_text(encoding="utf-8")
        routing = (ROOT / "workflows" / "routing.md").read_text(encoding="utf-8")
        workflow = (ROOT / "workflows" / "pptx-to-easyslides-template.md").read_text(encoding="utf-8")

        self.assertIn("skills/easyslides-distill/SKILL.md", adapter)
        self.assertIn("pptx-to-easyslides-template", routing)
        self.assertIn("plugin-local `easyslides-distill` first", routing)
        self.assertIn("canonical `easyslides`", workflow)
        self.assertIn("DOM-order", workflow)

    def test_canonical_skill_names_and_compatibility_alias(self):
        main = (ROOT / "skills" / "easyslides" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: easyslides", main)
        self.assertIn("蒸馏PPT", main)
        self.assertIn("component/symbol", main)
        self.assertIn("compatibility references only", main)
        gate = (ROOT / "scripts" / "clarification_gate.py").read_text(encoding="utf-8")
        self.assertIn('"easyslides": "new_deck"', gate)
        self.assertIn('"academic-pptx": "new_deck"', gate)

    def test_distill_command_help_is_available_from_plugin_repo(self):
        result = subprocess.run(
            [sys.executable, "scripts/easyslides.py", "distill", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Distill a source PPTX", result.stdout)
        self.assertIn("--from-existing-source", result.stdout)


if __name__ == "__main__":
    unittest.main()
