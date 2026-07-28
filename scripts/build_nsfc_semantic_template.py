#!/usr/bin/env python3
"""Build the clean semantic purple template distilled from the NSFC reference."""

from __future__ import annotations

import json
import html
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.template_package import build_package_manifest

OUT = ROOT / "templates" / "layouts" / "nsfc_purple_semantic"
KIT = ROOT / "templates" / "components" / "source_templates" / "nsfc_purple_semantic_kit"
SVG_NS = "http://www.w3.org/2000/svg"

PRIMARY = "#751497"
DEEP = "#4B0D65"
ACCENT = "#BF4BE7"
PALE = "#F8EAFC"
TEXT = "#2F2436"
MUTED = "#6F6275"
BORDER = "#E6D5EC"
WHITE = "#FFFFFF"
FONT = "Microsoft YaHei, Arial, sans-serif"
BACKGROUND_ASSET = "nsfc_purple_dark_pattern.png"


def measure_sample(slot: str) -> str:
    """Keep placeholder QA representative without measuring token syntax."""
    if slot == "PAGE_NUM":
        return "99"
    if slot == "AGENDA_COUNT" or slot == "CHAPTER_NUM":
        return "08"
    if slot.endswith("_VALUE"):
        return "100.0%"
    if slot.endswith("_TITLE") or slot in {"TITLE", "SUBTITLE", "KEY_MESSAGE", "SECTION"}:
        return "Sample title"
    if slot.endswith("_LABEL"):
        return "Metric label"
    if slot.endswith("_BODY") or slot in {"BODY", "AGENDA", "CHAPTER_DESC", "SOURCE", "CAPTION", "AUTHOR", "DATE", "CONTACT"}:
        return "Short evidence line"
    return "Sample text"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text(
    slot: str,
    x: int,
    y: int,
    w: int,
    h: int,
    size: int,
    color: str,
    *,
    weight: str = "normal",
    anchor: str = "start",
    kind: str = "text",
    line_height: int = 32,
    valign: str = "top",
    box_y: int | None = None,
    measure_text: str | None = None,
) -> str:
    box_x = x if anchor == "start" else (x - w if anchor == "end" else x - w / 2)
    declared_box_y = y - size if box_y is None else box_y
    sample = measure_text or measure_sample(slot)
    return (
        f'<text data-slot="{slot}" data-slot-kind="{kind}" x="{x}" y="{y}" '
        f'text-anchor="{anchor}" xml:space="preserve" font-family="{FONT}" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'data-pptx-textbox="true" data-pptx-box-x="{box_x:g}" '
        f'data-pptx-box-y="{declared_box_y:g}" data-pptx-box-w="{w}" data-pptx-box-h="{h}" '
        f'data-pptx-valign="{valign}" data-pptx-measure-text="{html.escape(sample)}" '
        f'data-line-height="{line_height}">{{{{{slot}}}}}</text>'
    )


def base_defs() -> str:
    return f"""
  <defs>
    <linearGradient id="purpleGlow" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{PRIMARY}"/>
      <stop offset="1" stop-color="{DEEP}"/>
    </linearGradient>
    <linearGradient id="softBand" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{PALE}"/>
      <stop offset="1" stop-color="#FFFFFF"/>
    </linearGradient>
  </defs>
"""


def header() -> str:
    return f"""
  <rect x="0" y="0" width="1280" height="72" fill="{PRIMARY}"/>
  <rect x="0" y="68" width="1280" height="4" fill="{ACCENT}"/>
  <path d="M1080 0H1280V72H1140L1080 0Z" fill="{DEEP}" opacity="0.8"/>
  {text("PAGE_TITLE", 52, 48, 900, 46, 30, WHITE, weight="bold")}
  {text("SECTION", 1220, 44, 190, 30, 15, WHITE, anchor="end")}
"""


def footer() -> str:
    return f"""
  <line x1="52" y1="682" x2="1228" y2="682" stroke="{BORDER}" stroke-width="1"/>
  {text("SOURCE", 52, 707, 900, 24, 13, MUTED)}
  {text("PAGE_NUM", 1228, 707, 96, 24, 14, PRIMARY, weight="bold", anchor="end")}
"""


def svg(body: str) -> str:
    return f"""<svg xmlns="{SVG_NS}" xmlns:xlink="http://www.w3.org/1999/xlink" width="1280" height="720" viewBox="0 0 1280 720">
{base_defs()}
  <rect width="1280" height="720" fill="#FFFFFF"/>
{body}
</svg>"""


