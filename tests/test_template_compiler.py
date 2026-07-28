from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"


class TemplateCompilerTests(unittest.TestCase):
    def test_nsfc_compiles_canonical_sources_into_runtime_ir(self) -> None:
        from scripts.template_compiler import compile_template

        report = compile_template(NSFC)
        template_ir = report["template_ir"]

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["capability_level"], "production")
        self.assertEqual(template_ir["capability_profile"]["composition"]["mode"], "template_composable")
        self.assertFalse(template_ir["capability_profile"]["composition"]["allow_global_component_fallback"])
        self.assertEqual(report["shell_count"], 5)
        self.assertEqual(report["body_variant_count"], 12)
        self.assertGreaterEqual(report["component_dependency_count"], 10)
        self.assertEqual(template_ir["package"]["version"], "0.3.0")
        self.assertEqual(template_ir["source_of_truth"]["shells"], "layouts.json")
        self.assertEqual(template_ir["source_of_truth"]["body_variants"], "body_variants.json")
        self.assertEqual(template_ir["component_pack"]["pack_id"], "template/nsfc_defense/components")
        self.assertEqual(template_ir["component_pack"]["dependencies"][0]["pack_id"], "research-core")
        self.assertEqual(report["lock"]["source_digest"], report["source_digest"])
        self.assertTrue(
            all(component.get("sha256") for component in template_ir["components"])
        )
        content = next(shell for shell in template_ir["shells"] if shell["shell_id"] == "content")
        self.assertEqual([slot["slot_id"] for slot in content["slots"]], ["PAGE_TITLE"])
        self.assertEqual(content["content_shell_policy"], "source_guided_body_variant_required")
        self.assertEqual(content["body_canvas"], {"x": 64.0, "y": 116.0, "width": 1152.0, "height": 548.0})
        self.assertEqual(len(content["legacy_shadow_slots"]), 13)
        self.assertEqual(
            len({variant["composition_scene"] for variant in template_ir["body_variants"]}),
            12,
        )
        evidence = next(variant for variant in template_ir["body_variants"] if variant["variant_id"] == "evidence_triptych")
        self.assertIn("component/nsfc_defense/claim_bar", evidence["component_dependency_asset_ids"])

    def test_compiler_materializes_ir_lock_and_compatibility_projections(self) -> None:
        from scripts.template_compiler import compile_template

        with tempfile.TemporaryDirectory() as tmp:
            report = compile_template(NSFC, write=True, output_dir=tmp)
            output = Path(tmp)
            stored_ir = json.loads((output / "template_ir.json").read_text(encoding="utf-8"))
            stored_lock = json.loads((output / "template.lock.json").read_text(encoding="utf-8"))

            self.assertEqual(stored_ir["source_digest"], report["source_digest"])
            self.assertEqual(stored_lock["source_digest"], report["source_digest"])
            self.assertEqual(stored_lock["capability_profile"]["lifecycle"], "production")
            self.assertTrue((output / "projections" / "template.json").is_file())
            self.assertTrue((output / "projections" / "page_catalog.json").is_file())
            self.assertTrue((output / "projections" / "slot_contracts.json").is_file())
            self.assertTrue((output / "projections" / "geometry_contract.json").is_file())
            self.assertTrue((output / "projections" / "template_status.json").is_file())

    def test_unified_registry_discovers_packages_and_legacy_templates(self) -> None:
        from scripts.template_package import rebuild_template_registry

        report = rebuild_template_registry(repo_root=ROOT, write=False)
        by_id = {row["template_id"]: row for row in report["templates"]}

        self.assertEqual(report["status"], "pass")
        self.assertGreaterEqual(report["template_count"], 10)
        self.assertGreaterEqual(report["package_count"], 2)
        self.assertEqual(by_id["nsfc_defense"]["capability_level"], "production")
        self.assertTrue(by_id["nsfc_defense"]["managed_package"])
        self.assertEqual(by_id["academic_general"]["capability_level"], "shell")
        self.assertFalse(by_id["academic_general"]["managed_package"])


if __name__ == "__main__":
    unittest.main()
