import unittest


class ComponentRendererRegistryTests(unittest.TestCase):
    def test_builtin_specs_are_shared_by_all_targets(self):
        from scripts.component_renderer_registry import (
            PPTX_TARGET,
            SVG_TARGET,
            supported_renderer_ids,
            validate_renderer_id,
        )

        ids = supported_renderer_ids()
        self.assertEqual(len(ids), 7)
        for renderer_id in ids:
            self.assertEqual(validate_renderer_id(renderer_id, target=SVG_TARGET)["status"], "pass")
        for renderer_id in ids:
            expected = "pass" if renderer_id != "source_template_projection" else "fail"
            self.assertEqual(validate_renderer_id(renderer_id, target=PPTX_TARGET)["status"], expected)

    def test_unknown_renderer_is_rejected(self):
        from scripts.component_renderer_registry import validate_renderer_id

        report = validate_renderer_id("community_custom_renderer")
        self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main()
