import unittest
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BodyVariantAdapterTests(unittest.TestCase):
    def test_loads_verified_body_variants_from_template_pack(self):
        from scripts.body_variant_adapter import load_body_variant_registry

        registry = load_body_variant_registry(ROOT / "templates" / "layouts" / "defense_topnav")

        self.assertEqual(registry.template_id, "defense_topnav")
        self.assertEqual(registry.primary_variant, "flexible_canvas")
        self.assertIn("table_matrix", registry.variants)
        self.assertEqual(registry.variants["table_matrix"].variant_id, "table_matrix")
        self.assertIn("research content", registry.variants["table_matrix"].best_for)

    def test_literature_minimal_exposes_classic_content_variants(self):
        from scripts.body_variant_adapter import load_body_variant_registry, select_body_variant

        registry = load_body_variant_registry(ROOT / "templates" / "layouts" / "literature_minimal")
        selection = select_body_variant(
            ROOT / "templates" / "layouts" / "literature_minimal",
            {"layout_id": "literature_minimal/result_with_figure", "content_shape": "figure"},
        )

        self.assertEqual(registry.primary_variant, "flexible_content")
        self.assertIn("result_with_figure", registry.variants)
        self.assertEqual(selection.variant.variant_id, "result_with_figure")
        self.assertEqual(selection.reason, "explicit_layout_id")

    def test_explicit_layout_id_selects_verified_variant(self):
        from scripts.body_variant_adapter import select_body_variant

        selection = select_body_variant(
            ROOT / "templates" / "layouts" / "defense_topnav",
            {
                "layout_id": "defense_topnav/table_matrix",
                "content_shape": "table",
                "claim": "The comparison matrix identifies the strongest plan.",
            },
        )

        self.assertEqual(selection.variant.variant_id, "table_matrix")
        self.assertEqual(selection.reason, "explicit_layout_id")
        self.assertEqual(selection.source, "body_variants.json")
        self.assertEqual(selection.tokens.palette_id, "academic_blue")
        self.assertEqual(selection.tokens.colors["primary"], "#183A6A")
        self.assertIn("text_fit_policy", selection.tokens.raw)
        self.assertIn("text_capacity", selection.required_gates)
        self.assertIn("svg_quality_checker", selection.required_gates)
        self.assertIn("pptx_roundtrip", selection.required_gates)
        self.assertIn("validate_pptx_text_layout", selection.required_gates)

    def test_content_shape_selects_table_and_question_variants_without_free_layout(self):
        from scripts.body_variant_adapter import select_body_variant

        table = select_body_variant(
            ROOT / "templates" / "layouts" / "defense_topnav",
            {"content_shape": "table", "claim": "A compact matrix compares four methods."},
        )
        question = select_body_variant(
            ROOT / "templates" / "layouts" / "defense_leftnav",
            {"content_shape": "question_card", "claim": "The answer choices diagnose the core concept."},
        )

        self.assertEqual(table.variant.variant_id, "table_matrix")
        self.assertEqual(table.reason, "content_shape")
        self.assertEqual(question.variant.variant_id, "card_grid")
        self.assertEqual(question.reason, "content_shape")

    def test_falls_back_to_primary_variant_when_shape_has_no_verified_match(self):
        from scripts.body_variant_adapter import select_body_variant

        selection = select_body_variant(
            ROOT / "templates" / "layouts" / "defense_topnav",
            {"content_shape": "unknown_shape", "claim": "A text explanation is sufficient."},
        )

        self.assertEqual(selection.variant.variant_id, "flexible_canvas")
        self.assertEqual(selection.reason, "primary_fallback")

    def test_payload_contract_accepts_exact_declared_slots(self):
        from scripts.body_variant_adapter import validate_body_variant_payload

        contract = validate_body_variant_payload(
            ROOT / "templates" / "layouts" / "defense_topnav",
            {
                "layout_id": "defense_topnav/three_card_summary",
                "slot_payload": {
                    "CARD_1_TITLE": "Problem",
                    "CARD_1_BODY": "Fragmented evidence makes manual composition brittle.",
                    "CARD_2_TITLE": "Approach",
                    "CARD_2_BODY": "Pick a verified body variant before rendering.",
                    "CARD_3_TITLE": "Gate",
                    "CARD_3_BODY": "Validate declared slots before SVG generation.",
                },
            },
        )

        self.assertEqual(contract.status, "pass")
        self.assertEqual(contract.selection.variant.variant_id, "three_card_summary")
        self.assertEqual(contract.missing_slots, ())
        self.assertEqual(contract.extra_slots, ())
        self.assertEqual(
            tuple(contract.payload),
            (
                "CARD_1_TITLE",
                "CARD_1_BODY",
                "CARD_2_TITLE",
                "CARD_2_BODY",
                "CARD_3_TITLE",
                "CARD_3_BODY",
            ),
        )

    def test_payload_contract_rejects_missing_and_freeform_slots(self):
        from scripts.body_variant_adapter import validate_body_variant_payload

        contract = validate_body_variant_payload(
            ROOT / "templates" / "layouts" / "defense_topnav",
            {
                "layout_id": "defense_topnav/three_card_summary",
                "slot_payload": {
                    "CARD_1_TITLE": "Problem",
                    "FREEFORM_SVG": "<rect />",
                },
            },
        )

        self.assertEqual(contract.status, "fail")
        self.assertIn("CARD_1_BODY", contract.missing_slots)
        self.assertIn("FREEFORM_SVG", contract.extra_slots)
        self.assertEqual(
            [issue["code"] for issue in contract.issues],
            ["BODY-VARIANT-MISSING-SLOT", "BODY-VARIANT-EXTRA-SLOT"],
        )

    def test_cli_reports_payload_contract(self):
        payload = {
            "CARD_1_TITLE": "Problem",
            "CARD_1_BODY": "Manual layouts drift.",
            "CARD_2_TITLE": "Adapter",
            "CARD_2_BODY": "Selects the verified body variant.",
            "CARD_3_TITLE": "Contract",
            "CARD_3_BODY": "Checks the declared slot payload.",
        }

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "body_variant_adapter.py"),
                "defense_topnav",
                "--layout-id",
                "defense_topnav/three_card_summary",
                "--slot-payload-json",
                json.dumps(payload),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        output = json.loads(result.stdout)

        self.assertEqual(output["variant_id"], "three_card_summary")
        self.assertEqual(output["payload_contract"]["status"], "pass")
        self.assertEqual(output["payload_contract"]["missing_slots"], [])
        self.assertEqual(output["payload_contract"]["extra_slots"], [])


if __name__ == "__main__":
    unittest.main()
