#!/usr/bin/env python3
"""Distill a PPTX source into a draft EasySlides template pack.

The workflow is intentionally evidence-first:

1. import the PPTX into a reference workspace (manifest, assets, SVG views)
2. distill the visible template language into ``distilled_spec.json``
3. copy the flat source SVGs into a slot-guided mirror template folder
4. write EasySlides sidecars that preserve fixed source geometry

This script does not redesign a deck. It creates a faithful draft that can be
reviewed, repaired, and promoted into a production template.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
REFERENCE_ROOT = ROOT / "templates" / "reference" / "template_asset_sources"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from layout_metrics import (  # noqa: E402
    IDENTITY_MATRIX,
    Box as LayoutBox,
    matrix_multiply,
    parse_transform_matrix,
    transform_box,
)
from canonical_shells import (  # noqa: E402
    CANONICAL_SHELL_MINIMUM,
    CANONICAL_SHELL_LIMIT,
    build_shell_profile,
    build_canonical_shell_pack,
)


def sanitize_template_id(value: str | None) -> str:
    """Return a stable folder-safe template id."""
    raw = (value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw or "pptx_distilled_template"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slide_size_tuple(manifest: dict[str, Any]) -> tuple[int, int]:
    size = manifest.get("slideSize") if isinstance(manifest.get("slideSize"), dict) else {}
    width = int(size.get("width_px") or size.get("width") or 1280)
    height = int(size.get("height_px") or size.get("height") or 720)
    return width, height


def classify_story_role(slide: dict[str, Any], total_slides: int) -> str:
    page_type = str(slide.get("pageType") or "")
    index = int(slide.get("index") or 0)
    if "cover" in page_type or index == 1:
        return "cover"
    if "toc" in page_type:
        return "toc"
    if "chapter" in page_type:
        return "chapter"
    if "ending" in page_type or (total_slides and index == total_slides):
        return "ending"
    return "content"


def density_score(slide: dict[str, Any]) -> int:
    text_count = int(slide.get("textCount") or len(slide.get("textSamples") or []))
    shape_count = int(slide.get("shapeCount") or 0)
    image_count = len(slide.get("imageAssets") or [])
    score = 1 + (text_count >= 4) + (text_count >= 8) + (shape_count >= 18) + (image_count >= 2)
    return max(1, min(5, int(score)))


def tag_name(node: ET.Element) -> str:
    if not isinstance(node.tag, str):
        return ""
    return node.tag.rsplit("}", 1)[-1]


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return default
    try:
        return float(match.group(0))
    except ValueError:
        return default


def parse_style_attr(style: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not style:
        return result
    for item in style.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def element_text(node: ET.Element) -> str:
    text = "".join(node.itertext())
    return re.sub(r"\s+", " ", text).strip()


def element_geometry(node: ET.Element) -> dict[str, float]:
    style = parse_style_attr(node.attrib.get("style"))
    x = parse_float(node.attrib.get("data-pptx-box-x"), parse_float(node.attrib.get("x")))
    y = parse_float(node.attrib.get("data-pptx-box-y"), parse_float(node.attrib.get("y")))
    width = parse_float(
        node.attrib.get("data-pptx-box-w"),
        parse_float(node.attrib.get("data-pptx-box-width"), parse_float(node.attrib.get("width"))),
    )
    height = parse_float(
        node.attrib.get("data-pptx-box-h"),
        parse_float(node.attrib.get("data-pptx-box-height"), parse_float(node.attrib.get("height"))),
    )
    font_size = parse_float(node.attrib.get("font-size"), parse_float(style.get("font-size"), 18.0))
    if tag_name(node) == "text":
        text_len = max(len(element_text(node)), 1)
        width = width or min(900.0, text_len * font_size * 0.62)
        height = height or font_size * 1.25
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "width": round(width, 2),
        "height": round(height, 2),
        "font_size": round(font_size, 2),
    }


def svg_candidates(svg_path: Path, story_role: str) -> list[dict[str, Any]]:
    if not svg_path.exists():
        return []
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8-sig"))
    except ET.ParseError:
        return []

    texts: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    for node in root.iter():
        name = tag_name(node)
        if name == "text":
            value = element_text(node)
            if value:
                texts.append({"kind": "text", "text": value, "geometry": element_geometry(node)})
        elif name == "image":
            href = (
                node.attrib.get("href")
                or node.attrib.get("{http://www.w3.org/1999/xlink}href")
                or ""
            )
            images.append({"kind": "image", "href": href, "geometry": element_geometry(node)})

    texts.sort(key=lambda item: (item["geometry"]["y"], item["geometry"]["x"]))
    images.sort(key=lambda item: (item["geometry"]["y"], item["geometry"]["x"]))

    slots: list[dict[str, Any]] = []
    used_slot_ids: Counter[str] = Counter()

    def add_slot(slot_id: str, kind: str, geometry: dict[str, float], sample: str = "") -> None:
        used_slot_ids[slot_id] += 1
        final_id = slot_id if used_slot_ids[slot_id] == 1 else f"{slot_id}_{used_slot_ids[slot_id]:02d}"
        record: dict[str, Any] = {
            "slot": final_id,
            "kind": kind,
            "geometry": {k: geometry[k] for k in ("x", "y", "width", "height")},
        }
        if kind == "text":
            chars = len(sample)
            lines = max(1, min(4, round(chars / 32) or 1))
            record["capacity"] = {
                "lines": lines,
                "max_chars_per_line": max(16, min(60, round(max(chars, 16) / lines))),
            }
            record["sample"] = sample[:120]
            if geometry.get("font_size"):
                record["font_size"] = geometry["font_size"]
        else:
            record["image_fit"] = "contain"
        slots.append(record)

    for i, text in enumerate(texts, 1):
        y = text["geometry"]["y"]
        if story_role == "cover":
            slot_id = ["TITLE", "SUBTITLE", "PRESENTER", "DATE"][min(i - 1, 3)]
        elif story_role == "toc":
            slot_id = f"TOC_ITEM_{i:02d}"
        elif story_role == "chapter":
            slot_id = ["CHAPTER_TITLE", "CHAPTER_DESC"][min(i - 1, 1)]
        elif story_role == "ending":
            slot_id = ["CLOSING_TITLE", "CLOSING_SUBTITLE", "CONTACT"][min(i - 1, 2)]
        else:
            slot_id = "PAGE_TITLE" if i == 1 or y < 120 else f"BODY_TEXT_{i - 1:02d}"
        add_slot(slot_id, "text", text["geometry"], text["text"])

    for i, image in enumerate(images, 1):
        slot_id = "HERO_IMAGE" if story_role == "cover" and i == 1 else f"IMAGE_{i:02d}"
        add_slot(slot_id, "image", image["geometry"])

    return slots


def svg_rectangles(svg_path: Path) -> list[dict[str, Any]]:
    if not svg_path.exists():
        return []
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8-sig"))
    except ET.ParseError:
        return []
    rects: list[dict[str, Any]] = []
    element_indexes = {id(node): index for index, node in enumerate(root.iter(), start=1)}

    def walk(node: ET.Element, parent_matrix: tuple[float, float, float, float, float, float]) -> None:
        style = parse_style_attr(node.attrib.get("style"))
        transform = node.attrib.get("transform") or style.get("transform") or ""
        matrix = matrix_multiply(parent_matrix, parse_transform_matrix(transform))
        if tag_name(node) == "rect":
            x = parse_float(node.attrib.get("x"))
            y = parse_float(node.attrib.get("y"))
            width = parse_float(node.attrib.get("width"))
            height = parse_float(node.attrib.get("height"))
            if width > 0 and height > 0:
                visible_box = transform_box(LayoutBox(x, y, width, height), matrix)
                fill = node.attrib.get("fill") or style.get("fill") or ""
                stroke = node.attrib.get("stroke") or style.get("stroke") or ""
                rects.append(
                    {
                        "element_index": element_indexes.get(id(node), 0),
                        "x": round(visible_box.x, 2),
                        "y": round(visible_box.y, 2),
                        "width": round(visible_box.width, 2),
                        "height": round(visible_box.height, 2),
                        "fill": fill,
                        "stroke": stroke,
                    }
                )
        for child in node:
            walk(child, matrix)

    walk(root, IDENTITY_MATRIX)
    return rects


def is_dark_chrome_fill(fill: str) -> bool:
    fill = (fill or "").strip()
    if not fill.startswith("#"):
        return False
    color = fill[1:]
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) < 6:
        return False
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
    except ValueError:
        return False
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance < 0.45


def has_visible_fill(fill: str) -> bool:
    return (fill or "").strip() not in {"", "none"}


def split_protected_region_by_light_overlays(
    region: dict[str, Any],
    rects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep light active-label surfaces out of a dark chrome contract."""
    region_x = float(region["x"])
    region_y = float(region["y"])
    region_right = region_x + float(region["width"])
    region_bottom = region_y + float(region["height"])
    overlays: list[tuple[float, float]] = []
    for rect in rects:
        x = float(rect["x"])
        y = float(rect["y"])
        w = float(rect["width"])
        h = float(rect["height"])
        fill = str(rect.get("fill") or "")
        if not has_visible_fill(fill) or is_dark_chrome_fill(fill) or fill.startswith("url("):
            continue
        if x > region_x + 2 or x + w < region_right - 2:
            continue
        if y <= region_y + 2 or y + h >= region_bottom - 2 or h < 24:
            continue
        overlays.append((max(region_y, y), min(region_bottom, y + h)))
    if not overlays:
        return [region]

    merged: list[list[float]] = []
    for start, end in sorted(overlays):
        if merged and start <= merged[-1][1] + 2:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    segments: list[dict[str, Any]] = []
    cursor = region_y
    for start, end in merged:
        if start - cursor >= 8:
            segments.append({**region, "y": round(cursor, 2), "height": round(start - cursor, 2)})
        cursor = max(cursor, end)
    if region_bottom - cursor >= 8:
        segments.append({**region, "y": round(cursor, 2), "height": round(region_bottom - cursor, 2)})
    if len(segments) <= 1:
        return [region]
    for index, segment in enumerate(segments, start=1):
        segment["id"] = f"{region['id']}_{index:02d}"
    return segments


