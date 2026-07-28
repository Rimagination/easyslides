#!/usr/bin/env python3
"""Create a cross-material adaptation smoke test for a distilled template.

The smoke test clones a template pack, replaces visible material text and image
slots with a different research topic, and leaves fixed SVG geometry intact.
It is intentionally conservative: the output is not a design generator, it is
an acceptance fixture that helps prove a distilled template can be reused
without drifting, overflowing, or leaving source-specific content behind.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover - depends on optional runtime
    raise SystemExit("Pillow is required for template_material_smoke_test.py") from exc

try:
    from pptx_template_distill import normalize_compact_control_text_alignment
except ImportError:  # pragma: no cover - when imported as scripts.*
    from scripts.pptx_template_distill import normalize_compact_control_text_alignment


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
SCHEMA_VERSION = "easyslides.template_material_smoke_report.v1"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


@dataclass(frozen=True)
class PageInfo:
    svg: str
    page_id: str
    role: str
    source_slide: int


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


MATERIAL_TEXT = {
    "cover": [
        "Urban Heat Risk and Low-Carbon Renewal",
        "Remote Sensing Adaptation Stress Test",
        "Remote Sensing Lab",
        "Dr. Lin Chen",
        "2026.06",
    ],
    "toc": [
        "Thermal Exposure Baseline",
        "Data Fusion and Model Route",
        "Priority Zones and Renewal Strategy",
        "Decision Support and Public Value",
    ],
    "toc_short": [
        "Thermal Baseline",
        "Data Route",
        "Renewal Zones",
        "Decision Value",
    ],
    "chapter": [
        "Urban Heat Risk Baseline",
        "Multisource Remote Sensing Evidence",
        "Renewal Strategy and Governance Route",
    ],
    "chapter_short": [
        "Urban Heat Risk",
        "Sensing Evidence",
        "Renewal Route",
    ],
    "ending": [
        "Thank You",
        "Q&A",
        "Remote Sensing Lab",
        "Dr. Lin Chen",
        "2026.06",
    ],
    "content_title": [
        "Urban Heat Island Risk Baseline",
        "Multisource Data and Indicator System",
        "Model Findings and Priority Zones",
        "Low-Carbon Renewal Strategy",
        "Scenario Evaluation and Decision Support",
    ],
    "body": [
        "High-temperature exposure, land-cover change, and population activity are fused to identify priority renewal zones.",
        "Thermal infrared imagery, street greenery, building density, and mobility intensity form a compact diagnostic matrix.",
        "The model separates persistent night heat retention from short-term surface temperature peaks and maps actionable causes.",
        "Cooling corridors, shade networks, blue-green spaces, and roof retrofits are matched to local risk profiles.",
        "The adapted deck keeps the source template language while replacing all scientific material with a new domain.",
    ],
    "body_short": [
        "Heat patterns guide local renewal.",
        "Sensors map exposure and shade.",
        "Priority zones receive targeted action.",
        "Green corridors reduce thermal stress.",
        "Evidence links risk to decisions.",
    ],
    "label": [
        "Baseline",
        "Sensor",
        "Model",
        "Risk",
        "Cooling",
        "Priority",
        "Value",
        "Route",
    ],
    "value": [
        "38.6",
        "15m",
        "92%",
        "4",
        "1km",
        "0.21",
        "8.7k",
    ],
}

SMOKE_ASSET_NAMES = [
    "smoke_heat_map.png",
    "smoke_satellite_grid.png",
    "smoke_dashboard.png",
    "smoke_model_panel.png",
    "smoke_strategy_map.png",
    "smoke_intervention_grid.png",
]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def node_text(node: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def font_size(node: ET.Element, default: float = 18.0) -> float:
    style = parse_style(node.attrib.get("style"))
    return parse_float(node.attrib.get("font-size"), parse_float(style.get("font-size"), default))


def has_explicit_text_box(node: ET.Element) -> bool:
    return node.attrib.get("data-pptx-box-w") is not None and node.attrib.get("data-pptx-box-h") is not None


def text_display_line_count(node: ET.Element) -> int:
    tspans = [child for child in node if local_name(child.tag) == "tspan"]
    if not tspans:
        return max(1, len((node.text or "").splitlines()))
    lines = 1
    seen = False
    for child in tspans:
        if seen and (child.attrib.get("dy") is not None or child.attrib.get("x") is not None):
            lines += 1
        seen = True
    return max(1, lines)


def text_box(node: ET.Element, canvas: tuple[float, float] | None = None) -> Box:
    fs = font_size(node)
    x = parse_float(node.attrib.get("data-pptx-box-x"), parse_float(node.attrib.get("x")))
    y = parse_float(node.attrib.get("data-pptx-box-y"), parse_float(node.attrib.get("y")) - fs * 0.85)
    width = parse_float(node.attrib.get("data-pptx-box-w"), parse_float(node.attrib.get("width")))
    height = parse_float(node.attrib.get("data-pptx-box-h"), parse_float(node.attrib.get("height")))
    if width <= 0:
        width = max(32.0, estimate_width(node_text(node), fs))
        if canvas is not None:
            width = min(width, max(48.0, canvas[0] - x - 28.0))
    if height <= 0:
        line_allowance = text_display_line_count(node)
        height = max(fs * 1.2, fs * 1.18 * line_allowance)
    anchor = node.attrib.get("text-anchor") or parse_style(node.attrib.get("style")).get("text-anchor")
    if node.attrib.get("data-pptx-box-x") is None:
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
    return Box(x=x, y=y, width=width, height=height)


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def transform_attr(node: ET.Element) -> str:
    style = parse_style(node.attrib.get("style"))
    return str(node.attrib.get("transform") or style.get("transform") or "")


def has_rotate_transform(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    current: ET.Element | None = node
    while current is not None:
        if "rotate(" in transform_attr(current):
            return True
        current = parents.get(current)
    return False


def has_directional_transform(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    current: ET.Element | None = node
    while current is not None:
        transform = transform_attr(current).replace(",", " ")
        if "rotate(" in transform:
            return True
        if re.search(r"scale\([^)]*-\d", transform):
            return True
        matrix_match = re.search(r"matrix\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)", transform)
        if matrix_match:
            a = parse_float(matrix_match.group(1), 1.0)
            b = parse_float(matrix_match.group(2), 0.0)
            c = parse_float(matrix_match.group(3), 0.0)
            d = parse_float(matrix_match.group(4), 1.0)
            if a < 0 or d < 0 or abs(b) > 1e-6 or abs(c) > 1e-6:
                return True
        current = parents.get(current)
    return False


def is_fixed_chrome_text(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    text = node_text(node)
    if not text:
        return True
    if has_rotate_transform(node, parents):
        return True
    compact = re.sub(r"\s+", "", text).upper()
    if compact in {"CONTENTS", "CONTENT", "目录", "目錄"}:
        return True
    if re.fullmatch(r"\d{1,2}[-.]?", compact):
        return True
    return False


def box_from_mapping(payload: dict[str, Any]) -> Box:
    return Box(
        x=float(payload.get("x", 0)),
        y=float(payload.get("y", 0)),
        width=float(payload.get("width", payload.get("w", 0))),
        height=float(payload.get("height", payload.get("h", 0))),
    )


def point_inside(box: Box, x: float, y: float) -> bool:
    return box.x <= x <= box.x + box.width and box.y <= y <= box.y + box.height


def overlap_area(a: Box, b: Box) -> float:
    dx = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
    dy = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    if dx <= 0 or dy <= 0:
        return 0.0
    return dx * dy


def horizontal_overlap_ratio(a: Box, b: Box) -> float:
    dx = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
    if dx <= 0:
        return 0.0
    return dx / max(min(a.width, b.width), 1.0)


def best_container(containers: list[tuple[str, Box]], box: Box) -> tuple[str, Box] | None:
    candidates: list[tuple[float, str, Box]] = []
    for name, container in containers:
        area = overlap_area(container, box)
        if area <= 1.0:
            continue
        cx = box.x + box.width / 2
        cy = box.y + box.height / 2
        if not point_inside(container, cx, cy) and area / max(box.area, 1.0) < 0.5:
            continue
        candidates.append((container.area, name, container))
    if not candidates:
        return None
    _area, name, container = min(candidates, key=lambda item: item[0])
    return name, container


def union_boxes(boxes: list[Box]) -> Box:
    left = min(box.x for box in boxes)
    top = min(box.y for box in boxes)
    right = max(box.x + box.width for box in boxes)
    bottom = max(box.y + box.height for box in boxes)
    return Box(x=left, y=top, width=right - left, height=bottom - top)


def short_control_text(text: str) -> bool:
    stripped = re.sub(r"\s+", "", text)
    return bool(stripped) and len(stripped) <= 16


def template_placeholder_text(text: str) -> bool:
    stripped = re.sub(r"\s+", "", text)
    if not stripped:
        return False
    if "请添加" in stripped:
        return True
    return "添加" in stripped and any(
        token in stripped for token in ("标题", "描述", "正文", "章节", "图片名称")
    )


def strong_overlap_ratio(a: Box, b: Box) -> float:
    return overlap_area(a, b) / max(min(a.area, b.area), 1.0)


def control_candidate(node: ET.Element, node_box: Box, container: Box) -> bool:
    if not short_control_text(node_text(node)):
        return False
    if container.height > 96.0:
        return False
    if node_box.height > container.height * 1.05 or node_box.height < container.height * 0.15:
        return False
    return horizontal_overlap_ratio(node_box, container) >= 0.45


def shift_text_node_y(node: ET.Element, delta: float) -> None:
    if node.attrib.get("y") is not None:
        node.set("y", f"{parse_float(node.attrib.get('y')) + delta:.2f}".rstrip("0").rstrip("."))
    if node.attrib.get("data-pptx-box-y") is not None:
        node.set(
            "data-pptx-box-y",
            f"{parse_float(node.attrib.get('data-pptx-box-y')) + delta:.2f}".rstrip("0").rstrip("."),
        )


def text_display_lines(node: ET.Element) -> int:
    text = node_text(node)
    if not text:
        return 1
    return max(1, len(text.splitlines()))


def center_lock_text_node_to_container(node: ET.Element, container: Box) -> None:
    """Make a compact control text box share the container's vertical center."""
    fs = font_size(node)
    line_count = text_display_lines(node)
    line_step = fs * 1.18
    total_height = fs if line_count <= 1 else fs + (line_count - 1) * line_step
    baseline_y = container.y + (container.height - total_height) / 2 + fs * 0.85
    node.set("data-pptx-valign", "middle")
    node.set("data-pptx-box-y", f"{container.y:.2f}".rstrip("0").rstrip("."))
    node.set("data-pptx-box-h", f"{container.height:.2f}".rstrip("0").rstrip("."))
    if node.attrib.get("y") is not None:
        node.set("y", f"{baseline_y:.2f}".rstrip("0").rstrip("."))


