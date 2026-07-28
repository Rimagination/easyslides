#!/usr/bin/env python3
"""Project declared source-template slots into an SVG source page."""

from __future__ import annotations

import html
import os
import re
import textwrap
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
TEXTBOX_TOLERANCE = 2.5


class SourceTemplateProjectionError(ValueError):
    """Raised when a declared source-template slot cannot be projected."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _float_attr(element: ET.Element, name: str) -> float | None:
    try:
        return float(element.attrib.get(name, ""))
    except (TypeError, ValueError):
        return None


def _close(a: float | None, b: Any, tolerance: float = TEXTBOX_TOLERANCE) -> bool:
    try:
        return a is not None and abs(a - float(b)) <= tolerance
    except (TypeError, ValueError):
        return False


def _box_matches(element: ET.Element, geometry: dict[str, Any] | None) -> bool:
    if not isinstance(geometry, dict):
        return False
    if _local_name(element.tag) == "text" and element.attrib.get("data-pptx-textbox") == "true":
        keys = ("data-pptx-box-x", "data-pptx-box-y", "data-pptx-box-w", "data-pptx-box-h")
    else:
        keys = ("x", "y", "width", "height")
    return all(
        _close(_float_attr(element, key), geometry.get(target))
        for key, target in zip(keys, ("x", "y", "width", "height"))
    )


def _slot_kind(slot: dict[str, Any]) -> str:
    return str(slot.get("kind") or "text").lower()


def _find_slot_element(root: ET.Element, slot: dict[str, Any]) -> ET.Element | None:
    slot_id = str(slot.get("slot_id") or "")
    kind = _slot_kind(slot)
    geometry = slot.get("geometry") if isinstance(slot.get("geometry"), dict) else {}
    candidates = []
    for element in root.iter():
        local = _local_name(element.tag)
        if kind == "text" and local != "text":
            continue
        if kind == "image" and local != "image":
            continue
        if element.attrib.get("data-slot-id") == slot_id:
            return element
        if _box_matches(element, geometry):
            candidates.append(element)
    return candidates[0] if candidates else None


def _value_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("text") or value.get("value") or value.get("label") or ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _wrap_lines(text: str, max_chars: int | None, max_lines: int | None) -> list[str]:
    raw_lines = text.splitlines() or [text]
    lines: list[str] = []
    for raw in raw_lines:
        if max_chars and max_chars > 0:
            lines.extend(textwrap.wrap(raw, width=max_chars, break_long_words=True, break_on_hyphens=False) or [""])
        else:
            lines.append(raw)
    if max_lines and max_lines > 0 and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "..."
    return lines or [""]


def _replace_text(element: ET.Element, slot: dict[str, Any], value: Any) -> None:
    geometry = slot.get("geometry") if isinstance(slot.get("geometry"), dict) else {}
    x = float(geometry.get("x") or 0)
    y = float(geometry.get("y") or 0)
    width = float(geometry.get("width") or 0)
    height = float(geometry.get("height") or 0)
    capacity = slot.get("capacity") if isinstance(slot.get("capacity"), dict) else {}
    max_chars = capacity.get("max_chars_per_line") or capacity.get("max_chars_per_line_zh")
    max_lines = capacity.get("max_lines")
    try:
        max_chars = int(max_chars) if max_chars is not None else None
    except (TypeError, ValueError):
        max_chars = None
    try:
        max_lines = int(max_lines) if max_lines is not None else None
    except (TypeError, ValueError):
        max_lines = None
    font_size = _float_attr(element, "font-size") or 20.0
    lines = _wrap_lines(_value_text(value), max_chars, max_lines)
    try:
        line_height_ratio = float(
            slot.get("line_height_ratio")
            or element.attrib.get("data-pptx-line-height-ratio")
            or 1.25
        )
    except (TypeError, ValueError):
        line_height_ratio = 1.25
    line_height = font_size * max(0.75, min(1.25, line_height_ratio))
    center_y = y + height / 2
    baseline_offset = font_size * 0.35
    start_y = center_y + baseline_offset - ((len(lines) - 1) * line_height) / 2

    anchor = str(
        slot.get("text_anchor")
        or element.attrib.get("data-pptx-text-anchor")
        or element.attrib.get("text-anchor")
        or "middle"
    ).lower()
    if anchor not in {"start", "middle", "end"}:
        anchor = "middle"
    anchor_x = x + width / 2 if anchor == "middle" else x + width if anchor == "end" else x

    for child in list(element):
        element.remove(child)
    element.text = None
    element.set("x", f"{anchor_x:.1f}")
    element.set("y", f"{start_y:.1f}")
    element.set("text-anchor", anchor)
    element.set("data-pptx-valign", "middle")
    element.set("data-center-lock", "true")
    element.set("data-slot-id", str(slot.get("slot_id") or "text"))
    if len(lines) == 1:
        element.text = html.unescape(lines[0])
        return
    namespace = element.tag.split("}", 1)[0].strip("{") if "}" in element.tag else SVG_NS
    for index, line in enumerate(lines):
        tspan = ET.SubElement(element, f"{{{namespace}}}tspan")
        tspan.set("x", f"{anchor_x:.1f}")
        tspan.set("y", f"{start_y + index * line_height:.1f}")
        tspan.text = html.unescape(line)


def _replace_image(
    element: ET.Element,
    slot: dict[str, Any],
    value: Any,
    asset_root: Path | None,
    output_root: Path,
) -> None:
    if isinstance(value, dict):
        value = value.get("href") or value.get("path") or value.get("src") or ""
    href = str(value or "")
    if not href:
        raise SourceTemplateProjectionError(f"image slot {slot.get('slot_id')} has no replacement href")
    if asset_root and not re.match(r"^(?:data:|https?://|#)", href):
        path = Path(href)
        if not path.is_absolute():
            if path.parts and path.parts[0].lower() == "assets":
                path = Path(*path.parts[1:])
            path = asset_root / path
        try:
            href = Path(os.path.relpath(path, output_root)).as_posix()
        except ValueError:
            href = path.as_posix()
    element.set("href", href)
    element.set(f"{{{XLINK_NS}}}href", href)
    element.set("data-slot-id", str(slot.get("slot_id") or "image"))


def _rewrite_fixed_asset_hrefs(root: ET.Element, asset_root: Path, output_root: Path) -> None:
    """Keep template-owned assets resolvable when projected outside the package."""
    for element in root.iter():
        if _local_name(element.tag) != "image":
            continue
        href = element.get("href") or element.get(f"{{{XLINK_NS}}}href") or ""
        if not href or re.match(r"^(?:data:|https?://|#)", href):
            continue
        path = Path(href)
        if path.is_absolute():
            continue
        parts = path.parts
        if not parts or parts[0].lower() != "assets":
            continue
        candidate = asset_root.joinpath(*parts[1:])
        if not candidate.is_file():
            continue
        try:
            relative = Path(os.path.relpath(candidate, output_root)).as_posix()
        except ValueError:
            # Windows cannot compute a relative path across drive letters.
            # Keep an absolute fallback so projection still fails visibly at
            # packaging time rather than silently dropping the asset.
            relative = candidate.as_posix()
        element.set("href", relative)
        element.set(f"{{{XLINK_NS}}}href", relative)


def project_source_template_svg(
    source_svg: str | Path,
    output_svg: str | Path,
    *,
    slots: list[dict[str, Any]],
    values: dict[str, Any],
    asset_root: str | Path | None = None,
) -> dict[str, Any]:
    """Replace declared text/image slots while preserving source geometry."""
    source_svg = Path(source_svg)
    output_svg = Path(output_svg)
    if not source_svg.exists():
        raise FileNotFoundError(source_svg)
    root = ET.parse(source_svg).getroot()
    asset_root_path = Path(asset_root).resolve() if asset_root else None
    if asset_root_path:
        _rewrite_fixed_asset_hrefs(root, asset_root_path, output_svg.parent.resolve())
    replaced: list[str] = []
    issues: list[dict[str, str]] = []
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        slot_id = str(slot.get("slot_id") or "")
        if slot_id not in values:
            continue
        element = _find_slot_element(root, slot)
        if element is None:
            issues.append({"slot_id": slot_id, "code": "SOURCE-SLOT-ELEMENT-NOT-FOUND"})
            continue
        if _slot_kind(slot) == "image":
            _replace_image(element, slot, values[slot_id], asset_root_path, output_svg.parent.resolve())
        elif _slot_kind(slot) == "text":
            _replace_text(element, slot, values[slot_id])
        else:
            issues.append({"slot_id": slot_id, "code": "SOURCE-SLOT-KIND-NOT-PROJECTABLE"})
            continue
        replaced.append(slot_id)

    output_svg.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.ElementTree(root).write(output_svg, encoding="utf-8", xml_declaration=True)
    return {
        "status": "pass" if not issues else "fail",
        "source_svg": str(source_svg),
        "output_svg": str(output_svg),
        "replaced_slots": replaced,
        "issue_count": len(issues),
        "issues": issues,
        "hard_geometry_rule": "text_center_y_matches_container_center_y",
    }


def render_source_template_projection(
    source_svg: str | Path,
    output_svg: str | Path,
    slots: list[dict[str, Any]],
    values: dict[str, Any],
    asset_root: str | Path | None = None,
) -> dict[str, Any]:
    return project_source_template_svg(
        source_svg,
        output_svg,
        slots=slots,
        values=values,
        asset_root=asset_root,
    )


try:
    from scripts.component_renderer_registry import register_renderer_handler
except ModuleNotFoundError:  # pragma: no cover
    from component_renderer_registry import register_renderer_handler

register_renderer_handler("source_template_projection", "svg", render_source_template_projection)
