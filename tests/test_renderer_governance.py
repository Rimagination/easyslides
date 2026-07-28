import unittest


class RendererGovernanceTests(unittest.TestCase):
    def test_builtin_component_renderers_are_repository_owned(self):
        from scripts.component_registry import build_component_registry
        from scripts.renderer_governance import validate_renderer_governance

        report = validate_renderer_governance(build_component_registry(include_template_asset_bank=False))

        self.assertEqual(report["status"], "pass", report)
        # The former research-core packages are migration sources, not
        # installable executable components. Runtime-governance now applies
        # only when a public component package is installed.
        self.assertEqual(report["checked_component_count"], 0)
        self.assertTrue(all(row["targets"] for row in report["components"]))


if __name__ == "__main__":
    unittest.main()
