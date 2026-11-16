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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

try:
    from scripts.academic_composition import render_composition, validate_academic_authoring
    from scripts.svg_slot_binding import set_image_slot_href, slot_content_node
    from scripts.academic_paper_visuals import VisualSelectionError, select_discipline_image
    from scripts.institution_logo import fetch_logo, identify_presenter_institution
    from scripts.template_palette import PaletteError, apply_color_replacements, palette_color_replacements, read_palette_catalog
except ModuleNotFoundError:  # direct script execution
    from academic_composition import render_composition, validate_academic_authoring
    from svg_slot_binding import set_image_slot_href, slot_content_node
    from academic_paper_visuals import VisualSelectionError, select_discipline_image
    from institution_logo import fetch_logo, identify_presenter_institution
    from template_palette import PaletteError, apply_color_replacements, palette_color_replacements, read_palette_catalog


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
SCHEMA_VERSION = "easyslides.semantic_render_manifest.v1"
ACADEMIC_TEMPLATE_IDS = {"academic_general", "academic_paper", "academic_paper_report"}
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
    pagination: dict[str, Any] = field(default_factory=dict)


def load_template(template_dir: str | Path) -> SemanticTemplate:
    root = Path(template_dir).resolve()
    # Historical repository paths also work in clean clones without Windows
    # junctions. An existing user template at the old path still takes priority.
    if (not root.exists() and root.name in {"academic_paper", "academic_paper_report"}
            and root.parent.name in {"layouts", "development"}
            and root.parent.parent.name == "templates"):
        canonical = root.parent.parent / "layouts" / "academic_general"
        if (canonical / "layouts.json").is_file():
            root = canonical.resolve()
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
    pagination = layouts_payload.get("pagination")
    return SemanticTemplate(root=root, template_id=template_id, layouts=layouts, variants=variants,
                            pagination=pagination if isinstance(pagination, dict) else {})


def resolve_layout(template: SemanticTemplate, slide: dict[str, Any]) -> dict[str, Any]:
    if isinstance(slide.get("composition"), dict) and not slide.get("layout_id"):
        if "scientific_composition" not in template.layouts:
            raise SemanticTemplateError("selected template has no scientific composition body")
        return template.layouts["scientific_composition"]
    explicit = str(slide.get("layout_id") or "")
    if explicit:
        explicit = explicit.split("/", 1)[-1]
        if explicit not in template.layouts:
            raise SemanticTemplateError(f"unknown layout_id {explicit!r}")
        return template.layouts[explicit]

    role = str(slide.get("role") or "content").lower()
    if template.template_id in ACADEMIC_TEMPLATE_IDS and role == "ending":
        # Preserve existing reference-heavy ending plans while new plans use
        # the user-selected blue-band ending by default.
        old = template.layouts.get("ending")
        new = template.layouts.get("ending_blue_band")
        payload = slide.get("slot_payload")
        if old and new and isinstance(payload, dict):
            old_ids = {slot.get("slot_id") for slot in old.get("slots", [])}
            new_ids = {slot.get("slot_id") for slot in new.get("slots", [])}
            present = {key for key, value in payload.items() if value not in (None, "", [])}
            if present & (old_ids - new_ids):
                if present & (new_ids - old_ids):
                    raise SemanticTemplateError("ending mixes legacy reference fields with blue-band fields")
                return old
    direct = [
        row for row in template.layouts.values()
        if str(row.get("role") or "") == role and not row.get("explicit_only", False)
    ]
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


def _reflow_numbered_toc(root: ET.Element, layout: dict[str, Any], payload: dict[str, Any]) -> None:
    """Distribute a template's optional numbered TOC entries over its available height."""
    config = layout.get("numbered_toc")
    if not config:
        return
    maximum = int(config["max_items"])
    first_y, last_y = float(config["first_row_y"]), float(config["last_row_y"])
    slot_ids = [f"TOC_ITEM_{i}_TITLE" for i in range(1, maximum + 1)]
    present = [i for i, slot_id in enumerate(slot_ids, 1) if payload.get(slot_id) not in (None, "", [])]
    if not present or present != list(range(1, len(present) + 1)):
        raise SemanticTemplateError("numbered TOC entries must start at 1 and be consecutive")

    slots = _slot_nodes(root)
    number_nodes = {node.get("data-toc-number-for"): node for node in root.iter()
                    if node.get("data-toc-number-for")}
    for index, slot_id in enumerate(slot_ids, 1):
        number, title = number_nodes.get(slot_id), slots.get(slot_id)
        if number is None or title is None:
            raise SemanticTemplateError(f"numbered TOC layout is missing {slot_id!r} or its number")
        if index not in present:
            _remove_node(root, number)
            continue
        target_y = ((first_y + last_y) / 2 if len(present) == 1 else
                    first_y + (last_y - first_y) * (index - 1) / (len(present) - 1))
        for node in (number, title):
            old_y = float(node.attrib["data-pptx-box-y"])
            node.set("data-pptx-box-y", f"{target_y:.2f}")
            node.set("y", f"{float(node.attrib['y']) + target_y - old_y:.2f}")