def build_svgs() -> None:
    write(
        OUT / "01_cover.svg",
        svg(
            f"""
  <image x="0" y="0" width="1280" height="720" preserveAspectRatio="none" href="assets/{BACKGROUND_ASSET}"/>
  <rect width="1280" height="720" fill="#16051D" opacity="0.14"/>
  <rect x="64" y="88" width="92" height="8" rx="4" fill="#E5B5F5"/>
  {text("TITLE", 64, 236, 650, 150, 54, WHITE, weight="bold", line_height=64)}
  {text("SUBTITLE", 66, 354, 620, 74, 26, "#F0D7F8", weight="bold", line_height=34)}
  {text("AUTHOR", 66, 574, 340, 34, 20, "#F1DFF6")}
  {text("DATE", 66, 622, 260, 30, 17, "#D9BFDF")}
  <image data-slot="HERO_IMAGE" data-slot-kind="image" x="825" y="178" width="390" height="330" preserveAspectRatio="xMidYMid meet" href="assets/transparent.svg"/>
"""
        ),
    )
    write(
        OUT / "02_toc.svg",
        svg(
            f"""
{header()}
  <rect x="72" y="124" width="1136" height="496" rx="18" fill="url(#softBand)" stroke="{BORDER}" stroke-width="2"/>
  <rect x="72" y="124" width="12" height="496" rx="6" fill="{PRIMARY}"/>
  {text("AGENDA", 126, 194, 1010, 360, 29, TEXT, kind="list", line_height=67)}
  <circle cx="1110" cy="186" r="48" fill="{PALE}" stroke="{ACCENT}" stroke-width="2"/>
  <text data-slot="AGENDA_COUNT" data-slot-kind="text" x="1110" y="198"
        text-anchor="middle" font-family="{FONT}" font-size="32" font-weight="bold"
        fill="{PRIMARY}" data-pptx-textbox="true" data-pptx-box-x="1070"
        data-pptx-box-y="162" data-pptx-box-w="80" data-pptx-box-h="48"
        data-pptx-valign="middle" data-pptx-measure-text="06">{{{{AGENDA_COUNT}}}}</text>
{footer()}
"""
        ),
    )
    write(
        OUT / "03_chapter.svg",
        svg(
            f"""
  <rect x="0" y="0" width="470" height="720" fill="url(#purpleGlow)"/>
  <path d="M470 0L620 0L470 720Z" fill="{PALE}"/>
  {text("CHAPTER_NUM", 70, 220, 300, 110, 86, WHITE, weight="bold")}
  {text("CHAPTER_TITLE", 560, 286, 610, 120, 46, DEEP, weight="bold", line_height=56)}
  {text("CHAPTER_DESC", 564, 410, 570, 100, 23, MUTED, line_height=34)}
  <rect x="564" y="500" width="94" height="6" fill="{ACCENT}"/>
"""
        ),
    )
    write(
        OUT / "04_text_focus.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="86" rx="12" fill="{PALE}" stroke="{BORDER}"/>
  <rect x="60" y="112" width="8" height="86" rx="4" fill="{PRIMARY}"/>
  {text("KEY_MESSAGE", 88, 166, 1090, 54, 24, DEEP, weight="bold", line_height=30)}
  <rect x="60" y="228" width="1160" height="412" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  {text("BODY", 96, 292, 1080, 310, 24, TEXT, kind="list", line_height=52)}
{footer()}
"""
        ),
    )
    write(
        OUT / "07b_comparison_focus.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
  <rect x="60" y="212" width="560" height="420" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="660" y="212" width="560" height="420" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="88" y="238" width="120" height="58" rx="29" fill="{PALE}" stroke="{ACCENT}" stroke-width="2"/>
  <rect x="688" y="238" width="120" height="58" rx="29" fill="{PALE}" stroke="{ACCENT}" stroke-width="2"/>
  <text data-slot="LEFT_BADGE" data-slot-kind="text" x="148" y="278"
        text-anchor="middle" font-family="{FONT}" font-size="25" font-weight="bold"
        fill="{PRIMARY}" data-pptx-textbox="true" data-pptx-box-x="98"
        data-pptx-box-y="246" data-pptx-box-w="100" data-pptx-box-h="42"
        data-pptx-valign="middle" data-pptx-measure-text="A">{{{{LEFT_BADGE}}}}</text>
  <text data-slot="RIGHT_BADGE" data-slot-kind="text" x="748" y="278"
        text-anchor="middle" font-family="{FONT}" font-size="25" font-weight="bold"
        fill="{PRIMARY}" data-pptx-textbox="true" data-pptx-box-x="698"
        data-pptx-box-y="246" data-pptx-box-w="100" data-pptx-box-h="42"
        data-pptx-valign="middle" data-pptx-measure-text="A">{{{{RIGHT_BADGE}}}}</text>
  {text("LEFT_TITLE", 232, 276, 340, 44, 24, DEEP, weight="bold", valign="middle", box_y=254)}
  {text("RIGHT_TITLE", 832, 276, 340, 44, 24, DEEP, weight="bold", valign="middle", box_y=254)}
  {text("LEFT_BODY", 96, 356, 476, 220, 21, TEXT, kind="list", line_height=48)}
  {text("RIGHT_BODY", 696, 356, 476, 220, 21, TEXT, kind="list", line_height=48)}
{footer()}
"""
        ),
    )
    figure_common = f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
{footer()}
"""
    write(
        OUT / "05_figure_left.svg",
        svg(
            figure_common
            + f"""
  <rect x="60" y="212" width="688" height="420" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <image data-slot="FIGURE" data-slot-kind="image" x="82" y="232" width="644" height="338" preserveAspectRatio="xMidYMid meet" href="assets/transparent.svg"/>
  {text("CAPTION", 82, 608, 644, 34, 14, MUTED)}
  <rect x="780" y="212" width="440" height="420" rx="14" fill="{PALE}" stroke="{BORDER}"/>
  {text("BODY", 816, 270, 368, 320, 20, TEXT, kind="list", line_height=43)}
"""
        ),
    )
    write(
        OUT / "06_figure_right.svg",
        svg(
            figure_common
            + f"""
  <rect x="60" y="212" width="440" height="420" rx="14" fill="{PALE}" stroke="{BORDER}"/>
  {text("BODY", 96, 270, 368, 320, 20, TEXT, kind="list", line_height=43)}
  <rect x="532" y="212" width="688" height="420" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <image data-slot="FIGURE" data-slot-kind="image" x="554" y="232" width="644" height="338" preserveAspectRatio="xMidYMid meet" href="assets/transparent.svg"/>
  {text("CAPTION", 554, 608, 644, 34, 14, MUTED)}
