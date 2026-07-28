import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SitePublicAssetsTests(unittest.TestCase):
    def test_public_asset_urls_are_ascii_and_exist(self):
        site = ROOT / "site"
        checked = []

        for html_path in site.glob("*.html"):
            html_text = html_path.read_text(encoding="utf-8")
            for match in re.findall(r"assets/[^\s\"'`)<>]+", html_text):
                asset_path = re.split(r"[?#]", match, maxsplit=1)[0]
                checked.append(match)
                with self.subTest(path=html_path.name, asset=match):
                    self.assertTrue(match.isascii())
                    self.assertTrue((site / asset_path).exists())

        readme_text = (site / "assets" / "slides" / "README.md").read_text(
            encoding="utf-8"
        )
        for match in re.findall(r"assets/[^\s\"'`)<>]+", readme_text):
            checked.append(match)
            with self.subTest(path="README.md", asset=match):
                self.assertTrue(match.isascii())

        self.assertTrue(checked)

    def test_scene_assets_have_webp_variants(self):
        site = ROOT / "site"

        for png in [
            site / "assets" / "seminar-hall.png",
            site / "assets" / "classroom.png",
            site / "assets" / "meeting-room.png",
            site / "assets" / "scenes-16x9" / "seminar-hall.png",
            site / "assets" / "scenes-16x9" / "classroom.png",
            site / "assets" / "scenes-16x9" / "meeting-room.png",
        ]:
            with self.subTest(asset=png.relative_to(site)):
                self.assertTrue(png.with_suffix(".webp").exists())

    def test_home_hero_preloads_webp_background(self):
        text = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

        self.assertIn('rel="preload"', text)
        self.assertIn('href="assets/seminar-hall.webp"', text)
        self.assertIn('type="image/webp"', text)
        self.assertIn("image-set(", text)

    def test_gallery_guide_matches_natural_language_workflow(self):
        text = (ROOT / "site" / "guide.html").read_text(encoding="utf-8")

        self.assertIn("你不需要学代码", text)
        self.assertIn("请帮我安装这个插件：", text)
        self.assertIn("Rimagination/easyslides", text)
        self.assertIn("如果时长、模板或内容重点仍不明确，请先问我并给出选项", text)
        self.assertIn("从参考 PPT 蒸馏模板", text)
        self.assertIn("模板不会把内容锁死", text)
        self.assertIn("assets/slides/work-04/slide-01.jpg", text)
        self.assertNotIn("有道龙虾路线", text)
        self.assertNotIn("准备模型 API Key", text)

    def test_public_case_uses_attention_transformer_deck_images(self):
        site = ROOT / "site"
        text = (site / "index.html").read_text(encoding="utf-8")

        self.assertIn("Attention Is All You Need", text)
        self.assertIn("16 slides", text)
        self.assertIn("literature_minimal", text)
        for index in range(1, 17):
            asset = f"assets/slides/work-01/slide-{index:02d}.jpg"
            self.assertIn(asset, text)
            self.assertTrue((site / asset).exists(), asset)

    def test_public_case_uses_defense_leftnav_deck_images(self):
        site = ROOT / "site"
        text = (site / "index.html").read_text(encoding="utf-8")

        self.assertIn("她为什么换了导师", text)
        self.assertIn("29 slides", text)
        self.assertIn("defense_leftnav", text)
        self.assertIn('"defense"', text)
        for index in range(1, 30):
            asset = f"assets/slides/work-02/slide-{index:02d}.jpg"
            self.assertIn(asset, text)
            self.assertTrue((site / asset).exists(), asset)

    def test_public_case_uses_defense_topnav_deck_images(self):
        site = ROOT / "site"
        text = (site / "index.html").read_text(encoding="utf-8")

        self.assertIn("她为什么换了导师（顶部导航版）", text)
        self.assertIn("defense_topnav", text)
        self.assertIn("assets/decks/she-why-changed-advisor-defense-topnav.pptx", text)
        for index in range(1, 30):
            asset = f"assets/slides/work-03/slide-{index:02d}.jpg"
            self.assertIn(asset, text)
            self.assertTrue((site / asset).exists(), asset)

    def test_public_case_uses_nsfc_grant_deck_images(self):
        site = ROOT / "site"
        text = (site / "index.html").read_text(encoding="utf-8")

        self.assertIn("社会学习促进听觉学习", text)
        self.assertIn("Social Learning Facilitates Auditory Learning", text)
        self.assertIn("14 slides", text)
        self.assertIn("nsfc_defense", text)
        self.assertIn(
            "assets/decks/nih-r01-social-learning-nsfc-defense.pptx",
            text,
        )
        self.assertTrue(
            (site / "assets/decks/nih-r01-social-learning-nsfc-defense.pptx").exists()
        )
        for index in range(1, 15):
            asset = f"assets/slides/work-04/slide-{index:02d}.jpg"
            self.assertIn(asset, text)
            self.assertTrue((site / asset).exists(), asset)

    def test_journal_and_defense_detail_pages_use_meeting_room_scene(self):
        text = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

        scene_function = re.search(
            r"function sceneForType\(type\) \{(?P<body>.*?)\n    \}",
            text,
            flags=re.S,
        )
        self.assertIsNotNone(scene_function)
        body = scene_function.group("body")

        self.assertIn('type === "defense"', body)
        self.assertIn('type === "journal"', body)
        self.assertIn('type === "grant"', body)
        self.assertRegex(
            body,
            r'if \(type === "defense" \|\| type === "journal"\) return "meeting";',
        )
        self.assertNotRegex(body, r'type === "defense".*return "classroom"')


if __name__ == "__main__":
    unittest.main()
