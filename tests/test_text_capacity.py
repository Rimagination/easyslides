import unittest


def fixture_layouts():
    return {
        "text_fit_policy": {
            "role_defaults": {
                "body": {
                    "default_font_size_px": 22,
                    "min_font_size_px": 16,
                    "line_height": 1.25,
                    "max_chars_per_line_zh": 8,
                    "overflow_action": "split",
                    "max_lines": 4,
                },
                "page_title": {
                    "default_font_size_px": 30,
                    "min_font_size_px": 22,
                    "line_height": 1.15,
                    "max_chars_per_line_zh": 6,
                    "overflow_action": "truncate",
                    "max_lines": 1,
                },
            }
        }
    }


class TextCapacityTests(unittest.TestCase):
    def test_resolve_slot_capacity_uses_slot_override_and_role_defaults(self):
        from scripts.text_capacity import resolve_slot_capacity

        capacity = resolve_slot_capacity(
            fixture_layouts(),
            {"slot_id": "CONTENT_BODY", "role": "body", "max_lines": 2},
        )

        self.assertEqual(capacity.slot_id, "CONTENT_BODY")
        self.assertEqual(capacity.role, "body")
        self.assertEqual(capacity.font_size_px, 22)
        self.assertEqual(capacity.min_font_size_px, 16)
        self.assertEqual(capacity.line_height, 1.25)
        self.assertEqual(capacity.max_chars_per_line_zh, 8)
        self.assertEqual(capacity.max_lines, 2)
        self.assertEqual(capacity.capacity_chars, 16)
        self.assertEqual(capacity.overflow_action, "split")

    def test_fit_text_to_capacity_caps_rendered_lines_and_reports_input_pressure(self):
        from scripts.text_capacity import fit_text_to_capacity, resolve_slot_capacity

        capacity = resolve_slot_capacity(
            fixture_layouts(),
            {"slot_id": "CONTENT_BODY", "role": "body", "max_lines": 2},
        )
        result = fit_text_to_capacity("abcdefghijklmnopqrstuvwxyz", capacity)

        self.assertEqual(result.lines, ["abcdefgh", "ijklmnop"])
        self.assertEqual(result.raw_line_count, 4)
        self.assertTrue(result.input_over_capacity)
        self.assertFalse(result.output_overflow)
        self.assertEqual(result.rendered_chars, 16)
        self.assertEqual(result.action, "compressed_or_split_before_render")

    def test_fit_text_to_capacity_keeps_short_title_within_capacity(self):
        from scripts.text_capacity import fit_text_to_capacity, resolve_slot_capacity

        capacity = resolve_slot_capacity(
            fixture_layouts(),
            {"slot_id": "PAGE_TITLE", "role": "page_title"},
        )
        result = fit_text_to_capacity("short", capacity)

        self.assertEqual(result.lines, ["short"])
        self.assertFalse(result.input_over_capacity)
        self.assertFalse(result.output_overflow)
        self.assertEqual(result.action, "within_capacity")


if __name__ == "__main__":
    unittest.main()
