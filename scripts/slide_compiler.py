#!/usr/bin/env python3
"""Compile deck intent plus Template IR into executable Slide IR.

The Slide IR is the shared input for SVG and native-PPTX rendering.  It is the
first point where a shell, body variant, component instances, placements, and
bound payload are one resolved object rather than parallel planning files.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any
from xml.etree import ElementTree as ET

try:
    from scripts.template_compiler import ROOT, TemplateCompileError, compile_template, read_json, write_json
except ModuleNotFoundError:  # pragma: no cover
    from template_compiler import ROOT, TemplateCompileError, compile_template, read_json, write_json


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
SLIDE_IR_SCHEMA = "easyslides.slide_ir.v1"
SLIDE_COMPILE_REPORT_SCHEMA = "easyslides.slide_compile_report.v1"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


class SlideCompileError(ValueError):
    """Raised when slide intent cannot be resolved without guessing."""


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _frame(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        frame = {
            "x": float(value.get("x", 0)),
            "y": float(value.get("y", 0)),
            "width": float(value.get("width", value.get("w", 0))),
            "height": float(value.get("height", value.get("h", 0))),
        }
    except (TypeError, ValueError):
        return None
    if frame["width"] <= 0 or frame["height"] <= 0:
        return None
    return frame


def _role_alias(value: object) -> str:
    role = str(value or "content").strip().lower()
    return {"agenda": "toc", "section": "chapter", "closing": "ending"}.get(role, role)


def _shell_map(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(shell["shell_id"]): shell
        for shell in template_ir.get("shells", [])
        if isinstance(shell, dict) and shell.get("shell_id")
    }


def _variant_map(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(variant["variant_id"]): variant
        for variant in template_ir.get("body_variants", [])
        if isinstance(variant, dict) and variant.get("variant_id")
    }


def _component_map(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(component["asset_id"]): component
        for component in template_ir.get("components", [])
        if isinstance(component, dict) and component.get("asset_id")
    }


def _resolve_shell(template_ir: dict[str, Any], slide: dict[str, Any]) -> dict[str, Any]:
    shells = _shell_map(template_ir)
    explicit = str(slide.get("shell_id") or "")
    if explicit:
        explicit = explicit.rsplit("/", 1)[-1]
        if explicit not in shells:
            raise SlideCompileError(f"unknown shell_id {explicit!r}")
        return shells[explicit]
    role = _role_alias(slide.get("role"))
    matches = [shell for shell in shells.values() if _role_alias(shell.get("role")) == role]
    if len(matches) != 1:
        raise SlideCompileError(f"role {role!r} must resolve to exactly one public shell")
    return matches[0]


def _component_plan_variant(
    slide: dict[str, Any],
    *,
    page: str,
    component_plan: dict[str, Any] | None,
    variants: dict[str, dict[str, Any]],
) -> str:
    if not isinstance(component_plan, dict):
        return ""
    rows = [
        row
        for row in component_plan.get("slides", [])
        if isinstance(row, dict) and str(row.get("page") or "") == page
    ]
    if not rows:
        return ""
    assets = rows[0].get("selected_assets")
    if not isinstance(assets, list):
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("asset_id") or "")
        if asset_id.startswith("body_variant/"):
            candidate = asset_id.rsplit("/", 1)[-1]
            if candidate in variants:
                return candidate
    return ""


def _variant_score(variant: dict[str, Any], slide: dict[str, Any]) -> tuple[int, str]:
    selection = _as_dict(variant.get("selection"))
    shape = str(slide.get("content_shape") or slide.get("evidence_shape") or "").lower()
    story_role = str(slide.get("story_role") or slide.get("narrative_role") or "").strip().lower()
    shapes = {str(value).lower() for value in selection.get("content_shapes", [])}
    story_roles = {str(value).lower() for value in selection.get("story_roles", [])}
    haystack = f"{variant.get('variant_id', '')} {variant.get('best_for', '')}".lower()
    score = 0
    if story_role:
        if story_role in story_roles:
            score += 160
        elif story_roles:
            score -= 1000
    if shape:
        if shape in shapes:
            score += 80
        elif shape in haystack:
            score += 30
    density = slide.get("density")
    if density is not None and selection.get("density") is not None:
        try:
            score += max(0, 20 - abs(int(density) - int(selection["density"])) * 5)
        except (TypeError, ValueError):
            pass
    figure_count = slide.get("figure_count")
    if figure_count is not None and selection.get("figure_count") is not None:
        try:
            score += max(0, 20 - abs(int(figure_count) - int(selection["figure_count"])) * 5)
        except (TypeError, ValueError):
            pass
    score += int(selection.get("priority") or 0)
    return score, str(variant.get("variant_id") or "")


def _resolve_variant(
    template_ir: dict[str, Any],
    slide: dict[str, Any],
    *,
    page: str,
    component_plan: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    variants = _variant_map(template_ir)
    if not variants:
        raise SlideCompileError("content shell has no body variants")
    explicit_values = [
        slide.get("body_variant_id"),
        slide.get("variant_id"),
        slide.get("layout_id"),
    ]
    for value in explicit_values:
        if not isinstance(value, str) or not value.strip():
            continue
        candidate = value.strip().rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if candidate in variants:
            return variants[candidate], "explicit"
    planned = _component_plan_variant(
        slide,
        page=page,
        component_plan=component_plan,
        variants=variants,
    )
    if planned:
        return variants[planned], "component_plan"
    scored = sorted((_variant_score(variant, slide) for variant in variants.values()), key=lambda row: (-row[0], row[1]))
    if not scored:
        raise SlideCompileError("no body variant candidates are available")
    best_score, best_id = scored[0]
    if best_score <= 0 and len(scored) > 1:
        raise SlideCompileError(
            "content intent is ambiguous; supply body_variant_id or content_shape"
        )
    return variants[best_id], "semantic_score"


def _slot_contract_map(slots: object) -> dict[str, dict[str, Any]]:
    if not isinstance(slots, list):
        return {}
    return {
        str(slot.get("slot_id")): slot
        for slot in slots
        if isinstance(slot, dict) and slot.get("slot_id")
    }


def _validate_payload(slots: object, payload: dict[str, Any], *, context: str) -> None:
    contracts = _slot_contract_map(slots)
    required = {
        slot_id
        for slot_id, slot in contracts.items()
        if bool(slot.get("required", True))
    }
    missing = sorted(slot_id for slot_id in required if payload.get(slot_id) in (None, "", []))
    extra = sorted(set(payload) - set(contracts))
    if missing:
        raise SlideCompileError(f"{context} is missing required slot payload: {', '.join(missing)}")
    if extra:
        raise SlideCompileError(f"{context} contains undeclared slot payload: {', '.join(extra)}")


def _frame_inside_canvas(frame: dict[str, float], canvas: dict[str, Any]) -> bool:
    width = float(canvas.get("width") or 1280)
    height = float(canvas.get("height") or 720)
    tolerance = 0.01
    return (
        frame["x"] >= -tolerance
        and frame["y"] >= -tolerance
        and frame["x"] + frame["width"] <= width + tolerance
        and frame["y"] + frame["height"] <= height + tolerance
    )


def _frame_contains(container: dict[str, float], child: dict[str, float]) -> bool:
    tolerance = 0.01
    return (
        child["x"] >= container["x"] - tolerance
        and child["y"] >= container["y"] - tolerance
        and child["x"] + child["width"] <= container["x"] + container["width"] + tolerance
        and child["y"] + child["height"] <= container["y"] + container["height"] + tolerance
    )


def _content_body_canvas(shell: dict[str, Any]) -> dict[str, float] | None:
    direct = _frame(shell.get("body_canvas"))
    if direct:
        return direct
    for region in shell.get("regions", []):
        if isinstance(region, dict) and str(region.get("region_id") or "") == "body_canvas":
            frame = _frame(region.get("frame"))
            if frame:
                return frame
    return None


def _validate_source_guided_content(
    shell: dict[str, Any],
    variant: dict[str, Any],
    slide: dict[str, Any],
) -> None:
    """Enforce a template's reviewed source narrative instead of free assembly."""
    if str(shell.get("content_shell_policy") or "") != "source_guided_body_variant_required":
        return
    if slide.get("body_components") not in (None, []):
        raise SlideCompileError(
            "source-guided content forbids direct body_components; select a registered source-derived body variant"
        )
    story_role = str(slide.get("story_role") or slide.get("narrative_role") or "").strip()
    if not story_role:
        raise SlideCompileError(
            "source-guided content requires story_role; choose the source narrative step before selecting a body variant"
        )
    allowed_roles = {
        str(value).strip()
        for value in _as_dict(variant.get("selection")).get("story_roles", [])
        if str(value).strip()
    }
    if story_role not in allowed_roles:
        raise SlideCompileError(
            f"body variant {variant.get('variant_id')!r} does not permit story_role {story_role!r}; "
            f"allowed: {', '.join(sorted(allowed_roles))}"
        )
    guidance = _as_dict(variant.get("source_guidance"))
    expected_section = str(guidance.get("section") or "").strip()
    section = str(slide.get("section") or "").strip()
    if expected_section and section != expected_section:
        raise SlideCompileError(
            f"body variant {variant.get('variant_id')!r} belongs to section {expected_section!r}; "
            f"received {section or '<missing>'!r}"
        )


