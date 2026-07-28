#!/usr/bin/env python3
"""Fail-closed production gate for semantic EasySlides templates."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import tempfile
from typing import Any
from zipfile import ZipFile
import xml.etree.ElementTree as ET

try:
    from scripts import pptx_distill_promotion_gate, pptx_visual_diff, template_component_pack, template_geometry_qa, visual_measure_gate
    from scripts.component_asset_manifest import validate_asset_manifest
    from scripts.body_variant_contract import validate_body_variant_contract
    from scripts.slide_compiler import compile_slides, render_slide_ir_to_svg, validate_native_component_bounds
    from scripts.template_compiler import compile_template
    from scripts.template_capabilities import validate_capability_profile
    from scripts.template_feedback_contract import validate_template_feedback_contract
    from scripts.template_visual_invariants import validate_template_visual_invariants
    from scripts.svg_quality_checker import SVGQualityChecker
    from scripts.validate_pptx_text_layout import validate_pptx_text_layout
    from scripts.validate_svg_text_slots import validate_svg_text_slots
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    import pptx_distill_promotion_gate
    import pptx_visual_diff
    import template_component_pack
    import template_geometry_qa
    import visual_measure_gate
    from component_asset_manifest import validate_asset_manifest
    from body_variant_contract import validate_body_variant_contract
    from slide_compiler import compile_slides, render_slide_ir_to_svg, validate_native_component_bounds
    from template_compiler import compile_template
    from template_capabilities import validate_capability_profile
    from template_feedback_contract import validate_template_feedback_contract
    from template_visual_invariants import validate_template_visual_invariants
    from svg_quality_checker import SVGQualityChecker
    from validate_pptx_text_layout import validate_pptx_text_layout
    from validate_svg_text_slots import validate_svg_text_slots


SCHEMA_VERSION = "easyslides.template_production_gate.v1"
TOKEN_RE = re.compile(r"\{\{([^{}]+)\}\}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_slide_shell_ids(
    pptx_path: Path,
    slide_ir_path: Path | None = None,
) -> tuple[list[str] | None, Path | None, dict[str, Any] | None]:
    candidate = slide_ir_path or (pptx_path.parent / "slide_ir.json")
    if not candidate.is_file():
        if slide_ir_path is not None:
            return None, candidate, issue(
                "PPTX-SLIDE-IR-MISSING",
                "The explicit compiled slide IR does not exist.",
                path=str(candidate),
            )
        return None, None, None
    try:
        payload = read_json(candidate)
        slides = payload.get("slides")
        if not isinstance(slides, list):
            raise ValueError("slides must be a list")
        shell_ids = [str(row.get("shell_id") or "").strip() for row in slides if isinstance(row, dict)]
        if len(shell_ids) != len(slides) or not all(shell_ids):
            raise ValueError("every slide must declare a non-empty shell_id")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, candidate, issue(
            "PPTX-SLIDE-IR-INVALID",
            "Compiled slide IR cannot provide an authoritative shell sequence.",
            path=str(candidate),
            error=str(exc),
        )
    return shell_ids, candidate, None


def issue(code: str, message: str, *, severity: str = "blocking", **details: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if details:
        row["details"] = details
    return row


def validate_compiled_contract(template_dir: Path) -> dict[str, Any]:
    """Validate canonical sources, the compiled IR, and the dependency lock."""
    issues: list[dict[str, Any]] = []
    try:
        report = compile_template(template_dir)
    except (OSError, ValueError) as exc:
        return {
            "status": "fail",
            "issues": [issue("TEMPLATE-COMPILE", "Canonical template sources do not compile.", error=str(exc))],
        }
    template_ir = report["template_ir"]
    compiled_ir_path = template_dir / "compiled" / "template_ir.json"
    lock_path = template_dir / "compiled" / "template.lock.json"
    if not compiled_ir_path.is_file() or not lock_path.is_file():
        issues.append(
            issue(
                "TEMPLATE-COMPILED-OUTPUT",
                "compiled/template_ir.json and compiled/template.lock.json are required.",
            )
        )
    else:
        stored_ir = read_json(compiled_ir_path)
        stored_lock = read_json(lock_path)
        expected_digest = str(template_ir.get("source_digest") or "")
        if stored_ir.get("source_digest") != expected_digest:
            issues.append(issue("TEMPLATE-IR-STALE", "compiled/template_ir.json is stale."))
        if stored_lock.get("source_digest") != expected_digest:
            issues.append(issue("TEMPLATE-LOCK-STALE", "compiled/template.lock.json is stale."))
    body_report = validate_body_variant_contract(template_dir)
    if body_report.get("status") != "pass":
        issues.extend(
            issue(
                str(item.get("code") or "BODY-VARIANT-CONTRACT"),
                str(item.get("message") or "Body variant contract failed."),
                path=str(item.get("path") or ""),
            )
            for item in body_report.get("issues", [])
        )
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "capability_level": report["capability_level"],
        "source_digest": report["source_digest"],
        "shell_count": report["shell_count"],
        "body_variant_count": report["body_variant_count"],
        "component_dependency_count": report["component_dependency_count"],
        "body_variant_report": body_report,
    }


def _sample_slot_value(
    slot: dict[str, Any],
    index: int,
    *,
    image_placeholder: str = "",
) -> Any:
    kind = str(slot.get("kind") or "text")
    if kind == "list":
        return [f"Item {index}"]
    if kind == "image":
        return image_placeholder
    if str(slot.get("text_layout") or "") == "balanced_cjk_stack":
        capacity = slot.get("capacity") if isinstance(slot.get("capacity"), dict) else {}
        max_chars = max(1, int(capacity.get("max_chars_per_line") or 1))
        # This is a compact label, not a location for the gate's descriptive
        # sample sentence. Keep the runtime probe inside the exact component
        # contract so it exercises deterministic wrapping rather than overflow.
        return "示例标签"[:max_chars]
    return f"Sample {index}"


def validate_composition_runtime(
    template_dir: Path,
    *,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile and render one executable Slide IR page for every body variant."""
    try:
        compile_report = compile_template(template_dir)
        template_ir = compile_report["template_ir"]
        if template_ir.get("capability_level") not in {"composable", "production"}:
            return {
                "status": "pass",
                "issues": [],
                "applicable": False,
                "reason": "component composition is required only for composable and production templates",
                "variant_count": len(template_ir.get("body_variants", [])),
                "rendered_slide_count": 0,
                "component_instance_count": 0,
            }
        variants = [
            variant
            for variant in template_ir.get("body_variants", [])
            if isinstance(variant, dict)
        ]
        if not variants:
            return {
                "status": "fail",
                "issues": [issue("SLIDE-COMPOSITION-VARIANTS", "No body variants are available for composition testing.")],
            }
        content_shell = next(
            (
                shell
                for shell in template_ir.get("shells", [])
                if isinstance(shell, dict) and str(shell.get("role") or "") == "content"
            ),
            None,
        )
        body_canvas = (
            content_shell.get("body_canvas")
            if isinstance(content_shell, dict) and isinstance(content_shell.get("body_canvas"), dict)
            else None
        )
        component_assets = [
            component
            for component in template_ir.get("components", [])
            if isinstance(component, dict) and component.get("asset_id") and component.get("slots")
        ]
        image_placeholder = str((template_dir / "assets" / "figure_placeholder.svg").resolve())
        if not Path(image_placeholder).is_file():
            raise ValueError("composition runtime needs assets/figure_placeholder.svg for required image slots")
        slides = []
        for index, variant in enumerate(variants, start=1):
            payload = {
                str(slot["slot_id"]): _sample_slot_value(
                    slot, index, image_placeholder=image_placeholder
                )
                for slot in variant.get("slots", [])
                if isinstance(slot, dict) and slot.get("slot_id")
            }
            shell_payload: dict[str, Any] = {}
            for slot in content_shell.get("slots", []) if isinstance(content_shell, dict) else []:
                if not isinstance(slot, dict) or not slot.get("slot_id"):
                    continue
                slot_id = str(slot["slot_id"])
                if slot.get("value_policy") == "automatic_slide_index":
                    continue
                if slot_id in {"PAGE_TITLE", "TITLE"}:
                    shell_payload[slot_id] = f"Variant {index}"
                elif slot_id == "KEY_MESSAGE":
                    shell_payload[slot_id] = f"Composition check for variant {index}."
                elif bool(slot.get("required", True)):
                    shell_payload[slot_id] = _sample_slot_value(
                        slot, index, image_placeholder=image_placeholder
                    )
            slide = {
                "page": f"V{index:02d}",
                "role": "content",
                "body_variant_id": variant["variant_id"],
                "shell_payload": shell_payload,
                "slot_payload": payload,
            }
            selection = variant.get("selection") if isinstance(variant.get("selection"), dict) else {}
            story_roles = selection.get("story_roles") if isinstance(selection.get("story_roles"), list) else []
            if story_roles:
                slide["story_role"] = str(story_roles[0])
            guidance = variant.get("source_guidance") if isinstance(variant.get("source_guidance"), dict) else {}
            if guidance.get("section") not in (None, ""):
                slide["section"] = str(guidance["section"])
            if str(variant.get("composition_mode") or "") == "open_component_composition":
                if not isinstance(body_canvas, dict) or not component_assets:
                    raise ValueError("open component composition requires a content body canvas and a registered component")
                component = component_assets[0]
                component_payload = {
                    str(slot["slot_id"]): _sample_slot_value(
                        slot, index, image_placeholder=image_placeholder
                    )
                    for slot in component.get("slots", [])
                    if isinstance(slot, dict) and slot.get("slot_id")
                }
                slide["body_components"] = [
                    {
                        "asset_id": component["asset_id"],
                        "instance_id": f"gate_explicit_{index}",
                        "frame": body_canvas,
                        "fit": "contain",
                        "slot_payload": component_payload,
                    }
                ]
            slides.append(slide)
        slide_ir = compile_slides(
            {
                "schema_version": "easyslides.deck_plan.v1",
                "deck_id": f"{template_ir['template_id']}-composition-gate",
                "template_id": template_ir["template_id"],
                "slides": slides,
            },
            template_ir,
        )
        if report_dir:
            target = report_dir / "composition_runtime"
            render_report = render_slide_ir_to_svg(slide_ir, target)
            for slide, svg_path in zip(slide_ir["slides"], render_report["svg_files"]):
                root = ET.parse(svg_path).getroot()
                actual = sum(
                    1
                    for node in root.iter()
                    if node.attrib.get("data-easyslides-instance")
                )
                expected = sum(
                    1
                    for layer in slide.get("layers", [])
                    if isinstance(layer, dict) and layer.get("layer_type") == "component"
                )
                if actual != expected:
                    raise ValueError(
                        f"{slide['body_variant_id']} rendered {actual} component instances; expected {expected}"
                    )
        else:
            with tempfile.TemporaryDirectory(prefix="easyslides-composition-") as tmp:
                render_report = render_slide_ir_to_svg(slide_ir, Path(tmp))
                for slide, svg_path in zip(slide_ir["slides"], render_report["svg_files"]):
                    root = ET.parse(svg_path).getroot()
                    actual = sum(
                        1
                        for node in root.iter()
                        if node.attrib.get("data-easyslides-instance")
                    )
                    expected = sum(
                        1
                        for layer in slide.get("layers", [])
                        if isinstance(layer, dict) and layer.get("layer_type") == "component"
                    )
                    if actual != expected:
                        raise ValueError(
                            f"{slide['body_variant_id']} rendered {actual} component instances; expected {expected}"
                        )
        return {
            "status": "pass",
            "issues": [],
            "variant_count": len(variants),
            "rendered_slide_count": render_report["slide_count"],
            "component_instance_count": sum(
                1
                for slide in slide_ir["slides"]
                for layer in slide.get("layers", [])
                if isinstance(layer, dict) and layer.get("layer_type") == "component"
            ),
            "render_report": render_report if report_dir else {"status": "pass", "slide_count": len(variants)},
        }
    except (OSError, ValueError, ET.ParseError) as exc:
        return {
            "status": "fail",
            "issues": [issue("SLIDE-COMPOSITION", "Template components could not be assembled into rendered slides.", error=str(exc))],
        }


