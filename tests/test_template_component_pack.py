import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"


class TemplateComponentPackTests(unittest.TestCase):
    def test_nsfc_template_component_pack_is_complete(self) -> None:
        from scripts.template_component_pack import validate_template_component_pack

        report = validate_template_component_pack(NSFC)

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["pack_id"], "template/nsfc_defense/components")
        self.assertEqual(report["component_count"], 14)
        self.assertEqual(report["primitive_count"], 0)
        self.assertEqual(report["recipe_count"], 9)
        self.assertEqual(report["dependencies"], [])

    def test_missing_required_token_blocks_the_pack(self) -> None:
        from scripts.template_component_pack import validate_template_component_pack

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nsfc_defense"
            __import__("shutil").copytree(NSFC, target)
            path = target / "component_pack.json"
            pack = json.loads(path.read_text(encoding="utf-8"))
            pack["design_tokens"]["required"].append("surface.missing")
            path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
            report = validate_template_component_pack(target)

        self.assertEqual(report["status"], "fail")
        self.assertIn("TEMPLATE-COMPONENT-PACK-TOKENS", {issue["code"] for issue in report["issues"]})


if __name__ == "__main__":
    unittest.main()