def _explicit_component_asset_id(
    raw: dict[str, Any],
    components: dict[str, dict[str, Any]],
    template_id: str,
) -> str:
    candidate = str(raw.get("asset_id") or raw.get("component_id") or "").strip()
    if candidate in components:
        return candidate
    prefixed = f"component/{template_id}/{candidate}"
    return prefixed if prefixed in components else candidate


def _compile_explicit_content_layers(
    template_ir: dict[str, Any],
    raw_components: object,
    *,
    body_canvas: dict[str, float],
    existing_instance_ids: set[str],
) -> list[dict[str, Any]]:
    """Compile opt-in, registered component instances inside an open content canvas."""
    if raw_components is None:
        return []
    if not isinstance(raw_components, list):
        raise SlideCompileError("body_components must be a list of registered component instances")
    components = _component_map(template_ir)
    layers: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_components, start=1):
        context = f"body_components[{index - 1}]"
        if not isinstance(raw, dict):
            raise SlideCompileError(f"{context} must be an object")
        asset_id = _explicit_component_asset_id(raw, components, str(template_ir.get("template_id") or ""))
        component = components.get(asset_id)
        if component is None:
            raise SlideCompileError(f"{context} references an unregistered component: {asset_id!r}")
        frame = _frame(raw.get("frame") or raw.get("placement"))
        if frame is None:
            raise SlideCompileError(f"{context} must declare a positive frame")
        if not _frame_inside_canvas(frame, template_ir["canvas"]) or not _frame_contains(body_canvas, frame):
            raise SlideCompileError(f"{context} frame must stay inside the content body_canvas")
        instance_id = str(raw.get("instance_id") or f"explicit_{index:02d}").strip()
        if not instance_id or instance_id in existing_instance_ids:
            raise SlideCompileError(f"{context} instance_id must be non-empty and unique")
        existing_instance_ids.add(instance_id)
        payload = _as_dict(raw.get("slot_payload") or raw.get("payload"))
        _validate_payload(component.get("slots"), payload, context=f"component {instance_id}")
        fit = str(raw.get("fit") or "contain")
        if fit not in {"contain", "stretch"}:
            raise SlideCompileError(f"{context} fit must be 'contain' or 'stretch'")
        if fit == "stretch" and _slot_contract_map(component.get("slots")):
            raise SlideCompileError(
                f"{context} cannot stretch a text-bearing component; use contain to preserve text geometry"
            )
        try:
            z_index = int(raw.get("z_index") or 50 + index * 10)
        except (TypeError, ValueError) as exc:
            raise SlideCompileError(f"{context} z_index must be an integer") from exc
        layers.append(
            {
                "layer_type": "component",
                "asset_id": asset_id,
                "instance_id": instance_id,
                "role": str(raw.get("role") or "explicit_component"),
                "region_id": "explicit",
                "frame": frame,
                "z_index": z_index,
                "fit": fit,
                "component": component,
                "slot_bindings": {},
                "payload": payload,
                "composition_source": "explicit_body_components",
            }
        )
    return sorted(layers, key=lambda row: (int(row["z_index"]), str(row["instance_id"])))


