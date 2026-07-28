from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NSFC = ROOT / "templates" / "layouts" / "nsfc_defense"


class TemplateCompilationGateTests(unittest.TestCase):
    def test_compiled_contract_and_real_composition_pass(self) -> None:
        from scripts.template_production_gate import (
            validate_compiled_contract,
            validate_composition_runtime,
        )

        compiled = validate_compiled_contract(NSFC)
        with tempfile.TemporaryDirectory() as tmp:
            composition = validate_composition_runtime(
                NSFC,
                report_dir=Path(tmp),
            )

        self.assertEqual(compiled["status"], "pass", compiled["issues"])
        self.assertEqual(compiled["capability_level"], "production")
        self.assertEqual(composition["status"], "pass", composition["issues"])
        self.assertEqual(composition["variant_count"], 12)
        self.assertEqual(composition["rendered_slide_count"], 12)
        self.assertEqual(composition["component_instance_count"], 12)


if __name__ == "__main__":
    unittest.main()