def validate_contract(template_dir: Path) -> dict[str, Any]:
    package_path = template_dir / "template_package.json"
    if package_path.is_file():
        package = read_json(package_path)
        if isinstance(package.get("source_of_truth"), dict):
            return validate_compiled_contract(template_dir)
    issues: list[dict[str, Any]] = []
    layouts_path = template_dir / "layouts.json"
    variants_path = template_dir / "body_variants.json"
    status_path = template_dir / "template_status.json"
    required_paths = (
        layouts_path,
        variants_path,
        status_path,
        template_dir / "template.json",
        template_dir / "design_spec.md",
        template_dir / "rules.md",
        template_dir / "page_catalog.json",
        template_dir / "geometry_contract.json",
        template_dir / "slot_contracts.json",
        template_dir / "spec_lock.md",
        template_dir / "component_catalog.json",
    )
    for path in required_paths:
        if not path.is_file():
            issues.append(issue("TEMPLATE-CONTRACT-MISSING", f"{path.name} is required.", path=str(path)))
    if issues:
        return {"status": "fail", "issues": issues}

    layouts_payload = read_json(layouts_path)
    variants_payload = read_json(variants_path)
    status_payload = read_json(status_path)
    layouts = [row for row in layouts_payload.get("layouts", []) if isinstance(row, dict)]
    if layouts_payload.get("mode") != "semantic":
        issues.append(issue("TEMPLATE-MODE", "Production templates must use semantic mode."))
    if status_payload.get("promotion_policy") != "fail_closed":
        issues.append(issue("TEMPLATE-PROMOTION-POLICY", "template_status.json must declare fail_closed promotion."))

    layout_ids: set[str] = set()
    content_layouts: set[str] = set()
    for layout in layouts:
        layout_id = str(layout.get("layout_id") or "")
        if not layout_id or layout_id in layout_ids:
            issues.append(issue("TEMPLATE-LAYOUT-ID", "Layout ids must be non-empty and unique.", layout_id=layout_id))
            continue
        layout_ids.add(layout_id)
        if layout.get("role") == "content":
            content_layouts.add(layout_id)
        svg_path = template_dir / str(layout.get("svg") or "")
        if not svg_path.is_file():
            issues.append(issue("TEMPLATE-SVG-MISSING", "Layout SVG is missing.", layout_id=layout_id, svg=str(svg_path)))
            continue
        declared = [slot for slot in layout.get("slots", []) if isinstance(slot, dict)]
        declared_ids = [str(slot.get("slot_id") or "") for slot in declared]
        if len(declared_ids) != len(set(declared_ids)) or "" in declared_ids:
            issues.append(issue("TEMPLATE-SLOT-ID", "Declared slot ids must be non-empty and unique.", layout_id=layout_id))
        for slot in declared:
            if slot.get("kind") not in {"text", "list", "image"}:
                issues.append(issue("TEMPLATE-SLOT-KIND", "Unsupported slot kind.", layout_id=layout_id, slot=slot))
            if int(slot.get("max_lines") or 0) < 1 or int(slot.get("max_chars_per_line") or 0) < 1:
                issues.append(issue("TEMPLATE-SLOT-CAPACITY", "Every slot must declare positive capacity.", layout_id=layout_id, slot=slot))

        root = ET.parse(svg_path).getroot()
        actual_ids = [str(node.attrib.get("data-slot")) for node in root.iter() if node.attrib.get("data-slot")]
        if len(actual_ids) != len(set(actual_ids)):
            issues.append(issue("TEMPLATE-SVG-SLOT-DUPLICATE", "SVG data-slot ids must be unique.", layout_id=layout_id))
        if set(actual_ids) != set(declared_ids):
            issues.append(
                issue(
                    "TEMPLATE-SVG-SLOT-MISMATCH",
                    "SVG data-slot ids must exactly match layouts.json.",
                    layout_id=layout_id,
                    missing=sorted(set(declared_ids) - set(actual_ids)),
                    undeclared=sorted(set(actual_ids) - set(declared_ids)),
                )
            )
        xml = ET.tostring(root, encoding="unicode")
        tokens = set(TOKEN_RE.findall(xml))
        if not tokens.issubset(set(declared_ids)):
            issues.append(issue("TEMPLATE-TOKEN-UNDECLARED", "SVG contains undeclared tokens.", layout_id=layout_id, tokens=sorted(tokens - set(declared_ids))))
        forbidden = [needle for needle in ("IMAGE SLOT", "data-source-background-hidden", "source_slide", "slide-01_", "opacity=\"0\"") if needle in xml]
        if forbidden:
            issues.append(issue("TEMPLATE-SOURCE-ARTIFACT", "Semantic template contains source/debug hiding artifacts.", layout_id=layout_id, values=forbidden))

    variants = [row for row in variants_payload.get("variants", []) if isinstance(row, dict)]
    mapped = {str(row.get("layout_id") or "") for row in variants}
    if not content_layouts.issubset(mapped):
        issues.append(issue("TEMPLATE-VARIANT-COVERAGE", "Every content layout must be reachable from body_variants.json.", layouts=sorted(content_layouts - mapped)))
    for variant in variants:
        if str(variant.get("layout_id") or "") not in content_layouts:
            issues.append(issue("TEMPLATE-VARIANT-LAYOUT", "Variant references a non-content or missing layout.", variant=variant))
        if not variant.get("content_shapes"):
            issues.append(issue("TEMPLATE-VARIANT-SHAPE", "Every variant must declare content_shapes.", variant=variant))

    return {
        "status": "fail" if any(row["severity"] == "blocking" for row in issues) else "pass",
        "layout_count": len(layouts),
        "variant_count": len(variants),
        "issues": issues,
    }


