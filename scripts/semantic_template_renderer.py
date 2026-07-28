#!/usr/bin/env python3
"""Render semantic EasySlides templates without DOM-order slot guessing.

Templates declare named slots in ``layouts.json`` and mark the corresponding
SVG element with ``data-slot="<slot_id>"``.  A deck plan supplies a
``slot_payload`` object.  Rendering is therefore role-to-role and fails closed
when capacity or contract checks fail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
SCHEMA_VERSION = "easyslides.semantic_render_manifest.v1"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


class SemanticTemplateError(ValueError):
    pass


class SlotCapacityError(SemanticTemplateError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise SemanticTemplateError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clear_generated_slide_svgs(output_dir: Path) -> None:
    """Remove deterministic slide outputs from an earlier render.

    Semantic output directories are rebuild targets.  Leaving renamed layouts
    behind silently adds stale slides during SVG-to-PPTX export, so only files
    matching the renderer's own ``NN_layout.svg`` naming contract are cleared.
    """
    generated_name = re.compile(r"^\d{2,4}_[A-Za-z0-9_-]+\.svg$")
    for path in output_dir.glob("*.svg"):
        if generated_name.fullmatch(path.name):
            path.unlink()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _visual_length(text: str) -> float:
    total = 0.0
    for char in text:
        total += 1.0 if ord(char) > 127 else 0.55
    return total


def _line_requirement(value: str, max_chars: int) -> int:
    if not value:
        return 0
    lines = value.splitlines() or [value]
    return sum(max(1, math.ceil(_visual_length(line) / max_chars)) for line in lines)


def _payload_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@dataclass(frozen=True)
class SemanticTemplate:
    root: Path
    template_id: str
    layouts: dict[str, dict[str, Any]]
    variants: list[dict[str, Any]]


def load_template(template_dir: str | Path) -> SemanticTemplate:
    root = Path(template_dir).resolve()
    layouts_payload = _read_json(root / "layouts.json")
    variants_payload = _read_json(root / "body_variants.json")
    template_id = str(layouts_payload.get("template_id") or root.name)
    rows = layouts_payload.get("layouts")
    if not isinstance(rows, list) or not rows:
        raise SemanticTemplateError("layouts.json must define a non-empty layouts list")
    layouts: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SemanticTemplateError("layout rows must be objects")
        layout_id = str(row.get("layout_id") or "")
        if not layout_id or layout_id in layouts:
            raise SemanticTemplateError(f"invalid or duplicate layout_id: {layout_id!r}")
        svg = root / str(row.get("svg") or "")
        if not svg.is_file():
            raise SemanticTemplateError(f"layout {layout_id!r} references missing SVG: {svg}")
        layouts[layout_id] = row
    variants = [row for row in variants_payload.get("variants", []) if isinstance(row, dict)]
    return SemanticTemplate(root=root, template_id=template_id, layouts=layouts, variants=variants)


def resolve_layout(template: SemanticTemplate, slide: dict[str, Any]) -> dict[str, Any]:
    explicit = str(slide.get("layout_id") or "")
    if explicit:
        explicit = explicit.split("/", 1)[-1]
        if explicit not in template.layouts:
            raise SemanticTemplateError(f"unknown layout_id {explicit!r}")
        return template.layouts[explicit]

    role = str(slide.get("role") or "content").lower()
    direct = [row for row in template.layouts.values() if str(row.get("role") or "") == role]
    if role != "content":
        if len(direct) != 1:
            raise SemanticTemplateError(f"role {role!r} must resolve to exactly one layout")
        return direct[0]

    shape = str(slide.get("content_shape") or "text_focus").lower()
    item_count = int(slide.get("item_count") or 0)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for variant in template.variants:
        shapes = {str(item).lower() for item in variant.get("content_shapes", [])}
        if shape not in shapes:
            continue
        minimum = int(variant.get("min_items") or 0)
        maximum = int(variant.get("max_items") or 999)
        if not minimum <= item_count <= maximum:
            continue
        layout_id = str(variant.get("layout_id") or variant.get("variant_id") or "")
        if layout_id in template.layouts:
            candidates.append((int(variant.get("priority") or 0), template.layouts[layout_id]))
    if not candidates:
        fallback = template.layouts.get("text_focus")
        if fallback is None:
            raise SemanticTemplateError(f"no layout matches content_shape {shape!r}")
        return fallback
    candidates.sort(key=lambda item: (-item[0], str(item[1].get("layout_id"))))
    return candidates[0][1]


def _slot_nodes(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    duplicates: set[str] = set()
    for node in root.iter():
        slot_id = str(node.attrib.get("data-slot") or "")
        if not slot_id:
            continue
        if slot_id in result:
            duplicates.add(slot_id)
        result[slot_id] = node
    if duplicates:
        raise SemanticTemplateError(f"duplicate SVG data-slot ids: {sorted(duplicates)}")
    return result


def _remove_node(root: ET.Element, node: ET.Element) -> None:
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parent = parents.get(node)
    if parent is not None:
        parent.remove(node)
        return
    for child in list(node):
        node.remove(child)
    node.text = ""


def _set_text(node: ET.Element, lines: list[str], *, bullet: bool, line_height: int) -> None:
    for child in list(node):
        node.remove(child)
    node.text = None
    x = node.attrib.get("x", "0")
    for index, line in enumerate(lines):
        tspan = ET.SubElement(node, f"{{{SVG_NS}}}tspan", {"x": x, "dy": "0" if index == 0 else str(line_height)})
        tspan.text = f"• {line}" if bullet else line


def _copy_image(source: Path, assets_dir: Path) -> str:
    digest = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()[:10]
    target = assets_dir / f"{digest}_{source.name}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        shutil.copy2(source, target)
    return f"assets/{target.name}"


def _copy_static_template_assets(template_dir: Path, assets_dir: Path) -> None:
    """Make template-owned raster/vector assets resolvable beside rendered SVGs."""
    source_dir = template_dir / "assets"
    if not source_dir.is_dir():
        return
    for source in source_dir.rglob("*"):
        if not source.is_file():
            continue
        target = assets_dir / source.relative_to(source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)


def _validate_capacity(slot: dict[str, Any], value: Any) -> list[str]:
    lines = _payload_lines(value)
    max_lines = int(slot.get("max_lines") or 1)
    max_chars = int(slot.get("max_chars_per_line") or 20)
    needed = sum(_line_requirement(line, max_chars) for line in lines)
    if needed > max_lines:
        raise SlotCapacityError(
            f"slot {slot.get('slot_id')!r} requires {needed} lines but allows {max_lines}; "
            f"overflow policy is {slot.get('overflow_policy', 'choose_variant_or_split')}"
        )
    return lines


def render_slide(
    template: SemanticTemplate,
    layout: dict[str, Any],
    slide: dict[str, Any],
    *,
    plan_dir: Path,
    assets_dir: Path,
) -> tuple[ET.ElementTree, list[str]]:
    source_svg = template.root / str(layout["svg"])
    tree = ET.parse(source_svg)
    root = tree.getroot()
    nodes = _slot_nodes(root)
    payload = slide.get("slot_payload")
    if not isinstance(payload, dict):
        raise SemanticTemplateError("each slide must define slot_payload")
    declared = [row for row in layout.get("slots", []) if isinstance(row, dict)]
    declared_ids = {str(row.get("slot_id") or "") for row in declared}
    unknown = sorted(set(payload) - declared_ids)
    if unknown:
        raise SemanticTemplateError(f"payload contains undeclared slots: {unknown}")

    rendered_slots: list[str] = []
    for slot in declared:
        slot_id = str(slot.get("slot_id") or "")
        if not slot_id or slot_id not in nodes:
            raise SemanticTemplateError(f"layout {layout.get('layout_id')} is missing data-slot {slot_id!r}")
        node = nodes[slot_id]
        required = bool(slot.get("required", True))
        if slot_id not in payload or payload.get(slot_id) in (None, "", []):
            if required:
                raise SemanticTemplateError(f"required slot {slot_id!r} has no payload")
            _remove_node(root, node)
            continue
        kind = str(slot.get("kind") or "text")
        value = payload[slot_id]
        if kind in {"text", "list"}:
            lines = _validate_capacity(slot, value)
            _set_text(
                node,
                lines,
                bullet=kind == "list",
                line_height=int(slot.get("line_height") or node.attrib.get("data-line-height") or 32),
            )
        elif kind == "image":
            source = Path(str(value))
            if not source.is_absolute():
                source = (plan_dir / source).resolve()
            if not source.is_file():
                raise SemanticTemplateError(f"image slot {slot_id!r} references missing file: {source}")
            href = _copy_image(source, assets_dir)
            node.set("href", href)
            node.set(f"{{{XLINK_NS}}}href", href)
        else:
            raise SemanticTemplateError(f"unsupported slot kind {kind!r}")
        rendered_slots.append(slot_id)

    xml = ET.tostring(root, encoding="unicode")
    if re.search(r"\{\{[^{}]+\}\}", xml):
        raise SemanticTemplateError(f"unresolved template token remains in {layout.get('layout_id')}")
    if "IMAGE SLOT" in xml or "data-source-background-hidden" in xml:
        raise SemanticTemplateError("debug/source-hiding artifacts are forbidden in semantic output")
    return tree, rendered_slots


def render_deck(template_dir: Path, deck_plan_path: Path, output_dir: Path) -> dict[str, Any]:
    template = load_template(template_dir)
    plan = _read_json(deck_plan_path)
    slides = [row for row in plan.get("slides", []) if isinstance(row, dict)]
    if not slides:
        raise SemanticTemplateError("deck plan contains no slides")
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_slide_svgs(output_dir)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    _copy_static_template_assets(template.root, assets_dir)
    assignments: list[dict[str, Any]] = []
    for index, slide in enumerate(slides, start=1):
        layout = resolve_layout(template, slide)
        tree, rendered_slots = render_slide(
            template,
            layout,
            slide,
            plan_dir=deck_plan_path.parent,
            assets_dir=assets_dir,
        )
        filename = f"{index:02d}_{layout['layout_id']}.svg"
        tree.write(output_dir / filename, encoding="utf-8", xml_declaration=False)
        assignments.append(
            {
                "slide": index,
                "role": slide.get("role"),
                "content_shape": slide.get("content_shape"),
                "layout_id": layout["layout_id"],
                "svg": filename,
                "rendered_slots": rendered_slots,
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "template_id": template.template_id,
        "deck_plan": str(deck_plan_path.resolve()),
        "slide_count": len(assignments),
        "assignments": assignments,
    }
    _write_json(output_dir / "render_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a named-slot semantic EasySlides template.")
    parser.add_argument("template_dir", type=Path)
    parser.add_argument("deck_plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = render_deck(args.template_dir.resolve(), args.deck_plan.resolve(), args.out.resolve())
    except (OSError, json.JSONDecodeError, SemanticTemplateError) as exc:
        print(f"Error: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Rendered {result['slide_count']} semantic slides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
