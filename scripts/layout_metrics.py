"""Shared layout measurement primitives for EasySlides.

This module is the single home for geometry helpers that are needed across
template distillation, SVG validation, PPTX validation, and SVG-to-PPTX export.
It intentionally stays small: deterministic canvas units, axis-aligned boxes,
SVG affine transforms, and conservative text/image box measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable, Iterator
from xml.etree import ElementTree as ET


EMU_PER_INCH = 914400
PX_PER_INCH = 96
PT_PER_INCH = 72
EMU_PER_PX = EMU_PER_INCH // PX_PER_INCH
FONT_PX_TO_HUNDREDTHS_PT = 75
DEFAULT_LINE_HEIGHT = 1.22

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

AffineMatrix = tuple[float, float, float, float, float, float]
IDENTITY_MATRIX: AffineMatrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TRANSFORM_RE = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")
_NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


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

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "Box":
        return cls(
            x=float(payload.get("x", 0)),
            y=float(payload.get("y", 0)),
            width=float(payload.get("width", payload.get("w", 0))),
            height=float(payload.get("height", payload.get("h", 0))),
        )


@dataclass(frozen=True)
class SvgImageBox:
    element_index: int
    href: str
    box: Box
    is_nested_svg_wrapper: bool = False


def px_to_emu(px: float) -> int:
    return round(px * EMU_PER_PX)


def emu_to_px(emu: str | int | float | None) -> float:
    try:
        return float(emu or 0) / EMU_PER_PX
    except (TypeError, ValueError):
        return 0.0


def px_to_pt(px: float) -> float:
    return px * PT_PER_INCH / PX_PER_INCH


def pt_to_px(pt: float) -> float:
    return pt * PX_PER_INCH / PT_PER_INCH


def emu_to_in(emu: str | int | float | None) -> float:
    try:
        return float(emu or 0) / EMU_PER_INCH
    except (TypeError, ValueError):
        return 0.0


def matrix_multiply(left: AffineMatrix, right: AffineMatrix) -> AffineMatrix:
    """Compose two SVG affine matrices as ``left(right(point))``."""
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


def translate_matrix(x: float, y: float = 0.0) -> AffineMatrix:
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


def parse_number_list(raw: str | None) -> list[float]:
    return [float(match.group(0)) for match in _NUMBER_RE.finditer(raw or "")]


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


def contains(outer: Box, inner: Box, tolerance: float = 0.0) -> bool:
    return (
        inner.x >= outer.x - tolerance
        and inner.y >= outer.y - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def point_inside(box: Box, x: float, y: float) -> bool:
    return box.x <= x <= box.right and box.y <= y <= box.bottom


def overlap_area(a: Box, b: Box) -> float:
    dx = min(a.right, b.right) - max(a.x, b.x)
    dy = min(a.bottom, b.bottom) - max(a.y, b.y)
    if dx <= 0 or dy <= 0:
        return 0.0
    return dx * dy


def inset(box: Box, padding: float) -> Box:
    return Box(
        x=box.x + padding,
        y=box.y + padding,
        width=max(0.0, box.width - padding * 2),
        height=max(0.0, box.height - padding * 2),
    )


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    match = _NUMBER_RE.search(str(value))
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


def is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def is_cjk_char(ch: str) -> bool:
    return (
        "\u4e00" <= ch <= "\u9fff"
        or "\u3400" <= ch <= "\u4dbf"
        or "\u3040" <= ch <= "\u30ff"
        or "\uac00" <= ch <= "\ud7af"
    )


def char_width_px(ch: str, font_size: float, font_weight: str = "400") -> float:
    bold = str(font_weight).lower() in {"600", "700", "800", "900", "bold", "bolder"}
    weight_factor = 1.06 if bold else 1.0
    if ch.isspace():
        return font_size * 0.32 * weight_factor
    if is_cjk_char(ch) or ord(ch) > 127:
        return font_size * 1.0 * weight_factor
    if ch in "MW@#%":
        return font_size * 0.85 * weight_factor
    if ch in "il.,:;!'|":
        return font_size * 0.28 * weight_factor
    if ch.isdigit():
        return font_size * 0.55 * weight_factor
    return font_size * 0.56 * weight_factor


def estimate_text_width_px(text: str, font_size: float, font_weight: str = "400") -> float:
    return sum(char_width_px(ch, font_size, font_weight) for ch in text)


def text_display_lines(elem: ET.Element, fallback_text: str | None = None) -> list[str]:
    tspans = [child for child in elem if local_name(child.tag) == "tspan"]
    fallback = fallback_text if fallback_text is not None else element_text(elem)
    if not tspans:
        return fallback.splitlines() or [fallback]

    lines: list[str] = []
    current: list[str] = []
    if elem.text and elem.text.strip():
        current.append(elem.text.strip())
    seen_text_run = bool(current)
    for child in tspans:
        starts_new_line = seen_text_run and (
            child.attrib.get("dy") is not None
            or child.attrib.get("x") is not None
            or child.attrib.get("y") is not None
        )
        if starts_new_line and current:
            lines.append(re.sub(r"\s+", " ", "".join(current)).strip())
            current = []
        if child.text:
            current.append(child.text)
            seen_text_run = True
        if child.tail and child.tail.strip():
            current.append(child.tail)
            seen_text_run = True
    if current:
        lines.append(re.sub(r"\s+", " ", "".join(current)).strip())
    return [line for line in lines if line] or [fallback]


def estimate_text_height_px(line_count: int, font_size: float, line_height: float = DEFAULT_LINE_HEIGHT) -> float:
    return max(1, line_count) * font_size * line_height


def measure_svg_text_box(
    elem: ET.Element,
    text: str | None = None,
    *,
    line_height: float = DEFAULT_LINE_HEIGHT,
) -> Box:
    style = parse_style(elem.attrib.get("style"))
    font_size = parse_float(elem.attrib.get("font-size"), parse_float(style.get("font-size"), 18.0))
    font_weight = elem.attrib.get("font-weight") or style.get("font-weight") or "400"

    has_explicit_box_x = elem.attrib.get("data-pptx-box-x") is not None
    x = parse_float(elem.attrib.get("data-pptx-box-x"), parse_float(elem.attrib.get("x")))
    y_anchor = parse_float(elem.attrib.get("data-pptx-box-y"), parse_float(elem.attrib.get("y")))
    width = parse_float(elem.attrib.get("data-pptx-box-w"), parse_float(elem.attrib.get("data-pptx-box-width")))
    height = parse_float(elem.attrib.get("data-pptx-box-h"), parse_float(elem.attrib.get("data-pptx-box-height")))

    content = text if text is not None else element_text(elem)
    display_lines = text_display_lines(elem, content)
    if width <= 0:
        width = max((estimate_text_width_px(line, font_size, font_weight) for line in display_lines), default=font_size)
    if height <= 0:
        height = estimate_text_height_px(len(display_lines), font_size, line_height)

    if not has_explicit_box_x:
        anchor = elem.attrib.get("text-anchor") or style.get("text-anchor") or "start"
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width

    y = y_anchor if elem.attrib.get("data-pptx-box-y") else y_anchor - font_size * 0.85
    return Box(x=x, y=y, width=width, height=height)


def numeric_pair_bounds(raw: str | None) -> Box | None:
    values = parse_number_list(raw)
    if len(values) < 4:
        return None
    xs = values[0::2]
    ys = values[1::2]
    return Box(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys))


def _href(elem: ET.Element) -> str:
    return elem.attrib.get("href") or elem.attrib.get(f"{{{XLINK_NS}}}href") or ""


def _child_images(elem: ET.Element) -> list[ET.Element]:
    return [child for child in elem if local_name(child.tag) == "image"]


def _element_matrix(elem: ET.Element, parent_matrix: AffineMatrix) -> AffineMatrix:
    style = parse_style(elem.attrib.get("style"))
    transform = elem.attrib.get("transform") or style.get("transform") or ""
    return matrix_multiply(parent_matrix, parse_transform_matrix(transform))


def iter_svg_image_boxes(root: ET.Element) -> Iterator[SvgImageBox]:
    index = 0

    def walk(elem: ET.Element, parent_matrix: AffineMatrix) -> Iterator[SvgImageBox]:
        nonlocal index
        index += 1
        name = local_name(elem.tag)
        matrix = _element_matrix(elem, parent_matrix)

        is_positioned_svg = elem.attrib.get("x") is not None or elem.attrib.get("y") is not None
        if (
            name == "svg"
            and is_positioned_svg
            and elem.attrib.get("width") is not None
            and elem.attrib.get("height") is not None
        ):
            images = _child_images(elem)
            if len(images) == 1 and _href(images[0]):
                box = Box(
                    x=parse_float(elem.attrib.get("x")),
                    y=parse_float(elem.attrib.get("y")),
                    width=parse_float(elem.attrib.get("width")),
                    height=parse_float(elem.attrib.get("height")),
                )
                if box.width > 0 and box.height > 0:
                    yield SvgImageBox(index, _href(images[0]), transform_box(box, matrix), True)
                    return

        if name == "image":
            box = Box(
                x=parse_float(elem.attrib.get("x")),
                y=parse_float(elem.attrib.get("y")),
                width=parse_float(elem.attrib.get("width")),
                height=parse_float(elem.attrib.get("height")),
            )
            if box.width > 0 and box.height > 0:
                yield SvgImageBox(index, _href(elem), transform_box(box, matrix), False)

        for child in elem:
            yield from walk(child, matrix)

    yield from walk(root, IDENTITY_MATRIX)


def iter_svg_text_boxes(root: ET.Element) -> Iterator[tuple[int, ET.Element, str, Box]]:
    index = 0

    def walk(elem: ET.Element, parent_matrix: AffineMatrix) -> Iterator[tuple[int, ET.Element, str, Box]]:
        nonlocal index
        index += 1
        matrix = _element_matrix(elem, parent_matrix)
        if local_name(elem.tag) == "text":
            text = element_text(elem)
            if text:
                yield index, elem, text, transform_box(measure_svg_text_box(elem, text), matrix)
        for child in elem:
            yield from walk(child, matrix)

    yield from walk(root, IDENTITY_MATRIX)


def boxes_from_mappings(payloads: Iterable[dict[str, Any]]) -> list[Box]:
    return [Box.from_mapping(payload) for payload in payloads]