def validate_slot_contract(template_dir: Path) -> dict[str, Any]:
    """Validate the editable-slot boundary used by both template modes."""
    report = visual_measure_gate.validate_template_slot_contract(template_dir)
    return {
        "status": report.get("status", "fail"),
        "issues": report.get("issues", []),
        "report": report,
    }


def validate_component_catalog(template_dir: Path) -> dict[str, Any]:
    """Ensure every promoted component/symbol is selectable and materialized."""
    path = template_dir / "component_catalog.json"
    if not path.is_file():
        return {
            "status": "fail",
            "issues": [issue("COMPONENT-CATALOG-MISSING", "component_catalog.json is required.")],
        }
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "fail",
            "issues": [issue("COMPONENT-CATALOG-INVALID", "component_catalog.json is not valid JSON.", error=str(exc))],
        }

    issues: list[dict[str, Any]] = []
    components = template_component_pack.expanded_catalog_components(template_dir, payload)
    symbols = payload.get("symbols")
    if not isinstance(components, list):
        issues.append(issue("COMPONENT-CATALOG-COMPONENTS", "component_catalog.json components must be a list."))
        components = []
    if not isinstance(symbols, list):
        issues.append(issue("COMPONENT-CATALOG-SYMBOLS", "component_catalog.json symbols must be a list."))
        symbols = []
    unknown_count = payload.get("unknown_component_count", 0)
    try:
        unknown_count = int(unknown_count)
    except (TypeError, ValueError):
        issues.append(issue("COMPONENT-CATALOG-UNKNOWN-COUNT", "unknown_component_count must be an integer."))
        unknown_count = 1
    if unknown_count:
        issues.append(
            issue(
                "COMPONENT-CATALOG-UNKNOWN",
                "Unclassified components cannot be promoted into the production asset registry.",
                count=unknown_count,
            )
        )

    asset_manifest_path = template_dir / "assets" / "asset_manifest.json"
    manifest_paths: set[str] = set()
    if asset_manifest_path.is_file():
        try:
            manifest = read_json(asset_manifest_path)
            manifest_paths = {
                str(row.get("path") or "").replace("\\", "/")
                for row in manifest.get("assets", [])
                if isinstance(row, dict)
            }
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    rows = [("component", components, "component_id"), ("symbol", symbols, "symbol_id")]
    for kind, entries, id_key in rows:
        for index, item in enumerate(entries):
            if not isinstance(item, dict):
                issues.append(issue("COMPONENT-CATALOG-ROW", f"{kind} entry must be an object.", index=index, kind=kind))
                continue
            item_id = str(item.get(id_key) or "")
            asset_path = str(item.get("asset_path") or "").replace("\\", "/")
            if not item_id or item_id in seen_ids:
                issues.append(issue("COMPONENT-CATALOG-ID", f"{kind} ids must be non-empty and unique.", id=item_id, kind=kind))
            seen_ids.add(item_id)
            if not asset_path:
                issues.append(issue("COMPONENT-CATALOG-ASSET-PATH", "Every component and symbol must declare asset_path.", id=item_id))
                continue
            relative = Path(asset_path)
            if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
                issues.append(issue("COMPONENT-CATALOG-ASSET-PATH", "asset_path must stay inside the template.", id=item_id, asset_path=asset_path))
                continue
            if not asset_path.startswith("assets/"):
                issues.append(issue("COMPONENT-CATALOG-ASSET-UNINDEXED", "Catalogued component assets must live under assets/.", id=item_id, asset_path=asset_path))
            materialized = template_dir / relative
            if not materialized.is_file():
                issues.append(issue("COMPONENT-CATALOG-ASSET-MISSING", "Catalogued asset is missing.", id=item_id, asset_path=asset_path))
            elif materialized.suffix.lower() == ".svg":
                try:
                    root = ET.parse(materialized).getroot()
                    if root.attrib.get("overflow", "visible").lower() == "hidden":
                        values = [float(value) for value in root.attrib.get("viewBox", "").replace(",", " ").split()]
                        if len(values) != 4:
                            raise ValueError("overflow-hidden SVG needs a four-value viewBox")
                        vx, vy, width, height = values
                        for node in root.iter():
                            if node.tag.rsplit("}", 1)[-1] != "rect":
                                continue
                            x = float(node.attrib.get("x", "0"))
                            y = float(node.attrib.get("y", "0"))
                            rect_width = float(node.attrib.get("width", "0"))
                            rect_height = float(node.attrib.get("height", "0"))
                            tolerance = 0.01
                            if (
                                x < vx - tolerance
                                or y < vy - tolerance
                                or x + rect_width > vx + width + tolerance
                                or y + rect_height > vy + height + tolerance
                            ):
                                issues.append(
                                    issue(
                                        "COMPONENT-CATALOG-VIEWPORT-OVERFLOW",
                                        "An overflow-hidden component has a rectangle outside its visible SVG viewport.",
                                        id=item_id,
                                        asset_path=asset_path,
                                    )
                                )
                                break
                    slots = item.get("slots") if isinstance(item.get("slots"), list) else []
                    for slot in slots:
                        if not isinstance(slot, dict):
                            continue
                        layout = str(slot.get("text_layout") or "").strip()
                        if not layout:
                            continue
                        if layout != "balanced_cjk_stack":
                            issues.append(
                                issue(
                                    "COMPONENT-CATALOG-TEXT-LAYOUT",
                                    "Component declares an unsupported text layout policy.",
                                    id=item_id,
                                    slot_id=slot.get("slot_id"),
                                    text_layout=layout,
                                )
                            )
                            continue
                        slot_id = str(slot.get("slot_id") or "")
                        capacity = slot.get("capacity") if isinstance(slot.get("capacity"), dict) else {}
                        expected_chars = str(int(capacity.get("max_chars_per_line") or 1))
                        expected_lines = str(int(capacity.get("max_lines") or 1))
                        text_node = next(
                            (
                                node
                                for node in root.iter()
                                if node.attrib.get("data-slot-id") == slot_id
                            ),
                            None,
                        )
                        if text_node is None or (
                            text_node.attrib.get("data-easyslides-layout") != layout
                            or text_node.attrib.get("data-pptx-no-wrap") != "true"
                            or text_node.attrib.get("data-easyslides-wrap-max-chars") != expected_chars
                            or text_node.attrib.get("data-easyslides-wrap-max-lines") != expected_lines
                        ):
                            issues.append(
                                issue(
                                    "COMPONENT-CATALOG-TEXT-LAYOUT",
                                    "Component text layout policy is not fully materialized in its SVG asset.",
                                    id=item_id,
                                    slot_id=slot_id,
                                    text_layout=layout,
                                )
                            )
                except (OSError, ET.ParseError, TypeError, ValueError) as exc:
                    issues.append(
                        issue(
                            "COMPONENT-CATALOG-SVG-GEOMETRY",
                            "Component SVG viewport geometry cannot be audited.",
                            id=item_id,
                            asset_path=asset_path,
                            error=str(exc),
                        )
                    )
            if asset_path in seen_paths:
                issues.append(issue("COMPONENT-CATALOG-ASSET-DUPLICATE", "Multiple catalog entries point to the same asset path.", asset_path=asset_path))
            seen_paths.add(asset_path)
            if asset_path.startswith("assets/"):
                manifest_path = asset_path[len("assets/"):]
                if manifest_paths and manifest_path not in manifest_paths:
                    issues.append(issue("COMPONENT-CATALOG-ASSET-UNINDEXED", "Catalogued asset is missing from assets/asset_manifest.json.", id=item_id, asset_path=asset_path))

    return {
        "status": "fail" if any(row["severity"] == "blocking" for row in issues) else "pass",
        "issues": issues,
        "component_count": len(components),
        "symbol_count": len(symbols),
        "unknown_component_count": unknown_count,
    }