def _set_text(node: ET.Element, lines: list[str], *, bullet: bool, line_height: int) -> None:
    node = slot_content_node(node, "text")
    for child in list(node):
        node.remove(child)
    if _local_name(node.tag) == "tspan":
        node.text = "\n".join(f"• {line}" if bullet else line for line in lines)
        return
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


def _footer_source_identity(slide: dict[str, Any], source_map: dict[str, dict[str, Any]],
                            source_text: str) -> tuple[str, str]:
    """Identify an article, preferring explicit evidence and figure parent links."""
    roots: set[str] = set()
    references = slide.get("evidence_sources")
    if isinstance(references, list):
        for reference in references:
            if not isinstance(reference, dict) or not reference.get("source_id"):
                continue
            source_id = str(reference["source_id"])
            visited: set[str] = set()
            while source_id not in visited:
                visited.add(source_id)
                parent = source_map.get(source_id, {}).get("parent_source")
                if not parent:
                    break
                source_id = str(parent)
            roots.add(source_id)
    if len(roots) == 1:
        return "id", next(iter(roots))

    text = re.sub(r"\s+", " ", source_text.strip().casefold())
    text = re.sub(r"^(?:来源|source)\s*[:：]\s*", "", text)
    locator = (r"(?:§{1,2}\s*|(?:fig(?:ure)?|tables?|tab|pp?|pages?|sec(?:tion)?)\.?\s*|"
               r"(?:图|表|第)\s*)(?=[0-9ivxlc])[^;；]*$")
    text = re.sub(r"(?:\s*[,，;；]\s*|\s+)" + locator, "", text, flags=re.IGNORECASE).strip()
    return "label", text


