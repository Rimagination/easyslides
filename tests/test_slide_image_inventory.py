import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SlideImageInventoryTests(unittest.TestCase):
    def test_valid_inventory_passes(self):
        from scripts.slide_image_inventory import validate_inventory

        report = validate_inventory(
            {
                "schema_version": "easyslides.slide_image_inventory.v1",
                "slides": [
                    {
                        "slide_id": "s01",
                        "elements": [
                            {
                                "element_id": "s01_e01",
                                "description": "clean illustration",
                                "bbox_percent": {"x": 10, "y": 10, "w": 30, "h": 40},
                                "layer": "A",
                                "implementation": "imagegen",
                                "asset_policy": {"no_text": True},
                                "z_order": 1,
                            },
                            {
                                "element_id": "s01_e02",
                                "description": "title",
                                "bbox_percent": {"x": 10, "y": 5, "w": 40, "h": 8},
                                "layer": "C",
                                "implementation": "native_text",
                                "text": "Title",
                                "z_order": 2,
                            },
                        ],
                        "completeness_check": {"performed": True, "layer_a_count": 1},
                    }
                ],
            }
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)
        self.assertEqual(report["layer_counts"]["visual_asset"], 1)
        self.assertEqual(report["layer_counts"]["editable_text"], 1)

    def test_blocks_dirty_crop_and_baked_text(self):
        from scripts.slide_image_inventory import validate_inventory

        report = validate_inventory(
            {
                "schema_version": "easyslides.slide_image_inventory.v1",
                "slides": [
                    {
                        "slide_id": "s01",
                        "elements": [
                            {
                                "element_id": "s01_e01",
                                "description": "cropped icon with label",
                                "bbox_percent": {"x": 0, "y": 0, "w": 90, "h": 98},
                                "layer": "A",
                                "implementation": "rect_crop",
                                "contains_text": True,
                                "z_order": 1,
                            }
                        ],
                        "completeness_check": {"performed": False},
                    }
                ],
            }
        )

        self.assertEqual(report["status"], "fail")
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("INVENTORY-A-ASSET-CONTAINS-TEXT", codes)
        self.assertIn("INVENTORY-A-ASSET-RECT-CROP", codes)
        self.assertIn("INVENTORY-FULL-SLIDE-ASSET", codes)
        self.assertIn("INVENTORY-COMPLETENESS-CHECK-MISSING", codes)

    def test_blocks_semantic_visuals_marked_as_native_structure(self):
        from scripts.slide_image_inventory import validate_inventory

        report = validate_inventory(
            {
                "schema_version": "easyslides.slide_image_inventory.v1",
                "slides": [
                    {
                        "slide_id": "s01",
                        "elements": [
                            {
                                "element_id": "s01_e01",
                                "description": "mangrove tree illustration with roots",
                                "object_class": "foreground_asset",
                                "bbox_percent": {"x": 5, "y": 20, "w": 25, "h": 50},
                                "layer": "B",
                                "implementation": "native_shape",
                                "z_order": 2,
                            }
                        ],
                        "completeness_check": {"performed": True, "layer_a_count": 0},
                    }
                ],
            }
        )

        self.assertEqual(report["status"], "fail")
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("INVENTORY-B-SEMANTIC-ASSET-NATIVE", codes)

    def test_masked_preserved_asset_passes_preservation_contract(self):
        from scripts.slide_image_inventory import validate_inventory

        report = validate_inventory(
            {
                "schema_version": "easyslides.slide_image_inventory.v1",
                "slides": [
                    {
                        "slide_id": "s01",
                        "elements": [
                            {
                                "element_id": "s01_e01",
                                "description": "scientific figure preserved as alpha-backed visual asset",
                                "object_class": "scientific_figure",
                                "bbox_percent": {"x": 20, "y": 20, "w": 35, "h": 35},
                                "layer": "A",
                                "implementation": "preserve_masked_source",
                                "asset_policy": {
                                    "no_text": True,
                                    "alpha_backed": True,
                                    "ratio_safe_placement": True,
                                    "preserve_reason": "scientific evidence figure",
                                },
                                "z_order": 1,
                            }
                        ],
                        "completeness_check": {"performed": True, "layer_a_count": 1},
                    }
                ],
            }
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)

    def test_strict_inventory_blocks_clipped_circles_plain_exponents_scatter_and_unmeasured_text(self):
        from scripts.slide_image_inventory import validate_inventory

        report = validate_inventory(
            {
                "schema_version": "easyslides.slide_image_inventory.v1",
                "source_fidelity": "strict",
                "slides": [
                    {
                        "slide_id": "s01",
                        "elements": [
                            {
                                "element_id": "circle_asset",
                                "description": "circular ecosystem icon with complete ring",
                                "object_class": "foreground_asset",
                                "bbox_percent": {"x": 70, "y": 70, "w": 15, "h": 15},
                                "layer": "A",
                                "implementation": "imagegen",
                                "asset_policy": {"no_text": True},
                                "z_order": 1,
                            },
                            {
                                "element_id": "scatter_plot",
                                "description": "scatter plot with many data points",
                                "bbox_percent": {"x": 35, "y": 35, "w": 30, "h": 25},
                                "layer": "B",
                                "implementation": "native_shape",
                                "z_order": 2,
                            },
                            {
                                "element_id": "tick_label",
                                "description": "x axis tick label",
                                "bbox_percent": {"x": 42, "y": 70, "w": 4, "h": 3},
                                "layer": "C",
                                "implementation": "native_text",
                                "text": "10^-1",
                                "z_order": 3,
                            },
                        ],
                        "completeness_check": {"performed": True, "layer_a_count": 1},
                    }
                ],
            }
        )

        codes = {issue["code"] for issue in report["issues"]}
        self.assertEqual(report["status"], "fail")
        self.assertIn("INVENTORY-A-CLOSED-SHAPE-CLIP-CHECK-MISSING", codes)
        self.assertIn("INVENTORY-B-SCATTER-DISTRIBUTION-CONTRACT-MISSING", codes)
        self.assertIn("INVENTORY-C-EXPONENT-NATIVE-RUNS-MISSING", codes)
        self.assertIn("INVENTORY-C-TEXT-GEOMETRY-SOURCE-MISSING", codes)

    def test_strict_inventory_accepts_measured_text_and_scatter_contracts(self):
        from scripts.slide_image_inventory import validate_inventory

        report = validate_inventory(
            {
                "schema_version": "easyslides.slide_image_inventory.v1",
                "source_fidelity": "strict",
                "slides": [
                    {
                        "slide_id": "s01",
                        "elements": [
                            {
                                "element_id": "circle_asset",
                                "description": "circular ecosystem icon with complete ring",
                                "object_class": "foreground_asset",
                                "bbox_percent": {"x": 70, "y": 70, "w": 15, "h": 15},
                                "layer": "A",
                                "implementation": "imagegen",
                                "asset_policy": {
                                    "no_text": True,
                                    "closed_shape_complete": True,
                                    "foreground_not_clipped": True,
                                },
                                "z_order": 1,
                            },
                            {
                                "element_id": "scatter_plot",
                                "description": "scatter plot with many data points",
                                "bbox_percent": {"x": 35, "y": 35, "w": 30, "h": 25},
                                "layer": "B",
                                "implementation": "native_shape",
                                "data_fidelity": {
                                    "source_points_px": [[10, 12], [18, 22]],
                                    "plot_area_px": [100, 100, 300, 220],
                                    "distribution_source": "source image measurement",
                                },
                                "z_order": 2,
                            },
                            {
                                "element_id": "tick_label",
                                "description": "x axis tick label",
                                "bbox_percent": {"x": 42, "y": 70, "w": 4, "h": 3},
                                "layer": "C",
                                "implementation": "native_text",
                                "text": "10^-1",
                                "native_superscript": True,
                                "font_size_source": "ink-measured",
                                "z_order": 3,
                            },
                        ],
                        "completeness_check": {"performed": True, "layer_a_count": 1},
                    }
                ],
            }
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_count"], 0)

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory_path = root / "inventory.json"
            report_path = root / "report.json"
            inventory_path.write_text(
                json.dumps(
                    {
                        "schema_version": "easyslides.slide_image_inventory.v1",
                        "slides": [{"slide_id": "s01", "elements": [], "completeness_check": {"performed": True}}],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/slide_image_inventory.py",
                    "validate",
                    str(inventory_path),
                    "--report",
                    str(report_path),
                    "--quiet",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "easyslides.slide_image_inventory_report.v1")


if __name__ == "__main__":
    unittest.main()
