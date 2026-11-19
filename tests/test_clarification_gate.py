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
        self.assertEqual(len(request["pending_question_ids"]), 6)
        self.assertEqual(request["questions"][0]["id"], "production_scheme")
        self.assertEqual(validate_clarification_request(request)["status"], "pass")

    def test_answering_rounds_eventually_confirms_and_records_decisions(self):
        from scripts.clarification_gate import answer_clarification_request, build_clarification_request

        request = build_clarification_request("new_deck")
        request = answer_clarification_request(
            request,
            {"production_scheme": "direct_editable", "purpose": "defense", "audience": "peers", "story_policy": "restructure"},
        )

        self.assertEqual(request["status"], "needs_confirmation")
        self.assertEqual(request["pending_question_ids"], ["theme_palette", "theme_image_source", "presentation_identity", "page_budget", "canvas_format"])
        self.assertEqual(len(request["questions"]), 3)

        request = answer_clarification_request(request, {"page_budget": "standard", "canvas_format": "16:9",
            "theme_palette": "academic_green", "theme_image_source": "template_assets", "presentation_identity": "材料已检查；汇报人和学校用户明确省略。"})

        self.assertEqual(request["status"], "confirmed")
        self.assertEqual(request["pending_question_ids"], [])
        self.assertEqual(request["decisions"]["purpose"], "defense")
        self.assertTrue(request["confirmed_at"])

    def test_known_values_are_not_asked_again(self):
        from scripts.clarification_gate import build_clarification_request

        request = build_clarification_request(
            "new_deck",
            known={"production_scheme": "direct_editable", "purpose": "defense", "audience": "peers", "story_policy": "restructure",
                   "theme_palette": "academic_blue", "theme_image_source": "template_assets", "presentation_identity": "已检查材料，身份字段用户明确省略。"},
        )

        self.assertEqual([item["id"] for item in request["questions"]], ["page_budget", "canvas_format"])
        self.assertEqual(request["decisions"]["purpose"], "defense")

    def test_invalid_answer_is_rejected(self):
        from scripts.clarification_gate import ClarificationError, answer_clarification_request, build_clarification_request

        with self.assertRaises(ClarificationError):
            answer_clarification_request(build_clarification_request("new_deck"), {"purpose": "unknown"})

    def test_recording_question_states_capture_mode_and_preserves_the_choice(self):
        from scripts.clarification_gate import (
            answer_clarification_request,
            build_clarification_request,
            next_clarification_question,
        )

        deck = {
            "production_scheme": "direct_editable", "purpose": "defense", "audience": "peers",
            "story_policy": "restructure", "theme_palette": "academic_green",
            "theme_image_source": "template_assets", "presentation_identity": "用户明确省略署名。",
            "page_budget": "standard",
        }
        for mode, choice, wording in (("replay", "record", "成稿回放"), ("live", "live", "实时录制")):
            with self.subTest(mode=mode):
                request = build_clarification_request("new_deck", known=deck, offer_recording=True, recording_mode=mode)
                self.assertEqual([q["id"] for q in request["questions"]], ["canvas_format"])
                request = answer_clarification_request(request, {"canvas_format": "16:9"})
                popup = next_clarification_question(request)
                self.assertEqual(popup["question_id"], "recording")
                self.assertEqual(popup["option_ids"], ["skip", choice])
                self.assertEqual(len(popup["questions"]), 1)
                self.assertIn("逐元素", popup["questions"][0]["title"])
                self.assertIn(wording, popup["questions"][0]["title"])
                self.assertIn("默认无配音", popup["questions"][0]["title"])
                request = answer_clarification_request(request, {"recording": choice})
                self.assertEqual(request["status"], "confirmed")
                self.assertEqual(request["decisions"]["recording"], choice)

        explicit = build_clarification_request("new_deck", known={**deck, "recording": "live"}, offer_recording=True)
        self.assertNotIn("recording", explicit["pending_question_ids"])

    def test_require_confirmed_reads_state_file(self):
        from scripts.clarification_gate import build_clarification_request, require_confirmed, answer_clarification_request

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "clarification_request.json"
            request = build_clarification_request("new_deck")
            for answers in (
                {"production_scheme": "direct_editable", "purpose": "defense", "audience": "peers", "story_policy": "restructure"},
                {"page_budget": "standard", "canvas_format": "16:9", "theme_palette": "academic_blue",
                 "theme_image_source": "template_assets",
                 "presentation_identity": "材料已检查；身份字段用户明确省略。"},
            ):
                request = answer_clarification_request(request, answers)
            path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

            confirmed = require_confirmed(path)

        self.assertEqual(confirmed["status"], "confirmed")

    def test_image_choice_inserts_second_round_without_default(self):
        from scripts.clarification_gate import build_clarification_request, answer_clarification_request, validate_clarification_request
        request = build_clarification_request("image_reconstruction")
        request = answer_clarification_request(request, {"production_scheme": "image_partial_rebuild"})
        self.assertEqual(request["status"], "needs_confirmation")
        self.assertEqual(request["questions"][0]["id"], "reconstruction_mode")
        self.assertNotIn("reconstruction_mode", request["decisions"])
        request = answer_clarification_request(request, {"reconstruction_mode": "full_vector"})
        self.assertEqual(validate_clarification_request(request)["status"], "pass")
        self.assertEqual(request["status"], "confirmed")
        request["decisions"].pop("reconstruction_mode")
        self.assertEqual(validate_clarification_request(request)["status"], "fail")

    def test_old_confirmed_state_cannot_bypass_scheme_choice(self):
        from scripts.clarification_gate import build_clarification_request, validate_clarification_request
        request = build_clarification_request("new_deck")
        request.update(status="confirmed", question_bank=[], questions=[], pending_question_ids=[])
        self.assertEqual(validate_clarification_request(request)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