def _set_chapter_image_crop(node: ET.Element, source: Path) -> None:
    """Zoom into the center while preserving a native, adjustable picture crop."""
    try:
        if source.suffix.lower() == ".svg":
            image = ET.parse(source).getroot()
            viewbox = re.split(r"[\s,]+", image.get("viewBox", "").strip())
            if len(viewbox) == 4:
                width, height = float(viewbox[2]), float(viewbox[3])
            else:
                width = float(re.match(r"[0-9.]+", image.get("width", "")).group())
                height = float(re.match(r"[0-9.]+", image.get("height", "")).group())
        else:
            from PIL import Image
            with Image.open(source) as image:
                width, height = image.size
        if width <= 0 or height <= 0:
            raise ValueError("nonpositive image dimensions")
    except (ImportError, OSError, ValueError, AttributeError, ET.ParseError) as exc:
        raise SemanticTemplateError(f"cannot determine chapter image dimensions: {source}") from exc

    image_ratio = width / height
    box_ratio = float(node.get("width", "0")) / float(node.get("height", "0"))
    zoom = 0.72
    crop_width = zoom * min(1.0, box_ratio / image_ratio)
    crop_height = zoom * min(1.0, image_ratio / box_ratio)
    left, top = (1 - crop_width) / 2, (1 - crop_height) / 2
    node.set("viewBox", f"{left:.6f} {top:.6f} {crop_width:.6f} {crop_height:.6f}")


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
    max_codepoints = slot.get("max_codepoints")
    if max_codepoints is not None and any(len(line) > int(max_codepoints) for line in lines):
        raise SlotCapacityError(
            f"slot {slot.get('slot_id')!r} exceeds its {max_codepoints}-character limit"
        )
    if slot.get("require_explicit_line_breaks") and any(_visual_length(line) > max_chars for line in lines):
        raise SlotCapacityError(
            f"slot {slot.get('slot_id')!r} needs explicit line breaks within {max_chars} characters per line"
        )
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
    palette_replacements: dict[str, str] | None = None,
) -> tuple[ET.ElementTree, list[str]]:
    source_svg = template.root / str(layout["svg"])
    tree = ET.parse(source_svg)
    root = tree.getroot()
    if palette_replacements:
        for node in root.iter():
            for name in ("fill", "stroke", "stop-color", "color", "style"):
                if name in node.attrib:
                    node.set(name, apply_color_replacements(node.attrib[name], palette_replacements))
    nodes = _slot_nodes(root)
    payload = slide.get("slot_payload")
    if not isinstance(payload, dict):
        raise SemanticTemplateError("each slide must define slot_payload")
    declared = [row for row in layout.get("slots", []) if isinstance(row, dict)]
    declared_ids = {str(row.get("slot_id") or "") for row in declared}
    unknown = sorted(set(payload) - declared_ids)
    if unknown:
        raise SemanticTemplateError(f"payload contains undeclared slots: {unknown}")

    if template.template_id in ACADEMIC_TEMPLATE_IDS and "CHAPTER_IMAGE" in declared_ids:
        if not payload.get("CHAPTER_IMAGE"):
            chapter_rect = next(node for node in root.iter() if node.get("id") == "header-chapter")
            chapter_rect.attrib.pop("fill-opacity", None)

    # Decorations linked to optional slots remain separate from the editable
    # text and image objects. Omit them when their corresponding slot is empty.
    for node in list(root.iter()):
        show_if = node.get("data-visible-if-slot")
        hide_if = node.get("data-visible-unless-slot")
        dependency = show_if or hide_if
        if not dependency:
            continue
        if dependency not in declared_ids:
            raise SemanticTemplateError(f"decoration references undeclared slot {dependency!r}")
        present = payload.get(dependency) not in (None, "", [])
        if (show_if and not present) or (hide_if and present):
            _remove_node(root, node)

    _reflow_numbered_toc(root, layout, payload)
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
            # Some cover titles reserve a taller, higher frame for two lines.
            # Keep the SVG baseline and native PowerPoint textbox in sync.
            if len(lines) > 1 and slot.get("multiline_layout"):
                geometry = slot["multiline_layout"]
                text_node = slot_content_node(node, "text")
                for attribute, key in (("y", "baseline_y"), ("data-pptx-box-y", "textbox_y"),
                                       ("data-pptx-box-h", "textbox_height")):
                    text_node.set(attribute, str(geometry[key]))
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
            if template.template_id in ACADEMIC_TEMPLATE_IDS and slot_id == "CHAPTER_IMAGE":
                _set_chapter_image_crop(node, source)
            href = _copy_image(source, assets_dir)
            set_image_slot_href(node, href)
        else:
            raise SemanticTemplateError(f"unsupported slot kind {kind!r}")
        rendered_slots.append(slot_id)

    if layout.get("layout_id") == "scientific_composition":
        if not isinstance(slide.get("composition"), dict):
            raise SemanticTemplateError("scientific_composition requires a scientific body payload")
        def resolve_body_image(raw: str) -> str:
            source = Path(raw)
            if not source.is_absolute():
                source = (plan_dir / source).resolve()
            if not source.is_file():
                raise SemanticTemplateError(f"scientific figure is missing: {source}")
            return _copy_image(source, assets_dir)
        try:
            body = render_composition(slide["composition"], image_resolver=resolve_body_image,
                                      colors={"primary": (palette_replacements or {}).get("#102F4A", "#102F4A")})
        except (KeyError, TypeError, ValueError) as exc:
            raise SemanticTemplateError(f"scientific body: {exc}") from exc
        root.append(body)

    xml = ET.tostring(root, encoding="unicode")
    if re.search(r"\{\{[^{}]+\}\}", xml):
        raise SemanticTemplateError(f"unresolved template token remains in {layout.get('layout_id')}")
    if "IMAGE SLOT" in xml or "data-source-background-hidden" in xml:
        raise SemanticTemplateError("debug/source-hiding artifacts are forbidden in semantic output")
    return tree, rendered_slots


