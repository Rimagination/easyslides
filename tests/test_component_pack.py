import json
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _make_pack(
    root: Path,
    pack_id: str = "demo-pack",
    component_id: str = "environment_summary",
    version: str = "0.1.0",
) -> Path:
    pack_root = root / pack_id
    component_root = pack_root / "components" / component_id
    _write_json(
        pack_root / "pack.json",
        {
            "schema_version": "easyslides.component_pack.v1",
            "pack_id": pack_id,
            "version": version,
            "display_name": "Demo Environment Pack",
            "description": "A test pack for environmental science components.",
            "license": "MIT",
            "trust": {"mode": "declarative_only", "permissions": [], "code_execution": False},
            "dependencies": {"component_packs": []},
            "design_tokens": {
                "mode": "self_contained",
                "source": "assets/design_tokens.json",
                "required": ["color.accent", "surface.panel", "text.primary"],
            },
            "components": [{"component_id": component_id, "path": f"components/{component_id}"}],
        },
    )
    _write_json(
        component_root / "component.json",
        {
            "schema_version": "easyslides.component_package.v1",
            "component_id": component_id,
            "asset_id": f"component_package/{component_id}",
            "display_name": "Environment Summary",
            "source_asset_id": "community/environment_summary",
            "granularity": "component_package",
            "render_backend": "component_package",
            "renderer_id": "evidence_stack",
            "render_targets": ["svg", "native_pptx"],
            "selection": {
                "content_shapes": ["definition"],
                "page_roles": ["overview"],
                "item_count_min": 1,
                "item_count_max": 1,
            },
            "input_schema": {
                "schema_version": "easyslides.component_input_schema.v1",
                "type": "object",
                "required": ["claim", "items"],
                    "additional_properties": False,
                "properties": {
                    "claim": {"type": "string", "min_length": 1, "max_length": 100},
                    "items": {
                        "type": "array",
                        "min_items": 1,
                        "max_items": 1,
                        "items": {
                            "type": "object",
                            "required": ["evidence"],
                                "additional_properties": False,
                            "properties": {
                                "evidence": {"type": "string", "min_length": 1, "max_length": 160}
                            },
                        },
                    },
                },
            },
            "slots": [
                {
                    "slot_id": "title",
                    "kind": "text",
                    "required": True,
                    "capacity": {"max_lines": 1, "max_chars_per_line_zh": 18},
                    "alignment": {"vertical": "middle", "text_center_y": "container_center_y"},
                }
            ],
            "qa": {
                "required_gates": ["component_package_contract"],
                "alignment_invariants": [
                    {
                        "id": "text_vertical_center",
                        "scope": "text_in_container",
                        "rule": "text_center_y_matches_container_center_y",
                        "tolerance_px": 2,
                        "severity": "error",
                    }
                ],
            },
            "stories": [{"story_id": "default", "payload": "stories/default.json", "expected_status": "pass"}],
        },
    )
    _write_json(
        component_root / "stories" / "default.json",
        {
            "schema_version": "easyslides.component_story.v1",
            "story_id": "default",
            "payload": {
                "claim": "Clean water access improves environmental health",
                "items": [{"evidence": "Water quality monitoring shows measurable improvement."}],
            },
        },
    )
    (pack_root / "assets" / "icons" / "water.svg").parent.mkdir(parents=True, exist_ok=True)
    (pack_root / "assets" / "icons" / "water.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>\n',
        encoding="utf-8",
    )
    _write_json(
        pack_root / "assets" / "design_tokens.json",
        {
            "color": {"accent": "#1F6FEB"},
            "surface": {"panel": "#F5F8FC"},
            "text": {"primary": "#152033"},
        },
    )
    return pack_root


