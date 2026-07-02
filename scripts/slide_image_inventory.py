#!/usr/bin/env python3
"""Validate a slide-image reconstruction element inventory.

The inventory is the handoff contract between visual analysis and PPTX
assembly: every visible element from the source image should be classified as
an image asset, native structure, or editable text before rebuilding the slide.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


INVENTORY_SCHEMA_VERSION = "easyslides.slide_image_inventory.v1"
REPORT_SCHEMA_VERSION = "easyslides.slide_image_inventory_report.v1"
FULL_SLIDE_ASSET_THRESHOLD = 85.0
ALLOWED_LAYERS = {"A", "B", "C"}
LAYER_NAMES = {
    "A": "visual_asset",
    "B": "native_structure",
    "C": "editable_text",
}
RECTANGULAR_CROP_IMPLEMENTATIONS = {
    "crop",
    "rect_crop",
    "rectangular_crop",
    "source_crop",
    "cropped_source",
}
NATIVE_STRUCTURE_IMPLEMENTATIONS = {"native_shape", "ppt_shape", "drawingml_shape"}
PRESERVED_SOURCE_IMPLEMENTATIONS = {
    "preserve_masked_source",
    "masked_source",
    "alpha_masked_source",
    "preserved_raster",
    "preserve_asset",
}
SEMANTIC_ASSET_CLASSES = {
    "foreground_asset",
    "semantic_asset",
    "visual_asset",
    "illustration",
    "icon",
    "photo",
    "logo",
    "scientific_figure",
    "raster_asset",
}
NATIVE_STRUCTURE_CLASSES = {
    "native_structure",
    "structure",
    "container",
    "panel",
    "frame",
    "divider",
    "line",
    "arrow",
    "axis",
    "grid",
    "background",
}
SEMANTIC_ASSET_TERMS = {
    "asset",
    "badge",
    "brand",
    "chart image",
    "device",
    "diagram",
    "figure",
    "icon",
    "illustration",
    "logo",
    "map",
    "microscopy",
    "photo",
    "pictogram",
    "render",
    "screenshot",
    "scientific figure",
    "texture",
    "tree",
    "leaf",
    "root",
    "mangrove",
    "图标",
    "插画",
    "照片",
    "截图",
    "标志",
    "logo",
    "显微",
    "纹理",
    "树",
    "叶",
    "根",
    "红树林",
}
STRUCTURE_EXEMPT_TERMS = {
    "axis",
    "background",
    "border",
    "box",
    "card",
    "container",
    "divider",
    "frame",
    "grid",
    "line",
    "panel",
    "rectangle",
    "shape",
    "轴",
    "背景",
    "边框",
    "卡片",
    "容器",
    "分隔",
    "线",
    "面板",
    "矩形",
}


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    slide_id: str | None = None,
    element_id: str | None = None,
    suggestion: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if slide_id:
        payload["slide_id"] = slide_id
    if element_id:
        payload["element_id"] = element_id
    if suggestion:
        payload["suggestion"] = suggestion
    return payload


STRICT_SOURCE_FIDELITY_VALUES = {"strict", "source_faithful", "source-faithful"}
CARET_EXPONENT_RE = r"[A-Za-z0-9]+\^[+-]?[A-Za-z0-9]+"
CLOSED_SHAPE_TERMS = {
    "circle",
    "circular",
    "ring",
    "round badge",
    "round icon",
    "closed loop",
    "closed outline",
    "badge outline",
    "圆",
    "圆圈",
    "环形",
}
SCATTER_PLOT_TERMS = {
    "scatter",
    "scatterplot",
    "scatter plot",
    "point cloud",
    "data points",
    "bivariate plot",
    "散点",
    "散点图",
}
MEASURED_TEXT_SOURCES = {
    "measured",
    "hints",
    "ocr",
    "paddleocr",
    "paddleocr-vl",
    "source",
    "source-measured",
    "ink-measured",
}


def _bbox_area_percent(bbox: dict[str, Any]) -> float:
    try:
        return max(0.0, float(bbox.get("w", 0))) * max(0.0, float(bbox.get("h", 0))) / 100.0
    except (TypeError, ValueError):
        return 0.0


def _validate_bbox(
    bbox: Any,
    *,
    slide_id: str,
    element_id: str,
    issues: list[dict[str, Any]],
) -> dict[str, float] | None:
    if not isinstance(bbox, dict):
        issues.append(
            _issue(
                "INVENTORY-ELEMENT-BBOX-MISSING",
                "blocking",
                "Element must declare bbox_percent as an object with x/y/w/h percentages.",
                slide_id=slide_id,
                element_id=element_id,
            )
        )
        return None

    parsed: dict[str, float] = {}
    for key in ("x", "y", "w", "h"):
        try:
            parsed[key] = float(bbox[key])
        except (KeyError, TypeError, ValueError):
            issues.append(
                _issue(
                    "INVENTORY-ELEMENT-BBOX-MALFORMED",
                    "blocking",
                    f"bbox_percent.{key} must be a number.",
                    slide_id=slide_id,
                    element_id=element_id,
                )
            )
            return None

    if parsed["w"] <= 0 or parsed["h"] <= 0:
        issues.append(
            _issue(
                "INVENTORY-ELEMENT-BBOX-EMPTY",
                "blocking",
                "Element bbox_percent must have positive width and height.",
                slide_id=slide_id,
                element_id=element_id,
            )
        )
    if parsed["x"] < 0 or parsed["y"] < 0 or parsed["x"] + parsed["w"] > 100.5 or parsed["y"] + parsed["h"] > 100.5:
        issues.append(
            _issue(
                "INVENTORY-ELEMENT-BBOX-OUTSIDE-SLIDE",
                "blocking",
                "Element bbox_percent extends outside the slide bounds.",
                slide_id=slide_id,
                element_id=element_id,
            )
        )
    return parsed


def _layer_a_no_text_declared(element: dict[str, Any]) -> bool:
    if element.get("contains_text") is False:
        return True
    if element.get("asset_no_text") is True:
        return True
    asset_policy = element.get("asset_policy")
    return isinstance(asset_policy, dict) and asset_policy.get("no_text") is True


def _implementation(element: dict[str, Any]) -> str:
    return str(element.get("implementation", "")).strip().lower()


def _asset_policy(element: dict[str, Any]) -> dict[str, Any]:
    policy = element.get("asset_policy")
    return policy if isinstance(policy, dict) else {}


def _object_class(element: dict[str, Any]) -> str:
    return str(element.get("object_class") or element.get("element_class") or "").strip().lower()


def _contains_term(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _looks_like_semantic_asset(element: dict[str, Any]) -> bool:
    object_class = _object_class(element)
    if object_class in SEMANTIC_ASSET_CLASSES:
        return True
    if object_class in NATIVE_STRUCTURE_CLASSES:
        return False

    description = str(element.get("description", ""))
    if not _contains_term(description, SEMANTIC_ASSET_TERMS):
        return False
    return not _contains_term(description, STRUCTURE_EXEMPT_TERMS)


def _has_mask_or_alpha_contract(element: dict[str, Any]) -> bool:
    policy = _asset_policy(element)
    return bool(
        policy.get("masked_source")
        or policy.get("alpha_backed")
        or policy.get("transparent")
        or element.get("mask_path")
        or element.get("alpha_path")
    )


def _has_ratio_safe_contract(element: dict[str, Any]) -> bool:
    policy = _asset_policy(element)
    placement = element.get("placement_policy")
    if isinstance(placement, dict) and placement.get("ratio_safe") is True:
        return True
    return bool(policy.get("ratio_safe_placement"))


def _preserve_reason(element: dict[str, Any]) -> str:
    policy = _asset_policy(element)
    return str(element.get("preserve_reason") or policy.get("preserve_reason") or "").strip()


def _is_strict_source_fidelity(inventory: dict[str, Any], slide: dict[str, Any]) -> bool:
    values = {
        str(inventory.get("source_fidelity", "")).strip().lower(),
        str(inventory.get("fidelity_mode", "")).strip().lower(),
        str(slide.get("source_fidelity", "")).strip().lower(),
        str(slide.get("fidelity_mode", "")).strip().lower(),
    }
    return bool(values & STRICT_SOURCE_FIDELITY_VALUES)


def _looks_like_closed_shape(element: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            _object_class(element),
            str(element.get("description", "")),
            str(element.get("shape_role", "")),
        ]
    )
    return _contains_term(haystack, CLOSED_SHAPE_TERMS)


def _has_closed_shape_clip_contract(element: dict[str, Any]) -> bool:
    policy = _asset_policy(element)
    clipping = element.get("clipping_check")
    if isinstance(clipping, dict) and clipping.get("passed") is True:
        return True
    if policy.get("closed_shape_complete") is True and policy.get("foreground_not_clipped") is True:
        return True
    margin = policy.get("min_transparent_margin_px") or element.get("min_transparent_margin_px")
    try:
        return float(margin) > 0 and policy.get("closed_shape_complete") is True
    except (TypeError, ValueError):
        return False


def _looks_like_scatter_plot(element: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            _object_class(element),
            str(element.get("description", "")),
            str(element.get("chart_type", "")),
        ]
    )
    return _contains_term(haystack, SCATTER_PLOT_TERMS)


def _has_scatter_distribution_contract(element: dict[str, Any]) -> bool:
    fidelity = element.get("data_fidelity")
    if not isinstance(fidelity, dict):
        return False
    has_points = any(
        isinstance(fidelity.get(key), list) and len(fidelity.get(key)) > 0
        for key in ("source_points_px", "points_px", "data_points", "sampled_points_px")
    )
    has_count = fidelity.get("point_count") not in (None, "")
    has_plot_area = fidelity.get("plot_area_px") or fidelity.get("axis_box_px")
    has_source = str(fidelity.get("distribution_source", "")).strip()
    return bool((has_points or has_count) and has_plot_area and has_source)


def _has_native_superscript_contract(element: dict[str, Any]) -> bool:
    if element.get("native_superscript") is True:
        return True
    if isinstance(element.get("runs"), list) and element["runs"]:
        return True
    if isinstance(element.get("paragraphs"), list) and element["paragraphs"]:
        return True
    return False


def _has_text_geometry_contract(element: dict[str, Any]) -> bool:
    geometry = element.get("text_geometry")
    if isinstance(geometry, dict):
        source = str(geometry.get("font_size_source", "")).strip().lower()
        if geometry.get("source_bbox_px") and source in MEASURED_TEXT_SOURCES:
            return True
    if element.get("text_hint_id") or element.get("source_text_id"):
        return True
    return str(element.get("font_size_source", "")).strip().lower() in MEASURED_TEXT_SOURCES


def validate_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if inventory.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        issues.append(
            _issue(
                "INVENTORY-SCHEMA-VERSION",
                "warning",
                f"Expected schema_version {INVENTORY_SCHEMA_VERSION}.",
            )
        )

    slides = inventory.get("slides")
    if not isinstance(slides, list) or not slides:
        issues.append(
            _issue(
                "INVENTORY-SLIDES-MISSING",
                "blocking",
                "Inventory must contain a non-empty slides list.",
            )
        )
        slides = []

    layer_counts = {name: 0 for name in LAYER_NAMES.values()}
    element_count = 0

    for slide_index, slide in enumerate(slides, start=1):
        slide_id = str(slide.get("slide_id") or f"s{slide_index:02d}") if isinstance(slide, dict) else f"s{slide_index:02d}"
        if not isinstance(slide, dict):
            issues.append(_issue("INVENTORY-SLIDE-MALFORMED", "blocking", "Each slide entry must be an object.", slide_id=slide_id))
            continue

        elements = slide.get("elements")
        if not isinstance(elements, list):
            issues.append(
                _issue(
                    "INVENTORY-SLIDE-ELEMENTS-MISSING",
                    "blocking",
                    "Slide must contain an elements list.",
                    slide_id=slide_id,
                )
            )
            elements = []

        completeness = slide.get("completeness_check")
        if not isinstance(completeness, dict) or completeness.get("performed") is not True:
            issues.append(
                _issue(
                    "INVENTORY-COMPLETENESS-CHECK-MISSING",
                    "blocking",
                    "Slide inventory must include a performed completeness_check second pass.",
                    slide_id=slide_id,
                    suggestion="Reinspect the source image for small icons, decorative details, in-card visuals, and chart decorations.",
                )
            )

        seen_ids: set[str] = set()
        layer_a_count = 0
        strict_source_fidelity = _is_strict_source_fidelity(inventory, slide)
        for element_index, element in enumerate(elements, start=1):
            element_count += 1
            if not isinstance(element, dict):
                issues.append(
                    _issue(
                        "INVENTORY-ELEMENT-MALFORMED",
                        "blocking",
                        "Each element entry must be an object.",
                        slide_id=slide_id,
                        element_id=f"{slide_id}_e{element_index:02d}",
                    )
                )
                continue

            element_id = str(element.get("element_id") or f"{slide_id}_e{element_index:02d}")
            if element_id in seen_ids:
                issues.append(
                    _issue(
                        "INVENTORY-ELEMENT-ID-DUPLICATE",
                        "blocking",
                        "Element ids must be unique within a slide.",
                        slide_id=slide_id,
                        element_id=element_id,
                    )
                )
            seen_ids.add(element_id)

            if not str(element.get("description", "")).strip():
                issues.append(
                    _issue(
                        "INVENTORY-ELEMENT-DESCRIPTION-MISSING",
                        "warning",
                        "Element should include a concise visual description.",
                        slide_id=slide_id,
                        element_id=element_id,
                    )
                )

            layer = str(element.get("layer", "")).upper()
            if layer not in ALLOWED_LAYERS:
                issues.append(
                    _issue(
                        "INVENTORY-ELEMENT-LAYER-INVALID",
                        "blocking",
                        "Element layer must be A, B, or C.",
                        slide_id=slide_id,
                        element_id=element_id,
                    )
                )
                continue
            layer_counts[LAYER_NAMES[layer]] += 1
            if layer == "A":
                layer_a_count += 1

            bbox = _validate_bbox(element.get("bbox_percent"), slide_id=slide_id, element_id=element_id, issues=issues)
            implementation = _implementation(element)
            if not implementation:
                issues.append(
                    _issue(
                        "INVENTORY-ELEMENT-IMPLEMENTATION-MISSING",
                        "warning",
                        "Element should declare its intended implementation method.",
                        slide_id=slide_id,
                        element_id=element_id,
                    )
                )
            if "z_order" not in element:
                issues.append(
                    _issue(
                        "INVENTORY-ELEMENT-Z-ORDER-MISSING",
                        "warning",
                        "Element should declare z_order so assembly can preserve stacking.",
                        slide_id=slide_id,
                        element_id=element_id,
                    )
                )

            if layer == "A":
                if not _object_class(element):
                    issues.append(
                        _issue(
                            "INVENTORY-A-OBJECT-CLASS-MISSING",
                            "warning",
                            "Layer A assets should declare object_class so semantic assets are not later rebuilt as native structure.",
                            slide_id=slide_id,
                            element_id=element_id,
                        )
                    )
                if bbox and _bbox_area_percent(bbox) >= FULL_SLIDE_ASSET_THRESHOLD:
                    issues.append(
                        _issue(
                            "INVENTORY-FULL-SLIDE-ASSET",
                            "blocking",
                            "Layer A asset covers most of the slide, which risks becoming a full-slide screenshot.",
                            slide_id=slide_id,
                            element_id=element_id,
                            suggestion="Split into visual assets, native structure, and editable text layers.",
                        )
                    )
                if element.get("contains_text") is True:
                    issues.append(
                        _issue(
                            "INVENTORY-A-ASSET-CONTAINS-TEXT",
                            "blocking",
                            "Layer A visual assets must not contain readable text.",
                            slide_id=slide_id,
                            element_id=element_id,
                            suggestion="Extract the text as Layer C and regenerate or mask the asset without text.",
                        )
                    )
                elif not _layer_a_no_text_declared(element):
                    issues.append(
                        _issue(
                            "INVENTORY-A-ASSET-NO-TEXT-POLICY-MISSING",
                            "warning",
                            "Layer A assets should explicitly declare contains_text=false or asset_policy.no_text=true.",
                            slide_id=slide_id,
                            element_id=element_id,
                        )
                    )
                if implementation in RECTANGULAR_CROP_IMPLEMENTATIONS or ("rect" in implementation and "mask" not in implementation):
                    issues.append(
                        _issue(
                            "INVENTORY-A-ASSET-RECT-CROP",
                            "blocking",
                            "Layer A source crops must be mask/alpha-backed or regenerated; a rectangular crop is not a clean element boundary.",
                            slide_id=slide_id,
                            element_id=element_id,
                        )
                    )
                if implementation in PRESERVED_SOURCE_IMPLEMENTATIONS:
                    if not _has_mask_or_alpha_contract(element):
                        issues.append(
                            _issue(
                                "INVENTORY-A-PRESERVE-MASK-MISSING",
                                "blocking",
                                "Preserved source assets must be mask/alpha-backed rather than rectangular crops.",
                                slide_id=slide_id,
                                element_id=element_id,
                                suggestion="Declare asset_policy.masked_source=true, asset_policy.alpha_backed=true, or provide mask_path/alpha_path.",
                            )
                        )
                    if not _has_ratio_safe_contract(element):
                        issues.append(
                            _issue(
                                "INVENTORY-A-PRESERVE-RATIO-SAFE-MISSING",
                                "blocking",
                                "Preserved source assets must declare ratio-safe placement to avoid stretch distortion.",
                                slide_id=slide_id,
                                element_id=element_id,
                                suggestion="Set asset_policy.ratio_safe_placement=true or placement_policy.ratio_safe=true.",
                            )
                        )
                    if not _preserve_reason(element):
                        issues.append(
                            _issue(
                                "INVENTORY-A-PRESERVE-REASON-MISSING",
                                "warning",
                                "Preserved source assets should record which hard preservation trigger was used.",
                                slide_id=slide_id,
                                element_id=element_id,
                            )
                        )
                if _looks_like_closed_shape(element) and not _has_closed_shape_clip_contract(element):
                    issues.append(
                        _issue(
                            "INVENTORY-A-CLOSED-SHAPE-CLIP-CHECK-MISSING",
                            "blocking",
                            "Closed or circular assets must prove that the full outline survived masking/splitting.",
                            slide_id=slide_id,
                            element_id=element_id,
                            suggestion="Add clipping_check.passed=true, or asset_policy.closed_shape_complete=true plus foreground_not_clipped/min_transparent_margin_px.",
                        )
                    )
            elif layer == "B":
                if implementation and implementation not in NATIVE_STRUCTURE_IMPLEMENTATIONS:
                    issues.append(
                        _issue(
                            "INVENTORY-B-STRUCTURE-NOT-NATIVE",
                            "warning",
                            "Layer B structure should be implemented as native PPT/DrawingML shapes.",
                            slide_id=slide_id,
                            element_id=element_id,
                        )
                    )
                if implementation in NATIVE_STRUCTURE_IMPLEMENTATIONS and _looks_like_semantic_asset(element):
                    issues.append(
                        _issue(
                            "INVENTORY-B-SEMANTIC-ASSET-NATIVE",
                            "blocking",
                            "Semantic visual assets must not be rebuilt as native structure because this creates crude vector approximations.",
                            slide_id=slide_id,
                            element_id=element_id,
                            suggestion="Move this element to Layer A and implement it as imagegen or preserve_masked_source.",
                        )
                    )
                if implementation in NATIVE_STRUCTURE_IMPLEMENTATIONS and _looks_like_scatter_plot(element):
                    if not _has_scatter_distribution_contract(element):
                        issues.append(
                            _issue(
                                "INVENTORY-B-SCATTER-DISTRIBUTION-CONTRACT-MISSING",
                                "blocking",
                                "Native scatter plots must carry source point/distribution measurements instead of invented point positions.",
                                slide_id=slide_id,
                                element_id=element_id,
                                suggestion="Record data_fidelity with source_points_px or point_count, plot_area_px/axis_box_px, and distribution_source.",
                            )
                        )
            elif layer == "C":
                if implementation and implementation not in {"native_text", "ppt_text", "drawingml_text"}:
                    issues.append(
                        _issue(
                            "INVENTORY-C-TEXT-NOT-NATIVE",
                            "blocking",
                            "Layer C content must be implemented as editable native text.",
                            slide_id=slide_id,
                            element_id=element_id,
                        )
                    )
                if not str(element.get("text", "")).strip():
                    issues.append(
                        _issue(
                            "INVENTORY-C-TEXT-MISSING",
                            "warning",
                            "Layer C element should include the recognized text content.",
                            slide_id=slide_id,
                            element_id=element_id,
                        )
                    )
                text = str(element.get("text", ""))
                if text and re.search(CARET_EXPONENT_RE, text) and not _has_native_superscript_contract(element):
                    issues.append(
                        _issue(
                            "INVENTORY-C-EXPONENT-NATIVE-RUNS-MISSING",
                            "blocking" if strict_source_fidelity else "warning",
                            "Caret exponent text should be emitted as native superscript runs in PPTX.",
                            slide_id=slide_id,
                            element_id=element_id,
                            suggestion="Use text runs with DrawingML baseline for the exponent, e.g. 10 plus superscript -1.",
                        )
                    )
                if not _has_text_geometry_contract(element):
                    issues.append(
                        _issue(
                            "INVENTORY-C-TEXT-GEOMETRY-SOURCE-MISSING",
                            "blocking" if strict_source_fidelity else "warning",
                            "Editable text should preserve the source bbox and measured font size instead of approximate placement.",
                            slide_id=slide_id,
                            element_id=element_id,
                            suggestion="Set font_size_source/text_hint_id or text_geometry.source_bbox_px with measured font metadata.",
                        )
                    )

        if isinstance(completeness, dict) and "layer_a_count" in completeness:
            try:
                expected_count = int(completeness["layer_a_count"])
            except (TypeError, ValueError):
                expected_count = layer_a_count
            if expected_count != layer_a_count:
                issues.append(
                    _issue(
                        "INVENTORY-COMPLETENESS-COUNT-MISMATCH",
                        "warning",
                        "completeness_check.layer_a_count does not match the actual Layer A element count.",
                        slide_id=slide_id,
                    )
                )

    blocking_count = sum(1 for issue in issues if issue["severity"] == "blocking")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "fail" if blocking_count else "pass",
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "slide_count": len(slides),
        "element_count": element_count,
        "layer_counts": layer_counts,
        "issues": issues,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _example_inventory() -> dict[str, Any]:
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "slides": [
            {
                "slide_id": "s01",
                "source_image": "slide_01.png",
                "width_px": 1920,
                "height_px": 1080,
                "elements": [
                    {
                        "element_id": "s01_e01",
                        "description": "Main technical illustration without labels",
                        "bbox_percent": {"x": 42.0, "y": 18.0, "w": 45.0, "h": 58.0},
                        "layer": "A",
                        "implementation": "imagegen",
                        "asset_policy": {"no_text": True, "transparent": True},
                        "z_order": 3,
                    },
                    {
                        "element_id": "s01_e02",
                        "description": "Title text",
                        "bbox_percent": {"x": 6.0, "y": 6.0, "w": 40.0, "h": 8.0},
                        "layer": "C",
                        "implementation": "native_text",
                        "text": "Example title",
                        "z_order": 8,
                    },
                ],
                "completeness_check": {"performed": True, "layer_a_count": 1, "notes": "Checked corners, cards, and small icons."},
            }
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate slide-image reconstruction inventories.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate an inventory JSON file.")
    validate_parser.add_argument("inventory", help="Path to _analysis.json / inventory JSON.")
    validate_parser.add_argument("--report", help="Optional JSON report path.")
    validate_parser.add_argument("--quiet", action="store_true")

    subparsers.add_parser("example", help="Print a minimal valid inventory example.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "example":
        print(json.dumps(_example_inventory(), ensure_ascii=False, indent=2))
        return 0

    payload = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    report = validate_inventory(payload)
    if args.report:
        _write_json(Path(args.report), report)
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