def infer_protected_regions(rects: list[dict[str, Any]], width: int, height: int) -> list[dict[str, Any]]:
    protected: list[dict[str, Any]] = []
    for rect in rects:
        x = float(rect["x"])
        y = float(rect["y"])
        w = float(rect["width"])
        h = float(rect["height"])
        fill = str(rect.get("fill") or "")
        if (
            x <= 8
            and y <= 8
            and h >= height * 0.75
            and 60 <= w <= width * 0.35
            and (is_dark_chrome_fill(fill) or fill.startswith("url("))
        ):
            protected.extend(
                split_protected_region_by_light_overlays(
                    {
                        "id": "left_nav",
                        "x": round(x, 2),
                        "y": round(y, 2),
                        "width": round(w, 2),
                        "height": round(h, 2),
                        "fill": fill,
                    },
                    rects,
                )
            )
        elif (
            y <= 8
            and x <= 8
            and w >= width * 0.75
            and 35 <= h <= height * 0.28
            and (is_dark_chrome_fill(fill) or fill.startswith("url(") or has_visible_fill(fill))
        ):
            protected.append(
                {
                    "id": "top_chrome",
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "width": round(w, 2),
                    "height": round(h, 2),
                    "fill": fill,
                }
            )
    return protected


def infer_containers(rects: list[dict[str, Any]], protected: list[dict[str, Any]], width: int, height: int) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for rect in rects:
        x = float(rect["x"])
        y = float(rect["y"])
        w = float(rect["width"])
        h = float(rect["height"])
        fill = str(rect.get("fill") or "")
        stroke = str(rect.get("stroke") or "")
        if w >= width * 0.92 and h >= height * 0.92:
            continue
        if any(
            abs(x - float(region["x"])) < 1
            and abs(y - float(region["y"])) < 1
            and abs(w - float(region["width"])) < 1
            and abs(h - float(region["height"])) < 1
            for region in protected
        ):
            continue
        if w < 70 or h < 64:
            continue
        if fill in {"", "none"} and stroke in {"", "none"}:
            continue
        containers.append(
            {
                "id": f"container_{len(containers) + 1:02d}",
                "x": round(x, 2),
                "y": round(y, 2),
                "width": round(w, 2),
                "height": round(h, 2),
                "fill": fill,
                "stroke": stroke,
            }
        )
    return containers


def role_fit(story_role: str) -> list[str]:
    if story_role in {"cover", "toc", "chapter", "ending"}:
        return [story_role]
    return ["content", "evidence", "explanation"]


def role_slot_name(story_role: str) -> str:
    if story_role in {"cover", "toc", "chapter", "ending"}:
        return story_role
    return "content"


def copy_assets(source_workspace: Path, template_dir: Path) -> None:
    source_assets = source_workspace / "assets"
    if not source_assets.exists():
        return
    target_assets = template_dir / "assets"
    target_assets.mkdir(parents=True, exist_ok=True)
    for asset in source_assets.iterdir():
        if asset.is_file():
            shutil.copy2(asset, target_assets / asset.name)


def copy_svg_for_template(source_svg: Path, target_svg: Path) -> None:
    text = source_svg.read_text(encoding="utf-8-sig")
    text = text.replace('href="../assets/', 'href="assets/')
    text = text.replace("href='../assets/", "href='assets/")
    text = text.replace('xlink:href="../assets/', 'xlink:href="assets/')
    text = text.replace("xlink:href='../assets/", "xlink:href='assets/")
    text = normalize_navigation_text_colors(text)
    text = normalize_compact_control_text_alignment(text)
    target_svg.write_text(text, encoding="utf-8")


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def fmt_svg_num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def normalize_navigation_text_colors(svg_text: str) -> str:
    """Restore fixed navigation text contrast from the visible chrome surfaces."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return svg_text

    rects: list[tuple[ET.Element, dict[str, float], str]] = []
    for node in root.iter():
        if tag_name(node) != "rect":
            continue
        style = parse_style_attr(node.attrib.get("style"))
        fill = (node.attrib.get("fill") or style.get("fill") or "").strip()
        geometry = element_geometry(node)
        if has_visible_fill(fill) and geometry["width"] > 0 and geometry["height"] > 0:
            rects.append((node, geometry, fill))

    nav_candidates = [
        (geometry, fill)
        for _node, geometry, fill in rects
        if geometry["x"] <= 8
        and geometry["y"] <= 8
        and geometry["height"] >= 500
        and 60 <= geometry["width"] <= 460
        and is_dark_chrome_fill(fill)
    ]
    if not nav_candidates:
        return svg_text

    nav, nav_fill = max(nav_candidates, key=lambda item: item[0]["width"] * item[0]["height"])
    nav_right = nav["x"] + nav["width"]
    overlays = [
        geometry
        for _node, geometry, fill in rects
        if not is_dark_chrome_fill(fill)
        and geometry["x"] <= nav["x"] + 2
        and geometry["x"] + geometry["width"] >= nav_right - 2
        and geometry["y"] > nav["y"] + 2
        and geometry["y"] + geometry["height"] < nav["y"] + nav["height"] - 2
        and geometry["height"] >= 24
    ]

    def in_box(box: dict[str, float], region: dict[str, float]) -> bool:
        return (
            region["x"] <= box["x"] + box["width"] / 2 <= region["x"] + region["width"]
            and region["y"] <= box["y"] + box["height"] / 2 <= region["y"] + region["height"]
        )

    changed = False
    for node in root.iter():
        if tag_name(node) != "text":
            continue
        box = element_geometry(node)
        if box["x"] + box["width"] / 2 >= nav_right or not in_box(box, nav):
            continue
        active = any(in_box(box, overlay) for overlay in overlays)
        node.set("data-pptx-fixed-chrome", "true")
        desired = nav_fill if active else "#FFFFFF"
        if node.attrib.get("fill") != desired:
            node.set("fill", desired)
            changed = True
        for child in node:
            if tag_name(child) == "tspan" and child.attrib.get("fill") != desired:
                child.set("fill", desired)
                changed = True

    if not changed and all(
        tag_name(node) != "text"
        or not (element_geometry(node)["x"] + element_geometry(node)["width"] / 2 < nav_right and in_box(element_geometry(node), nav))
        or node.attrib.get("data-pptx-fixed-chrome") == "true"
        for node in root.iter()
    ):
        return svg_text
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def normalize_source_svg_navigation(source_workspace: Path) -> None:
    """Apply the derived navigation correction to projection source SVGs."""
    svg_dir = source_workspace / "svg-flat"
    if not svg_dir.exists():
        return
    for path in sorted(svg_dir.glob("*.svg")):
        original = path.read_text(encoding="utf-8-sig")
        normalized = normalize_navigation_text_colors(original)
        if normalized != original:
            path.write_text(normalized, encoding="utf-8")


def normalize_compact_control_text_alignment(svg_text: str) -> str:
    """Center-lock text boxes that visually belong to compact rounded controls."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return svg_text

    rects: list[dict[str, Any]] = []
    texts: list[dict[str, Any]] = []
    for node in root.iter():
        name = tag_name(node)
        if name == "rect":
            rect = compact_control_rect(node)
            if rect:
                rects.append(rect)
        elif name == "text":
            textbox = compact_textbox(node)
            if textbox:
                texts.append(textbox)

    if not texts:
        return svg_text

    changed = False
    for textbox in texts:
        rect = matching_control_rect(textbox, rects) if rects else None
        node = textbox["node"]
        # Semantic slots already own an explicit geometry contract. Rebinding
        # them to a nearby decorative rectangle can silently corrupt their
        # capacity box during cross-material rendering.
        if node.attrib.get("data-slot") or node.attrib.get("data-slot-id"):
            continue
        if rect is None:
            if is_short_control_textbox(textbox):
                if node.attrib.get("data-pptx-valign") != "middle":
                    node.set("data-pptx-valign", "middle")
                    changed = True
            continue
        new_y = float(rect["y"])
        new_h = float(rect["height"])
        if node.attrib.get("data-pptx-valign") != "middle":
            node.set("data-pptx-valign", "middle")
            changed = True
        if abs(float(textbox["y"]) - new_y) > 0.01:
            node.set("data-pptx-box-y", fmt_svg_num(new_y))
            changed = True
        if abs(float(textbox["height"]) - new_h) > 0.01:
            node.set("data-pptx-box-h", fmt_svg_num(new_h))
            changed = True
        baseline_y = compact_control_baseline_y(node, new_y, new_h)
        if baseline_y is not None and abs(parse_float(node.attrib.get("y")) - baseline_y) > 0.01:
            node.set("y", fmt_svg_num(baseline_y))
            changed = True

    if not changed:
        return svg_text

    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def compact_control_baseline_y(node: ET.Element, box_y: float, box_h: float) -> float | None:
    if node.attrib.get("y") is None:
        return None
    font_size = parse_float(node.attrib.get("font-size"), 18.0)
    line_count = max(1, len(element_text(node).splitlines()) or 1)
    line_step = font_size * 1.18
    total_height = font_size if line_count <= 1 else font_size + (line_count - 1) * line_step
    return box_y + (box_h - total_height) / 2 + font_size * 0.85


def is_short_control_text(text: str) -> bool:
    stripped = re.sub(r"\s+", "", text)
    return bool(stripped) and len(stripped) <= 16