"""
        ),
    )
    write(
        OUT / "07_two_column.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="118" width="555" height="514" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="665" y="118" width="555" height="514" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="60" y="118" width="555" height="72" rx="16" fill="{PALE}"/>
  <rect x="665" y="118" width="555" height="72" rx="16" fill="{PALE}"/>
  {text("LEFT_TITLE", 92, 163, 480, 38, 23, DEEP, weight="bold", valign="middle", box_y=135)}
  {text("RIGHT_TITLE", 697, 163, 480, 38, 23, DEEP, weight="bold", valign="middle", box_y=135)}
  {text("LEFT_BODY", 92, 236, 480, 340, 20, TEXT, kind="list", line_height=45)}
  {text("RIGHT_BODY", 697, 236, 480, 340, 20, TEXT, kind="list", line_height=45)}
{footer()}
"""
        ),
    )
    cards = []
    for index, x in enumerate((60, 447, 834), start=1):
        cards.append(
            f"""
  <rect x="{x}" y="164" width="346" height="444" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="{x}" y="164" width="346" height="10" rx="5" fill="{PRIMARY if index == 1 else ACCENT}"/>
  <circle cx="{x+48}" cy="224" r="24" fill="{PALE}" stroke="{PRIMARY}" stroke-width="2"/>
  <text x="{x+48}" y="232" text-anchor="middle" font-family="Arial" font-size="20" font-weight="bold" fill="{PRIMARY}">{index}</text>
  {text(f"CARD_{index}_TITLE", x+84, 232, 230, 50, 22, DEEP, weight="bold")}
  {text(f"CARD_{index}_BODY", x+28, 302, 290, 250, 18, TEXT, kind="list", line_height=39)}
"""
        )
    write(OUT / "08_three_cards.svg", svg(header() + "".join(cards) + footer()))
    steps = []
    for index, x in enumerate((70, 360, 650, 940), start=1):
        if index < 4:
            steps.append(f'<path d="M{x+220} 350H{x+276}" stroke="{ACCENT}" stroke-width="5"/><path d="M{x+276} 350l-16-11v22Z" fill="{ACCENT}"/>')
        steps.append(
            f"""
  <circle cx="{x+92}" cy="250" r="54" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/>
  <text x="{x+92}" y="264" text-anchor="middle" font-family="Arial" font-size="34" font-weight="bold" fill="{PRIMARY}">{index}</text>
  {text(f"STEP_{index}_TITLE", x, 348, 240, 52, 21, DEEP, weight="bold", anchor="start")}
  {text(f"STEP_{index}_BODY", x, 412, 210, 130, 17, TEXT, line_height=27)}
"""
        )
    write(OUT / "09_process.svg", svg(header() + "".join(steps) + footer()))
    write(
        OUT / "10_result.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
  <rect x="60" y="212" width="720" height="420" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <image data-slot="FIGURE" data-slot-kind="image" x="82" y="232" width="676" height="338" preserveAspectRatio="xMidYMid meet" href="assets/transparent.svg"/>
  {text("CAPTION", 82, 608, 676, 34, 14, MUTED)}
  <rect x="812" y="212" width="408" height="122" rx="14" fill="{PALE}" stroke="{BORDER}"/>
  <rect x="812" y="354" width="408" height="122" rx="14" fill="{PALE}" stroke="{BORDER}"/>
  <rect x="812" y="496" width="408" height="122" rx="14" fill="{PALE}" stroke="{BORDER}"/>
  {text("METRIC_1_VALUE", 842, 268, 150, 48, 34, PRIMARY, weight="bold", measure_text="100.0%")}
  {text("METRIC_1_LABEL", 982, 268, 206, 48, 18, TEXT)}
  {text("METRIC_2_VALUE", 842, 410, 150, 48, 34, PRIMARY, weight="bold", measure_text="100.0%")}
  {text("METRIC_2_LABEL", 982, 410, 206, 48, 18, TEXT)}
  {text("METRIC_3_VALUE", 842, 552, 150, 48, 34, PRIMARY, weight="bold", measure_text="100.0%")}
  {text("METRIC_3_LABEL", 982, 552, 206, 48, 18, TEXT)}
{footer()}
"""
        ),
    )
    write(
        OUT / "12_timeline.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
  <line x1="130" y1="334" x2="1150" y2="334" stroke="{ACCENT}" stroke-width="5"/>
  <path d="M1150 334l-18-11v22Z" fill="{ACCENT}"/>
"""
            + "".join(
                f"""
  <circle cx="{x}" cy="334" r="34" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/>
  <text x="{x}" y="346" text-anchor="middle" font-family="Arial" font-size="24" font-weight="bold" fill="{PRIMARY}">{index}</text>
  {text(f"STEP_{index}_TITLE", x, 410, 216, 42, 20, DEEP, weight="bold", anchor="middle", valign="middle", box_y=386)}
  {text(f"STEP_{index}_BODY", x, 486, 216, 96, 16, TEXT, line_height=25, anchor="middle")}
"""
                for index, x in enumerate((130, 470, 810, 1150), start=1)
            )
            + footer()
        ),
    )
    write(
        OUT / "13_quote.svg",
        svg(
            f"""
{header()}
  <rect x="88" y="146" width="1104" height="388" rx="22" fill="{PALE}" stroke="{BORDER}" stroke-width="2"/>
  <rect x="88" y="146" width="14" height="388" rx="7" fill="{PRIMARY}"/>
  <text x="150" y="258" font-family="Georgia, serif" font-size="104" font-weight="bold" fill="{ACCENT}" opacity="0.65">“</text>
  {text("QUOTE", 174, 330, 930, 150, 32, DEEP, weight="bold", line_height=48)}
  {text("QUOTE_AUTHOR", 174, 442, 560, 34, 18, TEXT, weight="bold")}
  {text("QUOTE_SOURCE", 174, 486, 780, 28, 15, MUTED)}
  <rect x="174" y="566" width="210" height="6" rx="3" fill="{ACCENT}"/>
{footer()}
"""
        ),
    )
    write(
        OUT / "14_metrics.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
"""
            + "".join(
                f"""
  <rect x="{x}" y="230" width="260" height="250" rx="18" fill="{PALE if index % 2 else '#FFFFFF'}" stroke="{BORDER}" stroke-width="2"/>
  <circle cx="{x + 48}" cy="278" r="22" fill="{PRIMARY if index % 2 else ACCENT}"/>
  <text x="{x + 48}" y="286" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold" fill="{WHITE}">{index}</text>
  {text(f"METRIC_{index}_VALUE", x + 130, 366, 204, 54, 34, PRIMARY, weight="bold", anchor="middle", valign="middle", box_y=328, measure_text="100.0%")}
  {text(f"METRIC_{index}_LABEL", x + 130, 426, 204, 44, 17, TEXT, anchor="middle", valign="middle", box_y=404, measure_text="Metric label")}
"""
                for index, x in enumerate((60, 350, 640, 930), start=1)
            )
            + f"""
  {text("NOTE", 60, 552, 1160, 34, 16, MUTED)}
{footer()}
"""
        ),
    )
    table_rows = []
    for index, y in enumerate((294, 360, 426, 492), start=1):
        fill = PALE if index % 2 else "#FFFFFF"
        table_rows.append(
            f"""
  <rect x="70" y="{y}" width="1140" height="66" fill="{fill}"/>
  {text(f"ROW_{index}_LABEL", 96, y + 42, 300, 34, 17, TEXT, valign="middle", box_y=y + 16)}
  {text(f"ROW_{index}_VALUE_1", 430, y + 42, 220, 34, 17, TEXT, anchor="middle", valign="middle", box_y=y + 16)}
  {text(f"ROW_{index}_VALUE_2", 700, y + 42, 220, 34, 17, TEXT, anchor="middle", valign="middle", box_y=y + 16)}
  {text(f"ROW_{index}_VALUE_3", 1050, y + 42, 220, 34, 17, PRIMARY, weight="bold", anchor="middle", valign="middle", box_y=y + 16)}
"""
        )
    write(
        OUT / "15_table.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
  <rect x="70" y="228" width="1140" height="66" rx="10" fill="{PRIMARY}"/>
  {text("COL_1", 96, 270, 300, 34, 17, WHITE, weight="bold", valign="middle", box_y=244)}
  {text("COL_2", 540, 270, 220, 34, 17, WHITE, weight="bold", anchor="middle", valign="middle", box_y=244)}
  {text("COL_3", 810, 270, 220, 34, 17, WHITE, weight="bold", anchor="middle", valign="middle", box_y=244)}
  {text("COL_4", 1160, 270, 220, 34, 17, WHITE, weight="bold", anchor="middle", valign="middle", box_y=244)}
"""
            + "".join(table_rows)
            + f"""
  <rect x="70" y="558" width="1140" height="54" rx="10" fill="{PALE}"/>
  {text("TABLE_NOTE", 96, 592, 1080, 30, 15, MUTED)}
{footer()}
"""
        ),
    )
    grid_cards = []
    for index, (x, y) in enumerate(((60, 146), (650, 146), (60, 396), (650, 396)), start=1):
        grid_cards.append(
            f"""
  <rect x="{x}" y="{y}" width="570" height="214" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="{x}" y="{y}" width="570" height="10" rx="5" fill="{PRIMARY if index % 2 else ACCENT}"/>
  <circle cx="{x + 42}" cy="{y + 52}" r="24" fill="{PALE}" stroke="{PRIMARY}" stroke-width="2"/>
  <text x="{x + 42}" y="{y + 60}" text-anchor="middle" font-family="Arial" font-size="20" font-weight="bold" fill="{PRIMARY}">{index}</text>
  {text(f"CARD_{index}_TITLE", x + 82, y + 68, 450, 42, 21, DEEP, weight="bold", valign="middle", box_y=y + 36)}
  {text(f"CARD_{index}_BODY", x + 32, y + 142, 506, 58, 17, TEXT, line_height=26)}
"""
        )
    write(
        OUT / "16_four_cards.svg",
        svg(
            f"""
{header()}
  <rect x="60" y="112" width="1160" height="70" rx="10" fill="{PALE}" stroke="{BORDER}"/>
  {text("KEY_MESSAGE", 84, 157, 1100, 44, 22, DEEP, weight="bold")}
"""
            + "".join(grid_cards)
            + footer()
        ),
    )
    write(
        OUT / "11_ending.svg",
        svg(
            f"""
  <image x="0" y="0" width="1280" height="720" preserveAspectRatio="none" href="assets/{BACKGROUND_ASSET}"/>
  <rect width="1280" height="720" fill="#16051D" opacity="0.12"/>
  {text("CLOSING_TITLE", 640, 300, 900, 100, 64, WHITE, weight="bold", anchor="middle")}
  {text("CLOSING_SUBTITLE", 640, 390, 820, 70, 26, WHITE, anchor="middle")}
  {text("CONTACT", 640, 540, 700, 40, 18, WHITE, anchor="middle")}
"""
        ),
    )


