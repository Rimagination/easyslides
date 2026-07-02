#!/usr/bin/env python3
"""Validate template geometry contracts against SVG draft pages.

This gate catches the failures that whole-slide rendering checks miss:

- content text crossing protected chrome such as navigation rails
- text spilling outside a declared card/container
- missing image assets or "image?" placeholders
- text boxes extending off the slide canvas

It is conservative by design. A failure means the template draft needs a human
repair pass or stronger slot bounds before it is promoted.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from scripts import layout_metrics
except ImportError:  # pragma: no cover - direct script execution
    import layout_metrics


SCHEMA_VERSION = "easyslides.template_geometry_qa_report.v1"
CONTRACT_VERSION = "easyslides.template_geometry_contract.v1"
LINE_HEIGHT = 1.22
CONTAINER_PADDING = 0.0
OVERLAP_TOLERANCE = 1.0
CONTAINER_OVERFLOW_TOLERANCE = 8.0
CONTROL_TEXT_CENTER_TOLERANCE = 2.0
CONTROL_CONTAINER_MAX_HEIGHT = 96.0
EMU_PER_PX = 914400 / 96
AffineMatrix = tuple[float, float, float, float, float, float]
IDENTITY_MATRIX: AffineMatrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TRANSFORM_RE = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")
PPTX_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class SvgText:
    element_index: int
    text: str
    box: Box
    fill: str
    font_size: float
    pptx_textbox: bool = False
    valign: str = ""


@dataclass(frozen=True)
class SvgImage:
    element_index: int
    href: str
    box: Box


@dataclass(frozen=True)
class PptxText:
    slide_number: int
    shape_index: int
    text: str
    box: Box
    fill: str


def matrix_multiply(left: AffineMatrix, right: AffineMatrix) -> AffineMatrix:
    """Compose two SVG-style affine matrices as ``left(right(point))``."""
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def translate_matrix(x: float, y: float) -> AffineMatrix:
    return (1.0, 0.0, 0.0, 1.0, x, y)


def scale_matrix(x: float, y: float | None = None) -> AffineMatrix:
    return (x, 0.0, 0.0, x if y is None else y, 0.0, 0.0)


def rotate_matrix(angle_deg: float, cx: float = 0.0, cy: float = 0.0) -> AffineMatrix:
    theta = math.radians(angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    rotate: AffineMatrix = (cos_t, sin_t, -sin_t, cos_t, 0.0, 0.0)
    if cx or cy:
        return matrix_multiply(translate_matrix(cx, cy), matrix_multiply(rotate, translate_matrix(-cx, -cy)))
    return rotate


def parse_number_list(raw: str) -> list[float]:
    return [float(match.group(0)) for match in re.finditer(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw)]


def parse_transform_matrix(transform: str | None) -> AffineMatrix:
    matrix = IDENTITY_MATRIX
    for name, raw_args in _TRANSFORM_RE.findall(transform or ""):
        values = parse_number_list(raw_args)
        op = name.lower()
        if op == "matrix" and len(values) >= 6:
            next_matrix = (values[0], values[1], values[2], values[3], values[4], values[5])
        elif op == "translate" and values:
            next_matrix = translate_matrix(values[0], values[1] if len(values) > 1 else 0.0)
        elif op == "scale" and values:
            next_matrix = scale_matrix(values[0], values[1] if len(values) > 1 else None)
        elif op == "rotate" and values:
            next_matrix = rotate_matrix(
                values[0],
                values[1] if len(values) > 2 else 0.0,
                values[2] if len(values) > 2 else 0.0,
            )
        else:
            continue
        matrix = matrix_multiply(matrix, next_matrix)
    return matrix


def transform_point(matrix: AffineMatrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def transform_box(box: Box, matrix: AffineMatrix) -> Box:
    if matrix == IDENTITY_MATRIX:
        return box
    points = [
        transform_point(matrix, box.x, box.y),
        transform_point(matrix, box.right, box.y),
        transform_point(matrix, box.right, box.bottom),
        transform_point(matrix, box.x, box.bottom),
    ]
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    return Box(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys))


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return default
    try:
        return float(match.group(0))
    except ValueError:
        return default


def parse_style(style: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not style:
        return result
    for item in style.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def element_text(elem: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def char_width(ch: str, font_size: float) -> float:
    return layout_metrics.char_width_px(ch, font_size)


def text_display_lines(elem: ET.Element, fallback_text: str) -> list[str]:
    tspans = [child for child in elem if local_name(child.tag) == "tspan"]
    if not tspans:
        return fallback_text.splitlines() or [fallback_text]

    lines: list[str] = []
    current = ""
    seen_text_run = False
    for child in tspans:
        starts_new_line = seen_text_run and (child.attrib.get("dy") is not None or child.attrib.get("x") is not None)
        if starts_new_line:
            lines.append(current)
            current = ""
        current += "".join(child.itertext())
        seen_text_run = True
    lines.append(current)
    return [line for line in lines if line] or [fallback_text]


def estimate_text_box(elem: ET.Element, text: str) -> Box:
    return layout_metrics.measure_svg_text_box(elem, text, line_height=LINE_HEIGHT)


def element_fill(elem: ET.Element) -> str:
    style = parse_style(elem.attrib.get("style"))
    fill = elem.attrib.get("fill") or style.get("fill") or "#000000"
    return fill.strip()


def element_valign(elem: ET.Element) -> str:
    return str(elem.attrib.get("data-pptx-valign") or "").strip().lower()


def rect_from_mapping(payload: dict[str, Any]) -> Box:
    return Box(
        x=float(payload.get("x", 0)),
        y=float(payload.get("y", 0)),
        width=float(payload.get("width", payload.get("w", 0))),
        height=float(payload.get("height", payload.get("h", 0))),
    )


def contains(outer: Box, inner: Box, tolerance: float = 0.0) -> bool:
    return (
        inner.x >= outer.x - tolerance
        and inner.y >= outer.y - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def point_inside(box: Box, x: float, y: float) -> bool:
    return box.x <= x <= box.right and box.y <= y <= box.bottom


def protected_side_label_bleed_allowed(box: Box, canvas: Box, region: Box) -> bool:
    """Allow intentional rotated side labels to bleed slightly off protected chrome."""
    if not point_inside(region, box.cx, box.cy):
        return False
    if box.height < canvas.height * 0.60:
        return False
    if box.width > region.width * 0.68:
        return False
    if box.y < canvas.y - OVERLAP_TOLERANCE or box.bottom > canvas.bottom + OVERLAP_TOLERANCE:
        return False
    bleed_allowance = max(48.0, box.width * 0.4)
    left_bleed = (
        box.x < region.x
        and box.x >= canvas.x - bleed_allowance
        and box.right <= region.right + OVERLAP_TOLERANCE
    )
    right_bleed = (
        box.right > region.right
        and box.right <= canvas.right + bleed_allowance
        and box.x >= region.x - OVERLAP_TOLERANCE
    )
    return left_bleed or right_bleed


def overlap(a: Box, b: Box) -> float:
    dx = min(a.right, b.right) - max(a.x, b.x)
    dy = min(a.bottom, b.bottom) - max(a.y, b.y)
    if dx <= 0 or dy <= 0:
        return 0.0
    return dx * dy


def horizontal_overlap_ratio(a: Box, b: Box) -> float:
    dx = min(a.right, b.right) - max(a.x, b.x)
    if dx <= 0:
        return 0.0
    return dx / max(min(a.width, b.width), 1.0)


def best_container_for_text(
    containers: list[tuple[str, Box]],
    text_box: Box,
) -> tuple[str, Box] | None:
    center_candidates: list[tuple[float, str, Box]] = []
    overlap_candidates: list[tuple[float, str, Box]] = []
    for name, container in containers:
        overlap_area = overlap(container, text_box)
        if overlap_area <= OVERLAP_TOLERANCE:
            continue
        center_inside = point_inside(container, text_box.cx, text_box.cy)
        belongs = (
            center_inside
            or point_inside(container, text_box.x, text_box.cy)
            or overlap_area / max(text_box.area, 1.0) >= 0.5
        )
        if not belongs:
            continue
        if center_inside:
            center_candidates.append((container.area, name, container))
        else:
            overlap_candidates.append((overlap_area, name, container))
    if center_candidates:
        _area, name, container = min(center_candidates, key=lambda item: item[0])
        return name, container
    if not overlap_candidates:
        return None
    _score, name, container = max(overlap_candidates, key=lambda item: item[0])
    return name, container


def inset(box: Box, padding: float) -> Box:
    return Box(
        x=box.x + padding,
        y=box.y + padding,
        width=max(0.0, box.width - padding * 2),
        height=max(0.0, box.height - padding * 2),
    )


def luminance(hex_color: str) -> float | None:
    color = hex_color.strip()
    if not color.startswith("#"):
        return None
    color = color[1:]
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) < 6:
        return None
    try:
        r = int(color[0:2], 16) / 255
        g = int(color[2:4], 16) / 255
        b = int(color[4:6], 16) / 255
    except ValueError:
        return None
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def parse_svg(svg_path: Path) -> tuple[list[SvgText], list[SvgImage]]:
    root = ET.parse(svg_path).getroot()
    texts: list[SvgText] = []
    for index, elem, text, box in layout_metrics.iter_svg_text_boxes(root):
        texts.append(
            SvgText(
                element_index=index,
                text=text,
                box=box,
                fill=element_fill(elem),
                font_size=parse_float(elem.attrib.get("font-size"), 18.0),
                pptx_textbox=str(elem.attrib.get("data-pptx-textbox") or "").lower() == "true",
                valign=element_valign(elem),
            )
        )
    images = [
        SvgImage(element_index=image.element_index, href=image.href, box=image.box)
        for image in layout_metrics.iter_svg_image_boxes(root)
    ]
    return texts, images


def numeric_pair_bounds(raw: str | None) -> Box | None:
    if not raw:
        return None
    values = [float(match.group(0)) for match in re.finditer(r"-?\d+(?:\.\d+)?", raw)]
    if len(values) < 4:
        return None
    xs = values[0::2]
    ys = values[1::2]
    return Box(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys))


def shape_box(elem: ET.Element) -> Box | None:
    name = local_name(elem.tag)
    if name == "rect":
        return Box(
            x=parse_float(elem.attrib.get("x")),
            y=parse_float(elem.attrib.get("y")),
            width=parse_float(elem.attrib.get("width")),
            height=parse_float(elem.attrib.get("height")),
        )
    if name == "path":
        return numeric_pair_bounds(elem.attrib.get("d"))
    if name == "polygon":
        return numeric_pair_bounds(elem.attrib.get("points"))
    return None


def dark_label_regions(svg_path: Path) -> list[Box]:
    root = ET.parse(svg_path).getroot()
    regions: list[Box] = []
    for elem in root.iter():
        if local_name(elem.tag) not in {"rect", "path", "polygon"}:
            continue
        style = parse_style(elem.attrib.get("style"))
        fill = elem.attrib.get("fill") or style.get("fill") or ""
        luma = luminance(fill)
        if luma is None or luma >= 0.45:
            continue
        box = shape_box(elem)
        if box is None or box.width <= 0 or box.height <= 0:
            continue
        if 40 <= box.width <= 340 and 24 <= box.height <= 220:
            regions.append(box)
    return regions


def is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def compact_control_rects(root: ET.Element) -> list[tuple[int, Box]]:
    rects: list[tuple[int, Box]] = []
    for index, elem in enumerate(root.iter(), start=1):
        if local_name(elem.tag) != "rect":
            continue
        style = parse_style(elem.attrib.get("style"))
        box = Box(
            x=parse_float(elem.attrib.get("x")),
            y=parse_float(elem.attrib.get("y")),
            width=parse_float(elem.attrib.get("width")),
            height=parse_float(elem.attrib.get("height")),
        )
        if box.width <= 0 or box.height <= 0:
            continue
        if box.height < 14 or box.height > 96 or box.width < 24 or box.width > 760:
            continue
        rx = parse_float(elem.attrib.get("rx"))
        ry = parse_float(elem.attrib.get("ry"))
        fill_raw = (elem.attrib.get("fill") or style.get("fill") or "").strip()
        stroke_raw = (elem.attrib.get("stroke") or style.get("stroke") or "").strip()
        fill = fill_raw.lower()
        stroke = stroke_raw.lower()
        if fill in {"", "none"} and stroke in {"", "none"}:
            continue
        rounded = max(rx, ry) >= min(box.width, box.height) * 0.12
        dark_caption_bar = fill.startswith("url(") or (luminance(fill_raw) is not None and luminance(fill_raw) < 0.45)
        if not rounded and not dark_caption_bar:
            continue
        rects.append((index, box))
    return rects


def compact_textbox_candidates(root: ET.Element) -> list[tuple[int, ET.Element, str, Box]]:
    texts: list[tuple[int, ET.Element, str, Box]] = []
    for index, elem in enumerate(root.iter(), start=1):
        if local_name(elem.tag) != "text":
            continue
        text = element_text(elem)
        if not text or "\n" in text:
            continue
        if not is_truthy(elem.attrib.get("data-pptx-textbox")):
            continue
        required = ("data-pptx-box-x", "data-pptx-box-y", "data-pptx-box-w", "data-pptx-box-h")
        if any(elem.attrib.get(name) is None for name in required):
            continue
        box = Box(
            x=parse_float(elem.attrib.get("data-pptx-box-x")),
            y=parse_float(elem.attrib.get("data-pptx-box-y")),
            width=parse_float(elem.attrib.get("data-pptx-box-w")),
            height=parse_float(elem.attrib.get("data-pptx-box-h")),
        )
        font_size = parse_float(elem.attrib.get("font-size"), 18.0)
        if box.width <= 0 or box.height <= 0:
            continue
        if box.height < 8 or box.height > 90 or font_size > 48:
            continue
        texts.append((index, elem, text, box))
    return texts


def matching_compact_control(text_box: Box, rects: list[tuple[int, Box]]) -> tuple[int, Box] | None:
    candidates: list[tuple[float, float, int, Box]] = []
    for rect_index, rect in rects:
        if text_box.height > rect.height * 1.25 or text_box.height < rect.height * 0.25:
            continue
        horizontal_overlap = max(0.0, min(text_box.right, rect.right) - max(text_box.x, rect.x))
        overlap_ratio = horizontal_overlap / max(text_box.width, 1.0)
        if overlap_ratio < 0.45:
            continue
        center_delta = abs(text_box.cy - rect.cy)
        if center_delta > max(4.0, rect.height * 0.25):
            continue
        candidates.append((center_delta, -overlap_ratio, rect_index, rect))
    if not candidates:
        return None
    _delta, _overlap, rect_index, rect = min(candidates, key=lambda item: (item[0], item[1]))
    return rect_index, rect


def validate_compact_control_text_alignment(svg_path: Path, svg_name: str) -> list[dict[str, Any]]:
    root = ET.parse(svg_path).getroot()
    rects = compact_control_rects(root)
    if not rects:
        return []
    issues: list[dict[str, Any]] = []
    for element_index, elem, text, text_box in compact_textbox_candidates(root):
        match = matching_compact_control(text_box, rects)
        if match is None:
            continue
        _rect_index, rect = match
        valign = str(elem.attrib.get("data-pptx-valign") or "").strip().lower()
        center_delta = abs(text_box.cy - rect.cy)
        if valign in {"middle", "center", "ctr"} and center_delta <= CONTROL_TEXT_CENTER_TOLERANCE:
            continue
        issues.append(
            issue(
                "CONTROL-TEXT-VERTICAL-MISALIGN",
                "blocking",
                svg_name,
                "Compact control text is not vertically center-locked to its rounded rectangle.",
                element_index=element_index,
                text=text,
                text_box=box_payload(text_box),
                control_box=box_payload(rect),
                center_delta=round(center_delta, 2),
                valign=valign or None,
            )
        )
    return issues


def issue(
    code: str,
    severity: str,
    svg_file: str,
    message: str,
    *,
    element_index: int | None = None,
    text: str | None = None,
    **details: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "svg_file": svg_file,
        "message": message,
        "details": details,
    }
    if element_index is not None:
        payload["element_index"] = element_index
    if text is not None:
        payload["details"]["text_preview"] = text[:120]
    return payload


def short_control_text(text: str) -> bool:
    stripped = re.sub(r"\s+", "", text)
    return bool(stripped) and len(stripped) <= 16


def requires_svg_control_center_alignment(text: SvgText, container: Box) -> bool:
    if not text.pptx_textbox:
        return False
    if not short_control_text(text.text):
        return False
    if container.height > CONTROL_CONTAINER_MAX_HEIGHT:
        return False
    if text.box.height > container.height * 1.05 or text.box.height < container.height * 0.2:
        return False
    return horizontal_overlap_ratio(text.box, container) >= 0.45


def requires_pptx_control_center_alignment(text: PptxText, container: Box) -> bool:
    if not short_control_text(text.text):
        return False
    if container.height > CONTROL_CONTAINER_MAX_HEIGHT:
        return False
    if text.box.height > container.height * 1.05 or text.box.height < container.height * 0.15:
        return False
    return horizontal_overlap_ratio(text.box, container) >= 0.45


def union_boxes(boxes: list[Box]) -> Box:
    left = min(box.x for box in boxes)
    top = min(box.y for box in boxes)
    right = max(box.right for box in boxes)
    bottom = max(box.bottom for box in boxes)
    return Box(x=left, y=top, width=right - left, height=bottom - top)


def validate_svg_control_group_alignment(
    svg_name: str,
    texts: list[SvgText],
    containers: list[tuple[str, Box]],
) -> list[dict[str, Any]]:
    groups: dict[str, tuple[Box, list[SvgText]]] = {}
    for text in texts:
        assigned = best_container_for_text(containers, text.box)
        if assigned is None:
            continue
        name, container = assigned
        if not requires_pptx_control_center_alignment(
            PptxText(slide_number=0, shape_index=text.element_index, text=text.text, box=text.box, fill=text.fill),
            container,
        ):
            continue
        groups.setdefault(name, (container, []) )[1].append(text)

    issues: list[dict[str, Any]] = []
    for name, (container, members) in groups.items():
        if not members:
            continue
        if len(members) == 1 and not members[0].pptx_textbox:
            continue
        group_box = union_boxes([member.box for member in members])
        if group_box.height > container.height * 1.15:
            continue
        center_delta = abs(group_box.cy - container.cy)
        valign_bad = any(
            member.pptx_textbox and member.valign not in {"middle", "center", "ctr"}
            for member in members
        )
        if center_delta <= CONTROL_TEXT_CENTER_TOLERANCE and not valign_bad:
            continue
        issues.append(
            issue(
                "CONTROL-TEXT-VERTICAL-MISALIGN",
                "blocking",
                svg_name,
                f"Control-like text group is not vertically center-aligned with {name}.",
                element_index=members[0].element_index,
                text=" / ".join(member.text for member in members[:4]),
                text_box=box_payload(group_box),
                container=box_payload(container),
                center_delta=round(center_delta, 2),
                member_count=len(members),
                valign_values=[
                    member.valign or None for member in members if member.pptx_textbox
                ],
            )
        )
    return issues


def validate_pptx_control_group_alignment(
    svg_name: str,
    texts: list[PptxText],
    containers: list[tuple[str, Box]],
) -> list[dict[str, Any]]:
    groups: dict[str, tuple[Box, list[PptxText]]] = {}
    for text in texts:
        assigned = best_container_for_text(containers, text.box)
        if assigned is None:
            continue
        name, container = assigned
        if not requires_pptx_control_center_alignment(text, container):
            continue
        groups.setdefault(name, (container, []) )[1].append(text)

    issues: list[dict[str, Any]] = []
    for name, (container, members) in groups.items():
        if not members:
            continue
        group_box = union_boxes([member.box for member in members])
        if group_box.height > container.height * 1.15:
            continue
        center_delta = abs(group_box.cy - container.cy)
        if center_delta <= CONTROL_TEXT_CENTER_TOLERANCE:
            continue
        issues.append(
            issue(
                "PPTX-CONTROL-TEXT-VERTICAL-MISALIGN",
                "blocking",
                svg_name,
                f"Exported PPTX control-like text group is not vertically center-aligned with {name}.",
                element_index=members[0].shape_index,
                text=" / ".join(member.text for member in members[:4]),
                text_box=box_payload(group_box),
                container=box_payload(container),
                center_delta=round(center_delta, 2),
                member_count=len(members),
            )
        )
    return issues


def load_contract(template_dir: Path) -> dict[str, Any]:
    path = template_dir / "geometry_contract.json"
    if not path.exists():
        raise FileNotFoundError(f"missing geometry_contract.json in {template_dir}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("geometry_contract.json must contain an object")
    return payload


def resolve_image_path(template_dir: Path, href: str) -> Path | None:
    href = href.strip()
    if not href or href.startswith("data:"):
        return None
    normalized = href.replace("\\", "/")
    if normalized.startswith("../"):
        normalized = normalized[3:]
    return template_dir / normalized


def validate_page(template_dir: Path, contract: dict[str, Any], page: dict[str, Any]) -> list[dict[str, Any]]:
    svg_name = str(page.get("svg") or f"{page.get('id')}.svg")
    svg_path = template_dir / svg_name
    if not svg_path.exists():
        return [issue("SVG-MISSING", "blocking", svg_name, "Declared SVG file is missing.")]

    canvas_payload = page.get("canvas") if isinstance(page.get("canvas"), dict) else contract.get("canvas", {})
    canvas = Box(0, 0, float(canvas_payload.get("width", 1280)), float(canvas_payload.get("height", 720)))
    protected = [
        (str(region.get("id", "protected")), rect_from_mapping(region), str(region.get("fill", "")))
        for region in page.get("protected_regions", [])
        if isinstance(region, dict)
    ]
    containers = [
        (str(region.get("id", "container")), rect_from_mapping(region))
        for region in page.get("containers", [])
        if isinstance(region, dict)
    ]

    texts, images = parse_svg(svg_path)
    dark_labels = dark_label_regions(svg_path)
    issues: list[dict[str, Any]] = validate_compact_control_text_alignment(svg_path, svg_name)

    for text in texts:
        in_dark_label = any(point_inside(region, text.box.cx, text.box.cy) for region in dark_labels)
        center_in_protected = [
            (name, region, fill)
            for name, region, fill in protected
            if point_inside(region, text.box.cx, text.box.cy)
        ]
        protected_overlap = [
            (name, region, fill)
            for name, region, fill in protected
            if overlap(region, text.box) > OVERLAP_TOLERANCE
        ]
        allowed_protected_bleed = any(
            protected_side_label_bleed_allowed(text.box, canvas, region)
            for _name, region, _fill in center_in_protected
        )
        if not contains(canvas, text.box, tolerance=OVERLAP_TOLERANCE) and not allowed_protected_bleed:
            issues.append(
                issue(
                    "TEXT-OFF-CANVAS",
                    "blocking",
                    svg_name,
                    "Text estimate extends outside the slide canvas.",
                    element_index=text.element_index,
                    text=text.text,
                    box=box_payload(text.box),
                )
            )

        if protected_overlap and not center_in_protected:
            name, region, _fill = protected_overlap[0]
            issues.append(
                issue(
                    "TEXT-PROTECTED-OVERLAP",
                    "blocking",
                    svg_name,
                    f"Content text overlaps protected region {name}.",
                    element_index=text.element_index,
                    text=text.text,
                    text_box=box_payload(text.box),
                    protected_region=box_payload(region),
                )
            )
        elif center_in_protected:
            name, region, fill = center_in_protected[0]
            if not contains(region, text.box, tolerance=OVERLAP_TOLERANCE) and not allowed_protected_bleed:
                issues.append(
                    issue(
                        "TEXT-PROTECTED-ESCAPE",
                        "blocking",
                        svg_name,
                        f"Protected-region text escapes {name}.",
                        element_index=text.element_index,
                        text=text.text,
                        text_box=box_payload(text.box),
                        protected_region=box_payload(region),
                    )
                )
            bg_luma = luminance(fill)
            fg_luma = luminance(text.fill)
            if bg_luma is not None and fg_luma is not None and bg_luma < 0.35 and fg_luma < 0.35:
                issues.append(
                    issue(
                        "TEXT-PROTECTED-CONTRAST",
                        "blocking",
                        svg_name,
                        f"Dark text sits on dark protected region {name}.",
                        element_index=text.element_index,
                        text=text.text,
                        fill=text.fill,
                        region_fill=fill,
                    )
                )

        assigned = best_container_for_text(containers, text.box)
        if assigned is not None:
            name, container = assigned
            if not in_dark_label and not contains(
                inset(container, CONTAINER_PADDING), text.box, tolerance=CONTAINER_OVERFLOW_TOLERANCE
            ):
                issues.append(
                    issue(
                        "TEXT-CONTAINER-OVERFLOW",
                        "blocking",
                        svg_name,
                        f"Text exceeds declared container {name}.",
                        element_index=text.element_index,
                        text=text.text,
                        text_box=box_payload(text.box),
                        container=box_payload(container),
                    )
                )

        if text.text.strip().lower() in {"image?", "image", "picture?", "pic?"}:
            issues.append(
                issue(
                    "IMAGE-MISSING-PLACEHOLDER",
                    "blocking",
                    svg_name,
                    "SVG contains an image-missing placeholder label.",
                    element_index=text.element_index,
                    text=text.text,
                )
            )

    issues.extend(validate_svg_control_group_alignment(svg_name, texts, containers))

    for image in images:
        image_path = resolve_image_path(template_dir, image.href)
        if image_path is not None and not image_path.exists():
            issues.append(
                issue(
                    "IMAGE-MISSING-ASSET",
                    "blocking",
                    svg_name,
                    "Image href points to a missing asset.",
                    element_index=image.element_index,
                    href=image.href,
                    expected_path=str(image_path),
                )
            )

    return issues


def emu_to_px(value: str | int | None) -> float:
    return layout_metrics.emu_to_px(value)


def pptx_slide_order(pptx_path: Path) -> list[str]:
    with zipfile.ZipFile(pptx_path) as zf:
        pres = ET.fromstring(zf.read("ppt/presentation.xml"))
        rels = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
        relmap = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("rel:Relationship", PPTX_NS)
            if rel.attrib.get("Id") and rel.attrib.get("Target")
        }
        ordered: list[str] = []
        for slide_id in pres.findall(".//p:sldId", PPTX_NS):
            rid = slide_id.attrib.get(f"{{{PPTX_NS['r']}}}id")
            target = relmap.get(rid or "")
            if target:
                ordered.append("ppt/" + target.lstrip("../"))
        return ordered


def pptx_text_fill(sp: ET.Element) -> str:
    rpr = sp.find(".//a:rPr", PPTX_NS)
    if rpr is not None:
        color = rpr.find(".//a:solidFill/a:srgbClr", PPTX_NS)
        if color is not None and color.attrib.get("val"):
            return f"#{color.attrib['val']}"
    return "#000000"


def pptx_run_font_px(run: ET.Element, default: float = 18.0) -> float:
    rpr = run.find("a:rPr", PPTX_NS)
    if rpr is None:
        return default
    sz = rpr.attrib.get("sz")
    if not sz:
        return default
    try:
        return float(sz) / 75.0
    except ValueError:
        return default


def pptx_paragraph_metrics(paragraph: ET.Element) -> tuple[str, float, float]:
    text = ""
    width = 0.0
    max_font = 18.0
    for run in paragraph.findall("a:r", PPTX_NS):
        run_text = "".join(node.text or "" for node in run.findall("a:t", PPTX_NS))
        if not run_text:
            continue
        font_size = pptx_run_font_px(run, max_font)
        max_font = max(max_font, font_size)
        text += run_text
        width += sum(char_width(ch, font_size) for ch in run_text)
    return text, width, max_font


def pptx_visual_text_box(sp: ET.Element, shape_box: Box) -> Box:
    paragraphs = sp.findall(".//a:p", PPTX_NS)
    line_metrics = [pptx_paragraph_metrics(paragraph) for paragraph in paragraphs]
    line_metrics = [item for item in line_metrics if item[0]]
    if not line_metrics:
        return shape_box

    width = max((item[1] for item in line_metrics), default=shape_box.width)
    height = sum(max_font * LINE_HEIGHT for _text, _width, max_font in line_metrics)
    if width > shape_box.width:
        width = shape_box.width
    if height > shape_box.height:
        height = shape_box.height
    first_ppr = paragraphs[0].find("a:pPr", PPTX_NS) if paragraphs else None
    algn = first_ppr.attrib.get("algn", "l") if first_ppr is not None else "l"
    if algn == "ctr":
        x = shape_box.x + (shape_box.width - width) / 2
    elif algn == "r":
        x = shape_box.right - width
    else:
        x = shape_box.x
    body_pr = sp.find(".//a:bodyPr", PPTX_NS)
    anchor = str(body_pr.attrib.get("anchor") or "").lower() if body_pr is not None else ""
    if anchor in {"ctr", "middle", "center"}:
        y = shape_box.y + (shape_box.height - height) / 2
    elif anchor in {"b", "bottom"}:
        y = shape_box.bottom - height
    else:
        y = shape_box.y
    return Box(x=x, y=y, width=width, height=height)


def pptx_xfrm_box(xfrm: ET.Element | None) -> Box | None:
    off = xfrm.find("a:off", PPTX_NS) if xfrm is not None else None
    ext = xfrm.find("a:ext", PPTX_NS) if xfrm is not None else None
    if off is None or ext is None:
        return None
    return Box(
        x=emu_to_px(off.attrib.get("x")),
        y=emu_to_px(off.attrib.get("y")),
        width=emu_to_px(ext.attrib.get("cx")),
        height=emu_to_px(ext.attrib.get("cy")),
    )


def pptx_rotation_matrix(xfrm: ET.Element | None, box: Box) -> AffineMatrix:
    if xfrm is None:
        return IDENTITY_MATRIX
    raw = xfrm.attrib.get("rot")
    if not raw:
        return IDENTITY_MATRIX
    try:
        angle_deg = float(raw) / 60000.0
    except ValueError:
        return IDENTITY_MATRIX
    if not angle_deg:
        return IDENTITY_MATRIX
    return rotate_matrix(angle_deg, box.cx, box.cy)


def pptx_group_child_matrix(grp: ET.Element) -> AffineMatrix:
    xfrm = grp.find("p:grpSpPr/a:xfrm", PPTX_NS)
    outer = pptx_xfrm_box(xfrm)
    ch_off = xfrm.find("a:chOff", PPTX_NS) if xfrm is not None else None
    ch_ext = xfrm.find("a:chExt", PPTX_NS) if xfrm is not None else None
    if outer is None or ch_off is None or ch_ext is None:
        return IDENTITY_MATRIX
    child_x = emu_to_px(ch_off.attrib.get("x"))
    child_y = emu_to_px(ch_off.attrib.get("y"))
    child_w = emu_to_px(ch_ext.attrib.get("cx"))
    child_h = emu_to_px(ch_ext.attrib.get("cy"))
    sx = outer.width / child_w if child_w else 1.0
    sy = outer.height / child_h if child_h else 1.0
    scale_translate: AffineMatrix = (
        sx,
        0.0,
        0.0,
        sy,
        outer.x - child_x * sx,
        outer.y - child_y * sy,
    )
    return matrix_multiply(pptx_rotation_matrix(xfrm, outer), scale_translate)


def iter_pptx_texts(pptx_path: Path) -> list[PptxText]:
    texts: list[PptxText] = []
    order = pptx_slide_order(pptx_path)
    with zipfile.ZipFile(pptx_path) as zf:
        for slide_number, slide_name in enumerate(order, start=1):
            root = ET.fromstring(zf.read(slide_name))
            shape_index = 0

            def walk(parent: ET.Element, matrix: AffineMatrix) -> None:
                nonlocal shape_index
                for child in parent:
                    name = local_name(child.tag)
                    if name == "grpSp":
                        walk(child, matrix_multiply(matrix, pptx_group_child_matrix(child)))
                        continue
                    if name != "sp":
                        walk(child, matrix)
                        continue
                    shape_index += 1
                    sp = child
                    text = "".join(node.text or "" for node in sp.findall(".//a:t", PPTX_NS)).strip()
                    if not text:
                        continue
                    xfrm = sp.find("p:spPr/a:xfrm", PPTX_NS)
                    shape_box = pptx_xfrm_box(xfrm)
                    if shape_box is None:
                        continue
                    visual_box = pptx_visual_text_box(sp, shape_box)
                    visual_box = transform_box(visual_box, pptx_rotation_matrix(xfrm, shape_box))
                    visual_box = transform_box(visual_box, matrix)
                    texts.append(
                        PptxText(
                            slide_number=slide_number,
                            shape_index=shape_index,
                            text=text,
                            box=visual_box,
                            fill=pptx_text_fill(sp),
                        )
                    )

            walk(root, IDENTITY_MATRIX)
    return texts


def pptx_negative_extent_issues(pptx_path: Path, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    shape_tags = {"sp", "pic", "grpSp", "graphicFrame", "cxnSp"}
    order = pptx_slide_order(pptx_path)
    with zipfile.ZipFile(pptx_path) as zf:
        for slide_number, slide_name in enumerate(order, start=1):
            root = ET.fromstring(zf.read(slide_name))
            svg_name = (
                str(pages[slide_number - 1].get("svg") or f"{pages[slide_number - 1].get('id')}.svg")
                if slide_number - 1 < len(pages)
                else slide_name
            )
            shape_index = 0

            def walk(parent: ET.Element) -> None:
                nonlocal shape_index
                for child in parent:
                    name = local_name(child.tag)
                    if name in shape_tags:
                        shape_index += 1
                        xfrm = child.find(".//a:xfrm", PPTX_NS)
                        ext = xfrm.find("a:ext", PPTX_NS) if xfrm is not None else None
                        if ext is not None:
                            try:
                                cx = int(float(ext.attrib.get("cx", "0")))
                                cy = int(float(ext.attrib.get("cy", "0")))
                            except ValueError:
                                cx = cy = 0
                            if cx < 0 or cy < 0:
                                issues.append(
                                    issue(
                                        "PPTX-INVALID-NEGATIVE-EXTENT",
                                        "blocking",
                                        svg_name,
                                        "DrawingML shape has a negative a:ext cx/cy; PowerPoint may repair or corrupt the slide.",
                                        element_index=shape_index,
                                        slide_number=slide_number,
                                        slide_part=slide_name,
                                        cx_emu=cx,
                                        cy_emu=cy,
                                    )
                                )
                    walk(child)

            walk(root)
    return issues


def validate_pptx_against_contract(
    pptx_path: str | Path,
    template_dir: str | Path,
) -> dict[str, Any]:
    pptx_path = Path(pptx_path)
    template_dir = Path(template_dir)
    contract = load_contract(template_dir)
    pages = [page for page in contract.get("pages", []) if isinstance(page, dict)]
    by_slide = {text.slide_number: [] for text in iter_pptx_texts(pptx_path)}
    for text in iter_pptx_texts(pptx_path):
        by_slide.setdefault(text.slide_number, []).append(text)

    issues: list[dict[str, Any]] = pptx_negative_extent_issues(pptx_path, pages)
    canvas_payload = contract.get("canvas", {})
    default_canvas = Box(0, 0, float(canvas_payload.get("width", 1280)), float(canvas_payload.get("height", 720)))

    for slide_number, page in enumerate(pages, start=1):
        svg_name = str(page.get("svg") or f"{page.get('id')}.svg")
        canvas_payload = page.get("canvas") if isinstance(page.get("canvas"), dict) else {}
        canvas = Box(0, 0, float(canvas_payload.get("width", default_canvas.width)), float(canvas_payload.get("height", default_canvas.height)))
        protected = [
            (str(region.get("id", "protected")), rect_from_mapping(region), str(region.get("fill", "")))
            for region in page.get("protected_regions", [])
            if isinstance(region, dict)
        ]
        containers = [
            (str(region.get("id", "container")), rect_from_mapping(region))
            for region in page.get("containers", [])
            if isinstance(region, dict)
        ]
        dark_labels = dark_label_regions(template_dir / svg_name)
        for text in by_slide.get(slide_number, []):
            in_dark_label = any(point_inside(region, text.box.cx, text.box.cy) for region in dark_labels)
            center_in_protected = [
                (name, region, fill)
                for name, region, fill in protected
                if point_inside(region, text.box.cx, text.box.cy)
            ]
            protected_overlap = [
                (name, region, fill)
                for name, region, fill in protected
                if overlap(region, text.box) > OVERLAP_TOLERANCE
            ]
            allowed_protected_bleed = any(
                protected_side_label_bleed_allowed(text.box, canvas, region)
                for _name, region, _fill in center_in_protected
            )
            if not contains(canvas, text.box, tolerance=OVERLAP_TOLERANCE) and not allowed_protected_bleed:
                issues.append(
                    issue(
                        "PPTX-TEXT-OFF-CANVAS",
                        "blocking",
                        svg_name,
                        "Exported PPTX text extends outside the slide canvas.",
                        element_index=text.shape_index,
                        text=text.text,
                        box=box_payload(text.box),
                    )
                )
            if protected_overlap and not center_in_protected:
                name, region, _fill = protected_overlap[0]
                issues.append(
                    issue(
                        "PPTX-TEXT-PROTECTED-OVERLAP",
                        "blocking",
                        svg_name,
                        f"Exported PPTX text overlaps protected region {name}.",
                        element_index=text.shape_index,
                        text=text.text,
                        text_box=box_payload(text.box),
                        protected_region=box_payload(region),
                    )
                )
            elif center_in_protected:
                name, _region, fill = center_in_protected[0]
                bg_luma = luminance(fill)
                fg_luma = luminance(text.fill)
                if bg_luma is not None and fg_luma is not None and bg_luma < 0.35 and fg_luma < 0.35:
                    issues.append(
                        issue(
                            "PPTX-TEXT-PROTECTED-CONTRAST",
                            "blocking",
                            svg_name,
                            f"Dark exported PPTX text sits on dark protected region {name}.",
                            element_index=text.shape_index,
                            text=text.text,
                            fill=text.fill,
                            region_fill=fill,
                        )
                    )
            assigned = best_container_for_text(containers, text.box)
            if assigned is not None:
                name, container = assigned
                if not in_dark_label and not contains(
                    inset(container, CONTAINER_PADDING), text.box, tolerance=CONTAINER_OVERFLOW_TOLERANCE
                ):
                    issues.append(
                        issue(
                            "PPTX-TEXT-CONTAINER-OVERFLOW",
                            "blocking",
                            svg_name,
                            f"Exported PPTX text exceeds declared container {name}.",
                            element_index=text.shape_index,
                            text=text.text,
                            text_box=box_payload(text.box),
                            container=box_payload(container),
                        )
                    )
        issues.extend(validate_pptx_control_group_alignment(svg_name, by_slide.get(slide_number, []), containers))

    blocking_count = sum(1 for item in issues if item["severity"] == "blocking")
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_schema_version": contract.get("schema_version"),
        "template_dir": str(template_dir),
        "pptx_path": str(pptx_path),
        "status": "fail" if blocking_count else "pass",
        "page_count": len(pages),
        "text_box_count": sum(len(items) for items in by_slide.values()),
        "blocking_count": blocking_count,
        "warning_count": sum(1 for item in issues if item["severity"] == "warning"),
        "issues": issues,
    }


def box_payload(box: Box) -> dict[str, float]:
    return {
        "x": round(box.x, 2),
        "y": round(box.y, 2),
        "width": round(box.width, 2),
        "height": round(box.height, 2),
    }


def validate_template_geometry(template_dir: str | Path) -> dict[str, Any]:
    template_dir = Path(template_dir)
    contract = load_contract(template_dir)
    pages = contract.get("pages", [])
    if not isinstance(pages, list):
        raise ValueError("geometry_contract.json pages must be a list")
    issues: list[dict[str, Any]] = []
    for page in pages:
        if isinstance(page, dict):
            issues.extend(validate_page(template_dir, contract, page))
    blocking_count = sum(1 for item in issues if item["severity"] == "blocking")
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_schema_version": contract.get("schema_version"),
        "template_dir": str(template_dir),
        "status": "fail" if blocking_count else "pass",
        "page_count": len(pages),
        "blocking_count": blocking_count,
        "warning_count": sum(1 for item in issues if item["severity"] == "warning"),
        "issues": issues,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an EasySlides template geometry contract.")
    parser.add_argument("template_dir", help="Template directory containing geometry_contract.json.")
    parser.add_argument("--pptx", help="Optional exported PPTX to validate against the same contract.")
    parser.add_argument("--report", help="Optional JSON report output path.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = (
        validate_pptx_against_contract(args.pptx, args.template_dir)
        if args.pptx
        else validate_template_geometry(args.template_dir)
    )
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"{report['status'].upper()}: "
            f"{report['blocking_count']} blocking, {report['warning_count']} warnings"
        )
        for item in report["issues"][:80]:
            element = f"#{item.get('element_index')}" if item.get("element_index") is not None else ""
            print(f"{item['severity']}: {item['code']} {item['svg_file']}{element} {item['message']}")
        if len(report["issues"]) > 80:
            print(f"... {len(report['issues']) - 80} more issue(s)")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