def validate_template_component_pack_gate(template_dir: Path) -> dict[str, Any]:
    """Keep the template's component dependency and token contract fail-closed."""
    if not (template_dir / "component_pack.json").is_file():
        return {
            "status": "pass",
            "issues": [],
            "applicable": False,
            "reason": "template has not declared a template-scoped component pack",
        }
    report = template_component_pack.validate_template_component_pack(template_dir)
    return {
        "status": report.get("status", "fail"),
        "issues": report.get("issues", []),
        "applicable": True,
        "report": report,
    }


def validate_template_capability_gate(template_dir: Path) -> dict[str, Any]:
    """Ensure the template declares its composition boundary before promotion."""
    report = validate_capability_profile(template_dir)
    if report.get("status") != "pass":
        return {
            "status": "fail",
            "issues": report.get("issues", []),
            "report": report,
        }
    profile = report.get("profile") if isinstance(report.get("profile"), dict) else {}
    if profile.get("generation_enabled") is not True:
        return {
            "status": "fail",
            "issues": [
                issue(
                    "TEMPLATE-CAPABILITY-GENERATION-DISABLED",
                    "Source-scoped and non-template directories cannot be promoted as generation templates.",
                )
            ],
            "report": report,
        }
    return {"status": "pass", "issues": [], "report": report}