def slot(slot_id: str, kind: str, max_lines: int, max_chars: int, *, required: bool = True, line_height: int = 32) -> dict:
    return {
        "slot_id": slot_id,
        "kind": kind,
        "required": required,
        "max_lines": max_lines,
        "max_chars_per_line": max_chars,
        "line_height": line_height,
        "overflow_policy": "choose_variant_or_split",
    }


def build_contracts() -> None:
    layouts = [
        {"layout_id": "cover", "role": "cover", "svg": "01_cover.svg", "slots": [slot("TITLE", "text", 2, 18), slot("SUBTITLE", "text", 2, 30), slot("AUTHOR", "text", 1, 20), slot("DATE", "text", 1, 16), slot("HERO_IMAGE", "image", 1, 1, required=False)]},
        {"layout_id": "toc", "role": "toc", "svg": "02_toc.svg", "slots": [slot("PAGE_TITLE", "text", 1, 22), slot("SECTION", "text", 1, 12, required=False), slot("AGENDA", "list", 6, 28, line_height=67), slot("AGENDA_COUNT", "text", 1, 2), slot("SOURCE", "text", 1, 60, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "chapter", "role": "chapter", "svg": "03_chapter.svg", "slots": [slot("CHAPTER_NUM", "text", 1, 4), slot("CHAPTER_TITLE", "text", 2, 18), slot("CHAPTER_DESC", "text", 3, 34, required=False)]},
        {"layout_id": "text_focus", "role": "content", "svg": "04_text_focus.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 45), slot("BODY", "list", 7, 42, line_height=52), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "figure_left", "role": "content", "svg": "05_figure_left.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46), slot("FIGURE", "image", 1, 1), slot("CAPTION", "text", 1, 70), slot("BODY", "list", 7, 26, line_height=43), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "figure_right", "role": "content", "svg": "06_figure_right.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46), slot("BODY", "list", 7, 26, line_height=43), slot("FIGURE", "image", 1, 1), slot("CAPTION", "text", 1, 70), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "two_column", "role": "content", "svg": "07_two_column.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("LEFT_TITLE", "text", 1, 22), slot("RIGHT_TITLE", "text", 1, 22), slot("LEFT_BODY", "list", 7, 29, line_height=45), slot("RIGHT_BODY", "list", 7, 29, line_height=45), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "comparison_focus", "role": "content", "svg": "07b_comparison_focus.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46), slot("LEFT_BADGE", "text", 1, 5), slot("LEFT_TITLE", "text", 1, 18), slot("LEFT_BODY", "list", 5, 29, line_height=48), slot("RIGHT_BADGE", "text", 1, 5), slot("RIGHT_TITLE", "text", 1, 18), slot("RIGHT_BODY", "list", 5, 29, line_height=48), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "three_cards", "role": "content", "svg": "08_three_cards.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False)] + [slot(f"CARD_{i}_TITLE", "text", 2, 14) for i in range(1, 4)] + [slot(f"CARD_{i}_BODY", "list", 6, 18, line_height=39) for i in range(1, 4)] + [slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "process", "role": "content", "svg": "09_process.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False)] + [slot(f"STEP_{i}_TITLE", "text", 2, 12) for i in range(1, 5)] + [slot(f"STEP_{i}_BODY", "text", 4, 15, line_height=27) for i in range(1, 5)] + [slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "result", "role": "content", "svg": "10_result.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46), slot("FIGURE", "image", 1, 1), slot("CAPTION", "text", 1, 70)] + [slot(f"METRIC_{i}_VALUE", "text", 1, 10) for i in range(1, 4)] + [slot(f"METRIC_{i}_LABEL", "text", 2, 18) for i in range(1, 4)] + [slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "timeline", "role": "content", "svg": "12_timeline.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46)] + [slot(f"STEP_{i}_TITLE", "text", 1, 14) for i in range(1, 5)] + [slot(f"STEP_{i}_BODY", "text", 3, 18, line_height=25) for i in range(1, 5)] + [slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "quote", "role": "content", "svg": "13_quote.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("QUOTE", "text", 4, 46, line_height=48), slot("QUOTE_AUTHOR", "text", 1, 34), slot("QUOTE_SOURCE", "text", 1, 70), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "metrics", "role": "content", "svg": "14_metrics.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46)] + [slot(f"METRIC_{i}_VALUE", "text", 1, 10) for i in range(1, 5)] + [slot(f"METRIC_{i}_LABEL", "text", 2, 18) for i in range(1, 5)] + [slot("NOTE", "text", 1, 80), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "table", "role": "content", "svg": "15_table.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46)] + [slot(f"COL_{i}", "text", 1, 18) for i in range(1, 5)] + sum(([slot(f"ROW_{row}_LABEL", "text", 1, 22)] + [slot(f"ROW_{row}_VALUE_{column}", "text", 1, 16) for column in range(1, 4)] for row in range(1, 5)), []) + [slot("TABLE_NOTE", "text", 1, 80), slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "four_cards", "role": "content", "svg": "16_four_cards.svg", "slots": [slot("PAGE_TITLE", "text", 1, 26), slot("SECTION", "text", 1, 12, required=False), slot("KEY_MESSAGE", "text", 2, 46)] + sum(([slot(f"CARD_{i}_TITLE", "text", 1, 20), slot(f"CARD_{i}_BODY", "text", 2, 42, line_height=26)] for i in range(1, 5)), []) + [slot("SOURCE", "text", 1, 70, required=False), slot("PAGE_NUM", "text", 1, 4)]},
        {"layout_id": "ending", "role": "ending", "svg": "11_ending.svg", "slots": [slot("CLOSING_TITLE", "text", 1, 12), slot("CLOSING_SUBTITLE", "text", 2, 32, required=False), slot("CONTACT", "text", 1, 40, required=False)]},
    ]
    write_json(
        OUT / "layouts.json",
        {
            "schema_version": "easyslides.semantic_layouts.v1",
            "template_id": "nsfc_purple_semantic",
            "mode": "semantic",
            "canvas": {"width": 1280, "height": 720, "format": "ppt169"},
            "layouts": layouts,
        },
    )
    slot_contract_layouts = []
    for layout in layouts:
        svg_path = OUT / str(layout["svg"])
        root = ET.parse(svg_path).getroot()
        nodes = {
            str(node.attrib.get("data-slot")): node
            for node in root.iter()
            if node.attrib.get("data-slot")
        }
        details = []
        text_slots = []
        image_slots = []
        for declared in layout["slots"]:
            slot_id = str(declared["slot_id"])
            node = nodes.get(slot_id)
            if node is None:
                continue
            geometry = {}
            for key in ("x", "y", "w", "h"):
                raw = node.attrib.get(f"data-pptx-box-{key}")
                if raw is None:
                    raw = node.attrib.get({"w": "width", "h": "height"}.get(key, key))
                if raw is not None:
                    geometry[{"w": "width", "h": "height"}.get(key, key)] = float(raw)
            detail = {
                "slot_id": slot_id,
                "role": "image" if declared["kind"] == "image" else slot_id.lower(),
                "kind": declared["kind"],
                "required": declared.get("required", True),
                "max_lines": declared["max_lines"],
                "max_chars_per_line": declared["max_chars_per_line"],
                "geometry": geometry,
            }
            details.append(detail)
            (image_slots if declared["kind"] == "image" else text_slots).append(slot_id)
        slot_contract_layouts.append(
            {
                "layout_id": layout["layout_id"],
                "page_id": Path(str(layout["svg"])).stem,
                "svg_path": str(layout["svg"]),
                "slot_model": layout["layout_id"],
                "slots": [str(item["slot_id"]) for item in layout["slots"]],
                "text_slots": text_slots,
                "image_slots": image_slots,
                "replacement": "replace_declared_slots_preserve_template_geometry",
                "slot_details": details,
            }
        )
    write_json(
        OUT / "slot_contracts.json",
        {
            "schema_version": "easyslides.template_slot_contracts.v1",
            "template_id": "nsfc_purple_semantic",
            "source": "derived_from_semantic_layouts_and_named_svg_slots",
            "replacement_rule": "replace_declared_slots_preserve_template_geometry",
            "private_clone_required": False,
            "text_fit_policy": {
                "schema_version": "easyslides.template_text_fit_policy.v1",
                "overflow_strategy_order": [
                    "use_declared_capacity",
                    "choose_lower_density_variant",
                    "split_across_slides",
                    "shrink_font_with_floor",
                ],
            },
            "layouts": slot_contract_layouts,
        },
    )
    page_catalog = []
    geometry_pages = []
    compact_containers = {
        "02_toc.svg": [
            {"id": "agenda_count", "x": 1062, "y": 138, "width": 96, "height": 96, "fill": PALE, "stroke": ACCENT},
        ],
        "07b_comparison_focus.svg": [
            {"id": "left_badge", "x": 88, "y": 238, "width": 120, "height": 58, "fill": PALE, "stroke": ACCENT},
            {"id": "right_badge", "x": 688, "y": 238, "width": 120, "height": 58, "fill": PALE, "stroke": ACCENT},
        ],
    }
    for index, layout in enumerate(layouts, start=1):
        svg_name = str(layout["svg"])
        role = str(layout["role"])
        page_id = Path(svg_name).stem
        page_catalog.append(
            {
                "id": page_id,
                "source_slide": None,
                "story_role": role,
                "role_fit": [role] if role != "content" else ["content", "evidence", "explanation"],
                "density_score": 2 if role in {"cover", "chapter", "ending"} else 3,
                "best_for": f"semantic {role} page selected by role and content shape",
                "avoid": "content that exceeds declared slot capacity",
            }
        )
        geometry_pages.append(
            {
                "id": page_id,
                "svg": svg_name,
                "source_slide": None,
                "story_role": role,
                "protected_regions": [],
                "content_bounds": {"x": 0, "y": 0, "width": 1280, "height": 720},
                "containers": compact_containers.get(svg_name, []),
            }
        )
    write_json(
        OUT / "page_catalog.json",
        {
            "schema_version": "easyslides.page_catalog.v1",
            "template_id": "nsfc_purple_semantic",
            "mode": "semantic",
            "selection_policy": "role + content_shape + item_count; never source slide number",
            "pages": page_catalog,
        },
    )
    write_json(
        OUT / "geometry_contract.json",
        {
            "schema_version": "easyslides.template_geometry_contract.v1",
            "template_id": "nsfc_purple_semantic",
            "canvas": {"width": 1280, "height": 720},
            "hard_invariants": [
                "text_center_y_matches_container_center_y_for_compact_controls",
                "declared_text_boxes_stay_inside_canvas",
                "native_pptx_text_must_fit_declared_geometry",
            ],
            "pages": geometry_pages,
        },
    )
    variants = [
        {"variant_id": "text_focus", "layout_id": "text_focus", "content_shapes": ["text_focus", "supporting_points", "summary", "question"], "min_items": 1, "max_items": 7, "priority": 10},
        {"variant_id": "figure_left", "layout_id": "figure_left", "content_shapes": ["figure", "architecture", "table", "image_evidence"], "min_items": 1, "max_items": 7, "priority": 20},
        {"variant_id": "figure_right", "layout_id": "figure_right", "content_shapes": ["figure_explanation", "mechanism"], "min_items": 1, "max_items": 7, "priority": 20},
        {"variant_id": "comparison_focus", "layout_id": "comparison_focus", "content_shapes": ["comparison", "two_sides", "before_after"], "min_items": 2, "max_items": 8, "priority": 30},
        {"variant_id": "two_column", "layout_id": "two_column", "content_shapes": ["comparison", "two_sides", "before_after"], "min_items": 2, "max_items": 10, "priority": 20},
        {"variant_id": "three_cards", "layout_id": "three_cards", "content_shapes": ["three_findings", "three_contributions", "parallel_points"], "min_items": 3, "max_items": 9, "priority": 20},
        {"variant_id": "process", "layout_id": "process", "content_shapes": ["workflow", "process", "sequence"], "min_items": 4, "max_items": 8, "priority": 20},
        {"variant_id": "result", "layout_id": "result", "content_shapes": ["result", "metric_set", "benchmark"], "min_items": 1, "max_items": 6, "priority": 30},
        {"variant_id": "timeline", "layout_id": "timeline", "content_shapes": ["timeline", "milestones", "sequence_evidence"], "min_items": 3, "max_items": 6, "priority": 40},
        {"variant_id": "quote", "layout_id": "quote", "content_shapes": ["quote", "key_takeaway", "conclusion"], "min_items": 1, "max_items": 4, "priority": 40},
        {"variant_id": "metrics", "layout_id": "metrics", "content_shapes": ["metric_set", "kpi_summary", "benchmark_summary"], "min_items": 3, "max_items": 8, "priority": 40},
        {"variant_id": "table", "layout_id": "table", "content_shapes": ["table", "dataset", "benchmark_table"], "min_items": 2, "max_items": 12, "priority": 40},
        {"variant_id": "four_cards", "layout_id": "four_cards", "content_shapes": ["four_findings", "evidence_matrix", "risks_and_actions"], "min_items": 4, "max_items": 8, "priority": 40},
    ]
    write_json(
        OUT / "body_variants.json",
        {
            "schema_version": "easyslides.body_variants.v2",
            "template_id": "nsfc_purple_semantic",
            "selection_policy": "Resolve by semantic content_shape and item_count; never by source slide number.",
            "variants": variants,
        },
    )
    write_json(
        OUT / "template_status.json",
        {
            "schema_version": "easyslides.template_status.v1",
            "template_id": "nsfc_purple_semantic",
            "status": "review",
            "production_eligible": False,
            "source_template_id": "nsfc_defense_distilled",
            "promotion_policy": "fail_closed",
            "required_gates": [
                "contract",
                "template_slot_contract",
                "component_catalog",
                "svg_quality",
                "svg_text_slots",
                "template_geometry_svg",
                "asset_manifest",
                "template_geometry_pptx",
                "pptx_text_layout",
                "placeholder_scan",
                "render_diff",
                "cross_material_smoke",
                "human_visual_review",
            ],
        },
    )
    write_json(
        OUT / "template.json",
        {
            "schema_version": "easyslides.template_pack.v1",
            "template_id": "nsfc_purple_semantic",
            "display_name": "NSFC Purple Semantic",
            "availability": "semantic_template_status_gated",
            "recommended_template_route": "semantic_named_slots",
            "output_contract": "editable-native-pptx",
            "style_system": "nsfc_purple_semantic",
            "layout_source_format": "svg",
            "runtime_source_of_truth": "semantic_layouts_and_named_slots",
            "production_status_source": "template_status.json",
            "scenarios": [
                "academic_paper_report",
                "research_defense",
                "scientific_project_report",
            ],
            "roles": ["cover", "toc", "chapter", "content", "ending"],
            "layout_count": len(layouts),
            "primary_color": PRIMARY,
            "contract_sidecars": [
                "page_catalog.json",
                "geometry_contract.json",
                "spec_lock.md",
                "slot_contracts.json",
                "assets/asset_manifest.json",
                "component_catalog.json",
            ],
            "routing_policy": {
                "required_inputs": ["role", "content_shape", "item_count", "slot_payload"],
                "forbidden_inputs": ["source_slide_number", "dom_order"],
            },
        },
    )
    write(
        OUT / "design_spec.md",
        """---
template_id: nsfc_purple_semantic
canvas: ppt169
mode: semantic
category: academic_research
summary: Semantic named-slot template family for research reporting and defense decks.
keywords: academic, research, defense, semantic-layout, named-slots
primary_color: '#751497'
canvas_format: ppt169
replication_mode: semantic_named_slots
---

# NSFC Purple Semantic

A content-free semantic template family distilled from the purple NSFC reference.
It preserves the purple identity, title treatment, pale panels, rounded cards,
and restrained scientific tone without copying source slide order or content.
Cover and ending use a template-owned, content-free dark-purple decorative
background asset recorded in `assets/background_asset.json`.

Production rendering must use named `data-slot` bindings through
`scripts/semantic_template_renderer.py`. DOM-order replacement is forbidden.

## Visual language

- Primary: `#751497`; deep accent: `#4B0D65`; highlight: `#BF4BE7`.
- Surface: pale purple `#F8EAFC`, white cards, border `#E6D5EC`.
- Typography: Microsoft YaHei with bold titles, restrained body text, and no
  source-specific text, logo, figure, or background.
- Canvas: 1280 x 720 (`ppt169`), with a 72 px purple header and a 38 px footer
  band on content pages.
- Components: message bars, rounded cards, image frames, comparison badges,
  metric cards, process circles, timeline rails, quote panels, metric strips,
  table frames, four-card grids, and accent symbols are registered in
  `component_catalog.json` and indexed by `assets/asset_manifest.json`.

## Layout and content contract

Use `layouts.json`, `page_catalog.json`, and `body_variants.json` as the
machine-readable source of truth. Select content pages by semantic role,
`content_shape`, and `item_count`. Never select by source slide number or DOM
order. Every text slot declares capacity and overflow action; split or select
another variant when capacity is exceeded.

The expanded page family includes timeline/milestone, quote/key-takeaway,
metric/KPI summary, table/benchmark, and four-card evidence-matrix patterns.
These are selectable variants, not fixed source-page copies.

Compact control text is hard-locked: its text box center Y must equal its
container center Y within the geometry QA tolerance, and its vertical alignment
must be `middle`/`center`. This is a production invariant, not a styling hint.

## Promotion

The template is not production-ready until the unified gate passes contract,
SVG quality, strict SVG text slots, SVG geometry, native PPTX geometry, native
text layout, placeholder scan, visual diff, cross-material smoke, and human
visual review. See `spec_lock.md` and `rules.md`.
""",
    )
    write(
        OUT / "rules.md",
        """# Rules

- Scenario first, template second.
- Resolve content pages by `content_shape`, never by source page number.
- Every slot has an explicit capacity and overflow policy.
- Choose another variant or split the slide when capacity is exceeded.
- Prefer timeline, quote, metrics, table, or four-card variants when the
  content shape matches; do not force every argument into a two-column card.
- Use table slots for comparable rows and metric slots for independent KPIs;
  do not encode either as decorative body text.
- Source-specific text, figures, logos, and raster backgrounds are forbidden.
- A generic full-slide raster background is allowed only when it is template-owned,
  content-free, and recorded in `assets/background_asset.json`.
- A deck with any blocking QA issue is a review draft, not a final deliverable.
- `data-pptx-textbox` text must declare box geometry and `data-pptx-valign`.
- Compact control text must use `middle`/`center` and share the container center Y.
- Do not promote a template whose strict SVG text, geometry, native PPTX,
  visual-diff, or cross-material gate is missing or unresolved.
""",
    )
    write(
        OUT / "spec_lock.md",
        """# NSFC Purple Semantic Spec Lock

- Template id: `nsfc_purple_semantic`
- Source family: `nsfc_defense_distilled`
- Runtime binding: named `data-slot` only
- Canvas: 1280 x 720, `ppt169`
- Fixed identity: purple header language, pale-purple surfaces, rounded cards,
  restrained scientific typography, and template-owned cover/ending texture.
- Forbidden drift: source slide number routing, DOM-order replacement,
  source-specific text or figures, unbounded text boxes, and visibly displaced
  compact-control labels.
- Hard text rule: the center Y of compact-control text equals the center Y of
  its container within `template_geometry_qa.py` tolerance.
- Promotion authority: the latest unified promotion report, never a manually
  edited `template_status.json`.
""",
    )
    write(OUT / "assets" / "transparent.svg", f'<svg xmlns="{SVG_NS}" width="1" height="1" viewBox="0 0 1 1"><rect width="1" height="1" fill="#FFFFFF" fill-opacity="0"/></svg>')
    write_json(
        OUT / "assets" / "background_asset.json",
        {
            "schema_version": "easyslides.template_background_asset.v1",
            "asset_id": "nsfc_purple_dark_pattern",
            "asset_path": BACKGROUND_ASSET,
            "role": ["cover", "ending"],
            "content_free": True,
            "source_specific": False,
            "generated_with": "imagegen",
            "description": "Generic dark-purple abstract texture with subdued wave and line motifs.",
        },
    )


