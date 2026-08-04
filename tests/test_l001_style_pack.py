import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "templates" / "style_packs" / "l001_notebook_defense"
VALIDATOR = ROOT / "scripts" / "validate_l001.py"


@unittest.skipUnless(
    TEMPLATE_DIR.is_dir(),
    "L001 is an archived external style pack and is not part of this checkout.",
)
class L001StylePackTests(unittest.TestCase):
    def test_style_pack_contains_locked_tokens_and_layouts(self):
        tokens_path = TEMPLATE_DIR / "design_tokens.json"
        layouts_path = TEMPLATE_DIR / "layouts.json"

        self.assertTrue(tokens_path.exists(), "design_tokens.json is required")
        self.assertTrue(layouts_path.exists(), "layouts.json is required")

        tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
        self.assertEqual(tokens["style_system"], "l001_notebook_defense")
        self.assertEqual(tokens["colors"]["primary"], "#8B0012")
        self.assertIn("Microsoft YaHei", tokens["fonts"]["cjk"])
        self.assertEqual(tokens["closing"]["default_title"], "恳请老师批评指正！")

        layouts = json.loads(layouts_path.read_text(encoding="utf-8"))
        page_types = {item["page_type"] for item in layouts["layouts"]}
        self.assertEqual(page_types, {"cover", "toc", "section", "content", "closing"})

        for filename in (
            "01_cover.svg",
            "02_toc.svg",
            "03_section.svg",
            "04_content.svg",
            "05_closing.svg",
        ):
            svg = (TEMPLATE_DIR / filename).read_text(encoding="utf-8")
            self.assertIn('viewBox="0 0 1280 720"', svg)
            self.assertIn("#8B0012", svg)
            self.assertNotIn("#003366", svg)
            self.assertNotRegex(svg, r"<g\b[^>]*\bopacity=")

    def test_validator_passes_pack_and_rejects_primary_color_drift(self):
        self.assertTrue(VALIDATOR.exists(), "scripts/validate_l001.py is required")

        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(TEMPLATE_DIR), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertGreaterEqual(report["checked_files"], 7)

        with tempfile.TemporaryDirectory() as tmp:
            drifted = Path(tmp) / "l001_notebook_defense"
            shutil.copytree(TEMPLATE_DIR, drifted)
            token_path = drifted / "design_tokens.json"
            tokens = json.loads(token_path.read_text(encoding="utf-8"))
            tokens["colors"]["primary"] = "#130000"
            token_path.write_text(
                json.dumps(tokens, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            drift_result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(drifted), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertNotEqual(drift_result.returncode, 0)
        self.assertIn("L001-COLOR-PRIMARY", drift_result.stdout)

    def test_l001_render_module_exports_svg_helpers(self):
        l001 = import_module("scripts.styles.l001")
        for name in (
            "draw_l001_brand",
            "draw_l001_dots",
            "draw_l001_toc",
            "draw_l001_section",
            "draw_l001_content_shell",
            "draw_l001_closing",
        ):
            self.assertTrue(callable(getattr(l001, name)), name)

        section_svg = l001.draw_l001_section(
            section_number="03",
            part_label="PART THREE",
            section_title="临界证据",
            section_subtitle="Tipping evidence",
        )
        root = ET.fromstring(section_svg)
        self.assertEqual(root.attrib["viewBox"], "0 0 1280 720")
        self.assertIn("#8B0012", section_svg)
        self.assertIn("PART THREE", section_svg)
        self.assertNotRegex(section_svg, r"<g\b[^>]*\bopacity=")

        closing_svg = l001.draw_l001_closing()
        self.assertIn("恳请老师批评指正！", closing_svg)


if __name__ == "__main__":
    unittest.main()
