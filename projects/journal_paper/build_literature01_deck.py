#!/usr/bin/env python3
"""Build a literature_minimal-style paper-reading deck for the journal_paper project."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates" / "layouts" / "literature_minimal"
FIG_DIR = TASK / "sources" / "mineru" / "main" / "assets" / "figures"

SVG_OUT = TASK / "svg_output"
NOTES_DIR = TASK / "notes"
STORYBOARD_DIR = TASK / "storyboard"
PLANS_DIR = TASK / "plans"
ASSETS_DIR = TASK / "assets"
FIG_ASSETS = ASSETS_DIR / "figures"

PRIMARY = "#0D5DBE"
DEEP = "#0E2841"
TEXT = "#1F2937"
MUTED = "#6B7280"
SOFT = "#F5F9FE"
BORDER = "#D9E4F2"
FONT = "Microsoft YaHei, Arial, sans-serif"

TITLE = "Plant Ecoacoustics"
SUBTITLE = "A Sensory Ecology Approach | 从“声音刺激”转向“植物实际经历的振动”"
PRESENTER = "川柏同学"
INSTITUTION = "Trends in Ecology & Evolution | Journal club"
LOGO_IMAGE: str | None = None
# Keep this example deck reproducible across test runs and public releases.
TODAY = "2026-05-19"

FIGURES = {
    "plant": "fig-001-p03-illustration-of-a-plant-with-yellow-flowers-green-leaves-i.jpg",
    "vibroscape": "fig-002-p03-trends-in-ecologyecology-evolution-figure-1-the-vibroscape.jpg",
    "spray": "fig-003-p05-illustration-of-a-spray-bottle-dispensing-liquid-into-a-pl.jpg",
    "caterpillar": "fig-004-p05-illustration-of-a-caterpillar-on-a-green-leafy-branch-labe.jpg",
    "wave": "fig-005-p05-time-s-velocity-mm-s.jpg",
    "actuator": "fig-006-p05-diagram-of-a-cylindrical-apparatus-with-a-central-column-a.jpg",
    "playback": "fig-008-p05-trends-in-ecologyecology-evolution-figure-i-outline-of-the.jpg",
}


def read_template(name: str) -> str:
    return (TEMPLATE / name).read_text(encoding="utf-8")


def esc(value: object) -> str:
    return xml_escape(str(value), {'"': "&quot;"})


def replace_slots(svg: str, replacements: dict[str, object]) -> str:
    for key, value in replacements.items():
        svg = svg.replace(f"{{{{{key}}}}}", esc(value))
    return svg


ET.register_namespace("", "http://www.w3.org/2000/svg")


def remove_slot_groups(svg: str, slot: str) -> str:
    root = ET.fromstring(svg)
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    for node in list(root.iter()):
        if node.attrib.get("data-slot") != slot:
            continue
        parent = parents.get(node)
        if parent is not None:
            parent.remove(node)
    return ET.tostring(root, encoding="unicode")


def apply_template(name: str, replacements: dict[str, object], *, logo_image: str | None = LOGO_IMAGE) -> str:
    svg = replace_slots(read_template(name), replacements | {"LOGO_IMAGE": logo_image or ""})
    if not logo_image:
        svg = remove_slot_groups(svg, "LOGO_IMAGE")
    return svg


def clear_dirs() -> None:
    for path in [SVG_OUT, NOTES_DIR, STORYBOARD_DIR, PLANS_DIR, ASSETS_DIR]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    FIG_ASSETS.mkdir(parents=True, exist_ok=True)


def copy_assets() -> None:
    for filename in FIGURES.values():
        shutil.copy2(FIG_DIR / filename, FIG_ASSETS / filename)
    if LOGO_IMAGE:
        make_logo(ASSETS_DIR / "logo_mark.png")


def make_logo(path: Path) -> None:
    image = Image.new("RGBA", (420, 120), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 18, 412, 102), radius=16, outline=(13, 93, 190, 120), width=3)
    draw.rectangle((30, 42, 42, 78), fill=(13, 93, 190, 255))
    draw.text((58, 36), "Plant Ecoacoustics", fill=(14, 40, 65, 255))
    draw.text((58, 64), "journal club", fill=(107, 114, 128, 255))
    image.save(path)


def tspan_lines(lines: list[str], x: int | float, line_height: int | float) -> str:
    parts = []
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else line_height
        parts.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    return "".join(parts)


def text_block(
    x: int,
    y: int,
    lines: list[str],
    *,
    size: int = 22,
    fill: str = TEXT,
    weight: str = "normal",
    line_height: int | None = None,
    width: int = 600,
    name: str = "text-block",
    box_y: int | float | None = None,
    box_h: int | float | None = None,
) -> str:
    if line_height is None:
        line_height = int(size * 1.45)
    height = max(line_height * len(lines), line_height)
    if box_y is None:
        box_y = y - size
    if box_h is None:
        box_h = height + size
    return (
        f'<g id="{name}">'
        f'<rect x="{x}" y="{box_y}" width="{width}" height="{box_h}" fill="none"/>'
        f'<text x="{x}" y="{y}" text-anchor="start" xml:space="preserve" '
        f'font-family="{FONT}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
        f'data-pptx-box-x="{x}" data-pptx-box-y="{box_y}" '
        f'data-pptx-box-w="{width}" data-pptx-box-h="{box_h}" '
        f'data-pptx-valign="top" data-pptx-textbox="true">{tspan_lines(lines, x, line_height)}</text>'
        "</g>"
    )


def page_shell(chapter: str, title: str, key_message: str, source: str, page_num: int, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="1280" height="720" viewBox="0 0 1280 720">
  <rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
  <g id="content-header">
    <polygon points="52,77 1228,77 1230,85 50,85" fill="{PRIMARY}" fill-opacity="0.18"/>
    <polygon points="36,81 1244,81 1246,89 34,89" fill="{PRIMARY}"/>
    <text x="54" y="55" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="34" fill="{PRIMARY}" font-weight="bold" data-pptx-box-x="54" data-pptx-box-y="20" data-pptx-box-w="300" data-pptx-box-h="48" data-pptx-valign="top" data-pptx-textbox="true"><tspan>{esc(chapter)}</tspan></text>
    <text x="1224" y="55" text-anchor="end" xml:space="preserve" font-family="{FONT}" font-size="34" fill="#000000" font-weight="bold" data-pptx-box-x="700" data-pptx-box-y="20" data-pptx-box-w="524" data-pptx-box-h="48" data-pptx-valign="top" data-pptx-textbox="true"><tspan>{esc(title)}</tspan></text>
  </g>
  <g id="key-message">
    <rect x="54" y="116" width="1172" height="74" rx="4" ry="4" fill="{SOFT}" stroke="{PRIMARY}" stroke-width="1" stroke-opacity="0.18"/>
    <rect x="54" y="116" width="8" height="74" fill="{PRIMARY}"/>
    <text x="82" y="162" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="25" fill="{DEEP}" font-weight="bold" data-pptx-box-x="82" data-pptx-box-y="126" data-pptx-box-w="1116" data-pptx-box-h="54" data-pptx-valign="middle" data-pptx-textbox="true"><tspan>{esc(key_message)}</tspan></text>
  </g>
  {body}
  <g id="content-footer">
    <path d="M 0 713 L 1238 713 L 1245 717 L 1252 713 L 1280 713 L 1280 720 L 0 720 Z" fill="{PRIMARY}"/>
    <text x="54" y="688" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="14" fill="{MUTED}"><tspan>{esc(source)}</tspan></text>
    <text x="1245" y="710" text-anchor="middle" xml:space="preserve" font-family="Arial, Microsoft YaHei, sans-serif" font-size="14.67" fill="{PRIMARY}" font-weight="bold"><tspan>{page_num}</tspan></text>
  </g>
</svg>
'''


def img_href(key: str) -> str:
    return f"../assets/figures/{FIGURES[key]}"


def image_frame(x: int, y: int, w: int, h: int, key: str, caption: str, name: str) -> str:
    caption_x = x + 18
    caption_y = y + h - 43
    caption_w = w - 36
    caption_h = 30
    return (
        f'<g id="{name}">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" ry="6" fill="#FFFFFF" stroke="{BORDER}" stroke-width="1.4"/>'
        f'<image href="{img_href(key)}" x="{x + 12}" y="{y + 12}" width="{w - 24}" height="{h - 58}" preserveAspectRatio="xMidYMid meet"/>'
        f'<text x="{x + w / 2}" y="{y + h - 20}" text-anchor="middle" xml:space="preserve" font-family="{FONT}" font-size="14" fill="{MUTED}" data-pptx-box-x="{caption_x}" data-pptx-box-y="{caption_y}" data-pptx-box-w="{caption_w}" data-pptx-box-h="{caption_h}" data-pptx-valign="middle" data-pptx-textbox="true"><tspan>{esc(caption)}</tspan></text>'
        "</g>"
    )


def card(x: int, y: int, w: int, h: int, title: str, lines: list[str], name: str) -> str:
    title_x = x + 24
    title_y = y + 14
    title_w = w - 48
    title_h = 32
    body_box_y = y + 50
    body_box_h = max(24, h - 58)
    body_baseline = body_box_y + 18
    return (
        f'<g id="{name}">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" ry="6" fill="#FFFFFF" stroke="{BORDER}" stroke-width="1.3"/>'
        f'<rect x="{x}" y="{y}" width="7" height="{h}" fill="{PRIMARY}"/>'
        f'<text x="{title_x}" y="{y + 34}" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="21" fill="{DEEP}" font-weight="bold" data-pptx-box-x="{title_x}" data-pptx-box-y="{title_y}" data-pptx-box-w="{title_w}" data-pptx-box-h="{title_h}" data-pptx-valign="top" data-pptx-textbox="true"><tspan>{esc(title)}</tspan></text>'
        f'{text_block(x + 24, body_baseline, lines, size=17, fill=MUTED, line_height=24, width=w - 48, name=name + "-body", box_y=body_box_y, box_h=body_box_h)}'
        "</g>"
    )


def open_stat(x: int, y: int, num: str, title: str, desc: str, name: str) -> str:
    return (
        f'<g id="{name}">'
        f'<text x="{x}" y="{y}" text-anchor="start" xml:space="preserve" font-family="Arial, Microsoft YaHei, sans-serif" font-size="48" fill="{PRIMARY}" font-weight="bold"><tspan>{esc(num)}</tspan></text>'
        f'<text x="{x + 88}" y="{y - 8}" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="22" fill="{DEEP}" font-weight="bold" data-pptx-box-x="{x + 88}" data-pptx-box-y="{y - 34}" data-pptx-box-w="360" data-pptx-box-h="30" data-pptx-valign="top" data-pptx-textbox="true"><tspan>{esc(title)}</tspan></text>'
        f'<text x="{x + 88}" y="{y + 24}" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="16" fill="{MUTED}" data-pptx-box-x="{x + 88}" data-pptx-box-y="{y + 4}" data-pptx-box-w="360" data-pptx-box-h="34" data-pptx-valign="top" data-pptx-textbox="true"><tspan>{esc(desc)}</tspan></text>'
        "</g>"
    )


def write_svg(name: str, svg: str) -> None:
    (SVG_OUT / name).write_text(svg, encoding="utf-8")


def write_note(name: str, lines: list[str]) -> None:
    (NOTES_DIR / f"{Path(name).stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_cover() -> str:
    return apply_template(
        "01_cover.svg",
        {
            "TITLE": TITLE,
            "SUBTITLE": SUBTITLE,
            "AUTHOR": PRESENTER,
            "DATE": TODAY,
        },
    )


def build_toc() -> str:
    replacements: dict[str, object] = {}
    items = [
        ("论文问题", "植物声学为什么不能停留在“播放声音”"),
        ("核心概念", "vibroscape 与 plant-centered umwelt"),
        ("现有证据", "herbivory、pollination、root foraging"),
        ("方法框架", "测量、复现、校准植物组织振动"),
        ("讨论启发", "机制、适应性与农业潜力"),
    ]
    for idx, (title, desc) in enumerate(items, start=1):
        replacements[f"TOC_ITEM_{idx}_TITLE"] = title
        replacements[f"TOC_ITEM_{idx}_DESC"] = desc
    return apply_template("02_toc.svg", replacements)


def build_chapter(num: str, title: str, desc: str) -> str:
    return apply_template(
        "02_chapter.svg",
        {
            "CHAPTER_NUM": num,
            "CHAPTER_TITLE": title,
            "CHAPTER_DESC": desc,
        },
    )


def build_ending() -> str:
    return apply_template(
        "04_ending.svg",
        {
            "THANK_YOU": "敬请批评指正！",
            "ENDING_SUBTITLE": "Thank you for listening!",
            "AUTHOR": PRESENTER,
            "DATE": TODAY,
        },
    )


def slide_04() -> str:
    body = (
        image_frame(820, 224, 260, 394, "plant", "植物的“声景”首先发生在组织中", "plant-figure")
        + text_block(
            88,
            258,
            [
                "这篇 opinion 的核心贡献不是证明“植物会听见声音”，",
                "而是把问题改写为：植物组织中有哪些可用的机械波信息，",
                "这些信息如何改变防御、生长或繁殖等适应性决策。",
            ],
            size=24,
            fill=TEXT,
            line_height=36,
            width=680,
            name="thesis-open-text",
        )
        + open_stat(100, 440, "01", "从人工音调转向自然刺激", "单频或音乐实验不足以解释生态适应性。", "stat-1")
        + open_stat(100, 522, "02", "从空气声音转向组织振动", "植物实际经历的是叶、茎、根中的位移和振动。", "stat-2")
    )
    return page_shell("论文主张", "植物不是在“听”人类的声音", "真正的问题是：植物如何利用其组织中真实存在的机械波信息？", "Appel & Cocroft, Trends in Ecology & Evolution", 4, body)


def slide_05() -> str:
    body = (
        image_frame(74, 214, 360, 430, "vibroscape", "取食者、互利者与背景振动构成可感知线索", "vibroscape")
        + card(486, 230, 325, 120, "Herbivores", ["咀嚼、行走、取食产生", "可识别的振动签名。"], "herbivores")
        + card(848, 230, 325, 120, "Mutualists", ["飞行、接触花部与 buzz pollination", "形成传粉相关振动线索。"], "mutualists")
        + card(486, 390, 325, 120, "Background", ["风、雨、鸟鸣、交通噪声", "构成植物背景振动环境。"], "background")
        + card(848, 390, 325, 120, "Plant-centered", ["vibroscape 关注组织中的振动，", "而不是人的听觉经验。"], "plant-centered")
    )
    return page_shell("核心概念", "Vibroscape：植物的振动生态位", "声学环境不是外部背景，而是植物可感知的生态信息流。", "Figure 1 and vibroscape concept from Appel & Cocroft", 5, body)


def slide_07() -> str:
    body = (
        image_frame(82, 236, 190, 220, "caterpillar", "feeding vibration", "caterpillar")
        + image_frame(318, 236, 190, 220, "spray", "induced response", "spray")
        + image_frame(554, 236, 190, 220, "plant", "plant context", "plant-context")
        + card(790, 226, 350, 112, "Herbivory", ["Arabidopsis 与 tobacco 可在取食振动后提高化学防御。"], "evidence-herbivory")
        + card(790, 368, 350, 112, "Pollination", ["花可对传粉者相关声音/振动快速调整花蜜性状。"], "evidence-pollination")
        + card(790, 510, 350, 112, "Root foraging", ["根向水流声或特定声音源生长，提示土壤声景可能有信息价值。"], "evidence-root")
    )
    return page_shell("现有证据", "自然声学线索能触发相关响应", "当前证据虽不完整，但已经覆盖防御、繁殖与资源寻找三个方向。", "Evidence summarized from refs. 17-23 in the source article", 7, body)


def slide_09() -> str:
    body = (
        image_frame(78, 222, 320, 266, "playback", "先测量组织振动，再用 actuator 复现", "playback")
        + image_frame(96, 514, 130, 112, "actuator", "actuator", "actuator")
        + image_frame(246, 514, 130, 112, "wave", "calibration", "wave")
        + card(455, 224, 720, 88, "1. Measure the plant tissue", ["用 laser vibrometer 或合适传感器测量目标叶、茎、根实际位移。"], "method-1")
        + card(455, 333, 720, 88, "2. Reproduce the vibration", ["用 playback/actuator 重建事件振动，而不是只播放空气中的声音。"], "method-2")
        + card(455, 442, 720, 88, "3. Calibrate amplitude and filtering", ["补偿设备过滤效应，并让刺激幅度匹配植物经历的真实水平。"], "method-3")
        + card(455, 551, 720, 88, "4. Measure ecological responses", ["选择与生长、存活、繁殖或防御相关的响应，而不是只测易测指标。"], "method-4")
    )
    return page_shell("方法框架", "实验必须从植物实际经历出发", "方法论重点：先测到植物组织里的振动，再复现并评估生态相关响应。", "Box 1: measuring and reproducing plant-borne vibrations", 9, body)


def slide_11() -> str:
    body = (
        card(
            80,
            224,
            330,
            180,
            "Mechanosensing",
            ["植物没有动物式听觉器官，", "但活组织普遍具备机械感受能力。", "MSL10 等通道可能参与振动/伤害信号。"],
            "mechanosensing",
        )
        + card(
            474,
            224,
            330,
            180,
            "Signal integration",
            ["取食振动会与组织损伤、", "口腔分泌物、电信号、ROS/钙波并存。", "关键是声学线索的识别权重。"],
            "integration",
        )
        + card(
            868,
            224,
            330,
            180,
            "Systemic speed",
            ["振动可在植物体内快速传播，", "可能早于部分化学/电信号。", "这为“预警型”防御提供假说。"],
            "speed",
        )
        + text_block(
            100,
            500,
            [
                "汇报解读：这篇文章的价值在于提出一套研究框架，而不是给出完整机制模型。",
                "它把未来工作推向三个层面：物理信号、细胞转导、生态适应性。"
            ],
            size=25,
            fill=DEEP,
            weight="bold",
            line_height=38,
            width=1060,
            name="interpretation",
        )
    )
    return page_shell("机制与响应", "声学线索可能是一种快速、系统性的生态信息", "机制问题需要把振动、损伤和植物内部信号网络放在同一实验框架中。", "Mechanosensing and within-plant signaling section", 11, body)


def slide_12() -> str:
    questions = [
        ("区分", "植物如何区分取食、风、传粉者和背景噪声？"),
        ("噪声", "自然环境中风雨噪声下的检测空间有多大？"),
        ("传播", "振动在植株内部的 active space 如何定义？"),
        ("互作", "声学线索怎样与损伤、口腔分泌物等线索整合？"),
        ("应用", "能否用于减少化学投入并提升农业可持续性？"),
    ]
    rows = []
    for i, (tag, q) in enumerate(questions):
        y = 234 + i * 76
        rows.append(
            f'<g id="question-{i + 1}">'
            f'<text x="88" y="{y + 25}" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="28" fill="{PRIMARY}" font-weight="bold"><tspan>{esc(tag)}</tspan></text>'
            f'<line x1="164" y1="{y + 20}" x2="188" y2="{y + 20}" stroke="{PRIMARY}" stroke-width="2"/>'
            f'<text x="208" y="{y + 25}" text-anchor="start" xml:space="preserve" font-family="{FONT}" font-size="23" fill="{TEXT}" data-pptx-box-x="208" data-pptx-box-y="{y}" data-pptx-box-w="960" data-pptx-box-h="42" data-pptx-valign="top" data-pptx-textbox="true"><tspan>{esc(q)}</tspan></text>'
            "</g>"
        )
    body = "".join(rows) + text_block(
        790,
        292,
        [
            "讨论建议",
            "把这篇文章当作“研究计划书”阅读：",
            "它最强的是问题重构和方法约束，",
            "最弱的是自然场景中的因果证据仍少。"
        ],
        size=24,
        fill=DEEP,
        weight="bold",
        line_height=40,
        width=360,
        name="discussion-note",
    )
    return page_shell("讨论启发", "这篇文章真正留下的是可检验的问题", "好的 journal club 讨论应聚焦：哪些证据足以支持“适应性声学感知”？", "Outstanding questions and concluding remarks", 12, body)


def build_deck() -> list[dict[str, str]]:
    slides: list[tuple[str, str, list[str]]] = [
        ("01_cover.svg", build_cover(), ["Introduce the paper and the plant-centered framing."]),
        ("02_toc.svg", build_toc(), ["Preview the five-part journal club structure."]),
        ("03_chapter_core_thesis.svg", build_chapter("01", "论文主张", "Core thesis and conceptual reframing"), ["Transition into the paper's main argument."]),
        ("04_content_core_thesis.svg", slide_04(), ["Emphasize that the paper reframes sound as tissue vibration."]),
        ("05_content_vibroscape.svg", slide_05(), ["Use Figure 1 to explain vibroscape as a plant-centered sensory world."]),
        ("06_chapter_evidence.svg", build_chapter("02", "现有证据", "What responses have been shown so far?"), ["Transition into evidence."]),
        ("07_content_evidence.svg", slide_07(), ["Summarize evidence domains: herbivory, pollination, root foraging."]),
        ("08_chapter_methods.svg", build_chapter("03", "方法框架", "Measure, reproduce, calibrate, then test response"), ["Transition into methods."]),
        ("09_content_methods.svg", slide_09(), ["Walk through the method pipeline from Box 1."]),
        ("10_chapter_discussion.svg", build_chapter("04", "讨论启发", "Mechanisms, fitness traits, and open questions"), ["Transition into discussion."]),
        ("11_content_mechanisms.svg", slide_11(), ["Discuss mechanosensing and within-plant signaling."]),
        ("12_content_questions.svg", slide_12(), ["Use outstanding questions to guide discussion."]),
        ("13_ending.svg", build_ending(), ["Close the talk and invite discussion."]),
    ]
    rendered = []
    for filename, svg, notes in slides:
        write_svg(filename, svg)
        write_note(filename, notes)
        rendered.append({"filename": filename, "title": filename.removesuffix(".svg")})
    return rendered


def write_artifacts(rendered: list[dict[str, str]]) -> None:
    intake = {
        "scenario": "paper_reading_minimal",
        "audience": "lab meeting / journal club",
        "style": "templates/layouts/literature_minimal minimal blue-white classic shells",
        "duration": "10-15 minutes",
        "slide_count": len(rendered),
        "output_contract": "editable-native-pptx",
        "source_materials": [
            "projects/journal_paper/sources/main.pdf",
            "projects/journal_paper/sources/mineru/main/main.md",
            "projects/journal_paper/sources/mineru/main/assets/figures/",
        ],
        "source_policy": {
            "narrative_sources": [
                "source article PDF",
                "MinerU Markdown extraction",
                "source-article figures",
            ],
            "excluded_sources": [
                "Tencent Docs / 腾讯文档不参与当前 deck 生成；除非用户显式重新指定，否则不进入主线、证据或约束。"
            ],
            "current_decision": "Current deck narrative is derived only from the source article package.",
        },
        "assumptions": [
            "User requested literature_minimal style and did not specify duration; defaulted to a compact journal-club talk.",
            "Slides are in Chinese with original English scientific terms retained where useful.",
            "Tencent Docs content is omitted from the current input set because it does not materially improve the deck.",
        ],
    }
    (PLANS_DIR / "intake_brief.json").write_text(json.dumps(intake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    deck_plan = [
        "# journal_paper literature_minimal deck plan",
        "",
        "- Style: literature_minimal, minimal blue-white, classic page rhythm.",
        "- Audience: lab journal club.",
        "- Arc: conceptual reframing -> vibroscape evidence -> method framework -> discussion questions.",
        "- Source boundary: Tencent Docs / 腾讯文档不参与当前 deck；当前叙事只基于论文 PDF、MinerU Markdown 和论文图像素材。",
        "",
        "## Slides",
    ]
    for idx, item in enumerate(rendered, start=1):
        deck_plan.append(f"{idx}. `{item['filename']}`")
    (PLANS_DIR / "deck_plan.md").write_text("\n".join(deck_plan) + "\n", encoding="utf-8")

    story_items = [
        f'<section><h2>{idx:02d}. {item["title"]}</h2><object data="../svg_output/{item["filename"]}" type="image/svg+xml"></object></section>'
        for idx, item in enumerate(rendered, start=1)
    ]
    storyboard = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>journal_paper literature_minimal storyboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #f5f7fa; }}
    section {{ margin-bottom: 32px; }}
    object {{ width: 960px; height: 540px; background: white; box-shadow: 0 4px 18px rgba(0,0,0,.08); }}
  </style>
</head>
<body>
  <h1>journal_paper literature_minimal storyboard</h1>
  {''.join(story_items)}
</body>
</html>
"""
    (STORYBOARD_DIR / "index.html").write_text(storyboard, encoding="utf-8")


def main() -> None:
    clear_dirs()
    copy_assets()
    rendered = build_deck()
    write_artifacts(rendered)
    print(json.dumps({"slides": len(rendered), "svg_output": str(SVG_OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