def _compile_content_layers(
    template_ir: dict[str, Any],
    variant: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    components = _component_map(template_ir)
    regions = {
        str(region["region_id"]): region
        for region in variant.get("regions", [])
        if isinstance(region, dict) and region.get("region_id")
    }
    layers: list[dict[str, Any]] = []
    for ref in variant.get("component_refs", []):
        if not isinstance(ref, dict):
            continue
        asset_id = str(ref.get("asset_id") or "")
        component = components.get(asset_id)
        if not component:
            if bool(ref.get("required", True)):
                raise SlideCompileError(f"required component is unresolved: {asset_id}")
            continue
        region_id = str(ref.get("region") or "")
        region = regions.get(region_id)
        placement = _frame(ref.get("placement"))
        frame = placement or (_frame(region.get("frame")) if region else None)
        if not frame:
            raise SlideCompileError(
                f"component instance {ref.get('instance_id')!r} has no resolved region or placement"
            )
        if not _frame_inside_canvas(frame, template_ir["canvas"]):
            raise SlideCompileError(
                f"component instance {ref.get('instance_id')!r} falls outside the slide canvas"
            )
        bindings = _as_dict(ref.get("slot_bindings"))
        component_payload = {
            str(component_slot): payload.get(str(variant_slot))
            for component_slot, variant_slot in bindings.items()
            if str(variant_slot) in payload
        }
        _validate_payload(
            component.get("slots"),
            component_payload,
            context=f"component {ref.get('instance_id')}",
        )
        layers.append(
            {
                "layer_type": "component",
                "asset_id": asset_id,
                "instance_id": str(ref.get("instance_id") or asset_id.rsplit("/", 1)[-1]),
                "role": str(ref.get("role") or ""),
                "region_id": region_id,
                "frame": frame,
                "z_index": int(
                    ref.get("z_index")
                    or (region.get("z_index") if region else 0)
                    or int(ref.get("order") or 1) * 10
                ),
                "fit": str((region.get("fit") if region else "") or "contain"),
                "component": component,
                "slot_bindings": bindings,
                "payload": component_payload,
            }
        )
    return sorted(layers, key=lambda row: (int(row["z_index"]), str(row["instance_id"])))


def compile_slides(
    deck_plan: dict[str, Any],
    template_ir: dict[str, Any],
    *,
    component_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slides = deck_plan.get("slides")
    if not isinstance(slides, list) or not slides:
        raise SlideCompileError("deck_plan.json must define a non-empty slides list")
    compiled: list[dict[str, Any]] = []
    for index, raw in enumerate(slides, start=1):
        if not isinstance(raw, dict):
            raise SlideCompileError(f"slides[{index - 1}] must be an object")
        page = str(raw.get("page") or f"P{index:02d}")
        shell = _resolve_shell(template_ir, raw)
        role = _role_alias(raw.get("role") or shell.get("role"))
        shell_payload = _as_dict(raw.get("shell_payload"))
        body_payload = _as_dict(raw.get("slot_payload") or raw.get("body_payload"))
        variant: dict[str, Any] | None = None
        variant_reason = ""
        layers: list[dict[str, Any]] = [
            {
                "layer_type": "shell",
                "shell_id": shell["shell_id"],
                "svg_path": shell["svg_path"],
                "z_index": 0,
            }
        ]
        if role == "content":
            variant, variant_reason = _resolve_variant(
                template_ir,
                raw,
                page=page,
                component_plan=component_plan,
            )
            _validate_source_guided_content(shell, variant, raw)
            _validate_payload(variant.get("slots"), body_payload, context=f"body variant {variant['variant_id']}")
            variant_layers = _compile_content_layers(template_ir, variant, body_payload)
            layers.extend(variant_layers)
            body_canvas = _content_body_canvas(shell)
            if body_canvas is None:
                raise SlideCompileError("content shell must declare a positive body_canvas")
            explicit_layers = _compile_explicit_content_layers(
                template_ir,
                raw.get("body_components"),
                body_canvas=body_canvas,
                existing_instance_ids={
                    str(layer.get("instance_id") or "")
                    for layer in variant_layers
                    if isinstance(layer, dict)
                },
            )
            if (
                str(variant.get("composition_mode") or "") == "open_component_composition"
                and not explicit_layers
            ):
                raise SlideCompileError(
                    "open_component_composition requires at least one body_components entry"
                )
            layers.extend(explicit_layers)
        else:
            if not shell_payload:
                shell_payload = body_payload
            _validate_payload(shell.get("slots"), shell_payload, context=f"shell {shell['shell_id']}")

        if role == "content":
            shell_contracts = _slot_contract_map(shell.get("slots"))
            for key in ("PAGE_TITLE", "TITLE"):
                if key in shell_contracts and key not in shell_payload:
                    candidate = raw.get("title") or body_payload.get(key)
                    if candidate not in (None, ""):
                        shell_payload[key] = candidate
            missing_shell_required = [
                slot_id
                for slot_id, slot in shell_contracts.items()
                if bool(slot.get("required", True)) and shell_payload.get(slot_id) in (None, "", [])
            ]
            # Content shells may retain optional source-derived slots underneath
            # the clear region; only the page-title contract remains required.
            required_visible = [slot_id for slot_id in missing_shell_required if slot_id in {"PAGE_TITLE", "TITLE"}]
            if required_visible:
                raise SlideCompileError(
                    f"content shell is missing required payload: {', '.join(required_visible)}"
                )

        compiled.append(
            {
                "page": page,
                "slide_index": index,
                "role": role,
                "shell_id": shell["shell_id"],
                "shell": shell,
                "shell_payload": shell_payload,
                "body_variant_id": variant.get("variant_id") if variant else "",
                "body_variant_reason": variant_reason,
                "body_payload": body_payload,
                "clear_region": variant.get("clear_region") if variant else None,
                "layers": layers,
            }
        )
    return {
        "schema_version": SLIDE_IR_SCHEMA,
        "deck_id": str(deck_plan.get("deck_id") or deck_plan.get("title") or "easyslides-deck"),
        "template_id": template_ir["template_id"],
        "template_source_digest": template_ir["source_digest"],
        "canvas": template_ir["canvas"],
        "slide_count": len(compiled),
        "slides": compiled,
    }


def compile_deck(
    deck_plan_path: str | Path,
    *,
    template: str | Path | None = None,
    template_ir_path: str | Path | None = None,
    component_plan_path: str | Path | None = None,
    write: bool = False,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    plan_path = Path(deck_plan_path).resolve()
    deck_plan = read_json(plan_path)
    if template_ir_path:
        template_ir = read_json(Path(template_ir_path).resolve())
    else:
        template_value = template or deck_plan.get("template_id")
        if not template_value:
            raise SlideCompileError("template id or template IR is required")
        template_report = compile_template(template_value)
        template_ir = template_report["template_ir"]
    component_plan = read_json(Path(component_plan_path).resolve()) if component_plan_path else None
    slide_ir = compile_slides(deck_plan, template_ir, component_plan=component_plan)
    target = Path(output_path).resolve() if output_path else plan_path.parent / "slide_ir.json"
    if write:
        write_json(target, slide_ir)
    return {
        "schema_version": SLIDE_COMPILE_REPORT_SCHEMA,
        "status": "pass",
        "template_id": template_ir["template_id"],
        "slide_count": slide_ir["slide_count"],
        "output": str(target),
        "slide_ir": slide_ir,
    }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slot_nodes(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for node in root.iter():
        slot_id = str(node.attrib.get("data-slot") or node.attrib.get("data-slot-id") or "")
        if slot_id and slot_id not in result:
            result[slot_id] = node
    return result


def _remove_node(root: ET.Element, node: ET.Element) -> None:
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parent = parents.get(node)
    if parent is not None:
        parent.remove(node)
    else:
        node.clear()


def _text_lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line for line in str(value or "").splitlines() if line.strip()]


def _set_centered_text(node: ET.Element, value: object) -> None:
    lines = _text_lines(value) or [""]
    for child in list(node):
        node.remove(child)
    node.text = None
    font_size = float(node.attrib.get("font-size") or 24)
    line_height = font_size * float(node.attrib.get("data-pptx-line-height-ratio") or 1.15)
    box_y = float(node.attrib.get("data-pptx-box-y") or max(0, float(node.attrib.get("y") or 0) - font_size))
    box_h = float(node.attrib.get("data-pptx-box-h") or max(font_size * 1.3, line_height * len(lines)))
    first_y = box_y + box_h / 2 - (len(lines) - 1) * line_height / 2 + font_size * 0.35
    x = node.attrib.get("x", "0")
    for index, line in enumerate(lines):
        tspan = ET.SubElement(
            node,
            f"{{{SVG_NS}}}tspan",
            {"x": x, "y": f"{first_y + index * line_height:.2f}"},
        )
        tspan.text = line
    node.set("data-pptx-valign", "middle")
    node.set("data-center-lock", "true")


def _set_evidence_rows(root: ET.Element, node: ET.Element, value: object) -> None:
    """Render newline-delimited evidence as individual, centered text rows."""
    lines = _text_lines(value) or [""]
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parent = parents.get(node)
    if parent is None:
        _set_centered_text(node, value)
        return

    box_x = float(node.attrib.get("data-pptx-box-x") or node.attrib.get("x") or 0)
    box_y = float(node.attrib.get("data-pptx-box-y") or 0)
    box_w = float(node.attrib.get("data-pptx-box-w") or 0)
    box_h = float(node.attrib.get("data-pptx-box-h") or 0)
    if box_w <= 0 or box_h <= 0:
        _set_centered_text(node, value)
        return

    row_count = len(lines)
    outer_gap = 12.0
    row_gap = 12.0 if row_count <= 3 else 8.0
    row_h = (box_h - outer_gap * 2 - row_gap * (row_count - 1)) / row_count
    if row_h < 42:
        _set_centered_text(node, value)
        return

    font_size = min(24.0, max(18.0, row_h * 0.28))
    group = ET.Element(f"{{{SVG_NS}}}g", {"data-easyslides-generated": "evidence_rows"})
    text_font = node.attrib.get("font-family") or "Arial, sans-serif"
    text_fill = node.attrib.get("fill") or "#060607"
    for index, line in enumerate(lines):
        row_y = box_y + outer_gap + index * (row_h + row_gap)
        fill = "#FBF5FC" if index % 2 == 0 else "#FFFFFF"
        accent = "#C00000" if index == row_count - 1 and row_count > 1 else "#751497"
        group.append(
            ET.Element(
                f"{{{SVG_NS}}}rect",
                {
                    "x": f"{box_x + 4:.2f}",
                    "y": f"{row_y:.2f}",
                    "width": f"{box_w - 8:.2f}",
                    "height": f"{row_h:.2f}",
                    "fill": fill,
                    "stroke": "#751497",
                    "stroke-opacity": "0.26",
                },
            )
        )
        group.append(
            ET.Element(
                f"{{{SVG_NS}}}rect",
                {
                    "x": f"{box_x + 4:.2f}",
                    "y": f"{row_y:.2f}",
                    "width": "9",
                    "height": f"{row_h:.2f}",
                    "fill": accent,
                },
            )
        )
        number = ET.Element(
            f"{{{SVG_NS}}}text",
            {
                "x": f"{box_x + 28:.2f}",
                "y": f"{row_y + row_h / 2 + 7:.2f}",
                "font-family": text_font,
                "font-size": "18",
                "font-weight": "700",
                "fill": accent,
                "text-anchor": "start",
            },
        )
        number.text = f"{index + 1:02d}"
        group.append(number)
        line_node = ET.Element(
            f"{{{SVG_NS}}}text",
            {
                "x": f"{box_x + 82:.2f}",
                "y": f"{row_y + row_h / 2 + font_size * 0.35:.2f}",
                "text-anchor": "start",
                "font-family": text_font,
                "font-size": f"{font_size:.2f}",
                "fill": text_fill,
                "data-pptx-textbox": "true",
                "data-pptx-measure-text": "T",
                "data-pptx-box-x": f"{box_x + 82:.2f}",
                "data-pptx-box-y": f"{row_y + 4:.2f}",
                "data-pptx-box-w": f"{box_w - 102:.2f}",
                "data-pptx-box-h": f"{row_h - 8:.2f}",
                "data-pptx-valign": "middle",
                "data-center-lock": "true",
                "data-pptx-line-height-ratio": "1.150",
                "data-pptx-text-anchor": "start",
            },
        )
        line_node.text = line
        group.append(line_node)

    position = list(parent).index(node)
    parent.insert(position, group)
    parent.remove(node)


def _copy_asset(source: Path, assets_dir: Path) -> str:
    target = assets_dir / source.name
    if source.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return f"assets/{target.name}"


def _apply_payload(
    root: ET.Element,
    contracts: object,
    payload: dict[str, Any],
    *,
    source_root: Path,
    assets_dir: Path,
    remove_unbound: bool,
) -> None:
    nodes = _slot_nodes(root)
    contract_map = _slot_contract_map(contracts)
    for slot_id, contract in contract_map.items():
        node = nodes.get(slot_id)
        if node is None:
            raise SlideCompileError(f"SVG is missing declared data-slot {slot_id!r}")
        value = payload.get(slot_id)
        if value in (None, "", []):
            if bool(contract.get("required", True)):
                raise SlideCompileError(f"required SVG slot {slot_id!r} has no payload")
            if remove_unbound:
                _remove_node(root, node)
            continue
        kind = str(contract.get("kind") or node.attrib.get("data-slot-kind") or "text")
        if kind in {"text", "list"}:
            if node.attrib.get("data-easyslides-layout") == "evidence_rows":
                _set_evidence_rows(root, node, value)
            else:
                _set_centered_text(node, value)
        elif kind == "image":
            source = Path(str(value))
            if not source.is_absolute():
                source = (source_root / source).resolve()
            if not source.is_file():
                raise SlideCompileError(f"image slot {slot_id!r} references missing file: {source}")
            href = _copy_asset(source, assets_dir)
            node.set("href", href)
            node.set(f"{{{XLINK_NS}}}href", href)
        else:
            raise SlideCompileError(f"unsupported slot kind {kind!r}")


def _component_source(component: dict[str, Any]) -> Path:
    raw = str(component.get("asset_path") or "")
    if not raw:
        raise SlideCompileError(f"component {component.get('asset_id')!r} has no executable asset_path")
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.is_file():
        raise SlideCompileError(f"component asset does not exist: {path}")
    return path


def _append_component(
    slide_root: ET.Element,
    layer: dict[str, Any],
    *,
    assets_dir: Path,
) -> None:
    component = layer["component"]
    source = _component_source(component)
    component_root = ET.parse(source).getroot()
    _apply_payload(
        component_root,
        component.get("slots"),
        _as_dict(layer.get("payload")),
        source_root=source.parent,
        assets_dir=assets_dir,
        remove_unbound=True,
    )
    frame = layer["frame"]
    view_box = component_root.attrib.get(
        "viewBox",
        f"0 0 {component.get('geometry', {}).get('width', frame['width'])} "
        f"{component.get('geometry', {}).get('height', frame['height'])}",
    )
    try:
        _vx, _vy, source_width, source_height = [float(value) for value in view_box.replace(",", " ").split()]
    except (TypeError, ValueError):
        source_width = float(component.get("geometry", {}).get("width") or frame["width"])
        source_height = float(component.get("geometry", {}).get("height") or frame["height"])
    scale_x = frame["width"] / source_width
    scale_y = frame["height"] / source_height
    if str(layer.get("fit")) != "stretch":
        scale_x = scale_y = min(scale_x, scale_y)
    offset_x = frame["x"] + (frame["width"] - source_width * scale_x) / 2
    offset_y = frame["y"] + (frame["height"] - source_height * scale_y) / 2
    group = ET.Element(
        f"{{{SVG_NS}}}g",
        {
            "transform": f"translate({offset_x:.6f} {offset_y:.6f}) scale({scale_x:.8f} {scale_y:.8f})",
            "data-easyslides-instance": str(layer["instance_id"]),
            "data-easyslides-asset-id": str(layer["asset_id"]),
        },
    )
    for child in list(component_root):
        group.append(deepcopy(child))
    slide_root.append(group)


def render_slide_ir_to_svg(
    slide_ir: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    assets_dir = target / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    template_path = ROOT / "templates" / "layouts" / str(slide_ir["template_id"])
    template_assets = template_path / "assets"
    if template_assets.is_dir():
        shutil.copytree(template_assets, assets_dir, dirs_exist_ok=True)
    outputs: list[str] = []
    for slide in slide_ir.get("slides", []):
        shell = slide["shell"]
        shell_path = Path(str(shell["svg_path"]))
        if not shell_path.is_absolute():
            shell_path = (ROOT / shell_path).resolve()
        root = ET.parse(shell_path).getroot()
        _apply_payload(
            root,
            shell.get("slots"),
            _as_dict(slide.get("shell_payload")),
            source_root=shell_path.parent,
            assets_dir=assets_dir,
            remove_unbound=True,
        )
        clear_region = _frame(slide.get("clear_region"))
        if clear_region:
            root.append(
                ET.Element(
                    f"{{{SVG_NS}}}rect",
                    {
                        "x": str(clear_region["x"]),
                        "y": str(clear_region["y"]),
                        "width": str(clear_region["width"]),
                        "height": str(clear_region["height"]),
                        "fill": "#FFFFFF",
                        "data-easyslides-clear-region": str(slide.get("body_variant_id") or ""),
                    },
                )
            )
        for layer in slide.get("layers", []):
            if isinstance(layer, dict) and layer.get("layer_type") == "component":
                _append_component(root, layer, assets_dir=assets_dir)
        output = target / f"{int(slide['slide_index']):02d}_{slide['shell_id']}.svg"
        ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
        outputs.append(str(output))
    return {
        "schema_version": "easyslides.slide_ir_svg_render.v1",
        "status": "pass",
        "output_dir": str(target),
        "slide_count": len(outputs),
        "svg_files": outputs,
    }


def render_slide_ir_to_pptx(
    slide_ir: dict[str, Any],
    output_path: str | Path,
    *,
    svg_output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path).resolve()
    svg_dir = Path(svg_output_dir).resolve() if svg_output_dir else output.parent / f"{output.stem}_svg"
    svg_report = render_slide_ir_to_svg(slide_ir, svg_dir)
    try:
        from scripts.svg_to_pptx.pptx_builder import create_pptx_with_native_svg
    except ModuleNotFoundError:  # pragma: no cover
        from svg_to_pptx.pptx_builder import create_pptx_with_native_svg
    ok = create_pptx_with_native_svg(
        [Path(path) for path in svg_report["svg_files"]],
        output,
        canvas_format=str(slide_ir.get("canvas", {}).get("format") or "ppt169"),
        verbose=False,
        transition=None,
        use_compat_mode=False,
        use_native_shapes=True,
        enable_notes=False,
    )
    return {
        "schema_version": "easyslides.slide_ir_pptx_render.v1",
        "status": "pass" if ok and output.is_file() else "fail",
        "output": str(output),
        "slide_count": slide_ir.get("slide_count", 0),
        "svg_render": svg_report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_plan", type=Path)
    parser.add_argument("--template")
    parser.add_argument("--template-ir", type=Path)
    parser.add_argument("--component-plan", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--svg-out", type=Path)
    parser.add_argument("--pptx-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compile_deck(
            args.deck_plan,
            template=args.template,
            template_ir_path=args.template_ir,
            component_plan_path=args.component_plan,
            write=bool(args.out),
            output_path=args.out,
        )
        if args.svg_out:
            report["svg_render"] = render_slide_ir_to_svg(report["slide_ir"], args.svg_out)
        if args.pptx_out:
            report["pptx_render"] = render_slide_ir_to_pptx(
                report["slide_ir"],
                args.pptx_out,
                svg_output_dir=args.svg_out,
            )
            if report["pptx_render"]["status"] != "pass":
                report["status"] = "fail"
    except (OSError, TemplateCompileError, SlideCompileError, ET.ParseError) as exc:
        report = {
            "schema_version": SLIDE_COMPILE_REPORT_SCHEMA,
            "status": "fail",
            "issues": [{"code": "SLIDE-COMPILE", "message": str(exc)}],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Slide compiler: {report['status']} ({report.get('slide_count', 0)} slide(s))")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