def recenter_control_text_groups(template_dir: Path) -> None:
    geometry_path = template_dir / "geometry_contract.json"
    if not geometry_path.exists():
        return
    geometry = read_json(geometry_path)
    pages = [page for page in geometry.get("pages", []) if isinstance(page, dict)]
    for page in pages:
        svg_name = str(page.get("svg") or f"{page.get('id')}.svg")
        path = template_dir / svg_name
        if not path.exists():
            continue
        root = ET.parse(path).getroot()
        canvas = svg_canvas(root)
        containers = [
            (str(region.get("id", "container")), box_from_mapping(region))
            for region in page.get("containers", [])
            if isinstance(region, dict)
        ]
        groups: dict[str, tuple[Box, list[tuple[ET.Element, Box]]]] = {}
        for node in root.iter():
            if local_name(node.tag) != "text" or not node_text(node):
                continue
            box = text_box(node, canvas=canvas)
            assigned = best_container(containers, box)
            if assigned is None:
                continue
            name, container = assigned
            if not control_candidate(node, box, container):
                continue
            groups.setdefault(name, (container, []))[1].append((node, box))

        changed = False
        for _name, (container, members) in groups.items():
            if not members:
                continue
            has_metadata = any(
                str(node.attrib.get("data-pptx-textbox") or "").lower() == "true"
                for node, _box in members
            )
            if len(members) == 1 and not has_metadata:
                continue
            if len(members) == 1 and has_metadata:
                node, box = members[0]
                before = (
                    node.attrib.get("data-pptx-valign"),
                    node.attrib.get("data-pptx-box-y"),
                    node.attrib.get("data-pptx-box-h"),
                    node.attrib.get("y"),
                )
                center_lock_text_node_to_container(node, container)
                after = (
                    node.attrib.get("data-pptx-valign"),
                    node.attrib.get("data-pptx-box-y"),
                    node.attrib.get("data-pptx-box-h"),
                    node.attrib.get("y"),
                )
                if before != after or abs(box.cy - container.cy) > 0.01:
                    changed = True
                continue
            group_box = union_boxes([box for _node, box in members])
            if group_box.height > container.height * 1.15:
                continue
            delta = container.cy - group_box.cy
            group_changed = False
            for node, _box in members:
                if str(node.attrib.get("data-pptx-textbox") or "").lower() == "true":
                    if node.attrib.get("data-pptx-valign") != "middle":
                        node.set("data-pptx-valign", "middle")
                        group_changed = True
                if abs(delta) > 0.01:
                    shift_text_node_y(node, delta)
                    group_changed = True
            if not group_changed:
                continue
            changed = True

        if changed:
            path.write_text(ET.tostring(root, encoding="unicode", short_empty_elements=True), encoding="utf-8")