def is_short_control_textbox(textbox: dict[str, Any]) -> bool:
    if not is_short_control_text(str(textbox.get("text") or "")):
        return False
    return float(textbox.get("width") or 0) <= 360


def compact_control_rect(node: ET.Element) -> dict[str, Any] | None:
    style = parse_style_attr(node.attrib.get("style"))
    x = parse_float(node.attrib.get("x"))
    y = parse_float(node.attrib.get("y"))
    width = parse_float(node.attrib.get("width"))
    height = parse_float(node.attrib.get("height"))
    if width <= 0 or height <= 0:
        return None
    if height < 14 or height > 96 or width < 24 or width > 760:
        return None
    rx = parse_float(node.attrib.get("rx"))
    ry = parse_float(node.attrib.get("ry"))
    fill_raw = (node.attrib.get("fill") or style.get("fill") or "").strip()
    stroke_raw = (node.attrib.get("stroke") or style.get("stroke") or "").strip()
    fill = fill_raw.lower()
    stroke = stroke_raw.lower()
    if fill in {"", "none"} and stroke in {"", "none"}:
        return None
    rounded = max(rx, ry) >= min(width, height) * 0.12
    dark_caption_bar = fill.startswith("url(") or is_dark_chrome_fill(fill_raw)
    if not rounded and not dark_caption_bar:
        return None
    return {
        "node": node,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "cx": x + width / 2,
        "cy": y + height / 2,
    }


def compact_textbox(node: ET.Element) -> dict[str, Any] | None:
    if str(node.attrib.get("data-pptx-textbox") or "").lower() != "true":
        return None
    if "\n" in element_text(node):
        return None
    required = ("data-pptx-box-x", "data-pptx-box-y", "data-pptx-box-w", "data-pptx-box-h")
    if any(node.attrib.get(name) is None for name in required):
        return None
    x = parse_float(node.attrib.get("data-pptx-box-x"))
    y = parse_float(node.attrib.get("data-pptx-box-y"))
    width = parse_float(node.attrib.get("data-pptx-box-w"))
    height = parse_float(node.attrib.get("data-pptx-box-h"))
    font_size = parse_float(node.attrib.get("font-size"))
    if width <= 0 or height <= 0:
        return None
    if height < 8 or height > 90 or font_size > 48:
        return None
    return {
        "node": node,
        "text": element_text(node),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "cx": x + width / 2,
        "cy": y + height / 2,
    }


