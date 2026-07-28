import json
import tempfile
import unittest
from pathlib import Path


class ClarificationGateTests(unittest.TestCase):
    def test_new_deck_request_is_valid_and_batched(self):
        from scripts.clarification_gate import build_clarification_request, validate_clarification_request

        request = build_clarification_request("create")

        self.assertEqual(request["schema_version"], "easyslides.clarification_request.v1")
        self.assertEqual(request["route"], "new_deck")
        self.assertEqual(request["status"], "needs_confirmation")
        self.assertEqual(len(request["questions"]), 3)
        self.assertEqual(len(request["pending_question_ids"]), 5)
        self.assertEqual(validate_clarification_request(request)["status"], "pass")

    def test_answering_rounds_eventually_confirms_and_records_decisions(self):
        from scripts.clarification_gate import answer_clarification_request, build_clarification_request

        request = build_clarification_request("new_deck")
        request = answer_clarification_request(
            request,
            {"purpose": "defense", "audience": "peers", "story_policy": "restructure"},
        )

        self.assertEqual(request["status"], "needs_confirmation")
        self.assertEqual(request["pending_question_ids"], ["page_budget", "canvas_format"])
        self.assertEqual(len(request["questions"]), 2)

        request = answer_clarification_request(request, {"page_budget": "standard", "canvas_format": "16:9"})

        self.assertEqual(request["status"], "confirmed")
        self.assertEqual(request["pending_question_ids"], [])
        self.assertEqual(request["decisions"]["purpose"], "defense")
        self.assertTrue(request["confirmed_at"])

    def test_known_values_are_not_asked_again(self):
        from scripts.clarification_gate import build_clarification_request

        request = build_clarification_request(
            "new_deck",
            known={"purpose": "defense", "audience": "peers", "story_policy": "restructure"},
        )

        self.assertEqual([item["id"] for item in request["questions"]], ["page_budget", "canvas_format"])
        self.assertEqual(request["decisions"]["purpose"], "defense")

    def test_invalid_answer_is_rejected(self):
        from scripts.clarification_gate import ClarificationError, answer_clarification_request, build_clarification_request

        with self.assertRaises(ClarificationError):
            answer_clarification_request(build_clarification_request("new_deck"), {"purpose": "unknown"})

    def test_require_confirmed_reads_state_file(self):
        from scripts.clarification_gate import build_clarification_request, require_confirmed, answer_clarification_request

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "clarification_request.json"
            request = build_clarification_request("new_deck")
            for answers in (
                {"purpose": "defense", "audience": "peers", "story_policy": "restructure"},
                {"page_budget": "standard", "canvas_format": "16:9"},
            ):
                request = answer_clarification_request(request, answers)
            path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

            confirmed = require_confirmed(path)

        self.assertEqual(confirmed["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