def image_box(node: ET.Element) -> Box:
    return Box(
        x=parse_float(node.attrib.get("x")),
        y=parse_float(node.attrib.get("y")),
        width=parse_float(node.attrib.get("width")),
        height=parse_float(node.attrib.get("height")),
    )


def svg_canvas(root: ET.Element) -> tuple[float, float]:
    width = parse_float(root.attrib.get("width"), 1280)
    height = parse_float(root.attrib.get("height"), 720)
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [parse_float(part) for part in view_box.replace(",", " ").split()]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            width, height = parts[2], parts[3]
    return width, height


def normalized_role(value: str | None, svg_name: str) -> str:
    raw = (value or "").strip().lower()
    name = svg_name.lower()
    if "cover" in raw or "cover" in name:
        return "cover"
    if "ending" in raw or "closing" in raw or "ending" in name:
        return "ending"
    if "toc" in raw or "agenda" in raw or "content" == raw and "02_" in name:
        return "toc" if "toc" in name else raw or "content"
    if "chapter" in raw or "section" in raw:
        return "chapter"
    return raw or "content"


def load_pages(template_dir: Path) -> list[PageInfo]:
    layouts_path = template_dir / "layouts.json"
    pages: list[PageInfo] = []
    if layouts_path.exists():
        payload = read_json(layouts_path)
        for index, item in enumerate(payload.get("pages", []), start=1):
            if not isinstance(item, dict):
                continue
            svg = str(item.get("svg") or item.get("svg_path") or "")
            svg = Path(svg).name
            if not svg:
                continue
            page_id = str(item.get("id") or Path(svg).stem)
            role = normalized_role(str(item.get("story_role") or item.get("page_type") or ""), svg)
            source_slide = int(item.get("source_slide") or index)
            pages.append(PageInfo(svg=svg, page_id=page_id, role=role, source_slide=source_slide))
    if not pages:
        for index, path in enumerate(sorted(template_dir.glob("*.svg")), start=1):
            pages.append(
                PageInfo(
                    svg=path.name,
                    page_id=path.stem,
                    role=normalized_role("", path.name),
                    source_slide=index,
                )
            )
    return [page for page in pages if (template_dir / page.svg).exists()]