def build_assets() -> None:
    components = {
        "purple_header": f'<svg xmlns="{SVG_NS}" width="1280" height="72" viewBox="0 0 1280 72"><rect width="1280" height="72" fill="{PRIMARY}"/><rect y="68" width="1280" height="4" fill="{ACCENT}"/><path d="M1080 0H1280V72H1140L1080 0Z" fill="{DEEP}"/></svg>',
        "pale_message_bar": f'<svg xmlns="{SVG_NS}" width="1160" height="86" viewBox="0 0 1160 86"><rect width="1160" height="86" rx="12" fill="{PALE}" stroke="{BORDER}"/><rect width="8" height="86" rx="4" fill="{PRIMARY}"/></svg>',
        "rounded_card": f'<svg xmlns="{SVG_NS}" width="346" height="444" viewBox="0 0 346 444"><rect x="1" y="1" width="344" height="442" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect x="1" y="1" width="344" height="10" rx="5" fill="{PRIMARY}"/></svg>',
        "image_frame": f'<svg xmlns="{SVG_NS}" width="688" height="420" viewBox="0 0 688 420"><rect x="1" y="1" width="686" height="418" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/></svg>',
        "metric_card": f'<svg xmlns="{SVG_NS}" width="408" height="122" viewBox="0 0 408 122"><rect x="1" y="1" width="406" height="120" rx="14" fill="{PALE}" stroke="{BORDER}" stroke-width="2"/></svg>',
        "comparison_card": f'<svg xmlns="{SVG_NS}" width="560" height="420" viewBox="0 0 560 420"><rect x="1" y="1" width="558" height="418" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect x="28" y="26" width="120" height="58" rx="29" fill="{PALE}" stroke="{ACCENT}" stroke-width="2"/></svg>',
        "timeline_rail": f'<svg xmlns="{SVG_NS}" width="1160" height="100" viewBox="0 0 1160 100"><line x1="40" y1="50" x2="1110" y2="50" stroke="{ACCENT}" stroke-width="5"/><path d="M1148 50l-22-14v28Z" fill="{ACCENT}"/><circle cx="80" cy="50" r="22" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/><circle cx="400" cy="50" r="22" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/><circle cx="720" cy="50" r="22" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/><circle cx="1040" cy="50" r="22" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/></svg>',
        "quote_panel": f'<svg xmlns="{SVG_NS}" width="1104" height="388" viewBox="0 0 1104 388"><rect x="1" y="1" width="1102" height="386" rx="22" fill="{PALE}" stroke="{BORDER}" stroke-width="2"/><rect width="14" height="388" rx="7" fill="{PRIMARY}"/></svg>',
        "metric_strip": f'<svg xmlns="{SVG_NS}" width="1160" height="250" viewBox="0 0 1160 250"><rect x="1" y="1" width="1158" height="248" rx="18" fill="{PALE}" stroke="{BORDER}" stroke-width="2"/></svg>',
        "table_frame": f'<svg xmlns="{SVG_NS}" width="1140" height="384" viewBox="0 0 1140 384"><rect x="1" y="1" width="1138" height="382" rx="12" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect width="1140" height="66" rx="10" fill="{PRIMARY}"/></svg>',
        "four_card_grid": f'<svg xmlns="{SVG_NS}" width="1160" height="464" viewBox="0 0 1160 464"><rect x="1" y="1" width="568" height="212" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect x="591" y="1" width="568" height="212" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect x="1" y="251" width="568" height="212" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect x="591" y="251" width="568" height="212" rx="16" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/></svg>',
        "evidence_callout": f'<svg xmlns="{SVG_NS}" width="1160" height="86" viewBox="0 0 1160 86"><rect width="1160" height="86" rx="12" fill="{PALE}" stroke="{BORDER}"/><rect width="8" height="86" rx="4" fill="{ACCENT}"/></svg>',
    }
    symbols = {
        "arrow_right": f'<svg xmlns="{SVG_NS}" width="80" height="24" viewBox="0 0 80 24"><path d="M2 12H64" stroke="{ACCENT}" stroke-width="5"/><path d="M78 12L60 1v22Z" fill="{ACCENT}"/></svg>',
        "step_circle": f'<svg xmlns="{SVG_NS}" width="108" height="108" viewBox="0 0 108 108"><circle cx="54" cy="54" r="51" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/></svg>',
        "corner_orbit": f'<svg xmlns="{SVG_NS}" width="220" height="180" viewBox="0 0 220 180"><circle cx="150" cy="20" r="92" fill="none" stroke="{ACCENT}" stroke-width="2"/><circle cx="150" cy="20" r="56" fill="none" stroke="{PRIMARY}"/></svg>',
        "accent_rule": f'<svg xmlns="{SVG_NS}" width="96" height="8" viewBox="0 0 96 8"><rect width="96" height="8" rx="4" fill="{PRIMARY}"/></svg>',
        "timeline_node": f'<svg xmlns="{SVG_NS}" width="68" height="68" viewBox="0 0 68 68"><circle cx="34" cy="34" r="31" fill="{PALE}" stroke="{PRIMARY}" stroke-width="3"/><circle cx="34" cy="34" r="7" fill="{ACCENT}"/></svg>',
        "quote_mark": f'<svg xmlns="{SVG_NS}" width="96" height="72" viewBox="0 0 96 72"><text x="8" y="62" font-family="Georgia, serif" font-size="84" font-weight="bold" fill="{ACCENT}">“</text></svg>',
        "metric_badge": f'<svg xmlns="{SVG_NS}" width="48" height="48" viewBox="0 0 48 48"><circle cx="24" cy="24" r="22" fill="{PRIMARY}"/><path d="M15 25l6 6 13-15" fill="none" stroke="{WHITE}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "check_mark": f'<svg xmlns="{SVG_NS}" width="32" height="32" viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="{PALE}" stroke="{ACCENT}" stroke-width="2"/><path d="M9 16l5 5 9-10" fill="none" stroke="{PRIMARY}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    }
    component_selection = {
        "timeline_rail": {"content_shapes": ["timeline", "milestones", "sequence_evidence"], "page_roles": ["content"], "item_count_min": 3, "item_count_max": 6},
        "quote_panel": {"content_shapes": ["quote", "key_takeaway", "conclusion"], "page_roles": ["content"], "item_count_min": 1, "item_count_max": 4},
        "metric_strip": {"content_shapes": ["metric_set", "kpi_summary", "benchmark_summary"], "page_roles": ["content"], "item_count_min": 3, "item_count_max": 8},
        "table_frame": {"content_shapes": ["table", "dataset", "benchmark_table"], "page_roles": ["content"], "item_count_min": 2, "item_count_max": 12},
        "four_card_grid": {"content_shapes": ["four_findings", "evidence_matrix", "risks_and_actions"], "page_roles": ["content"], "item_count_min": 4, "item_count_max": 8},
        "evidence_callout": {"content_shapes": ["text_focus", "evidence", "summary"], "page_roles": ["content"], "item_count_min": 1, "item_count_max": 8},
    }
    component_rows = []
    symbol_rows = []
    for asset_id, body in components.items():
        path = KIT / "components" / f"{asset_id}.svg"
        write(path, body)
        local_path = OUT / "assets" / "components" / f"{asset_id}.svg"
        write(local_path, body)
        component_rows.append(
            {
                "asset_id": f"component/nsfc_purple_semantic/{asset_id}",
                "component_id": asset_id,
                "asset_path": local_path.relative_to(OUT).as_posix(),
                "asset_status": "renderable_svg",
                "reuse_policy": "semantic_template_component",
                "selection": component_selection.get(
                    asset_id,
                    {
                        "content_shapes": ["mixed_content", "supporting_points"],
                        "page_roles": ["content"],
                        "item_count_min": 1,
                        "item_count_max": 8,
                    },
                ),
                "qa": {
                    "required_gates": ["asset_manifest", "component_geometry", "vertical_center_alignment"],
                    "alignment_invariants": [
                        {
                            "rule": "text_center_y_matches_container_center_y",
                            "scope": "text_in_container",
                            "severity": "error",
                        }
                    ],
                },
            }
        )
    for asset_id, body in symbols.items():
        path = KIT / "symbols" / f"{asset_id}.svg"
        write(path, body)
        local_path = OUT / "assets" / "symbols" / f"{asset_id}.svg"
        write(local_path, body)
        symbol_rows.append(
            {
                "asset_id": f"symbol/nsfc_purple_semantic/{asset_id}",
                "symbol_id": asset_id,
                "asset_path": local_path.relative_to(OUT).as_posix(),
                "asset_status": "renderable_svg",
                "reuse_policy": "semantic_template_symbol",
            }
        )
    kit_component_rows = [
        {**row, "asset_path": f"components/{row['component_id']}.svg"}
        for row in component_rows
    ]
    kit_symbol_rows = [
        {**row, "asset_path": f"symbols/{row['symbol_id']}.svg"}
        for row in symbol_rows
    ]
    write_json(KIT / "component_asset_manifest.json", {"schema_version": "easyslides.source_component_assets.v2", "template_id": "nsfc_purple_semantic", "components": kit_component_rows, "review_queue": []})
    write_json(KIT / "symbol_asset_manifest.json", {"schema_version": "easyslides.source_symbol_assets.v2", "template_id": "nsfc_purple_semantic", "symbols": kit_symbol_rows, "review_queue": []})
    write_json(
        OUT / "component_catalog.json",
        {
            "schema_version": "easyslides.semantic_component_catalog.v1",
            "template_id": "nsfc_purple_semantic",
            "selection_policy": "Select by content_shape, page_role, and item_count; never source order.",
            "components": component_rows,
            "symbols": symbol_rows,
            "unknown_component_count": 0,
        },
    )
    try:
        from scripts.component_asset_manifest import materialize_asset_manifest
    except ModuleNotFoundError:  # pragma: no cover - direct script execution
        from component_asset_manifest import materialize_asset_manifest
    materialize_asset_manifest(OUT, namespace="nsfc_purple_semantic")


def main() -> int:
    build_svgs()
    build_contracts()
    build_assets()
    write_json(
        OUT / "template_package.json",
        build_package_manifest(OUT, version="0.1.0", status="review", examples=["templates/layouts/nsfc_purple_semantic"]),
    )
    print(f"Built semantic template: {OUT}")
    print(f"Built source-scoped asset kit: {KIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