def validate_svg_quality(template_dir: Path) -> dict[str, Any]:
    checker = SVGQualityChecker(template_mode=True)
    rows = checker.check_directory(str(template_dir), expected_format="ppt169")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for row in rows:
        for message in row.get("errors", []):
            errors.append(issue("SVG-QUALITY", str(message), file=row.get("file")))
        for message in row.get("warnings", []):
            warnings.append(issue("SVG-QUALITY-WARNING", str(message), severity="warning", file=row.get("file")))
    return {"status": "fail" if errors else "pass", "issues": errors + warnings, "file_count": len(rows)}


def validate_svg_text_slots_gate(template_dir: Path) -> dict[str, Any]:
    """Apply the hard SVG text-box contract before any PPTX export exists."""
    report = validate_svg_text_slots(
        template_dir,
        strict_unboxed=True,
        require_valign=True,
        check_canvas=True,
    )
    return {
        "status": report.get("status", "fail"),
        "issues": report.get("issues", []),
        "report": report,
    }


def validate_geometry_svg(template_dir: Path) -> dict[str, Any]:
    contract_path = template_dir / "geometry_contract.json"
    if not contract_path.is_file():
        return {
            "status": "fail",
            "issues": [issue("TEMPLATE-GEOMETRY-CONTRACT-MISSING", "geometry_contract.json is required.")],
        }
    report = template_geometry_qa.validate_template_geometry(template_dir)
    return {
        "status": report.get("status", "fail"),
        "issues": report.get("issues", []),
        "report": report,
    }