def choose_pages(
    pages: list[PageInfo],
    selected: list[str] | None,
    max_pages: int,
) -> list[PageInfo]:
    if selected:
        wanted = {Path(item).name for item in selected} | {Path(item).stem for item in selected}
        chosen = [page for page in pages if page.svg in wanted or page.page_id in wanted]
        if not chosen:
            raise ValueError("No selected pages matched template SVG files")
        return chosen
    if max_pages <= 0 or len(pages) <= max_pages:
        return pages

    chosen: list[PageInfo] = []

    def add_first(role: str) -> None:
        for page in pages:
            if page.role == role and page not in chosen:
                chosen.append(page)
                return

    add_first("cover")
    add_first("toc")
    add_first("chapter")
    for page in pages:
        if len(chosen) >= max_pages - 1:
            break
        if page.role not in {"cover", "ending"} and page not in chosen:
            chosen.append(page)
    add_first("ending")
    for page in pages:
        if len(chosen) >= max_pages:
            break
        if page not in chosen:
            chosen.append(page)
    return sorted(chosen[:max_pages], key=lambda page: pages.index(page))


def safe_prepare_target(source_dir: Path, out_dir: Path, force: bool) -> None:
    source_resolved = source_dir.resolve()
    out_resolved = out_dir.resolve()
    if out_resolved == source_resolved:
        raise ValueError("Output directory must differ from the source template directory")
    if out_resolved.exists():
        if not force:
            raise FileExistsError(f"Output directory already exists: {out_resolved}")
        tmp_resolved = TMP_ROOT.resolve()
        try:
            out_resolved.relative_to(tmp_resolved)
        except ValueError as exc:
            raise ValueError("--force only removes directories under the repository tmp/ folder") from exc
        shutil.rmtree(out_resolved)
    out_resolved.mkdir(parents=True, exist_ok=True)


def page_keep_filter(item: Any, selected_ids: set[str], selected_svgs: set[str]) -> bool:
    if not isinstance(item, dict):
        return False
    values = [
        item.get("id"),
        item.get("page_id"),
        item.get("svg"),
        item.get("svg_path"),
        item.get("source_svg"),
    ]
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text in selected_ids or Path(text).stem in selected_ids or Path(text).name in selected_svgs:
            return True
    return False


def filter_sidecar(payload: dict[str, Any], selected_ids: set[str], selected_svgs: set[str]) -> dict[str, Any]:
    filtered = json.loads(json.dumps(payload, ensure_ascii=False))
    for key in ("pages", "layouts", "contracts"):
        value = filtered.get(key)
        if isinstance(value, list):
            filtered[key] = [item for item in value if page_keep_filter(item, selected_ids, selected_svgs)]
    return filtered


def copy_template_subset(source_dir: Path, out_dir: Path, pages: list[PageInfo]) -> None:
    assets_in = source_dir / "assets"
    assets_out = out_dir / "assets"
    if assets_in.exists():
        shutil.copytree(assets_in, assets_out, dirs_exist_ok=True)
    else:
        assets_out.mkdir(parents=True, exist_ok=True)

    for page in pages:
        shutil.copy2(source_dir / page.svg, out_dir / page.svg)

    selected_ids = {page.page_id for page in pages} | {Path(page.svg).stem for page in pages}
    selected_svgs = {page.svg for page in pages}
    sidecar_names = [
        "geometry_contract.json",
        "layouts.json",
        "page_catalog.json",
        "story_structure.json",
        "slot_contracts.json",
        "layout_roster.json",
        "links.json",
        "template.json",
        "rules.md",
        "design_spec.md",
    ]
    for name in sidecar_names:
        source = source_dir / name
        if not source.exists() or source.is_dir():
            continue
        target = out_dir / name
        if source.suffix.lower() != ".json":
            shutil.copy2(source, target)
            continue
        try:
            payload = filter_sidecar(read_json(source), selected_ids, selected_svgs)
        except Exception:
            shutil.copy2(source, target)
        else:
            write_json(target, payload)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for item in candidates:
        path = Path(item)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int = 24) -> None:
    draw.text(xy, text, font=load_font(size, bold=True), fill=(54, 36, 86))


