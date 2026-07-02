import unittest

from scripts.svg_quality_checker import SVGQualityChecker


class SVGQualityCheckerTemplateModeTests(unittest.TestCase):
    def test_extracts_non_numbered_archetype_page_roster(self):
        spec = """# Template

## III. Page Roster

| Page | Role |
|---|---|
| `cover.svg` | Cover |
| `body_text.svg` | Long-form body |
| `figure_single.svg` | One exhibit |

## IV. Chapter Reuse

Do not create `007_chapter.svg` or `012_chapter.svg`.
"""

        roster = SVGQualityChecker._extract_spec_roster(spec)

        self.assertEqual(roster, ["cover", "body_text", "figure_single"])

    def test_image_opacity_is_warning_not_error(self):
        checker = SVGQualityChecker()
        result = {"errors": [], "warnings": []}

        checker._check_forbidden_elements(
            '<svg><image href="assets/photo.png" opacity="0.22"/></svg>',
            result,
        )

        self.assertEqual(result["errors"], [])
        self.assertIn("DrawingML image alpha", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