def validate_assets(template_dir: Path) -> dict[str, Any]:
    assets_dir = template_dir / "assets"
    manifest_path = assets_dir / "asset_manifest.json"
    if not assets_dir.is_dir():
        return {"status": "pass", "issues": [], "asset_count": 0}
    if not manifest_path.is_file():
        return {
            "status": "fail",
            "issues": [issue("ASSET-MANIFEST-MISSING", "assets/asset_manifest.json is required when a template has assets.")],
        }
    report = validate_asset_manifest(manifest_path)
    return {
        "status": report.get("status", "fail"),
        "issues": [issue(item.get("code", "ASSET-MANIFEST"), item.get("message", "Invalid asset manifest.")) for item in report.get("issues", [])],
        "report": report,
    }


def scan_pptx_placeholders(pptx_path: Path) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    with ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            text = archive.read(name).decode("utf-8", errors="replace")
            for needle in ("{{", "}}", "IMAGE SLOT", "TODO", "Lorem", "ipsum"):
                if needle.lower() in text.lower():
                    hits.append({"slide_part": name, "needle": needle})
    return {
        "status": "fail" if hits else "pass",
        "issues": [issue("PPTX-PLACEHOLDER", "Rendered PPTX contains a placeholder/debug token.", **row) for row in hits],
    }