def save_heat_map(path: Path, size: tuple[int, int] = (760, 500)) -> None:
    w, h = size
    image = Image.new("RGB", size, "#F8FAFC")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(45):
        x = int((i % 9) * w / 9 + 14)
        y = int((i // 9) * h / 5 + 18)
        hot = (math.sin(i * 0.9) + 1) / 2
        fill = (210 + int(35 * hot), 70 + int(100 * (1 - hot)), 54, 220)
        draw.rounded_rectangle([x, y, x + 58, y + 64], radius=7, fill=fill, outline=(255, 255, 255, 180), width=2)
    for x in range(0, w, 86):
        draw.line([x, 0, x + 35, h], fill=(45, 65, 85, 35), width=2)
    label(draw, (24, 22), "Urban Heat Risk Map", 28)
    image.save(path)


def save_satellite_grid(path: Path, size: tuple[int, int] = (680, 420)) -> None:
    image = Image.new("RGB", size, "#E9EEF3")
    draw = ImageDraw.Draw(image, "RGBA")
    colors = ["#7CA982", "#577D73", "#D5B46A", "#A8AFB7", "#6EA8C7"]
    for y in range(0, size[1], 52):
        for x in range(0, size[0], 68):
            draw.rectangle([x, y, x + 66, y + 50], fill=colors[((x // 68) + (y // 52)) % len(colors)])
    for i in range(8):
        draw.line([0, i * 48, size[0], i * 48 + 70], fill=(255, 255, 255, 95), width=5)
    label(draw, (24, 22), "Land Cover and Green Fraction", 24)
    image.save(path)


def save_dashboard(path: Path, size: tuple[int, int] = (700, 460)) -> None:
    image = Image.new("RGB", size, "#FFFFFF")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle([22, 22, size[0] - 22, size[1] - 22], radius=14, fill=(248, 249, 252), outline=(117, 20, 151, 130), width=3)
    label(draw, (44, 42), "Thermal Exposure Dashboard", 26)
    for i, name in enumerate(["LST", "NDVI", "Sky", "Pop"]):
        x = 52 + i * 150
        draw.rounded_rectangle([x, 100, x + 116, 178], radius=9, fill=(255, 255, 255), outline=(117, 20, 151, 90), width=2)
        draw.text((x + 18, 116), name, font=load_font(19, True), fill=(58, 60, 67))
        draw.text((x + 18, 144), ["38.6", "0.21", "42%", "8.7k"][i], font=load_font(23, True), fill=(198, 74, 62))
    points = [(70 + i * 56, 350 - int(62 * math.sin(i / 1.4) + i * 3)) for i in range(10)]
    draw.line(points, fill=(198, 74, 62), width=5)
    for x, y in points:
        draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(198, 74, 62))
    draw.text((44, 382), "risk index trend", font=load_font(18), fill=(72, 76, 84))
    image.save(path)


def save_panel(path: Path, title: str, size: tuple[int, int] = (680, 420)) -> None:
    image = Image.new("RGB", size, "#F7F9FB")
    draw = ImageDraw.Draw(image, "RGBA")
    label(draw, (28, 26), title, 26)
    colors = [(235, 92, 75), (103, 167, 94), (88, 145, 202), (214, 174, 62)]
    for i in range(4):
        x = 58 + i * 145
        y = 134 + int(24 * math.sin(i))
        draw.rounded_rectangle([x, y, x + 102, y + 102], radius=12, fill=(255, 255, 255), outline=(117, 20, 151, 110), width=3)
        draw.ellipse([x + 26, y + 24, x + 76, y + 74], fill=colors[i])
    for i in range(3):
        x1 = 160 + i * 145
        draw.line([x1, 185, x1 + 42, 185], fill=(198, 74, 62), width=4)
        draw.polygon([(x1 + 42, 185), (x1 + 30, 177), (x1 + 30, 193)], fill=(198, 74, 62))
    image.save(path)


def make_smoke_assets(assets_dir: Path) -> list[str]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    save_heat_map(assets_dir / "smoke_heat_map.png")
    save_satellite_grid(assets_dir / "smoke_satellite_grid.png")
    save_dashboard(assets_dir / "smoke_dashboard.png")
    save_panel(assets_dir / "smoke_model_panel.png", "UHI Model Route")
    save_heat_map(assets_dir / "smoke_strategy_map.png", size=(780, 520))
    save_panel(assets_dir / "smoke_intervention_grid.png", "Intervention Matrix")
    return [f"assets/{name}" for name in SMOKE_ASSET_NAMES]


def estimate_width(text: str, fs: float) -> float:
    width = 0.0
    for ch in text:
        if ch.isspace():
            width += fs * 0.32
        elif ord(ch) > 127:
            width += fs * 0.95
        elif ch in "MW@#%":
            width += fs * 0.82
        elif ch in "il.,:;!'|":
            width += fs * 0.28
        else:
            width += fs * 0.55
    return width


def wrap_words(text: str, fs: float, width: float, max_lines: int) -> list[str]:
    if width <= 0 or max_lines <= 1:
        return [trim_to_width(text, fs, width) if width > 0 else text]
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if current and estimate_width(trial, fs) > width:
            lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
        else:
            current = trial
    used_words = " ".join(lines + ([current] if current else [])).split()
    remaining = words[len(used_words):]
    if remaining:
        tail = " ".join([current] + remaining) if current else " ".join(remaining)
        current = trim_to_width(tail, fs, width)
    if current:
        lines.append(current)
    return lines[:max_lines] or [trim_to_width(text, fs, width)]


def trim_to_width(text: str, fs: float, width: float) -> str:
    if width <= 0 or estimate_width(text, fs) <= width:
        return text
    suffix = "..."
    limit = max(1, len(text))
    while limit > 1 and estimate_width(text[:limit].rstrip() + suffix, fs) > width:
        limit -= 1
    return text[:limit].rstrip() + suffix


def fit_text_to_box(text: str, box: Box, fs: float) -> tuple[float, list[str]]:
    if box.width <= 0:
        return fs, [text]
    min_fs = 18.0 if fs >= 30 else max(9.0, fs * 0.72)
    current = fs

    def max_lines_for(size: float) -> int:
        if box.height <= 0:
            return 1
        usable_height = max(0.0, box.height * 0.96)
        return max(1, int(usable_height // (size * 1.18)))

    while current >= min_fs:
        max_lines = max_lines_for(current)
        # Keep a deliberate width buffer: the smoke fitter uses a lightweight
        # metric while the production SVG validator uses font-aware metrics.
        # Without this margin, borderline English labels can pass here yet
        # overflow in the stricter gate.
        lines = wrap_words(text, current, box.width * 0.88, max_lines)
        ellipsized = any(line.rstrip().endswith("...") for line in lines)
        if (
            len(lines) <= max_lines
            and all(estimate_width(line, current) <= box.width * 0.88 for line in lines)
            and not ellipsized
        ):
            return round(current, 2), lines
        current -= 1.0
    max_lines = max_lines_for(min_fs)
    lines = wrap_words(text, min_fs, box.width * 0.86, max_lines)
    return round(min_fs, 2), lines


def clear_text_children(node: ET.Element) -> None:
    node.text = None
    for child in list(node):
        node.remove(child)


def clear_text_node(node: ET.Element) -> None:
    node.text = None
    for child in list(node):
        node.remove(child)


def drop_overlapping_smoke_labels(root: ET.Element, canvas: tuple[float, float]) -> int:
    removed = 0
    while True:
        texts = [
            (node, node_text(node), text_box(node, canvas=canvas))
            for node in root.iter()
            if local_name(node.tag) == "text" and node_text(node)
        ]
        loser: ET.Element | None = None
        for idx, (left_node, left_text, left_box) in enumerate(texts):
            for right_node, right_text, right_box in texts[idx + 1 :]:
                if overlap_area(left_box, right_box) < 18.0:
                    continue
                if strong_overlap_ratio(left_box, right_box) <= 0.55:
                    continue
                left_len = len(left_text.replace("...", ""))
                right_len = len(right_text.replace("...", ""))
                if left_len == right_len:
                    loser = right_node if right_box.area <= left_box.area else left_node
                else:
                    loser = left_node if left_len < right_len else right_node
                break
            if loser is not None:
                break
        if loser is None:
            return removed
        clear_text_node(loser)
        removed += 1


def text_fill(node: ET.Element) -> str:
    style = parse_style(node.attrib.get("style"))
    return node.attrib.get("fill") or style.get("fill") or "#000000"


def set_node_text(node: ET.Element, replacement: str, canvas: tuple[float, float]) -> None:
    box = text_box(node, canvas=canvas)
    fs, lines = fit_text_to_box(replacement, box, font_size(node))
    node.set("font-size", f"{fs:g}")
    node.set(f"{{{XML_NS}}}space", "preserve")
    if has_explicit_text_box(node):
        valign = str(node.attrib.get("data-pptx-valign") or "").strip().lower()
        line_step = fs * 1.18
        total_height = fs if len(lines) <= 1 else fs + (len(lines) - 1) * line_step
        if valign in {"middle", "center", "ctr"}:
            baseline_y = box.y + (box.height - total_height) / 2 + fs * 0.85
        elif valign in {"bottom", "b"}:
            baseline_y = box.y + box.height - total_height + fs * 0.85
        else:
            baseline_y = box.y + fs * 0.85
        node.set("y", f"{baseline_y:.2f}".rstrip("0").rstrip("."))
    clear_text_children(node)
    x = node.attrib.get("x") or node.attrib.get("data-pptx-box-x") or "0"
    fill = text_fill(node)
    for idx, line in enumerate(lines):
        tspan = ET.SubElement(node, f"{{{SVG_NS}}}tspan")
        tspan.text = line
        tspan.set("x", x)
        if idx > 0:
            tspan.set("dy", f"{fs * 1.18:g}")
        tspan.set("font-size", f"{fs:g}")
        tspan.set("fill", fill)
        tspan.tail = "\n"


class TextPicker:
    def __init__(self) -> None:
        self.indices = {key: 0 for key in MATERIAL_TEXT}

    def next(self, key: str) -> str:
        values = MATERIAL_TEXT[key]
        index = self.indices[key]
        self.indices[key] = index + 1
        return values[index % len(values)]


def replacement_for_text(node: ET.Element, role: str, ordinal: int, picker: TextPicker, canvas: tuple[float, float]) -> str:
    box = text_box(node, canvas=canvas)
    fs = font_size(node)
    text = node_text(node)
    if re.fullmatch(r"\d{1,2}", text):
        return f"{max(1, ordinal):02d}"
    # Cross-material smoke content must fit the source slot without relying on
    # ellipsis. Compact source boxes get compact semantic material, while
    # larger body slots still exercise the full-length replacement path.
    if role not in {"cover", "toc", "chapter", "ending"}:
        if box.width <= 150 or (box.height <= 54 and box.width <= 500):
            return picker.next("value" if re.search(r"\d|%|km|ms|ps|fj", text.lower()) else "label")
        if box.width <= 300 or box.height <= 100:
            return picker.next("body_short")
    if box.width <= 220 or (box.height <= 54 and box.width <= 380) or fs <= 18:
        return picker.next("value" if re.search(r"\d|%|km|ms|ps|fj", text.lower()) else "label")
    if role == "cover":
        return picker.next("cover")
    if role == "toc":
        if box.width <= 320 or box.height <= 56:
            return picker.next("toc_short")
        return picker.next("toc")
    if role == "chapter":
        if box.width <= 240 and fs >= 24:
            return picker.next("chapter_short")
        return picker.next("chapter")
    if role == "ending":
        return picker.next("ending")
    if not has_explicit_text_box(node):
        if box.y < 90 and box.width > 280:
            return picker.next("content_title")
        return picker.next("label")
    if fs >= 30 or box.y < 130:
        return picker.next("content_title")
    return picker.next("body")


def should_replace_image(node: ET.Element, canvas: tuple[float, float], parents: dict[ET.Element, ET.Element]) -> bool:
    href = node.attrib.get("href") or node.attrib.get(f"{{{XLINK_NS}}}href") or ""
    if not href or href.startswith("data:"):
        return False
    if has_directional_transform(node, parents):
        return False
    box = image_box(node)
    if box.width <= 20 or box.height <= 20:
        return False
    slide_area = max(1.0, canvas[0] * canvas[1])
    if box.area / slide_area > 0.62 and box.x <= 10 and box.y <= 10:
        return False
    return True


def adapt_svg(path: Path, role: str, asset_refs: list[str], picker: TextPicker) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    parents = parent_map(root)
    canvas = svg_canvas(root)
    text_replacements: list[dict[str, str]] = []
    ellipsized_texts: list[dict[str, Any]] = []
    image_replacements: list[dict[str, str]] = []
    fixed_text_count = 0
    text_nodes = []
    for node in root.iter():
        if local_name(node.tag) != "text" or not node_text(node):
            continue
        if is_fixed_chrome_text(node, parents):
            fixed_text_count += 1
            continue
        text_nodes.append(node)
    text_nodes.sort(key=lambda node: (round(text_box(node).y, 2), round(text_box(node).x, 2)))
    accepted_boxes: list[Box] = []
    for ordinal, node in enumerate(text_nodes, start=1):
        original = node_text(node)
        box = text_box(node, canvas=canvas)
        if template_placeholder_text(original) and any(
            strong_overlap_ratio(box, accepted) > 0.65 for accepted in accepted_boxes
        ):
            clear_text_node(node)
            text_replacements.append({"from": original, "to": ""})
            continue
        replacement = replacement_for_text(node, role, ordinal, picker, canvas)
        if replacement == original:
            continue
        set_node_text(node, replacement, canvas)
        fitted_text = node_text(node)
        if "..." in fitted_text:
            ellipsized_texts.append(
                {
                    "original": original[:80],
                    "replacement": replacement[:80],
                    "fitted": fitted_text[:80],
                    "box": {
                        "x": round(box.x, 2),
                        "y": round(box.y, 2),
                        "width": round(box.width, 2),
                        "height": round(box.height, 2),
                    },
                }
            )
        text_replacements.append({"from": original, "to": replacement})
        accepted_boxes.append(text_box(node, canvas=canvas))

    asset_index = 0
    for node in root.iter():
        if local_name(node.tag) != "image" or not should_replace_image(node, canvas, parents):
            continue
        attr = "href" if node.attrib.get("href") is not None else f"{{{XLINK_NS}}}href"
        original = node.attrib.get(attr, "")
        replacement = asset_refs[asset_index % len(asset_refs)]
        asset_index += 1
        node.set(attr, replacement)
        node.set("data-smoke-original-href", original)
        image_replacements.append({"from": original, "to": replacement})

    overlap_labels_removed = drop_overlapping_smoke_labels(root, canvas)
    text = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    text = normalize_compact_control_text_alignment(text)
    path.write_text(text, encoding="utf-8")
    return {
        "svg": path.name,
        "role": role,
        "text_replaced": len(text_replacements),
        "image_replaced": len(image_replacements),
        "fixed_text_skipped": fixed_text_count,
        "replaceable_text_count": len(text_nodes),
        "overlap_labels_removed": overlap_labels_removed,
        "ellipsized_text_count": len(ellipsized_texts),
        "ellipsized_text_samples": ellipsized_texts[:8],
        "ellipsized_heading_count": len(ellipsized_texts),
        "ellipsized_heading_samples": ellipsized_texts[:8],
        "text_samples": text_replacements[:12],
        "image_samples": image_replacements[:12],
    }


def replaceable_text_count(path: Path) -> int:
    root = ET.parse(path).getroot()
    parents = parent_map(root)
    return len(
        [
            node
            for node in root.iter()
            if local_name(node.tag) == "text" and node_text(node) and not is_fixed_chrome_text(node, parents)
        ]
    )


def find_forbidden_terms(template_dir: Path, terms: list[str]) -> list[dict[str, str]]:
    if not terms:
        return []
    matches: list[dict[str, str]] = []
    lowered = [(term, term.lower()) for term in terms if term]
    for path in sorted(template_dir.glob("*.svg")):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        lower = text.lower()
        for original, term in lowered:
            if term in lower:
                matches.append({"svg": path.name, "term": original})
    return matches


def run_material_smoke_test(
    template_dir: str | Path,
    out_dir: str | Path | None = None,
    *,
    selected_pages: list[str] | None = None,
    max_pages: int = 8,
    forbidden_keywords: list[str] | None = None,
    min_text_replacement_ratio: float = 0.45,
    force: bool = False,
) -> dict[str, Any]:
    source_dir = Path(template_dir).expanduser().resolve()
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    target_dir = (
        Path(out_dir).expanduser().resolve()
        if out_dir
        else (TMP_ROOT / f"{source_dir.name}_material_smoke").resolve()
    )
    all_pages = load_pages(source_dir)
    pages = choose_pages(all_pages, selected_pages, max_pages)
    safe_prepare_target(source_dir, target_dir, force=force)
    copy_template_subset(source_dir, target_dir, pages)
    asset_refs = make_smoke_assets(target_dir / "assets")

    picker = TextPicker()
    page_reports = []
    for page in pages:
        page_reports.append(adapt_svg(target_dir / page.svg, page.role, asset_refs, picker))
    recenter_control_text_groups(target_dir)

    text_replaced = sum(item["text_replaced"] for item in page_reports)
    image_replaced = sum(item["image_replaced"] for item in page_reports)
    ellipsized_text = sum(int(item.get("ellipsized_text_count") or 0) for item in page_reports)
    total_text = sum(int(item.get("replaceable_text_count") or 0) for item in page_reports)
    replacement_ratio = text_replaced / max(total_text, 1)
    forbidden_matches = find_forbidden_terms(target_dir, forbidden_keywords or [])
    failures: list[str] = []
    if text_replaced <= 0:
        failures.append("no_text_replaced")
    if replacement_ratio < min_text_replacement_ratio:
        failures.append("text_replacement_ratio_below_minimum")
    if forbidden_matches:
        failures.append("forbidden_source_terms_remaining")
    if ellipsized_text:
        failures.append("ellipsized_material_text")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if failures else "pass",
        "source_template_dir": str(source_dir),
        "target_template_dir": str(target_dir),
        "topic": "urban_heat_remote_sensing_low_carbon_renewal",
        "selected_pages": [page.svg for page in pages],
        "page_count": len(pages),
        "text_replaced_count": text_replaced,
        "image_replaced_count": image_replaced,
        "text_replacement_ratio": round(replacement_ratio, 4),
        "ellipsized_text_count": ellipsized_text,
        "ellipsized_heading_count": ellipsized_text,
        "forbidden_keyword_matches": forbidden_matches,
        "failures": failures,
        "page_reports": page_reports,
        "next_gates": [
            f"python scripts/svg_quality_checker.py {target_dir}",
            f"python scripts/template_geometry_qa.py {target_dir} --report tmp/{target_dir.name}_geometry_svg.json --json",
            f"python scripts/svg_to_pptx.py {target_dir} --only native -t none -a none -o tmp/{target_dir.name}.pptx",
            f"python scripts/validate_pptx_text_layout.py tmp/{target_dir.name}.pptx --report tmp/{target_dir.name}_text_layout.json",
            f"python scripts/template_geometry_qa.py {target_dir} --pptx tmp/{target_dir.name}.pptx --report tmp/{target_dir.name}_geometry_pptx.json --json",
        ],
    }
    write_json(target_dir / "material_smoke_manifest.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a cross-material adaptation smoke test for a template.")
    parser.add_argument("template_dir", help="Source EasySlides template directory.")
    parser.add_argument("--out", help="Output template directory. Defaults to tmp/<template>_material_smoke.")
    parser.add_argument("--page", action="append", dest="pages", help="SVG filename or page id to include. Repeatable.")
    parser.add_argument("--max-pages", type=int, default=8, help="Maximum pages to include when --page is omitted.")
    parser.add_argument("--forbidden-keyword", action="append", default=[], help="Source-specific term that must not remain.")
    parser.add_argument("--forbidden-keywords-file", help="UTF-8 text file with one forbidden source-specific term per line.")
    parser.add_argument("--min-text-replacement-ratio", type=float, default=0.45)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output under tmp/.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    forbidden = list(args.forbidden_keyword or [])
    if args.forbidden_keywords_file:
        forbidden.extend(
            line.strip()
            for line in Path(args.forbidden_keywords_file).read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        )
    try:
        report = run_material_smoke_test(
            args.template_dir,
            args.out,
            selected_pages=args.pages,
            max_pages=args.max_pages,
            forbidden_keywords=forbidden,
            min_text_replacement_ratio=args.min_text_replacement_ratio,
            force=args.force,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "fail", "error": str(exc)}, indent=2))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(
            f"{report['status'].upper()}: {report['page_count']} pages, "
            f"{report['text_replaced_count']} text replacements, "
            f"{report['image_replaced_count']} image replacements"
        )
        print(f"Output: {report['target_template_dir']}")
        if report["failures"]:
            print("Failures: " + ", ".join(report["failures"]))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
