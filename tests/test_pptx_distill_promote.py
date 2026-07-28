import json
import tempfile
import unittest
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PptxDistillPromoteTests(unittest.TestCase):
    def test_promotion_creates_content_free_template_and_source_scoped_assets(self):
        from scripts.pptx_distill_promote import promote

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            (source / "svg").mkdir(parents=True)
            template = root / "faithful"
            template.mkdir()
            (template / "01_cover.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
                '<text data-pptx-textbox="true" data-pptx-box-x="80" data-pptx-box-y="40" data-pptx-box-w="500" data-pptx-box-h="50">Source title</text>'
                '<text data-pptx-fixed-chrome="true">CONTENTS</text>'
                '</svg>',
                encoding="utf-8",
            )
            (source / "svg" / "layout_01_slideLayout1.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><g id="layout-shape-4"><rect width="20" height="20"/></g></svg>',
                encoding="utf-8",
            )
            write_json(source / "slot_contracts.json", {"slots": [{"source_slide_id": "slide-01", "slot_id": "TITLE", "kind": "text", "role": "title", "geometry": {"x": 80, "y": 40, "width": 500, "height": 50}}]})
            write_json(source / "component_catalog.json", {"components": [{"component_id": "layout_shape", "classification": "fixed", "kind": "shape", "instances": [{"object_id": "ppt/slideLayouts/slideLayout1.xml::shape:4"}, {"object_id": "ppt/slideLayouts/slideLayout1.xml::shape:4"}]}]})
            reusable = root / "reusable"
            assets = root / "assets"

            result = promote(
                source,
                template,
                template_id="demo",
                reusable_dir=reusable,
                asset_dir=assets,
                promotion_report={
                    "schema_version": "easyslides.pptx_distill_promotion_report.v1",
                    "status": "pass",
                    "promotable": True,
                },
            )

            svg = (reusable / "01_cover.svg").read_text(encoding="utf-8")
            self.assertIn("{{TITLE}}", svg)
            self.assertNotIn("Source title", svg)
            self.assertIn("CONTENTS", svg)
            self.assertTrue((assets / "component_asset_manifest.json").exists())
            self.assertTrue((assets / "symbol_asset_manifest.json").exists())
            self.assertTrue((assets / "symbols" / "layout_shape.svg").exists())
            self.assertEqual(result["assets"]["symbol_count"], 1)
            self.assertEqual(result["status"], "source_scoped_shell_profile_review_candidate")
            self.assertFalse(result["production_eligible"])
            status = json.loads((reusable / "template_status.json").read_text(encoding="utf-8"))
            self.assertFalse(status["production_eligible"])
            self.assertTrue(status["requires_semantic_rebuild"])
            self.assertEqual(json.loads((reusable / "asset_promotion.json").read_text(encoding="utf-8"))["promotion_policy"], "promotion_gate_verified_source_scoped_candidate")


if __name__ == "__main__":
    unittest.main()