def validate_human_review(template_dir: Path) -> dict[str, Any]:
    path = template_dir / "human_review.json"
    if not path.is_file():
        return {
            "status": "review_required",
            "issues": [issue("HUMAN-REVIEW-MISSING", "A visual reviewer must approve the rendered contact sheet.", severity="review")],
        }
    payload = read_json(path)
    passed = payload.get("status") == "pass" and payload.get("approved") is True
    return {
        "status": "pass" if passed else "review_required",
        "issues": [] if passed else [issue("HUMAN-REVIEW-NOT-APPROVED", "human_review.json is not approved.", severity="review")],
        "review": payload,
    }


def run_gate(
    template_dir: Path,
    *,
    pptx_path: Path | None = None,
    slide_ir_path: Path | None = None,
    source_render_dir: Path | None = None,
    generated_render_dir: Path | None = None,
    report_dir: Path | None = None,
    run_cross_material: bool = False,
) -> dict[str, Any]:
    gates: list[dict[str, Any]] = [
        {"id": "template_capability_profile", **validate_template_capability_gate(template_dir)},
        {"id": "template_compile", **validate_compiled_contract(template_dir)},
        {"id": "contract", **validate_contract(template_dir)},
        {"id": "slide_composition", **validate_composition_runtime(template_dir, report_dir=report_dir)},
        {"id": "template_slot_contract", **validate_slot_contract(template_dir)},
        {"id": "feedback_contract", **validate_template_feedback_contract(template_dir)},
        {"id": "template_component_pack", **validate_template_component_pack_gate(template_dir)},
        {"id": "component_catalog", **validate_component_catalog(template_dir)},
        {"id": "svg_quality", **validate_svg_quality(template_dir)},
        {"id": "svg_text_slots", **validate_svg_text_slots_gate(template_dir)},
        {"id": "template_geometry_svg", **validate_geometry_svg(template_dir)},
        {"id": "template_visual_invariants", **validate_template_visual_invariants(template_dir)},
        {"id": "asset_manifest", **validate_assets(template_dir)},
    ]
    if pptx_path is None:
        gates.extend(
            [
                {"id": "template_geometry_pptx", "status": "review_required", "issues": [issue("PPTX-MISSING", "A rendered PPTX is required.", severity="review")]},
                {"id": "pptx_text_layout", "status": "review_required", "issues": [issue("PPTX-MISSING", "A rendered PPTX is required.", severity="review")]},
                {"id": "placeholder_scan", "status": "review_required", "issues": [issue("PPTX-MISSING", "A rendered PPTX is required.", severity="review")]},
            ]
        )
    elif not pptx_path.is_file():
        missing = [issue("PPTX-MISSING", "The supplied native PPTX does not exist.", path=str(pptx_path))]
        gates.extend(
            [
                {"id": "template_geometry_pptx", "status": "fail", "issues": missing},
                {"id": "pptx_text_layout", "status": "fail", "issues": missing},
                {"id": "placeholder_scan", "status": "fail", "issues": missing},
            ]
        )
    else:
        shell_ids, resolved_slide_ir, mapping_issue = load_slide_shell_ids(pptx_path, slide_ir_path)
        geometry = template_geometry_qa.validate_pptx_against_contract(
            pptx_path,
            template_dir,
            slide_shell_ids=shell_ids,
        )
        geometry["slide_ir_path"] = str(resolved_slide_ir) if resolved_slide_ir else None
        if mapping_issue is not None:
            geometry["issues"] = [mapping_issue, *geometry.get("issues", [])]
            geometry["blocking_count"] = sum(
                item.get("severity") == "blocking" for item in geometry["issues"]
            )
            geometry["warning_count"] = sum(
                item.get("severity") == "warning" for item in geometry["issues"]
            )
            geometry["status"] = "fail" if geometry["blocking_count"] else "pass"
        gates.append(
            {
                "id": "template_geometry_pptx",
                "status": geometry.get("status", "fail"),
                "issues": geometry.get("issues", []),
                "report": geometry,
            }
        )
        text_layout = validate_pptx_text_layout(pptx_path)
        gates.append({"id": "pptx_text_layout", "status": text_layout.get("status", "fail"), "issues": text_layout.get("issues", []), "report": text_layout})
        if resolved_slide_ir is not None:
            try:
                native_component_bounds = validate_native_component_bounds(
                    pptx_path,
                    read_json(resolved_slide_ir),
                )
                gates.append(
                    {
                        "id": "native_component_bounds",
                        "status": native_component_bounds.get("status", "fail"),
                        "issues": native_component_bounds.get("issues", []),
                        "report": native_component_bounds,
                    }
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                gates.append(
                    {
                        "id": "native_component_bounds",
                        "status": "fail",
                        "issues": [issue("PPTX-COMPONENT-BOUNDS-IR", "Slide IR could not be read for native component bounds.", error=str(exc))],
                    }
                )
        else:
            gates.append(
                {
                    "id": "native_component_bounds",
                    "status": "review_required",
                    "issues": [issue("PPTX-COMPONENT-BOUNDS-IR-MISSING", "Compiled Slide IR is required for native component-bound checks.", severity="review")],
                }
            )
        gates.append({"id": "placeholder_scan", **scan_pptx_placeholders(pptx_path)})
    gates.append({"id": "human_visual_review", **validate_human_review(template_dir)})

    if (source_render_dir is None) != (generated_render_dir is None):
        gates.append(
            {
                "id": "render_diff",
                "status": "fail",
                "issues": [issue("VISUAL-DIFF-INCOMPLETE", "Source and generated render directories must be supplied together.")],
            }
        )
    elif source_render_dir is None and generated_render_dir is None:
        gates.append(
            {
                "id": "render_diff",
                "status": "review_required",
                "issues": [issue("VISUAL-DIFF-MISSING", "Source and generated render directories are required.", severity="review")],
            }
        )
    else:
        try:
            diff = pptx_visual_diff.compare_render_dirs(
                source_render_dir,
                generated_render_dir,
                report_dir or (template_dir / "promotion_gate" / "visual_diff"),
            )
            gates.append({"id": "render_diff", "status": diff.get("status", "fail"), "issues": diff.get("issues", []), "report": diff})
        except (OSError, ValueError) as exc:
            gates.append({"id": "render_diff", "status": "fail", "issues": [issue("VISUAL-DIFF-EXECUTION", "Visual diff could not be executed.", error=str(exc))]})

    if run_cross_material:
        target_report_dir = report_dir or (template_dir / "promotion_gate")
        gates.append(
            pptx_distill_promotion_gate.run_cross_material_gate(
                template_dir=template_dir,
                report_dir=target_report_dir,
                forbidden_keywords=[],
                max_pages=8,
            )
        )
    else:
        gates.append(
            {
                "id": "cross_material_smoke",
                "status": "review_required",
                "issues": [issue("CROSS-MATERIAL-MISSING", "Cross-material smoke test was not run.", severity="review")],
            }
        )

    if any(gate.get("status") == "fail" for gate in gates):
        status = "fail"
    elif any(gate.get("status") == "review_required" for gate in gates):
        status = "review_required"
    else:
        status = "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_dir.name,
        "status": status,
        "production_eligible": status == "pass",
        "blocking_count": sum(
            issue_row.get("severity", "blocking") == "blocking"
            for gate in gates
            for issue_row in gate.get("issues", [])
        ),
        "review_count": sum(
            issue_row.get("severity") == "review"
            for gate in gates
            for issue_row in gate.get("issues", [])
        ),
        "gates": gates,
    }


