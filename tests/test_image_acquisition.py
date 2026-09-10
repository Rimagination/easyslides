import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
_sample = io.BytesIO()
Image.new("RGB", (1, 1), "white").save(_sample, format="PNG")
ONE_PIXEL_PNG = _sample.getvalue()


class ImageAcquisitionTests(unittest.TestCase):
    def test_scaffold_creates_cover_and_ending_hero_resources(self):
        from scripts.image_acquisition import load_image_resource_manifest, scaffold_hero_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "images" / "image_prompts.json"
            scaffold_hero_manifest(manifest_path, topic="生态系统恢复")
            manifest = load_image_resource_manifest(manifest_path)

            self.assertEqual(manifest["schema_version"], "easyslides.image_resources.v1")
            self.assertEqual(manifest["acquisition"]["path"], "auto")
            self.assertEqual(
                {(item["slide_role"], item["page_role"]) for item in manifest["items"]},
                {("cover", "hero_page"), ("ending", "hero_page")},
            )
            self.assertTrue((manifest_path.with_suffix(".md")).is_file())

    def test_auto_path_matches_ppt_master_fallback_order(self):
        from scripts.image_acquisition import detect_imagegen_capability, resolve_acquisition_path

        self.assertEqual(
            resolve_acquisition_path(environment={})["path"],
            "manual",
        )
        self.assertEqual(
            resolve_acquisition_path(environment={}, host_native_available=True)["path"],
            "host-native",
        )
        self.assertEqual(
            resolve_acquisition_path(environment={"IMAGE_BACKEND": "openai"}, host_native_available=True)["path"],
            "api",
        )
        self.assertEqual(
            resolve_acquisition_path(
                environment={"IMAGE_BACKEND": "openai"},
                explicit_path="host-native",
                host_native_available=False,
            )["path"],
            "host-native",
        )
        capability = detect_imagegen_capability(
            {"EASYSLIDES_HOST_IMAGEGEN": "1"},
            host_native_override=None,
        )
        self.assertTrue(capability["available"])
        self.assertEqual(capability["mode"], "host-native")
        disabled = detect_imagegen_capability(
            {"EASYSLIDES_HOST_IMAGEGEN": "1"},
            host_native_override=False,
        )
        self.assertFalse(disabled["available"])
        self.assertEqual(disabled["mode"], "manual")

    def test_host_native_prepare_writes_request_without_falsely_marking_generated(self):
        from scripts.image_acquisition import load_image_resource_manifest, prepare_acquisition, scaffold_hero_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "image_prompts.json"
            scaffold_hero_manifest(manifest_path, topic="AI 辅助科研")
            report = prepare_acquisition(manifest_path, explicit_path="host-native")
            request_path = Path(report["request"])
            self.assertTrue(request_path.is_file())
            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request["path"], "host-native")
            self.assertEqual(len(request["items"]), 2)
            self.assertEqual(
                {item["status"] for item in load_image_resource_manifest(manifest_path)["items"]},
                {"Pending"},
            )

    def test_reconcile_promotes_existing_files_and_demotes_missing_generated_files(self):
        from scripts.image_acquisition import load_image_resource_manifest, reconcile_manifest, scaffold_hero_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "image_prompts.json"
            image_dir = manifest_path.parent
            scaffold_hero_manifest(manifest_path, topic="研究方法")
            (image_dir / "cover_bg.png").write_bytes(ONE_PIXEL_PNG)
            report = reconcile_manifest(manifest_path)
            self.assertTrue(report["changed"])
            manifest = load_image_resource_manifest(manifest_path)
            statuses = {item["id"]: item["status"] for item in manifest["items"]}
            self.assertEqual(statuses["cover_background"], "Generated")
            self.assertEqual(statuses["ending_background"], "Pending")

            (image_dir / "cover_bg.png").unlink()
            report = reconcile_manifest(manifest_path)
            manifest = load_image_resource_manifest(manifest_path)
            statuses = {item["id"]: item["status"] for item in manifest["items"]}
            self.assertEqual(statuses["cover_background"], "Failed")
            self.assertTrue(report["changed"])

    def test_generated_hero_is_bound_to_slide_ir_and_rendered_below_shell_content(self):
        from scripts.image_acquisition import apply_manifest_to_slide_ir, scaffold_hero_manifest
        from scripts.slide_compiler import compile_slides, render_slide_ir_to_svg
        from scripts.template_compiler import compile_template
        from xml.etree import ElementTree as ET

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "images" / "image_prompts.json"
            scaffold_hero_manifest(manifest_path, topic="气候风险")
            (manifest_path.parent / "cover_bg.png").write_bytes(ONE_PIXEL_PNG)

            template_ir = compile_template("academic_general")["template_ir"]
            deck_plan = {
                "template_id": "academic_general",
                "slides": [
                    {
                        "page": "C01",
                        "role": "cover",
                        "shell_payload": {
                            "LOGO": "LAB",
                            "TITLE": "气候风险",
                            "SUBTITLE": "研究报告",
                            "AUTHOR": "研究组",
                            "ADVISOR": "导师",
                            "INSTITUTION": "研究院",
                            "DATE": "2026",
                        },
                    }
                ],
            }
            slide_ir = compile_slides(deck_plan, template_ir)
            report = apply_manifest_to_slide_ir(slide_ir, manifest_path)
            self.assertEqual(report["bound_backgrounds"], 1)
            self.assertEqual(slide_ir["slides"][0]["background_asset"]["status"], "Generated")

            svg_report = render_slide_ir_to_svg(slide_ir, root / "svg")
            svg_root = ET.parse(svg_report["svg_files"][0]).getroot()
            background = next(node for node in svg_root.iter() if node.attrib.get("data-easyslides-background") == "true")
            scrim = next(node for node in svg_root.iter() if node.attrib.get("data-easyslides-background-scrim") == "true")
            self.assertEqual(background.attrib["preserveAspectRatio"], "xMidYMid slice")
            self.assertEqual(scrim.attrib["fill-opacity"], "0.2000")
            self.assertTrue((root / "svg" / "assets" / "cover_bg.png").is_file())

    def test_unreadable_generated_background_falls_back_to_template_shell(self):
        from PIL import Image
        from scripts.image_acquisition import apply_manifest_to_slide_ir, scaffold_hero_manifest
        from scripts.slide_compiler import compile_slides, render_slide_ir_to_svg
        from scripts.template_compiler import compile_template
        from xml.etree import ElementTree as ET

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "images" / "image_prompts.json"
            scaffold_hero_manifest(manifest_path, topic="readability fallback")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cover = manifest["items"][0]
            cover["safe_area"] = {"box": {"x": 100, "y": 200, "width": 900, "height": 260}}
            cover["background"]["contrast_target"] = 30.0
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            Image.new("RGB", (1280, 720), (120, 120, 120)).save(manifest_path.parent / "cover_bg.png")

            template_ir = compile_template("academic_general")["template_ir"]
            slide_ir = compile_slides(
                {
                    "template_id": "academic_general",
                    "slides": [
                        {
                            "page": "C01",
                            "role": "cover",
                            "shell_payload": {
                                "LOGO": "LAB",
                                "TITLE": "Readability fallback",
                                "SUBTITLE": "Template shell remains safe",
                                "AUTHOR": "Researcher",
                                "ADVISOR": "Advisor",
                                "INSTITUTION": "Institute",
                                "DATE": "2026",
                            },
                        }
                    ],
                },
                template_ir,
            )
            apply_manifest_to_slide_ir(slide_ir, manifest_path)
            svg_report = render_slide_ir_to_svg(slide_ir, root / "svg")
            svg_root = ET.parse(svg_report["svg_files"][0]).getroot()
            self.assertEqual(svg_report["fallback_count"], 1)
            self.assertFalse(any(node.attrib.get("data-easyslides-background") == "true" for node in svg_root.iter()))
            readability = json.loads(Path(svg_report["readability_report"]).read_text(encoding="utf-8"))
            self.assertEqual(readability["status"], "pass")
            self.assertEqual(readability["fallback_count"], 1)

    def test_local_illustration_uses_declared_frame_and_remains_editable(self):
        from scripts.image_acquisition import apply_manifest_to_slide_ir, scaffold_hero_manifest
        from scripts.slide_compiler import compile_slides, render_slide_ir_to_svg
        from scripts.template_compiler import compile_template
        from xml.etree import ElementTree as ET

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "images" / "image_prompts.json"
            scaffold_hero_manifest(manifest_path, topic="local illustration")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["items"].append(
                {
                    "id": "cover_illustration",
                    "filename": "cover_illustration.png",
                    "purpose": "Right-side illustration",
                    "slide_role": "cover",
                    "page_role": "local",
                    "asset_role": "illustration",
                    "placement": {
                        "frame": {"x": 860, "y": 145, "width": 330, "height": 380},
                        "fit": "contain",
                        "opacity": 0.92,
                        "corner_radius": 18,
                    },
                    "text_policy": "none",
                    "aspect_ratio": "4:5",
                    "status": "Pending",
                    "prompt": "No text; quiet research illustration.",
                }
            )
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            (manifest_path.parent / "cover_illustration.png").write_bytes(ONE_PIXEL_PNG)

            template_ir = compile_template("academic_general")["template_ir"]
            deck_plan = {
                "template_id": "academic_general",
                "slides": [
                    {
                        "page": "C01",
                        "role": "cover",
                        "image_bindings": [{"resource_id": "cover_illustration"}],
                        "shell_payload": {
                            "LOGO": "LAB",
                            "TITLE": "Local illustration",
                            "SUBTITLE": "Declared placement",
                            "AUTHOR": "Researcher",
                            "ADVISOR": "Advisor",
                            "INSTITUTION": "Institute",
                            "DATE": "2026",
                        },
                    }
                ],
            }
            slide_ir = compile_slides(deck_plan, template_ir)
            report = apply_manifest_to_slide_ir(slide_ir, manifest_path)
            self.assertEqual(report["bound_assets"], 1)
            self.assertEqual(report["bound_backgrounds"], 0)
            self.assertEqual(slide_ir["slides"][0]["image_assets"][0]["asset_role"], "illustration")

            svg_report = render_slide_ir_to_svg(slide_ir, root / "svg")
            svg_root = ET.parse(svg_report["svg_files"][0]).getroot()
            illustration = next(
                node
                for node in svg_root.iter()
                if node.attrib.get("data-easyslides-asset") == "true"
            )
            self.assertEqual(illustration.attrib["x"], "860.0")
            self.assertEqual(illustration.attrib["width"], "330.0")
            self.assertEqual(illustration.attrib["preserveAspectRatio"], "xMidYMid meet")
            self.assertTrue((root / "svg" / "assets" / "cover_illustration.png").is_file())

    def test_non_hero_image_resource_id_is_bound_without_explicit_binding_list(self):
        from scripts.image_acquisition import apply_manifest_to_slide_ir, scaffold_hero_manifest
        from scripts.slide_compiler import compile_slides
        from scripts.template_compiler import compile_template

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "images" / "image_prompts.json"
            scaffold_hero_manifest(manifest_path, topic="content decorative image")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["items"].append(
                {
                    "id": "p01_illustration",
                    "filename": "p01_illustration.png",
                    "purpose": "Decorative local illustration",
                    "slide_role": "content",
                    "page_role": "local",
                    "asset_role": "illustration",
                    "placement": {
                        "frame": {"x": 800, "y": 160, "width": 360, "height": 360},
                        "fit": "contain",
                    },
                    "text_policy": "none",
                    "aspect_ratio": "4:5",
                    "status": "Pending",
                    "prompt": "Decorative academic illustration; no text.",
                }
            )
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            (manifest_path.parent / "p01_illustration.png").write_bytes(ONE_PIXEL_PNG)

            template_ir = compile_template("academic_general")["template_ir"]
            slide_ir = compile_slides(
                {
                    "template_id": "academic_general",
                    "slides": [
                        {
                            "page": "P01",
                            "role": "content",
                            "content_shape": "figure",
                            "image_resource_id": "p01_illustration",
                            "shell_payload": {"PAGE_TITLE": "Decorative"},
                            "body_payload": {
                                "FIGURE": "p01_illustration.png",
                                "FIGURE_CAPTION": "Decorative illustration",
                                "KEY_MESSAGE": "A decorative visual stays separate from evidence.",
                                "EVIDENCE_01": "A",
                                "EVIDENCE_02": "B",
                                "EVIDENCE_03": "C",
                            },
                        }
                    ],
                },
                template_ir,
            )
            report = apply_manifest_to_slide_ir(slide_ir, manifest_path)
            self.assertEqual(report["bound_assets"], 1)
            self.assertEqual(slide_ir["slides"][0]["image_assets"][0]["resource_id"], "p01_illustration")


if __name__ == "__main__":
    unittest.main()