def matching_control_rect(textbox: dict[str, Any], rects: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[tuple[float, float, dict[str, Any]]] = []
    box_x = float(textbox["x"])
    box_y = float(textbox["y"])
    box_w = float(textbox["width"])
    box_h = float(textbox["height"])
    box_cy = box_y + box_h / 2
    for rect in rects:
        rect_x = float(rect["x"])
        rect_y = float(rect["y"])
        rect_w = float(rect["width"])
        rect_h = float(rect["height"])
        if box_h > rect_h * 1.25 or box_h < rect_h * 0.25:
            continue
        overlap = max(0.0, min(box_x + box_w, rect_x + rect_w) - max(box_x, rect_x))
        overlap_ratio = overlap / max(box_w, 1.0)
        if overlap_ratio < 0.45:
            continue
        center_delta = abs(box_cy - float(rect["cy"]))
        if center_delta > max(4.0, rect_h * 0.25):
            continue
        candidates.append((center_delta, -overlap_ratio, rect))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def primary_color(manifest: dict[str, Any]) -> str:
    colors = ((manifest.get("theme") or {}).get("colors") or {})
    for key in ("accent1", "dk1", "lt1"):
        value = colors.get(key)
        if isinstance(value, str) and value.startswith("#"):
            return value.upper()
    for value in colors.values():
        if isinstance(value, str) and value.startswith("#"):
            return value.upper()
    return "#1F4E79"


def normalize_hex_color(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value.startswith("#"):
        return None
    color = value[1:]
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) < 6:
        return None
    color = color[:6]
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        return None
    return f"#{color.upper()}"


def clean_font_family(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",", 1)[0].strip().strip("'\"")
    return first or None


def svg_feature_summary(svg_path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "colors": Counter(),
        "fonts": Counter(),
        "font_sizes": Counter(),
        "text_anchors": Counter(),
        "image_hrefs": Counter(),
        "gradients": 0,
        "filters": 0,
        "filter_refs": 0,
        "opacity": 0,
        "rotations": 0,
        "nested_svg_images": 0,
        "cropped_images": 0,
    }
    if not svg_path.exists():
        return summary
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8-sig"))
    except ET.ParseError:
        return summary

    for node in root.iter():
        name = tag_name(node)
        style = parse_style_attr(node.attrib.get("style"))
        if name in {"linearGradient", "radialGradient"}:
            summary["gradients"] += 1
        if name == "filter":
            summary["filters"] += 1
        if node.attrib.get("filter") or style.get("filter"):
            summary["filter_refs"] += 1
        transform = node.attrib.get("transform") or style.get("transform") or ""
        if "rotate(" in transform:
            summary["rotations"] += 1
        for key in ("fill", "stroke", "stop-color"):
            color = normalize_hex_color(node.attrib.get(key) or style.get(key))
            if color:
                summary["colors"][color] += 1
        for key in ("opacity", "fill-opacity", "stroke-opacity", "stop-opacity"):
            value = node.attrib.get(key) or style.get(key)
            if value is not None and parse_float(value, 1.0) < 0.999:
                summary["opacity"] += 1
        if name == "text":
            font = clean_font_family(node.attrib.get("font-family") or style.get("font-family"))
            if font:
                summary["fonts"][font] += 1
            size = parse_float(node.attrib.get("font-size"), parse_float(style.get("font-size")))
            if size:
                summary["font_sizes"][str(round(size, 1))] += 1
            anchor = node.attrib.get("text-anchor") or style.get("text-anchor")
            if anchor:
                summary["text_anchors"][anchor] += 1
        if name == "image":
            href = (
                node.attrib.get("href")
                or node.attrib.get("{http://www.w3.org/1999/xlink}href")
                or ""
            )
            if href:
                summary["image_hrefs"][href] += 1
        if name == "svg" and node is not root and any(tag_name(child) == "image" for child in node):
            summary["nested_svg_images"] += 1
            view_box = node.attrib.get("viewBox") or ""
            if view_box and view_box.strip() not in {"0 0 1 1", "0 0 1.0 1.0"}:
                summary["cropped_images"] += 1
    return summary


def merge_counter_features(features: list[dict[str, Any]], key: str) -> Counter:
    total: Counter = Counter()
    for feature in features:
        total.update(feature.get(key) or {})
    return total


def role_layout_grammar(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in pages:
        grouped[page["story_role"]].append(page)
    grammar: list[dict[str, Any]] = []
    for role, role_pages in sorted(grouped.items()):
        densities = [int(page["density_score"]) for page in role_pages]
        slot_prefixes: Counter = Counter()
        image_slots = 0
        text_slots = 0
        for page in role_pages:
            for slot in page["slot_candidates"]:
                prefix = str(slot["slot"]).split("_", 1)[0]
                slot_prefixes[prefix] += 1
                image_slots += slot.get("kind") == "image"
                text_slots += slot.get("kind") == "text"
        grammar.append(
            {
                "role": role,
                "count": len(role_pages),
                "page_ids": [page["id"] for page in role_pages],
                "source_slides": [page["source_slide"] for page in role_pages],
                "density_range": [min(densities), max(densities)] if densities else [0, 0],
                "slot_vocabulary": [name for name, _count in slot_prefixes.most_common(8)],
                "text_slot_count": int(text_slots),
                "image_slot_count": int(image_slots),
            }
        )
    return grammar


def build_template_language(
    *,
    manifest: dict[str, Any],
    source_workspace: Path,
    template_id: str,
    pages: list[dict[str, Any]],
    slot_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    features = [
        svg_feature_summary(source_workspace / "svg-flat" / page["source_svg"])
        for page in pages
    ]
    color_counts = merge_counter_features(features, "colors")
    font_counts = merge_counter_features(features, "fonts")
    anchor_counts = merge_counter_features(features, "text_anchors")
    image_counts = merge_counter_features(features, "image_hrefs")
    effect_counts = {
        "gradients": sum(int(feature.get("gradients") or 0) for feature in features),
        "filters": sum(int(feature.get("filters") or 0) for feature in features),
        "filter_refs": sum(int(feature.get("filter_refs") or 0) for feature in features),
        "opacity": sum(int(feature.get("opacity") or 0) for feature in features),
        "rotations": sum(int(feature.get("rotations") or 0) for feature in features),
        "nested_svg_images": sum(int(feature.get("nested_svg_images") or 0) for feature in features),
        "cropped_images": sum(int(feature.get("cropped_images") or 0) for feature in features),
    }
    theme = manifest.get("theme") if isinstance(manifest.get("theme"), dict) else {}
    theme_colors = theme.get("colors") if isinstance(theme.get("colors"), dict) else {}
    theme_fonts = theme.get("fonts") if isinstance(theme.get("fonts"), dict) else {}
    palette = [
        {"color": color, "count": count}
        for color, count in color_counts.most_common(12)
    ]
    for value in theme_colors.values():
        color = normalize_hex_color(value if isinstance(value, str) else None)
        if color and all(item["color"] != color for item in palette):
            palette.append({"color": color, "count": 0})
    primary = primary_color(manifest)

    fidelity_risks: list[dict[str, Any]] = []
    if effect_counts["gradients"] or effect_counts["filters"] or effect_counts["filter_refs"] or effect_counts["opacity"]:
        fidelity_risks.append(
            {
                "risk": "gradient_or_filter_effects",
                "evidence": {
                    "gradients": effect_counts["gradients"],
                    "filters": effect_counts["filters"],
                    "filter_refs": effect_counts["filter_refs"],
                    "opacity": effect_counts["opacity"],
                },
                "failure_mode": "Native editable PPTX export can flatten or mis-layer translucent atmosphere, shadows, and gradient masks.",
                "recommended_baseline": "source_rendered_raster_baseline",
            }
        )
    if effect_counts["nested_svg_images"] or effect_counts["cropped_images"] or effect_counts["rotations"]:
        fidelity_risks.append(
            {
                "risk": "layered_or_cropped_media",
                "evidence": {
                    "nested_svg_images": effect_counts["nested_svg_images"],
                    "cropped_images": effect_counts["cropped_images"],
                    "rotations": effect_counts["rotations"],
                },
                "failure_mode": "Image crop, rotation, and nested SVG viewBox semantics can drift during shape conversion.",
                "recommended_baseline": "source_rendered_raster_baseline",
            }
        )
    if anchor_counts:
        fidelity_risks.append(
            {
                "risk": "text_anchor_alignment",
                "evidence": dict(anchor_counts.most_common()),
                "failure_mode": "Text position checks and editable export must preserve start/middle/end anchors.",
                "recommended_baseline": "anchor_aware_text_rebuild",
            }
        )

    baseline_surface = "source_rendered_raster_baseline" if fidelity_risks else "editable_native_svg_candidate"
    return {
        "schema_version": "easyslides.template_language.v1",
        "template_id": template_id,
        "summary": {
            "slide_count": len(pages),
            "baseline_surface": baseline_surface,
            "role_counts": dict(Counter(page["story_role"] for page in pages)),
            "slot_count": len(slot_candidates),
            "top_repeated_images": [
                {"href": href, "count": count}
                for href, count in image_counts.most_common(8)
                if count > 1
            ],
        },
        "visual_system": {
            "primary_color": primary,
            "palette": palette[:12],
            "theme_fonts": theme_fonts,
            "observed_fonts": [
                {"font": font, "count": count}
                for font, count in font_counts.most_common(10)
            ],
            "effect_counts": effect_counts,
            "text_anchor_counts": dict(anchor_counts.most_common()),
        },
        "layout_grammar": role_layout_grammar(pages),
        "fidelity_risks": fidelity_risks,
        "editable_rebuild_plan": [
            {
                "phase": "faithful_visual_baseline",
                "surface": "source_rendered_raster_baseline",
                "goal": "Lock colors, transparency, text positions, alignment, and occlusion against the original PowerPoint render.",
            },
            {
                "phase": "editable_chrome_rebuild",
                "surface": "editable_primitives",
                "goal": "Rebuild repeated backgrounds, headers/nav, cards, labels, and image frames one primitive family at a time.",
            },
            {
                "phase": "slot_layer_rebuild",
                "surface": "editable_slots",
                "goal": "Replace only validated text/image slots after the chrome has a passing visual diff.",
            },
            {
                "phase": "visual_diff_gate",
                "surface": "source_vs_generated_render",
                "goal": "Compare PowerPoint-rendered PNGs before claiming fidelity or registering the template.",
            },
        ],
    }


def write_template_language_report(path: Path, language: dict[str, Any]) -> None:
    summary = language.get("summary", {})
    visual = language.get("visual_system", {})
    risks = language.get("fidelity_risks", [])
    grammar = language.get("layout_grammar", [])
    lines = [
        f"# {language.get('template_id')} Template Language",
        "",
        "## Summary",
        "",
        f"- Slide count: {summary.get('slide_count')}",
        f"- Recommended baseline surface: `{summary.get('baseline_surface')}`",
        f"- Slot count: {summary.get('slot_count')}",
        f"- Role counts: `{json.dumps(summary.get('role_counts', {}), ensure_ascii=False)}`",
        "",
        "## Visual System",
        "",
        f"- Primary color: `{visual.get('primary_color')}`",
        f"- Theme fonts: `{json.dumps(visual.get('theme_fonts', {}), ensure_ascii=False)}`",
        "- Palette: "
        + ", ".join(item["color"] for item in (visual.get("palette") or [])[:8]),
        f"- Effect counts: `{json.dumps(visual.get('effect_counts', {}), ensure_ascii=False)}`",
        "",
        "## Layout Grammar",
        "",
    ]
    for item in grammar:
        lines.append(
            f"- `{item['role']}`: {item['count']} page(s), density {item['density_range']}, slots {item['slot_vocabulary']}"
        )
    lines.extend(["", "## Fidelity Risks", ""])
    if risks:
        for risk in risks:
            lines.append(f"- `{risk['risk']}`: {risk['failure_mode']}")
    else:
        lines.append("- No high-risk SVG effects detected by the automatic scanner.")
    lines.extend(["", "## Editable Rebuild Plan", ""])
    for step in language.get("editable_rebuild_plan", []):
        lines.append(f"- `{step['phase']}` on `{step['surface']}`: {step['goal']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def choose_prototype_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role in ("cover", "toc", "chapter", "content", "ending"):
        candidates = [page for page in pages if page["story_role"] == role]
        if not candidates:
            continue
        page = max(candidates, key=lambda item: (int(item["density_score"]), len(item["slot_candidates"])))
        if page["id"] in seen:
            continue
        seen.add(page["id"])
        selected.append(
            {
                "page_id": page["id"],
                "source_slide": page["source_slide"],
                "story_role": page["story_role"],
                "reason": "prototype for editable primitive reconstruction",
            }
        )
    return selected


def build_editable_rebuild_plan(
    *,
    template_id: str,
    pages: list[dict[str, Any]],
    template_language: dict[str, Any],
) -> dict[str, Any]:
    visual = template_language.get("visual_system", {})
    summary = template_language.get("summary", {})
    risks = template_language.get("fidelity_risks", [])
    risk_names = {str(risk.get("risk")) for risk in risks if isinstance(risk, dict)}
    effect_counts = visual.get("effect_counts") if isinstance(visual.get("effect_counts"), dict) else {}
    baseline_surface = summary.get("baseline_surface") or (
        "source_rendered_raster_baseline" if risks else "editable_native_svg_candidate"
    )

    primitives: list[dict[str, Any]] = []
    if "gradient_or_filter_effects" in risk_names or int(effect_counts.get("opacity") or 0):
        primitives.append(
            {
                "primitive": "atmosphere_background",
                "evidence": {
                    "gradients": effect_counts.get("gradients", 0),
                    "filters": effect_counts.get("filters", 0),
                    "opacity": effect_counts.get("opacity", 0),
                },
                "editable_strategy": "rebuild after raster baseline using layered rectangles/images with explicit alpha and visual diff gates",
                "acceptance": "PowerPoint-rendered rebuild matches source render before text slots are introduced",
            }
        )
    top_images = summary.get("top_repeated_images") if isinstance(summary.get("top_repeated_images"), list) else []
    if top_images:
        primitives.append(
            {
                "primitive": "repeated_media_backdrop",
                "evidence": top_images[:5],
                "editable_strategy": "preserve repeated media as locked background assets until crop and layering are verified",
                "acceptance": "repeated backdrop placement is stable across source-rendered comparison pages",
            }
        )
    if any(page["story_role"] == "content" for page in pages):
        primitives.append(
            {
                "primitive": "section_header_chrome",
                "evidence": [page["id"] for page in pages if page["story_role"] == "content"][:5],
                "editable_strategy": "extract repeated title bars, section labels, and top/right chrome before body card reconstruction",
                "acceptance": "headers align across prototype content pages without text or image overlap",
            }
        )
    if any(slot["kind"] == "image" for page in pages for slot in page["slot_candidates"]):
        primitives.append(
            {
                "primitive": "image_frames",
                "evidence": "image slots detected in source page geometry",
                "editable_strategy": "rebuild crop boxes and captions as explicit image frame components",
                "acceptance": "image crops preserve source aspect and do not drift during PPTX export",
            }
        )
    if any(page["story_role"] in {"cover", "ending"} for page in pages):
        primitives.append(
            {
                "primitive": "cover_ending_lockups",
                "evidence": [page["id"] for page in pages if page["story_role"] in {"cover", "ending"}],
                "editable_strategy": "rebuild cover and ending compositions as page-specific lockups, not generic shells",
                "acceptance": "cover and ending pass visual diff before generalized variants are attempted",
            }
        )

    return {
        "schema_version": "easyslides.editable_rebuild_plan.v1",
        "template_id": template_id,
        "baseline": {
            "surface": baseline_surface,
            "reason": "Use the surface that preserves source PowerPoint visual truth before editable reconstruction.",
            "blocking_risks": sorted(risk_names),
        },
        "prototype_pages": choose_prototype_pages(pages),
        "primitive_candidates": primitives,
        "phases": [
            {
                "id": "visual_baseline",
                "goal": "Render the source PPTX and lock the raster baseline with a visual diff report.",
                "output": "source-rendered PNG deck and source-vs-generated metrics",
            },
            {
                "id": "chrome_rebuild",
                "goal": "Rebuild repeated background, atmosphere, headers, section labels, and cards as editable primitives.",
                "depends_on": ["visual_baseline"],
                "prototype_pages": [page["page_id"] for page in choose_prototype_pages(pages)],
            },
            {
                "id": "slot_rebuild",
                "goal": "Enable replacement only inside validated text/image slots and capacity bounds.",
                "depends_on": ["chrome_rebuild"],
            },
            {
                "id": "visual_diff_gate",
                "goal": "Compare PowerPoint-rendered source and generated decks before claiming fidelity.",
                "command": "python scripts/pptx_visual_diff.py <source_png_dir> <generated_png_dir> --out <diff_dir>",
                "depends_on": ["slot_rebuild"],
            },
        ],
    }


def page_pool_for_role(pages: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    pool = [page for page in pages if page["story_role"] == role]
    if pool:
        return sorted(pool, key=lambda item: (int(item["density_score"]), item["source_slide"]))
    if role in {"evidence", "explanation", "method"}:
        return sorted(
            [page for page in pages if page["story_role"] == "content"],
            key=lambda item: (int(item["density_score"]), item["source_slide"]),
        )
    return []


def page_refs(pages: list[dict[str, Any]], *, limit: int = 4) -> list[str]:
    return [page["id"] for page in pages[:limit]]


def build_adaptation_strategy(
    *,
    template_id: str,
    pages: list[dict[str, Any]],
    template_language: dict[str, Any],
    rebuild_plan: dict[str, Any],
) -> dict[str, Any]:
    content_pages = page_pool_for_role(pages, "content")
    cover_pages = page_pool_for_role(pages, "cover")
    ending_pages = page_pool_for_role(pages, "ending")
    low_density = [page for page in content_pages if int(page["density_score"]) <= 2]
    balanced_density = [page for page in content_pages if 2 <= int(page["density_score"]) <= 3]
    high_density = [page for page in content_pages if int(page["density_score"]) >= 4]
    visual = template_language.get("visual_system", {})

    material_types = [
        {
            "id": "deck_title",
            "intent": "open the talk and establish project identity",
            "signals": ["title", "subtitle", "speaker", "affiliation", "date"],
            "preferred_pages": page_refs(cover_pages, limit=2),
            "required_slots": ["TITLE", "SUBTITLE"],
            "overflow_action": "compress_metadata_not_title",
        },
        {
            "id": "agenda_or_storyline",
            "intent": "show the presentation route or section roadmap",
            "signals": ["outline", "agenda", "contents", "section list", "storyline"],
            "preferred_pages": page_refs(low_density or content_pages, limit=3),
            "required_slots": ["PAGE_TITLE", "BODY_TEXT"],
            "overflow_action": "split_across_multiple_pages",
        },
        {
            "id": "research_problem",
            "intent": "state the scientific problem, gap, or motivation",
            "signals": ["problem", "gap", "motivation", "challenge", "why it matters"],
            "preferred_pages": page_refs(balanced_density or content_pages, limit=4),
            "required_slots": ["PAGE_TITLE", "BODY_TEXT"],
            "overflow_action": "one_claim_plus_supporting_evidence",
        },
        {
            "id": "research_objective",
            "intent": "state objective, hypothesis, or contribution",
            "signals": ["objective", "aim", "hypothesis", "contribution", "innovation"],
            "preferred_pages": page_refs(balanced_density or content_pages, limit=4),
            "required_slots": ["PAGE_TITLE", "BODY_TEXT"],
            "overflow_action": "split_objectives_into_numbered_pages",
        },
        {
            "id": "technical_route",
            "intent": "explain workflow, model architecture, mechanism, or method pipeline",
            "signals": ["workflow", "pipeline", "architecture", "mechanism", "method"],
            "preferred_pages": page_refs([page for page in content_pages if any(slot["kind"] == "image" for slot in page["slot_candidates"])] or content_pages, limit=4),
            "required_slots": ["PAGE_TITLE", "IMAGE"],
            "overflow_action": "promote_diagram_and_move_explanation_to_body_slots",
        },
        {
            "id": "evidence_result",
            "intent": "present experiment, figure, metric, chart, table, or comparison result",
            "signals": ["result", "figure", "chart", "table", "metric", "comparison"],
            "preferred_pages": page_refs(high_density or balanced_density or content_pages, limit=5),
            "required_slots": ["PAGE_TITLE", "IMAGE", "BODY_TEXT"],
            "overflow_action": "split_across_multiple_pages",
        },
        {
            "id": "application_value",
            "intent": "explain impact, application, social value, or expected benefit",
            "signals": ["application", "impact", "value", "benefit", "societal", "translation"],
            "preferred_pages": page_refs(balanced_density or content_pages, limit=4),
            "required_slots": ["PAGE_TITLE", "BODY_TEXT"],
            "overflow_action": "summarize_to_claim_evidence_action",
        },
        {
            "id": "closing_acknowledgement",
            "intent": "close the talk, thank reviewers, or list contact information",
            "signals": ["thanks", "acknowledgement", "contact", "questions"],
            "preferred_pages": page_refs(ending_pages, limit=2),
            "required_slots": ["CLOSING_TITLE"],
            "overflow_action": "keep_closing_short",
        },
    ]

    return {
        "schema_version": "easyslides.material_adaptation_strategy.v1",
        "template_id": template_id,
        "baseline_surface": rebuild_plan.get("baseline", {}).get("surface"),
        "selection_policy": {
            "default_route": "classify_material_then_match_role_density_slots",
            "scoring": {
                "material_role_match": 0.35,
                "density_fit": 0.25,
                "slot_fit": 0.25,
                "visual_identity_preservation": 0.15,
            },
            "density_inputs": {
                "text_blocks": "number of claims, bullets, paragraphs, and captions",
                "visual_blocks": "number of figures, tables, charts, diagrams, or screenshots",
                "recommended_default": "one defensible claim plus one primary evidence object per slide",
            },
            "candidate_page_order": {
                "cover": page_refs(cover_pages),
                "low_density_content": page_refs(low_density or content_pages),
                "balanced_content": page_refs(balanced_density or content_pages),
                "high_density_content": page_refs(high_density or content_pages),
                "ending": page_refs(ending_pages),
            },
        },
        "material_types": material_types,
        "overflow_policy": {
            "trigger": "material exceeds declared slot capacity or would obscure fixed template identity",
            "actions": [
                "split_across_multiple_pages",
                "choose_lower_density_page",
                "summarize_to_claim_evidence_action",
                "move_secondary_detail_to_appendix",
                "keep_visual_evidence_primary",
            ],
            "never": [
                "shrink text until unreadable",
                "move fixed chrome to make room",
                "cover source identity regions with user material",
            ],
        },
        "identity_constraints": {
            "primary_color": visual.get("primary_color"),
            "preserve_primitives": [
                item.get("primitive")
                for item in rebuild_plan.get("primitive_candidates", [])
                if isinstance(item, dict) and item.get("primitive")
            ],
            "baseline_surface": rebuild_plan.get("baseline", {}).get("surface"),
        },
        "validation_gates": [
            {
                "id": "material_classification",
                "check": "every input item is assigned a material_type and confidence before layout selection",
            },
            {
                "id": "slot_capacity_gate",
                "check": "selected page has enough declared text/image slots or overflow_policy is applied",
            },
            {
                "id": "identity_preservation_gate",
                "check": "generated content does not obscure preserved chrome, cover/ending lockups, or atmosphere background",
            },
            {
                "id": "cross_material_smoke_test",
                "check": "clone the template with a different topic and images, then re-run SVG/PPTX geometry and text-layout gates",
                "command": f"python scripts/template_material_smoke_test.py templates/layouts/{template_id} --out tmp/{template_id}_material_smoke --force",
            },
            {
                "id": "visual_diff_gate",
                "check": "PowerPoint-rendered output remains within visual-diff threshold for the selected baseline surface",
            },
        ],
    }


def build_distilled_spec(
    *,
    manifest: dict[str, Any],
    source_workspace: Path,
    source_pptx: Path,
    template_id: str,
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    width, height = slide_size_tuple(manifest)
    theme = manifest.get("theme") if isinstance(manifest.get("theme"), dict) else {}
    colors = theme.get("colors") if isinstance(theme.get("colors"), dict) else {}
    fonts = theme.get("fonts") if isinstance(theme.get("fonts"), dict) else {}
    roles = [page["story_role"] for page in pages]
    role_counts = Counter(roles)
    common_assets = ((manifest.get("assets") or {}).get("commonAssets") or [])

    slot_candidates: list[dict[str, Any]] = []
    for page in pages:
        for slot in page["slot_candidates"]:
            slot_candidates.append(
                {
                    "source_slide": page["source_slide"],
                    "page_role": page["story_role"],
                    "slot": slot["slot"],
                    "kind": slot["kind"],
                    "geometry": slot["geometry"],
                    **({"capacity": slot["capacity"]} if "capacity" in slot else {}),
                    **({"image_fit": slot["image_fit"]} if "image_fit" in slot else {}),
                }
            )

    identity: list[dict[str, Any]] = [
        {
            "name": "source_slide_geometry",
            "evidence_slides": [f"slide_{page['source_slide']:02d}" for page in pages],
            "rule": f"Preserve fixed source slide geometry on a {width}x{height} canvas.",
            "failure_if_missing": "The template no longer reads as the source PPTX.",
        },
        {
            "name": "source_page_role_roster",
            "evidence_slides": [f"slide_{page['source_slide']:02d}" for page in pages],
            "rule": "Keep cover, section/content, and ending roles mapped to source pages.",
            "failure_if_missing": "Generators cannot choose faithful source pages by story role.",
        },
    ]
    if colors:
        identity.append(
            {
                "name": "theme_color_family",
                "evidence_slides": [f"slide_{page['source_slide']:02d}" for page in pages[: min(3, len(pages))]],
                "rule": "Use the extracted PPTX theme color family as the default palette.",
                "failure_if_missing": "The imported template drifts into an unrelated color system.",
            }
        )
    if common_assets:
        identity.append(
            {
                "name": "repeated_source_assets",
                "evidence_slides": [f"slide_{page['source_slide']:02d}" for page in pages],
                "rule": "Preserve repeated media assets unless a reviewer explicitly marks them replaceable.",
                "failure_if_missing": "Logos, repeated backgrounds, or template marks disappear.",
            }
        )

    structural_primitives: dict[str, Any] = {
        "background": {"source": "flat_source_svg", "editable_policy": "preserve_source_geometry"},
        "header": {"detected": any(page["story_role"] == "content" for page in pages)},
        "section_label": {"detected": any(page["story_role"] in {"toc", "chapter"} for page in pages)},
        "card": {"detected": any(page["density_score"] >= 4 for page in pages)},
        "image_frame": {"detected": any(slot["kind"] == "image" for slot in slot_candidates)},
        "cover": {"source_slides": [page["source_slide"] for page in pages if page["story_role"] == "cover"]},
        "ending": {"source_slides": [page["source_slide"] for page in pages if page["story_role"] == "ending"]},
    }

    adaptable_patterns = [
        {
            "name": f"{role}_source_pages",
            "allowed_use": "Use after the faithful baseline is accepted; preserve page geometry and replace only declared slots.",
            "source_slide_count": count,
        }
        for role, count in sorted(role_counts.items())
        if role not in {"cover", "ending"}
    ]

    template_language = build_template_language(
        manifest=manifest,
        source_workspace=source_workspace,
        template_id=template_id,
        pages=pages,
        slot_candidates=slot_candidates,
    )

    return {
        "schema_version": "easyslides.pptx_distilled_spec.v1",
        "template_id": template_id,
        "source": {
            "deck_path": str(source_pptx),
            "manifest_path": str(source_workspace / "manifest.json"),
            "preview_dir": str(source_workspace / "svg-flat"),
            "slide_size": [width, height],
        },
        "identity_must_preserve": identity,
        "structural_primitives": structural_primitives,
        "slot_candidates": slot_candidates,
        "adaptable_patterns": adaptable_patterns,
        "template_language": template_language,
        "forbidden_drift": [
            "Do not replace source cover and ending pages with generic EasySlides shells.",
            "Do not move, resize, recolor, regroup, or delete fixed source geometry during the faithful baseline pass.",
            "Do not treat the distilled spec as permission to redesign before visual comparison against source previews.",
            "Do not register the template before SVG/PPTX export and placeholder checks pass.",
        ],
        "qa_expectations": {
            "requires_source_contact_sheet": True,
            "requires_svg_export": True,
            "requires_pptx_render": True,
            "requires_cross_material_smoke_test": True,
            "geometry_checks": ["text_canvas", "text_text_overlap", "line_text_overlap"],
        },
        "theme": {
            "colors": colors,
            "fonts": fonts,
            "primary_color": primary_color(manifest),
        },
    }


def write_contact_sheet(source_workspace: Path, pages: list[dict[str, Any]]) -> None:
    rows = []
    for page in pages:
        svg_file = page["source_svg"]
        rows.append(
            "\n".join(
                [
                    '<figure class="slide">',
                    f'  <img src="svg-flat/{svg_file}" alt="Slide {page["source_slide"]}">',
                    f'  <figcaption>Slide {page["source_slide"]}: {page["story_role"]}</figcaption>',
                    "</figure>",
                ]
            )
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PPTX Template Source Contact Sheet</title>
  <style>
    body {{ margin: 24px; font-family: Arial, sans-serif; background: #f6f7f9; color: #151515; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 18px; }}
    .slide {{ margin: 0; padding: 12px; background: white; border: 1px solid #d8dde6; }}
    img {{ display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: #fff; }}
    figcaption {{ margin-top: 8px; font-size: 13px; color: #4d5562; }}
  </style>
</head>
<body>
  <h1>PPTX Template Source Contact Sheet</h1>
  <div class="grid">
{chr(10).join(rows)}
  </div>
</body>
</html>
"""
    (source_workspace / "contact_sheet.html").write_text(html, encoding="utf-8")


def build_pages(manifest: dict[str, Any], source_workspace: Path, template_dir: Path) -> list[dict[str, Any]]:
    slides = manifest.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("manifest.json has no slides")

    template_dir.mkdir(parents=True, exist_ok=True)
    copy_assets(source_workspace, template_dir)
    for stale_svg in template_dir.glob("*.svg"):
        stale_svg.unlink()

    total = len(slides)
    role_seen: defaultdict[str, int] = defaultdict(int)
    pages: list[dict[str, Any]] = []
    for slide in slides:
        index = int(slide.get("index") or len(pages) + 1)
        story_role = classify_story_role(slide, total)
        role_seen[story_role] += 1
        source_svg_name = str(slide.get("flatSvgFile") or slide.get("svgFile") or f"slide_{index:02d}.svg")
        source_svg = source_workspace / "svg-flat" / source_svg_name
        if not source_svg.exists():
            source_svg = source_workspace / "svg" / source_svg_name
        target_stem = f"{index:02d}_{story_role}"
        if role_seen[story_role] > 1:
            target_stem = f"{index:02d}_{story_role}_{role_seen[story_role]:02d}"

        slot_candidates = svg_candidates(source_svg, story_role)
        if not slot_candidates:
            for i, sample in enumerate(slide.get("textSamples") or [], 1):
                slot_id = "PAGE_TITLE" if story_role == "content" and i == 1 else f"TEXT_{i:02d}"
                slot_candidates.append(
                    {
                        "slot": slot_id,
                        "kind": "text",
                        "geometry": {"x": 80.0, "y": 80.0 + (i - 1) * 40, "width": 640.0, "height": 32.0},
                        "capacity": {"lines": 1, "max_chars_per_line": 32},
                        "sample": str(sample)[:120],
                    }
                )
            for i, _asset in enumerate(slide.get("imageAssets") or [], 1):
                slot_candidates.append(
                    {
                        "slot": f"IMAGE_{i:02d}",
                        "kind": "image",
                        "geometry": {"x": 720.0, "y": 160.0, "width": 420.0, "height": 300.0},
                        "image_fit": "contain",
                    }
                )

        pages.append(
            {
                "id": target_stem,
                "svg": source_svg_name,
                "source_svg": source_svg_name,
                "source_slide": index,
                "page_type": story_role,
                "story_role": story_role,
                "role_fit": role_fit(story_role),
                "slot_model": role_slot_name(story_role),
                "density_score": density_score(slide),
                "slot_candidates": slot_candidates,
                "text_samples": slide.get("textSamples") or [],
            }
        )
    return pages


def materialize_canonical_shells(
    *,
    source_pages: list[dict[str, Any]],
    source_workspace: Path,
    template_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Write the evidence-driven public shells; keep the full source roster in metadata."""
    shells, variants, roster = build_canonical_shell_pack(source_pages)
    for shell in shells:
        source_svg_name = str(shell.get("source_svg") or "")
        source_svg = source_workspace / "svg-flat" / source_svg_name
        if not source_svg.exists():
            source_svg = source_workspace / "svg" / source_svg_name
        target_svg = template_dir / str(shell["svg"])
        if source_svg.exists():
            copy_svg_for_template(source_svg, target_svg)
            measured = svg_candidates(source_svg, str(shell["story_role"]))
            if measured:
                shell["slot_candidates"] = measured
        shell["source_svg"] = source_svg_name
    if not CANONICAL_SHELL_MINIMUM <= len(shells) <= CANONICAL_SHELL_LIMIT:
        raise RuntimeError(
            "canonical shell policy requires "
            f"{CANONICAL_SHELL_MINIMUM}-{CANONICAL_SHELL_LIMIT} shells, got {len(shells)}"
        )
    return shells, variants, roster


def slot_models_from_pages(pages: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for page in pages:
        model_name = page["slot_model"]
        for slot in page["slot_candidates"]:
            slot_id = slot["slot"]
            existing = grouped[model_name].get(slot_id)
            if existing:
                continue
            record: dict[str, Any] = {
                "slot_id": slot_id,
                "role": slot_id.lower(),
                "kind": slot["kind"],
            }
            if slot["kind"] == "image":
                record["image_fit"] = slot.get("image_fit", "contain")
            else:
                capacity = slot.get("capacity") or {}
                record["max_lines"] = capacity.get("lines", 1)
                record["max_chars_per_line"] = capacity.get("max_chars_per_line", 32)
            grouped[model_name][slot_id] = record
    return {name: list(records.values()) for name, records in sorted(grouped.items())}


def write_template_sidecars(
    *,
    template_dir: Path,
    template_id: str,
    manifest: dict[str, Any],
    pages: list[dict[str, Any]],
    source_pages: list[dict[str, Any]],
    body_variants: list[dict[str, Any]],
    source_page_roster: list[dict[str, Any]],
    distilled_spec: dict[str, Any],
) -> None:
    width, height = slide_size_tuple(manifest)
    colors = distilled_spec.get("theme", {}).get("colors", {})
    fonts = distilled_spec.get("theme", {}).get("fonts", {})
    primary = distilled_spec.get("theme", {}).get("primary_color") or primary_color(manifest)
    shell_profile = build_shell_profile(pages)

    layouts = {
        "schema_version": f"easyslides.{template_id}.layouts.v1",
        "template_id": template_id,
        "replication_mode": "slot_guided_mirror",
        "global_contract": {
            "replication_mode": "slot_guided_mirror",
            "source_geometry_policy": "preserve_fixed_geometry_replace_declared_slots",
            "canonical_shell_policy": shell_profile["policy"],
            "canonical_shell_minimum": shell_profile["minimum_shell_count"],
            "canonical_shell_limit": CANONICAL_SHELL_LIMIT,
            "required_shell_roles": shell_profile["required_shell_roles"],
            "optional_shell_roles": shell_profile["optional_shell_roles"],
            "active_shell_roles": shell_profile["active_shell_roles"],
        },
        "canvas": {"width": width, "height": height, "format": "ppt169"},
        "style_system": template_id,
        "colors": {"primary": primary, **colors},
        "fonts": fonts,
        "pages": [
            {
                "id": page["id"],
                "page_id": page["shell_id"],
                "layout_id": page["shell_id"],
                "svg": page["svg"],
                "role": page["story_role"],
                "page_type": page["page_type"],
                "story_role": page["story_role"],
                "role_fit": page["role_fit"],
                "slot_model": page["slot_model"],
                "source_slide": page["source_slide"],
                "density_score": page["density_score"],
                "shell_id": page["shell_id"],
                "body_variants": page.get("body_variants", []),
            }
            for page in pages
        ],
        "layouts": [
            {
                "layout_id": page["shell_id"],
                "id": page["id"],
                "page_id": page["shell_id"],
                "svg": page["svg"],
                "role": page["story_role"],
                "story_role": page["story_role"],
                "slot_model": page["slot_model"],
                "body_variants": page.get("body_variants", []),
            }
            for page in pages
        ],
        "shells": [
            {
                "shell_id": page["shell_id"],
                "page_id": page["id"],
                "svg": page["svg"],
                "role": page["story_role"],
                "source_slide": page["source_slide"],
                "source_page_id": page.get("source_page_id"),
                "fallback_source_role": page.get("fallback_source_role", False),
            }
            for page in pages
        ],
        "body_variants": "body_variants.json",
        "source_page_roster": "source_page_roster.json",
        "shell_profile": shell_profile,
        "slot_models": slot_models_from_pages(pages),
        "text_fit_policy": {
            "schema_version": "easyslides.template_text_fit_policy.v1",
            "overflow_strategy_order": [
                "use_declared_capacity",
                "choose_lower_density_source_page",
                "split_across_slides",
                "shrink_font_with_floor",
            ],
        },
    }
    write_json(template_dir / "layouts.json", layouts)
    write_json(
        template_dir / "body_variants.json",
        {
            "schema_version": "easyslides.body_variants.v1",
            "template_id": template_id,
            "source_shell": "04_content.svg",
            "selection_policy": "canonical_shell_then_body_variant_then_density_and_slot_fit",
            "variants": [{**variant, "layout_id": "content"} for variant in body_variants],
        },
    )
    write_json(
        template_dir / "source_page_roster.json",
        {
            "schema_version": "easyslides.source_page_roster.v1",
            "template_id": template_id,
            "source_slide_count": len(source_pages),
            "canonical_shell_count": len(pages),
            "body_variant_count": len(body_variants),
            "shell_profile": shell_profile,
            "required_shell_roles": shell_profile["required_shell_roles"],
            "optional_shell_roles": shell_profile["optional_shell_roles"],
            "active_shell_roles": shell_profile["active_shell_roles"],
            "pages": source_page_roster,
        },
    )

    catalog = {
        "schema_version": "easyslides.page_catalog.v1",
        "template_id": template_id,
        "selection_policy": "canonical_shell_then_body_variant_then_role_density_slots",
        "pages": [
            {
                "id": page["id"],
                "source_slide": page["source_slide"],
                "story_role": page["story_role"],
                "role_fit": page["role_fit"],
                "density_score": page["density_score"],
                "best_for": page_best_for(page),
                "avoid": page_avoid(page),
                "shell_id": page["shell_id"],
                "body_variants": page.get("body_variants", []),
            }
            for page in pages
        ],
        "body_variants": body_variants,
        "source_pages": source_page_roster,
    }
    write_json(template_dir / "page_catalog.json", catalog)

    story = {
        "schema_version": "easyslides.story_structure.v1",
        "template_id": template_id,
        "default_scenario": "source_faithful_template_reuse",
        "canonical_shells": [page["shell_id"] for page in pages],
        "shell_profile": shell_profile,
        "source_slide_count": len(source_pages),
        "recommended_flow": [
            {"story_role": page["story_role"], "page_id": page["id"], "source_slide": page["source_slide"]}
            for page in pages
        ],
    }
    write_json(template_dir / "story_structure.json", story)

    write_design_spec(template_dir / "design_spec.md", template_id, primary, width, height, pages)
    write_rules(template_dir / "rules.md", template_id)
    write_geometry_contract(template_dir, template_id, width, height, pages)


def write_geometry_contract(
    template_dir: Path,
    template_id: str,
    width: int,
    height: int,
    pages: list[dict[str, Any]],
) -> None:
    contract_pages: list[dict[str, Any]] = []
    for page in pages:
        rects = svg_rectangles(template_dir / page["svg"])
        protected = infer_protected_regions(rects, width, height)
        protected_right = max((float(region["x"]) + float(region["width"]) for region in protected), default=0.0)
        content_bounds = {
            "x": round(protected_right + 24 if protected_right else 24, 2),
            "y": 96,
            "width": round(width - (protected_right + 48 if protected_right else 48), 2),
            "height": height - 120,
        }
        contract_pages.append(
            {
                "id": page["id"],
                "svg": page["svg"],
                "source_slide": page["source_slide"],
                "story_role": page["story_role"],
                "protected_regions": protected,
                "content_bounds": content_bounds,
                "containers": infer_containers(rects, protected, width, height),
            }
        )
    write_json(
        template_dir / "geometry_contract.json",
        {
            "schema_version": "easyslides.template_geometry_contract.v1",
            "template_id": template_id,
            "canvas": {"width": width, "height": height},
            "pages": contract_pages,
        },
    )


def page_best_for(page: dict[str, Any]) -> str:
    role = page["story_role"]
    if role == "cover":
        return "opening slide that must preserve source title composition"
    if role == "ending":
        return "closing or acknowledgement slide that must preserve source closing composition"
    if role == "toc":
        return "agenda, outline, or section roadmap"
    if role == "chapter":
        return "section opener or transition"
    if any(slot["kind"] == "image" for slot in page["slot_candidates"]):
        return "content with a source figure, image, or visual exhibit"
    return "text-led content with source-faithful geometry"


def page_avoid(page: dict[str, Any]) -> str:
    if page["density_score"] >= 4:
        return "very sparse messages that would make dense source geometry feel empty"
    return "content that requires moving fixed source chrome"


def write_design_spec(
    path: Path,
    template_id: str,
    primary: str,
    width: int,
    height: int,
    pages: list[dict[str, Any]],
) -> None:
    placeholders: dict[str, list[str]] = {}
    for page in pages:
        placeholders[page["id"]] = [f"{{{{{slot['slot']}}}}}" for slot in page["slot_candidates"]]
    frontmatter_placeholders = "\n".join(
        f'  "{page_id}": {json.dumps(values, ensure_ascii=False)}'
        for page_id, values in placeholders.items()
    )
    placeholders_json = json.dumps(placeholders, ensure_ascii=False, indent=2)
    body = f"""---
template_id: {template_id}
category: imported
summary: Source-faithful slot-guided mirror template distilled from a PPTX source deck.
keywords:
  - pptx_import
  - slot_guided_mirror
  - source_faithful
primary_color: "{primary}"
canvas_format: ppt169
replication_mode: slot_guided_mirror
placeholders:
{frontmatter_placeholders}
---

# {template_id} Design Specification

This template was generated by `scripts/pptx_template_distill.py` as an
evidence-driven EasySlides shell profile. Treat the source PPTX previews,
`source_page_roster.json`, and `distilled_spec.json` as the authority when
reviewing visual fidelity.

## Template Contract

| Property | Value |
|---|---|
| Template ID | `{template_id}` |
| Replication Mode | `slot_guided_mirror` |
| Canvas | {width} x {height}, 16:9 |
| Primary Color | `{primary}` |
| Runtime Surface | {len(pages)} active shell SVGs plus named-slot sidecars |

## Page Roster

| SVG | Role | Source Slide | Density |
|---|---|---:|---:|
"""
    for page in pages:
        body += f"| `{page['svg']}` | `{page['story_role']}` | {page['source_slide']} | {page['density_score']} |\n"

    body += f"""
## Placeholder Inventory

```json
{placeholders_json}
```

## Shell Policy

The public runtime surface is an evidence-driven shell profile with three
required shells (`cover`, `content`, `ending`) and two optional shells (`toc`,
`chapter`). Optional shells are materialized only when the source PPTX contains
evidence for that role; this template currently exposes: `{", ".join(page["shell_id"] for page in pages)}`.
Source pages beyond these shells are kept as evidence and grouped into
`body_variants.json`; they must not become new public layout files. Use
`source_page_roster.json` to trace every variant back to its source slide.

## Source-Faithful Rules

Use this as a review draft, not as a redesigned style pack. Replace declared
slots only after confirming the faithful baseline against the source contact
sheet. Promote repeated elements into reusable components only when they remain
visually consistent with the imported source pages. Select a shell first, then
choose a body variant; never route by source page number.
"""
    path.write_text(body, encoding="utf-8")


def write_rules(path: Path, template_id: str) -> None:
    path.write_text(
        f"""# {template_id} Rules

- The runtime template must expose the required shells `cover`, `content`, and `ending`, plus optional `toc` and `chapter` shells only when source evidence supports them.
- Keep the active shell profile between 3 and 5 public layouts; do not synthesize a missing TOC or chapter page.
- Preserve fixed source geometry before introducing body variants.
- Keep source-only pages in `source_page_roster.json`; do not add one SVG per source slide.
- Select `content` body variants by semantic shape, density, evidence count, and slot capacity.
- Replace only declared slots from `layouts.json` and `slot_contracts.json`.
- Do not move, resize, recolor, or delete repeated source chrome during faithful reuse.
- Keep cover and ending pages page-specific unless a reviewer explicitly approves a generalized variant.
- Use `page_catalog.json` for page selection by story role, density, and source-slide evidence.
- Verify SVG previews and exported PPTX previews before registering this as production-ready.
- Run `scripts/template_material_smoke_test.py` with a different topic/material set before claiming the template can be reused.
""",
        encoding="utf-8",
    )


def write_source_geometry_risks(source_workspace: Path, template_dir: Path) -> Path:
    try:
        from template_geometry_qa import validate_template_geometry
    except ImportError:  # pragma: no cover - used when imported as scripts.*
        from scripts.template_geometry_qa import validate_template_geometry

    report = validate_template_geometry(template_dir)
    risks = {
        "schema_version": "easyslides.source_geometry_risks.v1",
        "template_dir": str(template_dir),
        "status": report.get("status"),
        "blocking_count": report.get("blocking_count", 0),
        "warning_count": report.get("warning_count", 0),
        "issues": report.get("issues", []),
        "interpretation": (
            "Source-authored geometry risks are preserved as template evidence. "
            "Use them to avoid treating intentional labels, overfull source text, "
            "or decorative overlaps as unconstrained user-material slots."
        ),
    }
    path = source_workspace / "source_geometry_risks.json"
    write_json(path, risks)
    return path


def build_from_reference_workspace(
    *,
    source_workspace: Path,
    template_dir: Path,
    template_id: str,
    source_pptx: Path,
    promote_assets: bool = False,
) -> dict[str, Any]:
    source_workspace = source_workspace.resolve()
    template_dir = template_dir.resolve()
    template_id = sanitize_template_id(template_id)
    manifest_path = source_workspace / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest.json in {source_workspace}")

    manifest = read_json(manifest_path)
    from pptx_design_system_compiler import compile_design_system_pack, write_design_system_pack
    from pptx_distill_registry import build_semantic_specs, write_semantic_specs
    from pptx_projection import build_projection_manifest, write_projection_manifest
    from pptx_distill_promotion_gate import build_promotion_report
    from pptx_source_graph import build_distill_manifest, build_manifest_graph, build_source_graph

    if source_pptx.exists():
        source_graph = build_source_graph(source_pptx, manifest=manifest)
    else:
        source_graph = build_manifest_graph(manifest, source_pptx)
    normalize_source_svg_navigation(source_workspace)
    source_graph_path = source_workspace / "source_graph.json"
    write_json(source_graph_path, source_graph)
    semantic_specs = build_semantic_specs(
        template_id=template_id,
        graph=source_graph,
        manifest=manifest,
    )
    semantic_paths = write_semantic_specs(source_workspace, semantic_specs)
    compiled_design_system = compile_design_system_pack(
        template_id=template_id,
        source_workspace=source_workspace,
        repository_root=ROOT,
    )
    design_system_paths = write_design_system_pack(source_workspace, compiled_design_system)
    projection_manifest_path = write_projection_manifest(
        source_workspace,
        build_projection_manifest(template_id=template_id, source_workspace=source_workspace),
    )
    distill_manifest = build_distill_manifest(
        template_id=template_id,
        source_workspace=source_workspace,
        source_pptx=source_pptx,
        source_graph=source_graph,
        stage="phase_5_qa_and_promotion",
        next_phase="phase_6_human_review_and_promotion",
    )
    distill_manifest_path = source_workspace / "distill_manifest.json"
    write_json(distill_manifest_path, distill_manifest)

    source_pages = build_pages(manifest, source_workspace, template_dir)
    pages, body_variants, source_page_roster = materialize_canonical_shells(
        source_pages=source_pages,
        source_workspace=source_workspace,
        template_dir=template_dir,
    )
    distilled_spec = build_distilled_spec(
        manifest=manifest,
        source_workspace=source_workspace,
        source_pptx=source_pptx.resolve(),
        template_id=template_id,
        pages=source_pages,
    )
    write_json(source_workspace / "distilled_spec.json", distilled_spec)
    write_template_language_report(source_workspace / "template_language.md", distilled_spec["template_language"])
    rebuild_plan = build_editable_rebuild_plan(
        template_id=template_id,
        pages=source_pages,
        template_language=distilled_spec["template_language"],
    )
    write_json(source_workspace / "editable_rebuild_plan.json", rebuild_plan)
    adaptation_strategy = build_adaptation_strategy(
        template_id=template_id,
        pages=source_pages,
        template_language=distilled_spec["template_language"],
        rebuild_plan=rebuild_plan,
    )
    write_json(source_workspace / "adaptation_strategy.json", adaptation_strategy)
    write_contact_sheet(source_workspace, source_pages)
    write_template_sidecars(
        template_dir=template_dir,
        template_id=template_id,
        manifest=manifest,
        pages=pages,
        source_pages=source_pages,
        body_variants=body_variants,
        source_page_roster=source_page_roster,
        distilled_spec=distilled_spec,
    )
    source_geometry_risks_path = write_source_geometry_risks(source_workspace, template_dir)

    from template_contract_pack import write_contract_pack

    written_contracts = write_contract_pack(template_dir)
    promotion_report = build_promotion_report(
        source_workspace=source_workspace,
        template_dir=template_dir,
        output_dir=source_workspace / "promotion_gate",
        run_cross_material=False,
    )
    promotion_report_path = source_workspace / "promotion_report.json"
    write_json(promotion_report_path, promotion_report)
    asset_promotion: dict[str, Any] | None = None
    if promote_assets:
        if not promotion_report.get("promotable"):
            asset_promotion = {
                "status": "blocked",
                "template_id": template_id,
                "reason": "promotion_gate_not_passed",
                "promotion_status": promotion_report.get("status"),
                "promotion_report": str(promotion_report_path),
            }
        else:
            from pptx_distill_promote import promote

            asset_promotion = promote(
                source_workspace,
                template_dir,
                template_id=template_id,
                promotion_report=promotion_report,
            )
    return {
        "template_id": template_id,
        "source_workspace": str(source_workspace),
        "template_dir": str(template_dir),
        "slide_count": len(pages),
        "source_slide_count": len(source_pages),
        "canonical_shell_count": len(pages),
        "body_variant_count": len(body_variants),
        "source_graph": str(source_graph_path),
        "distill_manifest": str(distill_manifest_path),
        "semantic_contracts": {key: str(path) for key, path in semantic_paths.items()},
        "design_system_pack": {key: str(path) for key, path in design_system_paths.items()},
        "projection_manifest": str(projection_manifest_path),
        "promotion_report": str(promotion_report_path),
        "editable_rebuild_plan": str(source_workspace / "editable_rebuild_plan.json"),
        "adaptation_strategy": str(source_workspace / "adaptation_strategy.json"),
        "source_geometry_risks": str(source_geometry_risks_path),
        "contract_files": [str(path) for path in written_contracts],
        **({"asset_promotion": asset_promotion} if asset_promotion is not None else {}),
    }


def import_pptx_source(pptx_path: Path, source_workspace: Path) -> dict[str, Any]:
    from pptx_to_svg import convert_pptx_to_svg
    from pptx_to_svg.converter import ConvertOptions
    from pptx_source_graph import build_source_graph
    from template_import.manifest import build_manifest

    source_workspace.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(pptx_path, source_workspace)
    write_json(source_workspace / "manifest.json", manifest)
    write_json(
        source_workspace / "source_graph.json",
        build_source_graph(pptx_path, manifest=manifest),
    )

    options = ConvertOptions(
        media_subdir="assets",
        embed_images=False,
        keep_hidden=False,
        inheritance_mode="both",
        asset_name_map=manifest.get("assets", {}).get("assetMap", {}),
    )
    convert_pptx_to_svg(pptx_path, source_workspace, options)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distill a source PPTX into a draft EasySlides template pack."
    )
    parser.add_argument("pptx_file", help="Source .pptx file")
    parser.add_argument("--template-id", help="Template id. Defaults to the PPTX stem.")
    parser.add_argument(
        "--source-dir",
        help="Reference workspace. Defaults to templates/reference/template_asset_sources/<template_id>.",
    )
    parser.add_argument(
        "--template-dir",
        help="Template output directory. Defaults to templates/layouts/<template_id>.",
    )
    parser.add_argument(
        "--from-existing-source",
        action="store_true",
        help="Skip PPTX import and build from an existing reference workspace with manifest.json.",
    )
    parser.set_defaults(promote_assets=False)
    parser.add_argument(
        "--promote-assets",
        dest="promote_assets",
        action="store_true",
        help="Promote reusable assets only when the complete promotion gate passes.",
    )
    parser.add_argument(
        "--no-promote-assets",
        dest="promote_assets",
        action="store_false",
        help="Compatibility alias for the default: build only the faithful review layer.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable result.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pptx_path = Path(args.pptx_file).expanduser().resolve()
    if not pptx_path.exists():
        print(f"Error: file does not exist: {pptx_path}", file=sys.stderr)
        return 1
    if pptx_path.suffix.lower() != ".pptx":
        print(f"Error: expected a .pptx file, got: {pptx_path.name}", file=sys.stderr)
        return 1

    template_id = sanitize_template_id(args.template_id or pptx_path.stem)
    source_workspace = (
        Path(args.source_dir).expanduser().resolve()
        if args.source_dir
        else (REFERENCE_ROOT / template_id).resolve()
    )
    template_dir = (
        Path(args.template_dir).expanduser().resolve()
        if args.template_dir
        else (LAYOUTS_ROOT / template_id).resolve()
    )

    if not args.from_existing_source:
        import_pptx_source(pptx_path, source_workspace)

    result = build_from_reference_workspace(
        source_workspace=source_workspace,
        template_dir=template_dir,
        template_id=template_id,
        source_pptx=pptx_path,
        promote_assets=args.promote_assets,
    )
    promotion = result.get("asset_promotion")
    if args.promote_assets and isinstance(promotion, dict) and promotion.get("status") == "blocked":
        print(
            "Error: asset promotion was blocked because the promotion gate did not pass. "
            f"Review {promotion.get('promotion_report')}.",
            file=sys.stderr,
        )
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Distilled PPTX template: {template_id}")
        print(f"Source workspace: {source_workspace}")
        print(f"Template directory: {template_dir}")
        print(f"Slides mapped: {result['slide_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