class ComponentPackTests(unittest.TestCase):
    def test_generic_git_source_can_carry_a_version_reference(self):
        from scripts.component_pack import _generic_git_source

        self.assertEqual(
            _generic_git_source("https://example.com/easyslides/pack.git#v1.2.3"),
            ("https://example.com/easyslides/pack.git", "v1.2.3"),
        )

    def test_valid_pack_passes(self):
        from scripts.component_pack import validate_component_pack

        with tempfile.TemporaryDirectory() as tmp:
            report = validate_component_pack(_make_pack(Path(tmp)))

        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(report["pack_id"], "demo-pack")
        self.assertEqual(report["component_count"], 1)

    def test_executable_files_are_rejected(self):
        from scripts.component_pack import validate_component_pack

        with tempfile.TemporaryDirectory() as tmp:
            pack = _make_pack(Path(tmp))
            (pack / "components" / "environment_summary" / "render.py").write_text("print('no')\n", encoding="utf-8")
            report = validate_component_pack(pack)

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PACK-FILE", {item["code"] for item in report["issues"]})

    def test_local_install_rebuilds_registry(self):
        from scripts.component_pack import install_component_pack, list_component_packs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = _make_pack(root / "source")
            target = root / "installed"
            registry_path = root / "component_registry.json"
            report = install_component_pack(
                pack,
                target=target,
                rebuild_registry=True,
                registry_output=registry_path,
            )
            listing = list_component_packs(target)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            asset_manifest_exists = (target / "demo-pack" / "assets" / "asset_manifest.json").is_file()
            lock = json.loads((target / "demo-pack" / "pack.lock.json").read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "pass", report.get("issues"))
        self.assertEqual(listing["pack_count"], 1)
        self.assertIn("component_package/environment_summary", {asset["asset_id"] for asset in registry["assets"]})
        self.assertIn("demo-pack", {pack["pack_id"] for pack in registry["component_packs"]})
        installed_asset = next(asset for asset in registry["assets"] if asset["asset_id"] == "component_package/environment_summary")
        self.assertEqual(installed_asset["metadata"]["pack"]["version"], "0.1.0")
        self.assertEqual(registry["media_asset_count"], 1)
        self.assertTrue(asset_manifest_exists)
        self.assertEqual(lock["version"], "0.1.0")
        self.assertTrue(lock["content_sha256"])

    def test_missing_required_dependency_blocks_install(self):
        from scripts.component_pack import install_component_pack

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = _make_pack(root / "source")
            manifest_path = pack / "pack.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dependencies"] = {
                "component_packs": [
                    {"pack_id": "missing-pack", "version_range": "^1.0.0"}
                ]
            }
            _write_json(manifest_path, manifest)
            report = install_component_pack(pack, target=root / "installed", rebuild_registry=False)

        self.assertEqual(report["status"], "fail")
        self.assertIn("COMPONENT-PACK-DEPENDENCY-MISSING", {issue["code"] for issue in report["issues"]})

    def test_update_rollback_and_remove_keep_registry_consistent(self):
        from scripts.component_pack import (
            install_component_pack,
            remove_component_pack,
            rollback_component_pack,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "installed"
            registry_path = root / "component_registry.json"
            v1 = _make_pack(root / "v1", version="0.1.0")
            v2 = _make_pack(root / "v2", version="0.2.0")

            first = install_component_pack(v1, target=target, rebuild_registry=True, registry_output=registry_path)
            updated = install_component_pack(v2, target=target, force=True, rebuild_registry=True, registry_output=registry_path)
            rolled_back = rollback_component_pack("demo-pack", target=target, registry_output=registry_path)
            removed = remove_component_pack("demo-pack", target=target, registry_output=registry_path)

        self.assertEqual(first["status"], "pass", first)
        self.assertEqual(updated["status"], "pass", updated)
        self.assertEqual(rolled_back["status"], "pass", rolled_back)
        self.assertEqual(rolled_back["version"], "0.1.0")
        self.assertEqual(removed["status"], "pass", removed)
        self.assertFalse((target / "demo-pack").exists())

    def test_installed_pack_flows_through_gallery_and_native_pptx(self):
        from scripts.component_gallery import build_component_gallery
        from scripts.component_pack import install_component_pack
        from scripts.component_pptx_renderer import build_component_pptx

        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        pack = _make_pack(root / "source")
        target = root / "installed"
        install_report = install_component_pack(pack, target=target, rebuild_registry=False)
        gallery = build_component_gallery(
            packages_root=Path(__file__).resolve().parents[1] / "templates" / "components" / "packages",
            installed_root=target,
            output_dir=root / "gallery",
        )
        pptx = build_component_pptx(
            packages_root=Path(__file__).resolve().parents[1] / "templates" / "components" / "packages",
            installed_root=target,
            output_path=root / "gallery" / "component_gallery.pptx",
            validate_text_layout=True,
        )

        self.assertEqual(install_report["status"], "pass", install_report)
        self.assertEqual(gallery["status"], "pass", gallery)
        self.assertEqual(gallery["package_count"], 7)
        self.assertEqual(pptx["status"], "pass", pptx)
        self.assertEqual(pptx["text_layout_status"], "pass")


if __name__ == "__main__":
    unittest.main()
