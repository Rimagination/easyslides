import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EMBLEMS = ROOT / "references" / "assets" / "university_emblems"
PROJECT = ROOT / "projects" / "she_why_changed_advisor_leftnav_ppt169_20260523"


class EcnuLogoAssetsTests(unittest.TestCase):
    def test_ecnu_wordmark_is_registered_in_university_emblem_library(self):
        manifest = json.loads((EMBLEMS / "manifest.json").read_text(encoding="utf-8"))
        school_index = json.loads((EMBLEMS / "school_index.json").read_text(encoding="utf-8"))

        assets = {asset["id"]: asset for asset in manifest["assets"]}
        self.assertIn("ecnu_logo_wordmark", assets)
        self.assertEqual(assets["ecnu_logo_wordmark"]["file"], "svg/ecnu_logo_wordmark.svg")
        self.assertEqual(assets["ecnu_logo_wordmark"]["preview_png"], "png/ecnu_logo_wordmark.png")
        self.assertTrue((EMBLEMS / "svg" / "ecnu_logo_wordmark.svg").exists())
        self.assertTrue((EMBLEMS / "png" / "ecnu_logo_wordmark.png").exists())

        entries = {entry["id"]: entry for entry in school_index["entries"]}
        self.assertEqual(entries["ecnu_logo_wordmark"]["school_name_zh"], "华东师范大学")
        self.assertIn("ECNU", entries["ecnu_logo_wordmark"]["aliases"])

    def test_defense_project_uses_ecnu_wordmark_asset_not_web_fallback(self):
        build_script = (PROJECT / "build_deck.py").read_text(encoding="utf-8")

        self.assertRegex(build_script, r'BRAND_LOGO_FILE\s*=\s*"ecnu_logo_wordmark\.png"')
        self.assertNotRegex(build_script, r'BRAND_LOGO_FILE\s*=\s*"ecnu_logo_urongda\.png"')
        self.assertTrue((PROJECT / "assets" / "figures" / "ecnu_logo_wordmark.png").exists())

    def test_defense_project_places_chapter_logo_in_upper_left_only(self):
        build_script = (PROJECT / "build_deck.py").read_text(encoding="utf-8")

        self.assertIn('add_raw_image(group, BRAND_LOGO_FILE, 54, 42, 178, 32)', build_script)
        self.assertIn('add_raw_image(group, BRAND_LOGO_FILE, 1038, 38, 188, 34)', build_script)
        self.assertIn('add_raw_image(group, BRAND_LOGO_FILE, 1048, 44, 178, 32)', build_script)
        self.assertNotIn('add_raw_image(group, BRAND_LOGO_FILE, 1038, 616, 188, 34)', build_script)


if __name__ == "__main__":
    unittest.main()