def render_deck(template_dir: Path, deck_plan_path: Path, output_dir: Path) -> dict[str, Any]:
    template = load_template(template_dir)
    plan = _read_json(deck_plan_path)
    authoring_issues = validate_academic_authoring(plan)
    if any(item["severity"] == "error" for item in authoring_issues):
        raise SemanticTemplateError("; ".join(f"{i['code']}: {i['message']}" for i in authoring_issues[:8]))
    replacements: dict[str, str] = {}
    theme_selection = None
    if template.template_id in ACADEMIC_TEMPLATE_IDS:
        brief = plan.get("academic_brief") if isinstance(plan.get("academic_brief"), dict) else {}
        theme_id = plan.get("theme_palette") or brief.get("theme_palette")
        if plan.get("theme_palette") and brief.get("theme_palette") and plan["theme_palette"] != brief["theme_palette"]:
            raise SemanticTemplateError("theme_palette conflicts with academic_brief.theme_palette")
        if theme_id:
            try:
                catalog = read_palette_catalog(template.root)
                replacements = palette_color_replacements(catalog, str(theme_id))
                preset = catalog["palettes"].get(str(theme_id))
                name = preset["name"] if preset else f"自定义 {str(theme_id).upper()}"
                theme_selection = {"id": str(theme_id), "name": name}
            except (KeyError, OSError, ValueError, PaletteError) as exc:
                raise SemanticTemplateError(f"cannot select theme palette: {exc}") from exc
    slides = [row for row in plan.get("slides", []) if isinstance(row, dict)]
    if not slides:
        raise SemanticTemplateError("deck plan contains no slides")
    visual_selection = None
    default_visual = None
    if template.template_id in ACADEMIC_TEMPLATE_IDS:
        try:
            visual_selection = select_discipline_image(template.root, plan, slides)
        except (OSError, KeyError, TypeError, ValueError, VisualSelectionError) as exc:
            raise SemanticTemplateError(f"cannot select academic cover image: {exc}") from exc
        manual_cover = next(
            (row.get("slot_payload", {}).get("BAND_IMAGE") for row in slides
             if str(row.get("role") or "").lower() == "cover"
             and isinstance(row.get("slot_payload"), dict)
             and row["slot_payload"].get("BAND_IMAGE")),
            None,
        )
        brief = plan.get("academic_brief") if isinstance(plan.get("academic_brief"), dict) else {}
        image_source = plan.get("theme_image_source") or brief.get("theme_image_source")
        theme_image = plan.get("theme_image_path") or brief.get("theme_image_path")
        if image_source in {"generate_new", "user_provided"} and not (manual_cover or theme_image):
            raise SemanticTemplateError(
                f"theme_image_source={image_source} requires its theme image before rendering; "
                "supply theme_image_path or cover BAND_IMAGE instead of falling back to template assets"
            )
        default_visual = manual_cover or theme_image or visual_selection.get("path")
        if manual_cover:
            visual_selection["image_source"] = "provided_cover"
        elif theme_image:
            visual_selection["image_source"] = image_source or "user_provided"
        elif default_visual:
            visual_selection["image_source"] = "discipline_catalogue"
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_slide_svgs(output_dir)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    _copy_static_template_assets(template.root, assets_dir)
    logo_selection = None
    default_logo = None
    if template.template_id in ACADEMIC_TEMPLATE_IDS:
        needs_logo = any(
            (str(slide.get("role") or "").lower() == "ending" or
             str(slide.get("layout_id") or "").split("/")[-1] == "ending_blue_band")
            and resolve_layout(template, slide)["layout_id"] == "ending_blue_band"
            and isinstance(slide.get("slot_payload"), dict)
            and "INSTITUTION_LOGO" not in slide["slot_payload"]
            for slide in slides
        )
        if needs_logo:
            identity = identify_presenter_institution(plan, slides)
            logo_selection = {"identity": identity, "status": "fallback", "reason": identity.get("reason")}
            if identity["status"] == "identified":
                project_dir = output_dir.resolve().parent
                try:
                    result = fetch_logo(project_dir, identity["institution"], variant="emblem", timeout=10)
                    logo_selection.update(status=result["status"], reason=result["reason"], resolution=result)
                    if result["status"] == "resolved" and result.get("asset_path"):
                        default_logo = str(project_dir / result["asset_path"])
                except (OSError, ValueError) as exc:
                    logo_selection.update(reason="resource_unavailable", error=str(exc))
    assignments: list[dict[str, Any]] = []
    cover_seen = False
    cover_image = None
    source_map = {str(row["id"]): row for row in plan.get("source_map", [])
                  if isinstance(row, dict) and row.get("id")} if isinstance(plan.get("source_map"), list) else {}
    seen_footer_sources: set[tuple[str, str]] = set()
    seen_footer_labels: set[str] = set()
    for index, slide in enumerate(slides, start=1):
        layout = resolve_layout(template, slide)
        payload = slide.get("slot_payload")
        if not isinstance(payload, dict):
            raise SemanticTemplateError("each slide must define slot_payload")
        payload = dict(payload)
        # For the default native template, a compatible unspecified cover uses the
        # image-enabled shell automatically. Explicit and legacy covers keep
        # their chosen layout and fields.
        band_fields = {"BAND_IMAGE", "RESEARCH_FIELD", "SUBTITLE", "AFFILIATION"}
        if (template.template_id in ACADEMIC_TEMPLATE_IDS and layout["layout_id"] == "cover"
                and not slide.get("layout_id") and (default_visual or band_fields.intersection(payload))):
            band_cover = template.layouts.get("cover_blue_band")
            if band_cover:
                slots = band_cover.get("slots", [])
                if set(payload).issubset({slot.get("slot_id") for slot in slots}):
                    try:
                        for slot in slots:
                            if slot.get("kind") == "text" and slot.get("slot_id") in payload:
                                _validate_capacity(slot, payload[slot["slot_id"]])
                    except SlotCapacityError:
                        pass
                    else:
                        layout = band_cover
        if default_visual:
            if layout["layout_id"] == "cover_blue_band" and "BAND_IMAGE" not in payload:
                payload["BAND_IMAGE"] = default_visual
            if layout["layout_id"] == "toc" and "TOC_IMAGE" not in payload:
                payload["TOC_IMAGE"] = default_visual
        if template.template_id in ACADEMIC_TEMPLATE_IDS:
            if layout.get("role") == "cover":
                cover_seen = True
                cover_image = payload.get("BAND_IMAGE") if layout["layout_id"] == "cover_blue_band" else None
            if layout.get("role") == "content" and "CHAPTER_IMAGE" not in payload:
                chapter_image = cover_image or default_visual
                if chapter_image:
                    payload["CHAPTER_IMAGE"] = chapter_image
            if layout["layout_id"] == "ending_blue_band" and "BAND_IMAGE" not in payload:
                ending_image = cover_image if cover_seen else default_visual
                if ending_image:
                    payload["BAND_IMAGE"] = ending_image
            if layout["layout_id"] == "ending_blue_band" and default_logo and "INSTITUTION_LOGO" not in payload:
                payload["INSTITUTION_LOGO"] = default_logo
        footer_source = None
        if (template.template_id in ACADEMIC_TEMPLATE_IDS and layout.get("role") in {"chapter", "content"}
                and payload.get("SOURCE") not in (None, "", [])):
            original_source = " ".join(_payload_lines(payload["SOURCE"]))
            identity = _footer_source_identity(slide, source_map, original_source)
            label = _footer_source_identity({}, {}, original_source)[1]
            repeated = (identity in seen_footer_sources or
                        (identity[0] == "label" and label in seen_footer_labels))
            seen_footer_sources.add(identity)
            seen_footer_labels.add(label)
            footer_source = {"status": "repeat_suppressed" if repeated else "first_occurrence",
                             "identity_type": identity[0], "identity": identity[1],
                             "original": original_source}
            if repeated:
                payload.pop("SOURCE", None)
        for slot in layout.get("slots", []):
            if not isinstance(slot, dict) or slot.get("value_policy") != "automatic_slide_index":
                continue
            slot_id = str(slot.get("slot_id") or "")
            unpadded = template.pagination.get("format") == "integer"
            expected = str(index) if unpadded else f"{index:02d}"
            supplied = payload.get(slot_id)
            equivalent_padded = (unpadded and isinstance(supplied, str)
                                 and supplied.isdigit() and int(supplied) == index)
            if supplied not in (None, "", expected) and not equivalent_padded:
                raise SemanticTemplateError(f"{slot_id} is template-owned and must be {expected}")
            payload[slot_id] = expected
        tree, rendered_slots = render_slide(
            template,
            layout,
            {**slide, "slot_payload": payload},
            plan_dir=deck_plan_path.parent,
            assets_dir=assets_dir,
            palette_replacements=replacements,
        )
        filename = f"{index:02d}_{layout['layout_id']}.svg"
        tree.write(output_dir / filename, encoding="utf-8", xml_declaration=False)
        assignment = {
                "slide": index,
                "role": slide.get("role"),
                "content_shape": slide.get("content_shape"),
                "layout_id": layout["layout_id"],
                "svg": filename,
                "rendered_slots": rendered_slots,
            }
        if footer_source is not None:
            assignment["footer_source"] = footer_source
        assignments.append(assignment)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "template_id": template.template_id,
        "deck_plan": str(deck_plan_path.resolve()),
        "slide_count": len(assignments),
        "assignments": assignments,
    }
    if visual_selection is not None:
        manifest["visual_selection"] = visual_selection
    if logo_selection is not None:
        manifest["institution_logo"] = logo_selection
    if theme_selection is not None:
        manifest["theme_palette"] = theme_selection
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
