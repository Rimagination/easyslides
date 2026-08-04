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
TEMPLATE_DIR = ROOT / "templates" / "style_packs" / "guizang_ppt"
VALIDATOR = ROOT / "scripts" / "validate_guizang.py"


@unittest.skipUnless(
    TEMPLATE_DIR.is_dir(),
    "Guizang is an archived external style pack and is not part of this checkout.",
)
class GuizangStylePackTests(unittest.TestCase):
    def test_style_pack_contains_upstream_tokens_and_layout_contracts(self):
        tokens = json.loads((TEMPLATE_DIR / "design_tokens.json").read_text(encoding="utf-8"))
        layouts = json.loads((TEMPLATE_DIR / "layouts.json").read_text(encoding="utf-8"))

        self.assertEqual(tokens["style_system"], "guizang_ppt")
        self.assertEqual(tokens["source"]["upstream_repo"], "https://github.com/op7418/guizang-ppt-skill")
        self.assertEqual(len(tokens["variants"]["style_a_editorial_ink"]["themes"]), 5)
        self.assertEqual(len(tokens["variants"]["style_b_swiss"]["themes"]), 4)
        self.assertEqual(tokens["variants"]["style_b_swiss"]["themes"]["ikb"]["accent"], "#002FA7")

        swiss_layouts = layouts["variants"]["style_b_swiss"]["registered_layouts"]
        self.assertEqual(swiss_layouts, [f"S{idx:02d}" for idx in range(1, 23)])
        native_layouts = layouts["variants"]["style_b_swiss"]["native_layouts"]
        self.assertEqual([item["id"] for item in native_layouts], swiss_layouts)

        shell_files = [
            shell["template"]
            for variant in layouts["variants"].values()
            for shell in variant["native_shells"]
        ]
        self.assertEqual(len(shell_files), 9)
        native_files = [item["template"] for item in native_layouts]
        self.assertEqual(len(native_files), 22)

        for filename in shell_files + native_files:
            svg = (TEMPLATE_DIR / filename).read_text(encoding="utf-8")
            root = ET.fromstring(svg)
            self.assertEqual(root.attrib["viewBox"], "0 0 1280 720")
            self.assertNotIn("foreignObject", svg)
            self.assertNotIn("<script", svg)
            if filename.startswith("swiss/"):
                self.assertEqual(root.attrib["data-style"], "guizang-style-b")
                self.assertIn(root.attrib["data-layout"], swiss_layouts)

    def test_validator_passes_pack_and_rejects_token_color_drift(self):
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
        self.assertGreaterEqual(report["checked_files"], 33)

        with tempfile.TemporaryDirectory() as tmp:
            drifted = Path(tmp) / "guizang_ppt"
            shutil.copytree(TEMPLATE_DIR, drifted)
            token_path = drifted / "design_tokens.json"
            tokens = json.loads(token_path.read_text(encoding="utf-8"))
            tokens["variants"]["style_b_swiss"]["themes"]["ikb"]["accent"] = "#ABCDEF"
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
        self.assertIn("GUZ-COLOR-DRIFT", drift_result.stdout)

    def test_guizang_render_module_exports_editable_svg_helpers(self):
        guizang = import_module("scripts.styles.guizang")
        for name in (
            "draw_style_a_cover",
            "draw_style_a_content",
            "draw_style_b_cover",
            "draw_style_b_image_hero",
        ):
            self.assertTrue(callable(getattr(guizang, name)), name)

        cover = guizang.draw_style_b_cover(title="Native", title_line_2="Swiss")
        root = ET.fromstring(cover)
        self.assertEqual(root.attrib["viewBox"], "0 0 1280 720")
        self.assertEqual(root.attrib["data-style"], "guizang-style-b")
        self.assertIn("#002FA7", cover)
        self.assertIn("Native", cover)

        content = guizang.draw_style_a_content(page_title="Editorial", body_lines=["One", "Two"])
        self.assertIn("#0A0A0B", content)
        self.assertIn("Editorial", content)

    def test_style_pack_contract_resolves_spec_lock_layouts(self):
        contract = import_module("scripts.style_pack_contract")
        with tempfile.TemporaryDirectory() as tmp:
            spec_lock = Path(tmp) / "spec_lock.md"
            spec_lock.write_text(
                "\n".join(
                    [
                        "## style_pack",
                        "- package: guizang_ppt",
                        "- variant: style_b_swiss",
                        "- theme: ikb",
                        "- layout_source: templates/style_packs/guizang_ppt",
                        "",
                        "## page_layouts",
                        "- P01: S01",
                        "- P02: swiss/S08_duo_compare",
                        "- P03: templates/style_packs/guizang_ppt/swiss/S22_image_hero.svg",
                    ]
                ),
                encoding="utf-8",
            )

            report = contract.validate_spec_lock(spec_lock, repo_root=ROOT)
            validator_result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    str(TEMPLATE_DIR),
                    "--spec-lock",
                    str(spec_lock),
                    "--repo-root",
                    str(ROOT),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(validator_result.returncode, 0, validator_result.stdout + validator_result.stderr)
        validator_report = json.loads(validator_result.stdout)
        self.assertEqual(validator_report["style_pack_contract"]["status"], "pass")
        self.assertEqual(
            report["resolved_layouts"]["P01"]["path"],
            "templates/style_packs/guizang_ppt/swiss/S01_index_cover.svg",
        )
        self.assertEqual(
            report["resolved_layouts"]["P02"]["path"],
            "templates/style_packs/guizang_ppt/swiss/S08_duo_compare.svg",
        )
        self.assertEqual(
            report["resolved_layouts"]["P03"]["path"],
            "templates/style_packs/guizang_ppt/swiss/S22_image_hero.svg",
        )

    def test_style_pack_contract_rejects_unknown_theme_and_layout(self):
        contract = import_module("scripts.style_pack_contract")
        with tempfile.TemporaryDirectory() as tmp:
            spec_lock = Path(tmp) / "spec_lock.md"
            spec_lock.write_text(
                "\n".join(
                    [
                        "## style_pack",
                        "- package: guizang_ppt",
                        "- variant: style_b_swiss",
                        "- theme: not_a_theme",
                        "",
                        "## page_layouts",
                        "- P01: S99",
                    ]
                ),
                encoding="utf-8",
            )

            report = contract.validate_spec_lock(spec_lock, repo_root=ROOT)

        codes = {item["code"] for item in report["issues"]}
        self.assertEqual(report["status"], "fail")
        self.assertIn("GUZ-STYLE-PACK-THEME", codes)
        self.assertIn("GUZ-STYLE-PACK-LAYOUT", codes)

    def test_style_pack_contract_accepts_legacy_guizang_path_aliases(self):
        contract = import_module("scripts.style_pack_contract")
        legacy_source = "templates/" + "guizang_ppt"
        legacy_layout = legacy_source + "/swiss/S01_index_cover.svg"
        with tempfile.TemporaryDirectory() as tmp:
            spec_lock = Path(tmp) / "spec_lock.md"
            spec_lock.write_text(
                "\n".join(
                    [
                        "## style_pack",
                        "- package: guizang_ppt",
                        "- variant: style_b_swiss",
                        "- theme: ikb",
                        f"- layout_source: {legacy_source}",
                        "",
                        "## page_layouts",
                        f"- P01: {legacy_layout}",
                    ]
                ),
                encoding="utf-8",
            )

            report = contract.validate_spec_lock(spec_lock, repo_root=ROOT)

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["style_pack"]["root"], "templates/style_packs/guizang_ppt")
        self.assertEqual(
            report["resolved_layouts"]["P01"]["path"],
            "templates/style_packs/guizang_ppt/swiss/S01_index_cover.svg",
        )


if __name__ == "__main__":
    unittest.main()
