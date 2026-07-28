#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
TASK = Path(__file__).resolve().parent
TEMPLATE_ID = "defense_topnav"
TEMPLATE_DIR = ROOT / "templates" / "layouts" / TEMPLATE_ID
SOURCE_PLAN = TASK / "source_plan.py"
SOURCE_DIR = ROOT / "projects" / "degree_thesis" / "sources"
MINERU_DIR = SOURCE_DIR / "mineru" / "degree_thesis"
SOURCE_MD = MINERU_DIR / "degree_thesis.md"
FIGURE_DIR = MINERU_DIR / "assets" / "figures"

SVG_NS = "http://www.w3.org/2000/svg"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def load_source_plan():
    spec = importlib.util.spec_from_file_location("degree_thesis_defense_leftnav_source_plan", SOURCE_PLAN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load source plan: {SOURCE_PLAN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = load_source_plan()

PRIMARY = "#183A6A"
DARK_PRIMARY = "#0F294E"
BLACK = "#000000"
MUTED = "#595959"
LIGHT = "#FFFFFF"
PALE = "#E7E6E6"
SOFT_BLUE = "#F1F5FA"
GRAY = "#F2F2F2"

SECTIONS = list(SOURCE.SECTIONS)
SECTION_EN = dict(SOURCE.SECTION_EN)
PART_LABELS = list(SOURCE.PART_LABELS)
SLIDES = deepcopy(SOURCE.SLIDES)
FIGURES = dict(SOURCE.FIGURES)
REFERENCE_SECTION = "参考文献"
NAV_SECTIONS = SECTIONS + [REFERENCE_SECTION]
TOC_SECTIONS = SECTIONS + ["参考文献与致谢"]
NAV_SUBTITLES = [
    "Research Background",
    "Purpose and Significance",
    "Materials and Methods",
    "Results and Analysis",
    "Conclusion and Discussion",
    "References",
]


def apply_defense_topnav_content_edits() -> None:
    """Tighten text for the compact defense_topnav content canvas."""
    for slide in SLIDES:
        if slide.get("slide") == 13:
            for step in slide.get("steps", []):
                if step.get("title") == "确定个案":
                    step["body"] = "目的性抽样，聚焦上海某高校一名研究生换导师事件。"
        elif slide.get("slide") == 27:
            replacement_bodies = {
                "匹配机制": "减少单向分配和信息不对称，建立更充分的互选基础。",
                "沟通机制": "把学术、生活和情感支持纳入常态责任。",
                "评价机制": "完善学生评价和反馈渠道，及时识别并调整失衡关系。",
            }
            for card in slide.get("cards", []):
                title = card.get("title")
                if title in replacement_bodies:
                    card["body"] = replacement_bodies[title]


apply_defense_topnav_content_edits()


def tag(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def ensure_dirs() -> None:
    for rel in [
        "svg_output",
        "notes",
        "assets/figures",
        "plans",
        "sources",
        "reports",
        "storyboard",
        "exports",
    ]:
        (TASK / rel).mkdir(parents=True, exist_ok=True)


def clean_dirs() -> None:
    for rel in ["svg_output", "notes"]:
        path = TASK / rel
        if path.exists():
            for item in path.glob("*"):
                if item.is_file():
                    item.unlink()


def copy_figures() -> None:
    out = TASK / "assets" / "figures"
    for filename in FIGURES.values():
        src = FIGURE_DIR / filename
        if src.exists():
            shutil.copy2(src, out / filename)


def svg_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def weighted_len(text: str) -> float:
    total = 0.0
    for char in text:
        total += 0.55 if ord(char) < 128 else 1.0
    return total


def wrap_mixed(text: str, max_weight: float) -> list[str]:
    chunks: list[str] = []
    trailing_punctuation = set("，。；：、！？）】》”’")
    preferred_breaks = set("，。；：、！？,;:!? ")
    for raw in text.split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        line = ""
        for token in raw:
            if token in trailing_punctuation and line:
                line += token
            elif weighted_len(line + token) <= max_weight or not line:
                line += token
            else:
                split_at = -1
                for pos in range(len(line) - 1, -1, -1):
                    if line[pos] in preferred_breaks and weighted_len(line[: pos + 1]) >= max_weight * 0.55:
                        split_at = pos
                        break
                if split_at >= 0:
                    chunks.append(line[: split_at + 1].rstrip())
                    line = line[split_at + 1 :].lstrip() + token
                else:
                    chunks.append(line)
                    line = token
        if line:
            chunks.append(line)
    return chunks or [""]


def sub(parent: ET.Element, name: str, attrib: dict[str, object] | None = None) -> ET.Element:
    return ET.SubElement(parent, tag(name), {k: str(v) for k, v in (attrib or {}).items()})


def add_rect(
    parent: ET.Element,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    stroke: str | None = None,
    stroke_width: float = 1,
    rx: float | None = None,
    opacity: float | None = None,
) -> ET.Element:
    attrib: dict[str, object] = {"x": x, "y": y, "width": w, "height": h, "fill": fill}
    if stroke:
        attrib.update({"stroke": stroke, "stroke-width": stroke_width})
    else:
        attrib.update({"stroke": "none", "stroke-width": stroke_width})
    if rx is not None:
        attrib["rx"] = rx
        attrib["ry"] = rx
    if opacity is not None:
        attrib["fill-opacity"] = opacity
    return sub(parent, "rect", attrib)


def add_line(parent: ET.Element, x1: float, y1: float, x2: float, y2: float, stroke: str = PRIMARY, width: float = 2) -> None:
    sub(parent, "line", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke": stroke, "stroke-width": width})


def add_image(parent: ET.Element, filename: str, x: float, y: float, w: float, h: float, fit: str = "xMidYMid meet") -> None:
    sub(
        parent,
        "image",
        {
            "href": f"../assets/figures/{filename}",
            f"{{{XLINK_NS}}}href": f"../assets/figures/{filename}",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "preserveAspectRatio": fit,
        },
    )


def add_text(
    parent: ET.Element,
    x: float,
    y: float,
    text: str | list[str],
    size: float = 20,
    fill: str = BLACK,
    weight: str | None = None,
    anchor: str = "start",
    family: str = '"Microsoft YaHei", "微软雅黑", sans-serif',
    max_weight: float | None = None,
    line_height: float | None = None,
    letter_spacing: float | None = None,
    box: tuple[float, float, float, float] | None = None,
) -> ET.Element:
    lines = wrap_mixed(text, max_weight) if isinstance(text, str) and max_weight else (text.split("\n") if isinstance(text, str) else text)
    attrib: dict[str, object] = {
        "x": x,
        "y": y,
        "text-anchor": anchor,
        f"{{{XML_NS}}}space": "preserve",
        "font-family": family,
        "font-size": size,
        "fill": fill,
    }
    if weight:
        attrib["font-weight"] = weight
    if letter_spacing is not None:
        attrib["letter-spacing"] = letter_spacing
    if box:
        attrib["data-pptx-textbox"] = "true"
        attrib["data-pptx-box-x"] = box[0]
        attrib["data-pptx-box-y"] = box[1]
        attrib["data-pptx-box-w"] = box[2]
        attrib["data-pptx-box-h"] = box[3]
        attrib["data-pptx-valign"] = "middle" if anchor == "middle" else "top"
    node = sub(parent, "text", attrib)
    dy = line_height if line_height is not None else size * 1.35
    for idx, line in enumerate(lines):
        tspan = sub(node, "tspan", {"x": x, "fill": fill, "font-size": size})
        if weight:
            tspan.set("font-weight", weight)
        if letter_spacing is not None:
            tspan.set("letter-spacing", str(letter_spacing))
        if idx:
            tspan.set("dy", str(dy))
        tspan.text = line
    return node


def set_text_node(node: ET.Element, text: str | list[str], *, size: float | None = None, max_weight: float | None = None, line_height: float | None = None) -> None:
    if size is not None:
        node.set("font-size", str(size))
    fill = node.get("fill", BLACK)
    font_size = float(node.get("font-size", "20"))
    x = node.get("x", "0")
    lines = wrap_mixed(text, max_weight) if isinstance(text, str) and max_weight else (text.split("\n") if isinstance(text, str) else text)
    for child in list(node):
        node.remove(child)
    node.text = None
    dy = line_height if line_height is not None else font_size * 1.35
    for idx, line in enumerate(lines):
        tspan_attrib = {"x": x} if idx else {}
        tspan = sub(node, "tspan", tspan_attrib)
        if idx:
            tspan.set("dy", str(dy))
        tspan.text = line


def replace_slots(text: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")


def multiply_matrix(left: tuple[float, float, float, float, float, float], right: tuple[float, float, float, float, float, float]) -> tuple[float, float, float, float, float, float]:
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


def translate_matrix(tx: float, ty: float = 0.0) -> tuple[float, float, float, float, float, float]:
    return (1.0, 0.0, 0.0, 1.0, tx, ty)


def scale_matrix(sx: float, sy: float | None = None) -> tuple[float, float, float, float, float, float]:
    return (sx, 0.0, 0.0, sx if sy is None else sy, 0.0, 0.0)


def rotate_matrix(angle: float, cx: float | None = None, cy: float | None = None) -> tuple[float, float, float, float, float, float]:
    radians = math.radians(angle)
    base = (math.cos(radians), math.sin(radians), -math.sin(radians), math.cos(radians), 0.0, 0.0)
    if cx is None or cy is None:
        return base
    return multiply_matrix(multiply_matrix(translate_matrix(cx, cy), base), translate_matrix(-cx, -cy))


def parse_transform_matrix(transform: str) -> tuple[float, float, float, float, float, float]:
    matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, raw_args in TRANSFORM_RE.findall(transform):
        args = [float(value) for value in NUMBER_RE.findall(raw_args)]
        local = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        name = name.lower()
        if name == "matrix" and len(args) >= 6:
            local = (args[0], args[1], args[2], args[3], args[4], args[5])
        elif name == "translate" and args:
            local = translate_matrix(args[0], args[1] if len(args) > 1 else 0.0)
        elif name == "scale" and args:
            local = scale_matrix(args[0], args[1] if len(args) > 1 else None)
        elif name == "rotate" and args:
            local = rotate_matrix(args[0], args[1] if len(args) > 2 else None, args[2] if len(args) > 2 else None)
        matrix = multiply_matrix(matrix, local)
    return matrix


def transform_point(matrix: tuple[float, float, float, float, float, float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def flatten_points(points: str, transform: str) -> str:
    parsed = [tuple(float(value) for value in pair.split(",")) for pair in points.split()]
    if not transform:
        return " ".join(f"{x:g},{y:g}" for x, y in parsed)
    matrix = parse_transform_matrix(transform)
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in (transform_point(matrix, x, y) for x, y in parsed))


def remove_text_element_indent_whitespace(root: ET.Element) -> None:
    for node in root.iter(tag("text")):
        if node.text is not None and not node.text.strip():
            node.text = None
        for child in list(node):
            if child.tail is not None and not child.tail.strip():
                child.tail = None


def write_svg(path: Path, root_or_text: ET.Element | str) -> None:
    if isinstance(root_or_text, str):
        path.write_text(root_or_text, encoding="utf-8")
    else:
        ET.indent(root_or_text, space="  ")
        remove_text_element_indent_whitespace(root_or_text)
        path.write_text(ET.tostring(root_or_text, encoding="unicode"), encoding="utf-8")


KEY_MESSAGES = {
    4: "导师制不仅是培养制度，也直接塑造研究生的学术与关系体验。",
    5: "导生关系研究从制度安排转向真实关系质量与冲突机制。",
    6: "既有研究偏宏观与单侧资料，难以解释个案中关系如何裂变。",
    8: "本研究要回答换导师为何发生，并厘清个体、互动与制度因素。",
    9: "个案研究的价值在于把导生关系问题放入可分析的制度现场。",
    10: "过程还原、多方互证与制度反思共同构成本研究的贡献。",
    11: "围绕A同学及相关主体建立案例边界，是后续解释的证据基础。",
    13: "研究设计通过个案、访谈、互证与事实厘清形成解释路径。",
    14: "多源访谈材料让个人叙述、旁观证据与后续关系相互校验。",
    15: "效度与伦理控制保证结论不被单一叙述或单一归因支配。",
    16: "分析框架把叙事材料转化为过程复原与机制解释。",
    18: "换导师不是突发决定，而是期待落差持续累积后的关系转折。",
    19: "初识阶段的结构落差没有立即爆发，却削弱了后续信任基础。",
    20: "论文写作把学术分歧转化为关系冲突，并推动换导师选择。",
    21: "多方访谈显示，换导师由动机、认同、情感与制度协调共同促成。",
    22: "理想落差、志趣摇摆与生涯迷茫构成更换导师的主观基础。",
    23: "认同危机与情感淡漠共同削弱导生关系的稳定性。",
    24: "系所协调与新导师信任为关系转换提供了现实通道。",
    26: "导师制问题不只发生在个体之间，也暴露匹配与评价机制不足。",
    27: "改进导生关系需要同步完善匹配、沟通和评价机制。",
    28: "文献为导师制、关系质量与质性研究方法提供理论支撑。",
}

SYNTHESIS_LINES = {
    5: "导生关系研究的焦点，正从制度确立转向关系质量。",
    6: "宏观讨论和单侧材料不足以解释真实关系的裂变过程。",
    8: "本研究围绕“为何换导师”建立问题链和解释目标。",
    9: "个案让关系质量、导师制运行和现实冲突进入同一分析现场。",
    10: "贡献在于把关系问题放回事件过程，而不只停留在概念讨论。",
    18: "换导师是关系裂变逐步累积后的转折，而不是突然决定。",
    19: "初识与蜜月期的表面稳定，掩盖了深层期待差异。",
    23: "认同危机和情感淡漠让关系缺乏修复弹性。",
}


def short_claim(cfg: dict[str, object]) -> str:
    page = int(cfg.get("slide", 0))
    if page in KEY_MESSAGES:
        return KEY_MESSAGES[page]
    if cfg.get("summary"):
        return str(cfg["summary"])
    if cfg.get("bullets"):
        return str(cfg["bullets"][0])
    return str(cfg.get("title", "本页承接答辩论证。"))


def synthesis_summary(cfg: dict[str, object]) -> str:
    page = int(cfg.get("slide", 0))
    return SYNTHESIS_LINES.get(page, str(cfg.get("summary") or short_claim(cfg)))


def compact_heading(title: str) -> str:
    heading = title.split("：", 1)[0].strip()
    replacements = {
        "研究问题与研究目标": "研究问题",
        "研究意义": "研究意义",
        "案例边界": "案例边界",
        "资料来源与互证逻辑": "资料互证",
        "研究效度与伦理控制": "效度伦理",
        "分析框架": "分析框架",
        "事件主线": "事件主线",
        "事实厘清": "事实厘清",
        "导师制反思": "制度反思",
        "结论与建议": "结论建议",
    }
    heading = replacements.get(heading, heading)
    return heading if weighted_len(heading) <= 8 else heading[:8]


def set_navigation(root: ET.Element, section: str) -> None:
    idx = NAV_SECTIONS.index(section) + 1
    nav = json.loads((TEMPLATE_DIR / "navigation_states.json").read_text(encoding="utf-8"))
    state = nav["sections"][idx - 1]
    for node in root.iter():
        node_id = node.get("id")
        if node_id == "nav-active-tab":
            band = state["active_tab"]
            for key in ["x", "y", "width", "height", "fill"]:
                node.set(key, str(band[key]))
            node.set("data-active-index", str(idx))
            node.set("data-active-section", section)

    nav_items = next(node for node in root.iter(tag("g")) if node.get("id") == "nav-items")
    for child in list(nav_items):
        nav_items.remove(child)

    for pos, (title, subtitle) in enumerate(zip(NAV_SECTIONS, NAV_SUBTITLES), 1):
        item_state = nav["sections"][pos - 1]
        label = item_state["label"]
        is_active = pos == idx
        title_node = sub(
            nav_items,
            "text",
            {
                "id": "nav-active-label" if is_active else f"nav-label-{pos}",
                "x": label["x"],
                "y": label["title_y"],
                "font-size": 24,
                "font-weight": "bold",
                "fill": PRIMARY if is_active else LIGHT,
                "text-anchor": label["anchor"],
            },
        )
        if is_active:
            title_node.set("data-slot", "ACTIVE_SECTION_LABEL")
            title_node.set("data-slot-token", "{{ACTIVE_SECTION_LABEL}}")
        title_node.text = title

        subtitle_node = sub(
            nav_items,
            "text",
            {
                "id": "nav-active-subtitle" if is_active else f"nav-subtitle-{pos}",
                "x": label["x"],
                "y": label["subtitle_y"],
                "font-size": 12,
                "fill": PRIMARY if is_active else LIGHT,
                "text-anchor": label["anchor"],
            },
        )
        if not is_active:
            subtitle_node.set("fill-opacity", "0.4")
        subtitle_node.text = subtitle


def content_shell(cfg: dict[str, object]) -> tuple[ET.Element, ET.Element]:
    root = ET.fromstring(svg_text(TEMPLATE_DIR / "03_content.svg"))
    page = int(cfg["slide"])
    title = str(cfg["title"])
    section = str(cfg["section"])
    set_navigation(root, section)

    for node in list(root.iter(tag("text"))):
        slot = node.get("data-slot")
        if slot == "PAGE_TITLE":
            heading = f"◆ {compact_heading(title)}"
            size = 28 if weighted_len(heading) <= 7 else 24
            set_text_node(node, heading, size=size)
        elif slot == "KEY_MESSAGE":
            set_text_node(node, short_claim(cfg), max_weight=55, line_height=23)
        elif slot == "PAGE_NUM":
            set_text_node(node, f"{page:02d}")
        elif slot == "CONTENT_BODY":
            parent_map = {child: parent for parent in root.iter() for child in parent}
            parent = parent_map.get(node)
            if parent is not None:
                parent.remove(node)

    body_region = next(node for node in root.iter(tag("g")) if node.get("id") == "body-region")
    layer = sub(body_region, "g", {"id": f"content-body-{page:02d}"})
    return root, layer


def add_bullets(layer: ET.Element, bullets: list[str], *, x: float = 110, y: float = 260, gap: float = 72, size: float = 21, max_weight: float = 54) -> None:
    for idx, bullet in enumerate(bullets):
        yy = y + idx * gap
        add_rect(layer, x, yy - 15, 12, 12, PRIMARY, rx=2)
        add_text(layer, x + 26, yy, bullet, size=size, fill=BLACK, max_weight=max_weight, line_height=size * 1.35, box=(x + 26, yy - 24, 1030, gap - 8))


def add_synthesis_band(layer: ET.Element, cfg: dict[str, object], *, y: float = 570, label: str = "归纳") -> None:
    add_rect(layer, 92, y, 1096, 42, PALE, rx=6)
    add_rect(layer, 92, y, 108, 42, PRIMARY, rx=6)
    add_text(layer, 146, y + 27, label, size=18, fill=LIGHT, weight="bold", anchor="middle")
    add_text(layer, 224, y + 27, synthesis_summary(cfg), size=18, fill=BLACK, weight="bold", max_weight=50, line_height=20)


def add_body_slide(layer: ET.Element, cfg: dict[str, object]) -> None:
    title = str(cfg.get("title", ""))
    body_title = title.split("：", 1)[-1] if cfg.get("body_title_from_title") else title
    add_text(layer, 92, 230, body_title, size=25, fill=PRIMARY, weight="bold", max_weight=34)
    add_line(layer, 92, 253, 1188, 253, stroke=PRIMARY, width=1.6)
    add_bullets(layer, [str(item) for item in cfg["bullets"]], y=302, gap=70, size=20, max_weight=55)


def timeline_node_positions(count: int, *, left: float = 180, right: float = 1095) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [round((left + right) / 2, 2)]
    step = (right - left) / (count - 1)
    return [round(left + idx * step, 2) for idx in range(count)]


def timeline_card_width(positions: list[float]) -> float:
    if len(positions) <= 1:
        return 244
    min_gap = min(b - a for a, b in zip(positions, positions[1:]))
    return min(244, max(150, min_gap - 24))


def add_timeline_slide(layer: ET.Element, cfg: dict[str, object]) -> None:
    items = [dict(item) for item in cfg["items"]]  # type: ignore[index]
    compact_body = {
        "1953": "《暂行办法》正式确立指导教师负责制。",
        "1980s": "研究生培养普遍采取导师制，导师成为培养链条核心。",
        "2000s": "研究逐渐走向鲜活教育事实。",
        "近年": "扩招、冲突与评价缺失，推动关系质量反思。",
    }
    y = 390
    positions = timeline_node_positions(len(items))
    card_w = timeline_card_width(positions)
    if len(positions) > 1:
        add_line(layer, positions[0], y, positions[-1], y, stroke=PRIMARY, width=3)
    for idx, (item, x) in enumerate(zip(items, positions)):
        sub(layer, "circle", {"cx": x, "cy": y, "r": 13, "fill": PRIMARY, "stroke": LIGHT, "stroke-width": 4})
        card_y = 230 if idx % 2 == 0 else 430
        card_x = x - card_w / 2
        add_rect(layer, card_x, card_y, card_w, 122, LIGHT, stroke=PRIMARY, stroke_width=1.6, rx=6)
        add_text(layer, x, card_y + 34, item["year"], size=24, fill=PRIMARY, weight="bold", anchor="middle", family="Arial, sans-serif")
        add_text(layer, x, card_y + 64, item["title"], size=20, fill=BLACK, weight="bold", anchor="middle", max_weight=max(6, card_w / 24))
        body = compact_body.get(str(item["year"]), item["body"])
        add_text(layer, card_x + 16, card_y + 92, body, size=15.5, fill=MUTED, max_weight=max(8, (card_w - 32) / 13), line_height=19)
    add_synthesis_band(layer, cfg, y=572, label="脉络")


def add_compare_slide(layer: ET.Element, cfg: dict[str, object]) -> None:
    cards = [(cfg["left"], 92), (cfg["right"], 668)]  # type: ignore[index]
    for item, x in cards:
        add_rect(layer, x, 230, 520, 318, LIGHT, stroke=PRIMARY, stroke_width=2, rx=8)
        add_rect(layer, x, 230, 520, 52, PALE, stroke=PRIMARY, stroke_width=0)
        add_text(layer, x + 260, 265, item["title"], size=24, fill=PRIMARY, weight="bold", anchor="middle", max_weight=18)
        add_text(layer, x + 34, 322, item["body"], size=19, fill=BLACK, max_weight=25, line_height=28, box=(x + 34, 298, 452, 220))
    add_text(layer, 640, 392, "VS", size=44, fill=PRIMARY, weight="bold", anchor="middle", family="Arial, sans-serif")
    add_synthesis_band(layer, cfg, y=570, label="判断")


def add_card_grid(layer: ET.Element, cfg: dict[str, object]) -> None:
    cards = [dict(item) for item in cfg["cards"]]  # type: ignore[index]
    positions = [(92, 242), (462, 242), (832, 242)]
    for idx, (card, (x, y)) in enumerate(zip(cards[:3], positions), 1):
        add_rect(layer, x, y, 326, 300, LIGHT, stroke=PRIMARY, stroke_width=1.8, rx=8)
        add_rect(layer, x, y, 52, 52, PRIMARY, rx=6)
        add_text(layer, x + 26, y + 35, f"{idx}", size=25, fill=LIGHT, weight="bold", anchor="middle", family="Arial, sans-serif")
        add_text(layer, x + 70, y + 36, card["title"], size=22, fill=PRIMARY, weight="bold", max_weight=10)
        add_text(layer, x + 26, y + 96, card["body"], size=19, fill=BLACK, max_weight=17, line_height=27, box=(x + 26, y + 76, 272, 198))
    add_synthesis_band(layer, cfg, y=570, label="合并")


def add_process_steps(layer: ET.Element, cfg: dict[str, object]) -> None:
    steps = [dict(item) for item in cfg["steps"]]  # type: ignore[index]
    positions = [(92, 230), (668, 230), (92, 420), (668, 420)]
    for idx, (step, (x, y)) in enumerate(zip(steps[:4], positions), 1):
        add_rect(layer, x, y, 520, 150, LIGHT, stroke=PRIMARY, stroke_width=1.6, rx=8)
        sub(layer, "circle", {"cx": x + 42, "cy": y + 45, "r": 25, "fill": PRIMARY})
        add_text(layer, x + 42, y + 54, f"{idx:02d}", size=20, fill=LIGHT, weight="bold", anchor="middle", family="Arial, sans-serif")
        add_text(layer, x + 84, y + 42, step["title"], size=22, fill=PRIMARY, weight="bold", max_weight=14)
        add_text(layer, x + 84, y + 78, step["body"], size=17, fill=BLACK, max_weight=27, line_height=23)


def add_matrix(layer: ET.Element, cfg: dict[str, object]) -> None:
    items = [dict(item) for item in cfg["items"]]  # type: ignore[index]
    for idx, item in enumerate(items[:3], 1):
        y = 230 + (idx - 1) * 122
        add_rect(layer, 92, y, 1096, 102, LIGHT, stroke=PRIMARY, stroke_width=1.4, rx=8)
        add_rect(layer, 92, y, 92, 102, PALE, stroke=PRIMARY, stroke_width=0, rx=8)
        add_text(layer, 138, y + 62, f"{idx:02d}", size=30, fill=PRIMARY, weight="bold", anchor="middle", family="Arial, sans-serif")
        add_text(layer, 218, y + 40, item["title"], size=23, fill=PRIMARY, weight="bold", max_weight=24)
        add_text(layer, 218, y + 75, item["body"], size=18, fill=BLACK, max_weight=52, line_height=24)


def add_table(layer: ET.Element, x: float, y: float, columns: list[str], rows: list[list[str]], widths: list[float], row_h: float = 40) -> None:
    total_w = sum(widths)
    add_rect(layer, x, y, total_w, row_h * (len(rows) + 1), LIGHT, stroke=PRIMARY, stroke_width=1.2, rx=5)
    add_rect(layer, x, y, total_w, row_h, PALE, stroke=PRIMARY, stroke_width=0, rx=5)
    cx = x
    for w in widths[:-1]:
        cx += w
        add_line(layer, cx, y, cx, y + row_h * (len(rows) + 1), stroke=PRIMARY, width=0.9)
    for i in range(1, len(rows) + 1):
        add_line(layer, x, y + row_h * i, x + total_w, y + row_h * i, stroke=PRIMARY, width=0.9)
    cx = x
    for col, w in zip(columns, widths):
        add_text(layer, cx + w / 2, y + 27, col, size=16, fill=PRIMARY, weight="bold", anchor="middle", max_weight=max(5, w / 15))
        cx += w
    for r, row in enumerate(rows):
        cx = x
        for cell, w in zip(row, widths):
            add_text(layer, cx + 10, y + row_h * (r + 1) + 25, cell, size=14.5, fill=BLACK, max_weight=max(6, w / 13), line_height=18)
            cx += w


def add_data_grid(layer: ET.Element, cfg: dict[str, object]) -> None:
    summaries = [dict(item) for item in cfg["summaries"]]  # type: ignore[index]
    for idx, item in enumerate(summaries[:2]):
        x = 92 if idx == 0 else 668
        add_rect(layer, x, 218, 520, 108, LIGHT, stroke=PRIMARY, stroke_width=1.5, rx=7)
        add_text(layer, x + 22, 252, item["title"], size=22, fill=PRIMARY, weight="bold", max_weight=16)
        add_text(layer, x + 22, 286, item["body"], size=16.5, fill=BLACK, max_weight=29, line_height=22)
    if cfg.get("table"):
        table = cfg["table"]  # type: ignore[assignment]
        widths = [float(w) * (1040 / sum(table["widths"])) for w in table["widths"]]  # type: ignore[index]
        add_table(layer, 120, 365, table["columns"], table["rows"], widths, row_h=table.get("row_h", 42))  # type: ignore[index]
    if cfg.get("image"):
        table_caption = str(cfg.get("table_caption", "")).strip()
        figure_caption = str(cfg.get("figure_caption", cfg.get("caption", ""))).strip()
        image_y = 350
        image_h = 230
        if table_caption:
            add_text(layer, 640, 350, table_caption, size=17, fill=PRIMARY, weight="bold", anchor="middle", max_weight=42)
            image_y = 365
            image_h = 215
        add_image(layer, str(cfg["image"]), 250, image_y, 780, image_h)
        if figure_caption and not table_caption:
            add_text(layer, 640, image_y + image_h + 24, figure_caption, size=16, fill=MUTED, anchor="middle", max_weight=56)


def add_figure_single(layer: ET.Element, cfg: dict[str, object]) -> None:
    if cfg.get("image"):
        add_image(layer, str(cfg["image"]), 230, 230, 820, 330)
        if cfg.get("caption"):
            add_text(layer, 640, 585, str(cfg["caption"]), size=16, fill=MUTED, anchor="middle", max_weight=56)
    elif cfg.get("flow"):
        flow = [str(item) for item in cfg["flow"]]  # type: ignore[index]
        add_rect(layer, 92, 238, 1096, 68, SOFT_BLUE, stroke=PRIMARY, stroke_width=1.2, rx=8)
        add_text(layer, 122, 278, short_claim(cfg), size=21, fill=PRIMARY, weight="bold", max_weight=50, line_height=25)
        start_x = 118
        y = 390
        for idx, label in enumerate(flow):
            x = start_x + idx * 218
            add_rect(layer, x, y, 168, 82, PALE if idx % 2 == 0 else LIGHT, stroke=PRIMARY, stroke_width=2, rx=8)
            add_text(layer, x + 84, y + 49, label, size=18, fill=PRIMARY, weight="bold", anchor="middle", max_weight=8, line_height=22)
            if idx < len(flow) - 1:
                add_line(layer, x + 174, y + 41, x + 205, y + 41, stroke=PRIMARY, width=3)
                sub(layer, "polygon", {"points": f"{x + 205},{y + 41} {x + 195},{y + 34} {x + 195},{y + 48}", "fill": PRIMARY, "stroke": "none"})


def add_figure_pair(layer: ET.Element, cfg: dict[str, object]) -> None:
    for item, x in [(cfg["left"], 92), (cfg["right"], 668)]:  # type: ignore[index]
        if "image" in item:
            add_image(layer, item["image"], x, 260, 520, 280)
            add_text(layer, x + 260, 235, item["title"], size=20, fill=PRIMARY, weight="bold", anchor="middle", max_weight=20)
        else:
            add_rect(layer, x, 242, 520, 300, LIGHT, stroke=PRIMARY, stroke_width=1.8, rx=8)
            add_text(layer, x + 260, 296, item["title"], size=24, fill=PRIMARY, weight="bold", anchor="middle", max_weight=16)
            add_text(layer, x + 36, 356, item["body"], size=18.5, fill=BLACK, max_weight=25, line_height=27)
    add_synthesis_band(layer, cfg, y=570, label="关系")


def build_content_slide(cfg: dict[str, object]) -> ET.Element:
    root, layer = content_shell(cfg)
    kind = str(cfg["kind"])
    if kind == "body":
        add_body_slide(layer, cfg)
    elif kind == "timeline":
        add_timeline_slide(layer, cfg)
    elif kind == "compare":
        add_compare_slide(layer, cfg)
    elif kind == "cards":
        add_card_grid(layer, cfg)
    elif kind == "steps":
        add_process_steps(layer, cfg)
    elif kind == "matrix":
        add_matrix(layer, cfg)
    elif kind == "data":
        add_data_grid(layer, cfg)
    elif kind == "figure_single":
        add_figure_single(layer, cfg)
    elif kind == "figure_pair":
        add_figure_pair(layer, cfg)
    else:
        raise ValueError(f"Unknown slide kind: {kind}")
    return root


def chapter_replacements(section: str) -> dict[str, str]:
    idx = SECTIONS.index(section)
    return {
        "CHAPTER_NUM": f"{idx + 1:02d}",
        "CHAPTER_TITLE": section,
        "CHAPTER_DESC": SECTION_EN[section],
        "SECTION_NUMBER": f"{idx + 1:02d}",
        "PART_LABEL": PART_LABELS[idx],
        "SECTION_TITLE": section,
        "SECTION_SUBTITLE": SECTION_EN[section],
    }


def build_references(page: int) -> ET.Element:
    cfg = {
        "slide": page,
        "title": "主要参考文献",
        "section": REFERENCE_SECTION,
        "source": "来源：学位论文参考文献节选。",
        "summary": "参考文献为论文中的核心理论、方法与导师制研究提供来源支撑。",
    }
    root, layer = content_shell(cfg)
    refs = [
        "潘懋元. 论高等教育[M]. 福州: 福建教育出版社, 2000.",
        "薛天祥. 研究生教育学[M]. 桂林: 广西师范大学出版社, 2004.",
        "于光远. 导师与研究生的对话[M]. 苏州: 苏州大学出版社, 2001.",
        "陈向明. 质的研究方法与社会科学研究[M]. 北京: 教育科学出版社, 2000.",
        "周光礼. “导师制”与“老板制”[J]. 高等工程教育研究, 2008(2).",
        "许克毅, 郑英蓉. 三重反思[J]. 教育发展研究, 2007(4).",
        "张静. 导师与研究生之间的和谐关系研究[J]. 中国高教研究, 2007(9).",
        "罗尧成, 曹海莹, 孙跃东. 导师制度内涵、困境及超越[J]. 江苏高教, 2011(3).",
    ]
    y = 216
    for i, ref in enumerate(refs, 1):
        add_text(layer, 92, y + i * 42, f"{i}. {ref}", size=17.5, fill=BLACK, max_weight=70, line_height=23)
    return root


def title_for_slide(cfg: dict[str, object]) -> str:
    archetype = str(cfg["archetype"])
    if archetype == "cover":
        return SOURCE.TITLE
    if archetype == "toc":
        return "目录"
    if archetype == "chapter":
        return str(cfg["section"])
    if archetype == "references":
        return "主要参考文献"
    if archetype == "closing":
        return "恳请老师批评指正！"
    return str(cfg.get("title", ""))


def render_slides() -> list[dict[str, object]]:
    rendered: list[dict[str, object]] = []
    svg_out = TASK / "svg_output"
    for cfg in SLIDES:
        page = int(cfg["slide"])
        archetype = str(cfg["archetype"])
        filename = f"{page:02d}_{archetype}.svg"
        out_path = svg_out / filename
        if archetype == "cover":
            text = replace_slots(
                svg_text(TEMPLATE_DIR / "01_cover.svg"),
                {
                    "TITLE": SOURCE.TITLE,
                    "SUBTITLE": SOURCE.SUBTITLE,
                    "PRESENTER": SOURCE.PRESENTER,
                    "ADVISOR": SOURCE.ADVISOR,
                    "DATE": SOURCE.DATE,
                },
            )
            write_svg(out_path, text)
        elif archetype == "toc":
            replacements = {f"SECTION_{idx}": section for idx, section in enumerate(TOC_SECTIONS, 1)}
            write_svg(out_path, replace_slots(svg_text(TEMPLATE_DIR / "02_toc.svg"), replacements))
        elif archetype == "chapter":
            write_svg(out_path, replace_slots(svg_text(TEMPLATE_DIR / "02_chapter.svg"), chapter_replacements(str(cfg["section"]))))
        elif archetype == "references":
            write_svg(out_path, build_references(page))
        elif archetype == "closing":
            text = replace_slots(
                svg_text(TEMPLATE_DIR / "04_ending.svg"),
                {
                    "CLOSING_TITLE": "恳请老师批评指正！",
                    "CLOSING_SUBTITLE": SOURCE.SUBTITLE,
                    "PRESENTER": SOURCE.PRESENTER,
                    "ADVISOR": SOURCE.ADVISOR,
                    "CONTACT": SOURCE.CONTACT,
                },
            )
            write_svg(out_path, text)
        else:
            write_svg(out_path, build_content_slide(cfg))
        rendered.append({"slide": page, "filename": filename, "archetype": archetype, "section": cfg["section"], "title": title_for_slide(cfg)})
    return rendered


def write_notes(rendered: list[dict[str, object]]) -> None:
    notes_dir = TASK / "notes"
    for item, cfg in zip(rendered, SLIDES):
        page = int(item["slide"])
        title = str(item["title"])
        note = [
            f"# Slide {page}: {title}",
            "",
            f"- page_role: {cfg['archetype']}",
            f"- section: {cfg['section']}",
            "- presenter_intent: 用一页讲清当前页的一个核心观点，避免展开论文原文长段。",
        ]
        if "source" in cfg:
            note.append(f"- source: {cfg['source']}")
        (notes_dir / f"{page:02d}_{cfg['archetype']}.md").write_text("\n".join(note) + "\n", encoding="utf-8")


def write_locks(rendered: list[dict[str, object]]) -> None:
    plans = TASK / "plans"
    sources = TASK / "sources"
    now = datetime.now(timezone.utc).isoformat()
    intake = f"""# Intake Lock

- scenario: thesis_defense
- audience: 学位论文答辩委员会与导师组
- slide count / duration: 29 slides, formal thesis defense, about 20 minutes
- language: Chinese with English section subtitles
- output contract: editable-native PPTX
- source materials: {SOURCE_MD.relative_to(ROOT)} plus 8 MinerU extracted figures
- institution / logo: East China Normal University from thesis cover image; no web lookup
- template route: local `defense_topnav` academic-blue top-navigation template
- style family: academic blue thesis defense, dynamic active top navigation
- unresolved questions: no official school logo file beyond thesis-extracted image; no user-provided updated presenter metadata
"""
    spec = """# Spec Lock

## Deck Contract

Use `defense_topnav` in 16:9, editable-native output. Reuse the existing 29-page thesis-defense content plan and redraw it through the academic-blue five-shell template.

## Source Contract

Claims, methods, findings, references, and figures come from the converted dissertation artifacts under `projects/degree_thesis/sources/mineru/degree_thesis/` and the local `defense_leftnav_deck/source_plan.py` content plan.

## Template Contract

Every content slide uses `03_content.svg` with the active top-navigation state matching the current chapter. Body compositions are rendered inside the open template `CONTENT_AREA`.

## QA Gates

Run SVG quality check, PPTX export, text extraction/placeholder scan, rendered preview generation, and visual inspection.
"""
    (plans / "intake_lock.md").write_text(intake, encoding="utf-8")
    (plans / "spec_lock.md").write_text(spec, encoding="utf-8")
    (plans / "asset_lock.json").write_text(
        json.dumps(
            {
                "created_at": now,
                "font_stack": ["微软雅黑", "Microsoft YaHei", "Arial"],
                "institution": "华东师范大学 / East China Normal University",
                "logo_source": str((FIGURE_DIR / FIGURES["logo"]).relative_to(ROOT)),
                "logo_policy": "Use only thesis-extracted cover logo if needed; no invented official mark.",
                "template_id": TEMPLATE_ID,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (sources / "source_pack.json").write_text(
        json.dumps(
            {
                "created_at": now,
                "source_pdf": str((SOURCE_DIR / "degree_thesis.pdf").relative_to(ROOT)),
                "markdown": str(SOURCE_MD.relative_to(ROOT)),
                "paper_metadata": {
                    "title": SOURCE.TITLE,
                    "institution": "华东师范大学",
                    "degree": "硕士学位论文",
                    "student": SOURCE.PRESENTER,
                    "supervisor": SOURCE.ADVISOR,
                    "date": SOURCE.DATE,
                },
                "main_claim": "换导师事件由个人动机、导生互动和导师制制度条件共同促成。",
                "figures": [str((FIGURE_DIR / f).relative_to(ROOT)) for f in FIGURES.values()],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    figure_items = [
        {
            "id": key,
            "file": str((TASK / "assets" / "figures" / filename).relative_to(TASK)),
            "source_file": str((FIGURE_DIR / filename).relative_to(ROOT)),
            "role": "mainline" if key in {"fact_flow", "relationship_table"} else "supporting",
            "action": "use",
        }
        for key, filename in FIGURES.items()
    ]
    (plans / "figure_index.json").write_text(json.dumps({"created_at": now, "figures": figure_items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    story = []
    for slide in rendered:
        cfg = deepcopy(SLIDES[int(slide["slide"]) - 1])
        story.append(
            {
                "slide": slide["slide"],
                "title": slide["title"],
                "archetype": slide["archetype"],
                "section": slide["section"],
                "claim": cfg.get("summary") or cfg.get("title") or slide["title"],
                "source": cfg.get("source", "template structural slide"),
            }
        )
    (plans / "story_blueprint.json").write_text(
        json.dumps(
            {
                "created_at": now,
                "audience_question": "答辩委员会需要确认研究问题、方法、事实厘清与导师制反思是否成立。",
                "central_thesis": "换导师事件不是单点冲突，而是理想落差、认同危机、情感淡漠与制度协调共同作用的结果。",
                "slides": story,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (plans / "template_binding.json").write_text(
        json.dumps(
            {
                "created_at": now,
                "bindings": [
                    {
                        "slide": item["slide"],
                        "svg": item["filename"],
                        "template_id": TEMPLATE_ID,
                        "shell": "03_content.svg" if item["archetype"] not in {"cover", "toc", "chapter", "closing"} else item["archetype"],
                        "archetype": item["archetype"],
                        "section": item["section"],
                    }
                    for item in rendered
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (plans / "element_plan.json").write_text(
        json.dumps(
            {
                "created_at": now,
                "scenario": "thesis_defense",
                "template_id": TEMPLATE_ID,
                "slides": [
                    {
                        "slide": item["slide"],
                        "page_role": item["archetype"],
                        "body_variant": "figure_with_takeaway" if item["archetype"] in {"figure_single", "figure_pair", "data_grid"} else item["archetype"],
                        "content_element": "source_image" if item["archetype"] in {"figure_single", "figure_pair", "data_grid"} else "native_text_shapes",
                    }
                    for item in rendered
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (plans / "deck_brief.md").write_text(
        """# Deck Brief

Audience: thesis defense committee.

Before-state: committee has the source dissertation but needs a concise, defensible oral route.

After-state: committee sees the case logic, methodological grounding, core findings, and tutor-system reflection in an academic-blue defense_topnav visual system.

Central tension: a visible interpersonal conflict is used to reveal hidden tutor-system matching, communication, and evaluation problems.
""",
        encoding="utf-8",
    )
    (plans / "slide_spec.json").write_text(
        json.dumps(
            {
                "created_at": now,
                "output_contract": "editable-native",
                "slides": [
                    {
                        "slide": item["slide"],
                        "svg": item["filename"],
                        "objects": ["native_text", "native_shape", "source_image"] if item["archetype"] in {"figure_single", "figure_pair", "data_grid"} else ["native_text", "native_shape"],
                    }
                    for item in rendered
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    state = {
        "schema_version": "0.1.0",
        "created_at": now,
        "updated_at": now,
        "skill": "easyppt",
        "scenario": "thesis_defense",
        "output_contract": "editable-native",
        "template_id": TEMPLATE_ID,
        "stages": {
            stage: {"status": "complete", "updated_at": now}
            for stage in [
                "intake",
                "intake_lock",
                "spec_lock",
                "asset_lock",
                "source_pack",
                "figure_index",
                "audience_state_brief",
                "story_blueprint",
                "element_plan",
                "template_binding",
                "design_system",
                "slide_spec",
                "html_storyboard",
            ]
        },
    }
    (TASK / "pipeline_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_storyboard(rendered: list[dict[str, object]]) -> None:
    items = []
    for item in rendered:
        items.append(f'<section><h2>{item["slide"]:02d}. {item["title"]}</h2><object data="../svg_output/{item["filename"]}" type="image/svg+xml"></object></section>')
    html = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>degree_thesis defense_topnav storyboard</title>
<style>
body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; background: #f4f4f4; color: #111; }
section { width: 1280px; margin: 24px auto; background: white; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
h2 { margin: 0; padding: 14px 20px; font-size: 20px; background: #183A6A; color: white; }
object { width: 1280px; height: 720px; display: block; }
</style>
</head>
<body>
""" + "\n".join(items) + "\n</body>\n</html>\n"
    (TASK / "storyboard" / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    clean_dirs()
    copy_figures()
    rendered = render_slides()
    write_notes(rendered)
    write_locks(rendered)
    write_storyboard(rendered)
    print(json.dumps({"task": str(TASK), "svg_count": len(rendered), "storyboard": str(TASK / "storyboard" / "index.html")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
