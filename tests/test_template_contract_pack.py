import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_slot_guided_fixture(root: Path) -> Path:
    template_dir = root / "fixture_slot"
    template_dir.mkdir()
    write_json(
        template_dir / "layouts.json",
        {
            "template_id": "fixture_slot",
            "default_scenario": "literature_report",
            "style_system": "fixture_blue",
            "colors": {"primary": "#123456"},
            "global_contract": {"replication_mode": "slot_guided_mirror"},
            "pages": [
                {
                    "id": "cover",
                    "svg": "01_cover.svg",
                    "page_type": "cover",
                    "story_role": "cover",
                    "slot_model": "cover",
                    "source_slide": 1,
                },
                {
                    "id": "evidence",
                    "svg": "02_evidence.svg",
                    "page_type": "content",
                    "story_role": "evidence",
                    "slot_model": "evidence",
                    "role_fit": ["result"],
                    "density_score": 3,
                    "source_slide": 2,
                },
            ],
            "slot_models": {
                "cover": [{"slot_id": "TITLE", "role": "title", "max_lines": 2}],
                "evidence": [
                    {"slot_id": "PAGE_TITLE", "role": "title", "max_lines": 2},
                    {"slot_id": "MAIN_EXHIBIT", "role": "main_figure", "image_fit": "contain"},
                    {"slot_id": "FIGURE_CAPTION", "role": "caption", "max_lines": 2},
                ],
            },
            "text_fit_policy": {
                "schema_version": "easyslides.template_text_fit_policy.v1",
                "overflow_strategy_order": ["wrap_text", "split_across_slides"],
            },
        },
    )
    write_json(
        template_dir / "page_catalog.json",
        {
            "pages": [
                {"id": "cover", "density_score": 1, "best_for": "opening"},
                {"id": "evidence", "density_score": 3, "best_for": "figure evidence", "avoid": "dense tables"},
            ]
        },
    )
    write_json(template_dir / "story_structure.json", {"default_scenario": "literature_report"})
    (template_dir / "design_spec.md").write_text("# Fixture\n", encoding="utf-8")
    (template_dir / "rules.md").write_text("# Fixture Rules\n", encoding="utf-8")
    (template_dir / "01_cover.svg").write_text("<svg />\n", encoding="utf-8")
    (template_dir / "02_evidence.svg").write_text("<svg />\n", encoding="utf-8")
    return template_dir


class TemplateContractPackTests(unittest.TestCase):
    def test_builds_contract_pack_from_slot_guided_template_sidecars(self):
        from scripts.template_contract_pack import build_contract_pack

        with tempfile.TemporaryDirectory() as tmp:
            template_dir = make_slot_guided_fixture(Path(tmp))
            pack = build_contract_pack(template_dir)

        self.assertEqual(pack["template"]["schema_version"], "easyslides.template_pack.v1")
        self.assertEqual(pack["template"]["template_id"], "fixture_slot")
        self.assertEqual(pack["template"]["runtime_source_of_truth"], "templates_layout_svgs")
        self.assertFalse(pack["template"]["source_policy"]["raw_pptx_required_at_runtime"])
        self.assertEqual(pack["template"]["layout_count"], 2)
        self.assertEqual(pack["template"]["scenarios"], ["literature_report"])

        roster = pack["layout_roster"]
        self.assertEqual(roster["schema_version"], "easyslides.template_layout_roster.v1")
        self.assertEqual(roster["layouts"][0]["layout_id"], "FS-S01")
        self.assertEqual(roster["layouts"][0]["role_fit"], ["cover"])
        self.assertEqual(roster["layouts"][1]["role_fit"], ["result"])
        self.assertTrue(roster["layouts"][1]["svg_path"].endswith("fixture_slot/02_evidence.svg"))

        slots = pack["slot_contracts"]
        self.assertEqual(slots["schema_version"], "easyslides.template_slot_contracts.v1")
        self.assertEqual(slots["replacement_rule"], "replace_declared_slots_preserve_template_geometry")
        evidence = slots["layouts"][1]
        self.assertIn("MAIN_EXHIBIT", evidence["image_slots"])
        self.assertIn("PAGE_TITLE", evidence["text_slots"])
        self.assertIn("FIGURE_CAPTION", evidence["text_slots"])
        self.assertNotIn("FIGURE_CAPTION", evidence["image_slots"])

    def test_cli_writes_contract_sidecars_without_private_paths(self):
        from scripts.template_contract_pack import write_contract_pack

        with tempfile.TemporaryDirectory() as tmp:
            template_dir = make_slot_guided_fixture(Path(tmp))
            written = write_contract_pack(template_dir)

            self.assertEqual(
                {path.name for path in written},
                {"template.json", "layout_roster.json", "slot_contracts.json", "links.json"},
            )
            template = json.loads((template_dir / "template.json").read_text(encoding="utf-8"))
            slots_text = (template_dir / "slot_contracts.json").read_text(encoding="utf-8")

        self.assertFalse(template["source_policy"]["contains_local_paths"])
        self.assertNotIn("D:\\", slots_text)
        self.assertNotIn("private_asset_bank", slots_text)

    def test_cli_prints_written_paths_for_external_template_directory(self):
        from scripts.template_contract_pack import main

        with tempfile.TemporaryDirectory() as tmp:
            template_dir = make_slot_guided_fixture(Path(tmp))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([str(template_dir)])

        self.assertEqual(code, 0)
        self.assertIn("Wrote 4 contract sidecar", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