def promote_status(template_dir: Path, report: dict[str, Any]) -> None:
    if report.get("status") != "pass" or report.get("production_eligible") is not True:
        raise ValueError("production promotion is blocked until every gate passes")
    package_path = template_dir / "template_package.json"
    package = read_json(package_path)
    package.update(
        {
            "status": "production",
            "production_eligible": True,
            "last_gate_schema": report.get("schema_version"),
            "last_gate_status": report.get("status"),
        }
    )
    write_json(package_path, package)
    status_path = template_dir / "template_status.json"
    if status_path.is_file():
        status = read_json(status_path)
        status.update(
            {
                "status": "production",
                "production_eligible": True,
                "reason": "all fail-closed production gates passed",
                "last_gate_schema": report.get("schema_version"),
                "last_gate_status": report.get("status"),
            }
        )
        write_json(status_path, status)
    compile_template(template_dir, write=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fail-closed semantic template production gate.")
    parser.add_argument("template_dir", type=Path)
    parser.add_argument("--pptx", type=Path)
    parser.add_argument("--slide-ir", type=Path)
    parser.add_argument("--source-render-dir", type=Path)
    parser.add_argument("--generated-render-dir", type=Path)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--no-cross-material", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    template_dir = args.template_dir.resolve()
    try:
        report = run_gate(
            template_dir,
            pptx_path=args.pptx.resolve() if args.pptx else None,
            slide_ir_path=args.slide_ir.resolve() if args.slide_ir else None,
            source_render_dir=args.source_render_dir.resolve() if args.source_render_dir else None,
            generated_render_dir=args.generated_render_dir.resolve() if args.generated_render_dir else None,
            report_dir=args.report_dir.resolve() if args.report_dir else None,
            run_cross_material=not args.no_cross_material,
        )
        if args.report:
            write_json(args.report.resolve(), report)
        if args.promote:
            promote_status(template_dir, report)
    except (OSError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
        print(f"Error: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"{template_dir.name}: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
