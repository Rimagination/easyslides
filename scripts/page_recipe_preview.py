"""Generate renderable preview pages for PPT Master whole-page recipes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import sys
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.page_recipe import load_page_recipes, recipes


BG = "#F6F8FB"
INK = "#172033"
MUTED = "#64748B"
NAVY = "#123B5D"
TEAL = "#0F766E"
BLUE = "#2563EB"
PURPLE = "#7C3AED"
CORAL = "#EF6F5E"
GOLD = "#F2B84B"
LINE = "#D9E2EC"
SOFT_LINE = "#D8E2ED"
PANEL = "#F8FAFC"
WHITE = "#FFFFFF"
ORANGE_SOFT = "#FFF7ED"
ORANGE_LINE = "#FED7AA"
TEAL_SOFT = "#EAF7F5"
TEAL_LINE = "#B8E3DC"


@dataclass(frozen=True)
class TextSlot:
    slot_id: str
    x: float
    y: float
    w: float
    h: float
    lines: list[str]
    size: float
    fill: str = INK
    weight: str = "400"
    anchor: str = "start"


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def render_text_slot(slot: TextSlot) -> str:
    line_h = slot.size * 1.25
    anchor_x = slot.x
    if slot.anchor == "middle":
        anchor_x = slot.x + slot.w / 2
    elif slot.anchor == "end":
        anchor_x = slot.x + slot.w
    attrs = [
        f'x="{_num(anchor_x)}"',
        f'y="{_num(slot.y + slot.size)}"',
        f'text-anchor="{slot.anchor}"',
        'font-family="Microsoft YaHei, Arial"',
        f'font-size="{_num(slot.size)}"',
        f'font-weight="{slot.weight}"',
        f'fill="{slot.fill}"',
        'data-pptx-textbox="true"',
        f'data-pptx-box-x="{_num(slot.x)}"',
        f'data-pptx-box-y="{_num(slot.y)}"',
        f'data-pptx-box-w="{_num(slot.w)}"',
        f'data-pptx-box-h="{_num(slot.h)}"',
        f'data-slot-id="{slot.slot_id}"',
    ]
    tspans = [
        f'<tspan x="{_num(anchor_x)}" y="{_num(slot.y + slot.size + index * line_h)}">{line}</tspan>'
        for index, line in enumerate(slot.lines)
    ]
    return f"<text {' '.join(attrs)}>{''.join(tspans)}</text>"


def text_label(x: float, y: float, value: str, size: float = 12, fill: str = MUTED, weight: str = "400", anchor: str = "start") -> str:
    return (
        f'<text x="{_num(x)}" y="{_num(y)}" text-anchor="{anchor}" '
        f'font-family="Microsoft YaHei, Arial" font-size="{_num(size)}" '
        f'font-weight="{weight}" fill="{fill}">{value}</text>'
    )


def rect(x: float, y: float, w: float, h: float, fill: str = WHITE, stroke: str = LINE, rx: float = 10, sw: float = 1) -> str:
    return (
        f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{_num(h)}" '
        f'rx="{_num(rx)}" fill="{fill}" stroke="{stroke}" stroke-width="{_num(sw)}"/>'
    )


def circle(cx: float, cy: float, r: float, fill: str) -> str:
    return f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="{_num(r)}" fill="{fill}"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = NAVY) -> str:
    return (
        f'<path d="M{_num(x1)} {_num(y1)} L{_num(x2)} {_num(y2)}" stroke="{color}" stroke-width="3" fill="none"/>'
        f'<path d="M{_num(x2)} {_num(y2)} l-9 -6 v12 z" fill="{color}"/>'
    )


def header(title: str, subtitle: str) -> str:
    return "\n".join(
        [
            rect(0, 0, 1280, 86, NAVY, NAVY, 0),
            render_text_slot(TextSlot("title", 64, 24, 760, 44, [title], 30, WHITE, "700")),
            render_text_slot(TextSlot("subtitle", 64, 94, 760, 42, [subtitle], 14, MUTED, "400")),
            '<rect x="1128" y="30" width="88" height="28" rx="14" fill="#FFFFFF" opacity="0.16"/>',
            text_label(1172, 49, "page recipe", 12, WHITE, "400", "middle"),
        ]
    )


def wrap_svg(title: str, subtitle: str, body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">\n'
        f'<rect x="0" y="0" width="1280" height="720" fill="{BG}"/>\n'
        f"{header(title, subtitle)}\n{body}\n</svg>\n"
    )


def render_pm_overview_mosaic() -> tuple[str, str, str]:
    body: list[str] = [
        render_text_slot(TextSlot("lead", 70, 142, 520, 58, ["核心判断先行", "再用模块分解证据与行动"], 20, INK, "700")),
    ]
    cards = [
        (72, 245, 250, 124, "01", "发现", ["结构先变", "功能后降"], TEAL),
        (350, 245, 250, 124, "02", "机制", ["水分胁迫", "根系放大"], BLUE),
        (628, 245, 250, 124, "03", "证据", ["遥感样地", "相互印证"], CORAL),
        (906, 245, 250, 124, "04", "行动", ["监测阈值", "分区干预"], GOLD),
    ]
    for x, y, w, h, n, title, lines, color in cards:
        body.extend([rect(x, y, w, h, WHITE, SOFT_LINE, 10), circle(x + 31, y + 35, 19, color), text_label(x + 31, y + 41, n, 13, WHITE, "700", "middle")])
        body.append(render_text_slot(TextSlot("card_title", x + 62, y + 20, 120, 30, [title], 20, INK, "700")))
        body.append(render_text_slot(TextSlot("card_body", x + 32, y + 66, 150, 54, lines, 18, INK, "700")))
    body.extend(
        [
            rect(72, 584, 1136, 72, TEAL_SOFT, TEAL_LINE, 12),
            render_text_slot(TextSlot("synthesis", 112, 598, 560, 58, ["结论、证据、行动同屏呈现", "长内容拆页，不压缩字号"], 20, INK, "700")),
        ]
    )
    return "pm_overview_mosaic", "总览马赛克", wrap_svg("总览马赛克", "整页 recipe：不等宽模块 + synthesis band。", "\n".join(body))


def render_pm_evidence_split() -> tuple[str, str, str]:
    body = [
        rect(70, 150, 560, 410, WHITE, SOFT_LINE, 12),
        '<rect x="98" y="188" width="504" height="282" rx="12" fill="#DDEEF7" stroke="#BFD7EA"/>',
        '<circle cx="180" cy="300" r="58" fill="#99D5C9" opacity="0.72"/>',
        '<circle cx="286" cy="270" r="60" fill="#7CC3E7" opacity="0.74"/>',
        '<circle cx="406" cy="318" r="58" fill="#F3C575" opacity="0.76"/>',
        '<circle cx="512" cy="268" r="58" fill="#E8897D" opacity="0.72"/>',
        render_text_slot(TextSlot("image_caption", 108, 488, 360, 44, ["图像 / 地图 / 显微照片区域", "真实证据保持视觉主导"], 16, INK, "700")),
        rect(685, 150, 525, 410, WHITE, SOFT_LINE, 12),
        render_text_slot(TextSlot("claim_title", 724, 190, 140, 28, ["证据解释"], 18, INK, "700")),
    ]
    for i, (title, lines, color) in enumerate(
        [
            ("观察", ["边缘斑块扩大", "核心区变化滞后"], TEAL),
            ("量化", ["指数下降同步", "水分缺口上升"], BLUE),
            ("解释", ["压力先改结构", "再影响功能"], CORAL),
        ],
        start=1,
    ):
        y = 238 + (i - 1) * 90
        body.extend([rect(724, y, 52, 52, color, color, 10), text_label(750, y + 33, str(i), 18, WHITE, "700", "middle")])
        body.append(render_text_slot(TextSlot("claim_title", 800, y + 2, 80, 28, [title], 18, INK, "700")))
        body.append(render_text_slot(TextSlot("claim_body", 800, y + 32, 300, 46, lines, 16, MUTED, "400")))
    return "pm_evidence_split", "左证据右解释", wrap_svg("左证据右解释", "整页 recipe：证据视觉主导 + 解释 rail。", "\n".join(body))


def render_pm_causal_map() -> tuple[str, str, str]:
    body = [render_text_slot(TextSlot("title", 74, 142, 560, 42, ["机制链路：因果拆解"], 28, INK, "700"))]
    nodes = [
        ("外部压力", ["极端干旱", "管理扰动"], TEAL),
        ("中介过程", ["根系分配", "水分竞争"], BLUE),
        ("系统响应", ["冠层稀疏", "斑块扩张"], CORAL),
        ("管理结果", ["产量波动", "恢复成本"], GOLD),
    ]
    for i, (title, lines, color) in enumerate(nodes):
        x = 86 + i * 292
        body.extend([rect(x, 244, 220, 180, WHITE, SOFT_LINE, 12), circle(x + 34, 278, 16, color), text_label(x + 34, 284, str(i + 1), 13, WHITE, "700", "middle")])
        body.append(render_text_slot(TextSlot("node_title", x + 64, 260, 96, 28, [title], 20, INK, "700")))
        body.append(render_text_slot(TextSlot("node_body", x + 34, 318, 124, 60, lines, 22, INK, "700")))
        if i < 3:
            body.append(arrow(x + 230, 334, x + 282, 334))
    body.extend([rect(86, 500, 1108, 88, ORANGE_SOFT, ORANGE_LINE, 10), render_text_slot(TextSlot("interpretation", 120, 522, 610, 52, ["原因 → 机制 → 结果 → 建议", "复杂解释拆为短节点"], 20, INK, "700"))])
    return "pm_causal_map", "机制因果图", wrap_svg("机制因果图", "整页 recipe：节点卡 + 连接线 + 解释带。", "\n".join(body))


def render_pm_metric_dashboard() -> tuple[str, str, str]:
    body = [
        rect(70, 155, 380, 230, WHITE, SOFT_LINE, 12),
        render_text_slot(TextSlot("metric_label", 110, 194, 120, 24, ["主指标"], 15, MUTED, "700")),
        render_text_slot(TextSlot("metric", 110, 232, 180, 60, ["86%"], 46, TEAL, "700")),
        render_text_slot(TextSlot("interpretation", 110, 310, 230, 56, ["覆盖率提升", "但结构风险仍在"], 17, INK, "700")),
        rect(485, 155, 720, 230, WHITE, SOFT_LINE, 12),
    ]
    for i, (metric, label, color) in enumerate([("17", "异常斑块", CORAL), ("3.2x", "风险增幅", BLUE), ("42", "监测样地", GOLD)]):
        x = 525 + i * 220
        body.append(rect(x, 205, 170, 118, PANEL, SOFT_LINE, 10))
        body.append(render_text_slot(TextSlot("metric", x + 24, 222, 95, 52, [metric], 38, color, "700")))
        body.append(render_text_slot(TextSlot("metric_label", x + 24, 286, 100, 24, [label], 15, INK, "700")))
    body.extend([rect(70, 420, 1135, 155, WHITE, SOFT_LINE, 12), render_text_slot(TextSlot("interpretation", 110, 454, 780, 72, ["先用主指标抓住注意力", "再用解释面板说明局部风险与行动"], 20, INK, "700"))])
    return "pm_metric_dashboard", "指标仪表盘", wrap_svg("指标仪表盘", "整页 recipe：主指标 + 辅助指标 + 解释区。", "\n".join(body))


def render_pm_comparison_matrix() -> tuple[str, str, str]:
    body = [
        render_text_slot(TextSlot("title", 70, 142, 610, 38, ["四象限比较：风险与收益"], 28, INK, "700")),
        '<line x1="640" y1="202" x2="640" y2="570" stroke="#D9E2EC" stroke-width="2"/>',
        '<line x1="128" y1="386" x2="1152" y2="386" stroke="#D9E2EC" stroke-width="2"/>',
        render_text_slot(TextSlot("axis_x", 570, 600, 140, 22, ["预期收益"], 14, MUTED, "700", "middle")),
        render_text_slot(TextSlot("axis_y", 42, 374, 120, 22, ["实施风险"], 14, MUTED, "700")),
    ]
    quads = [
        (150, 224, "高收益低风险", ["优先执行"], TEAL),
        (682, 224, "高收益高风险", ["小范围试点"], CORAL),
        (150, 414, "低收益低风险", ["自动化监测"], BLUE),
        (682, 414, "低收益高风险", ["暂缓投入"], MUTED),
    ]
    for x, y, title, lines, color in quads:
        body.append(rect(x, y, 420, 128, WHITE, SOFT_LINE, 10))
        body.append(f'<rect x="{x}" y="{y}" width="10" height="128" rx="5" fill="{color}"/>')
        body.append(render_text_slot(TextSlot("quadrant_title", x + 34, y + 28, 190, 30, [title], 20, INK, "700")))
        body.append(render_text_slot(TextSlot("quadrant_body", x + 34, y + 72, 170, 46, lines, 17, color, "700")))
    return "pm_comparison_matrix", "四象限比较", wrap_svg("四象限比较", "整页 recipe：两轴比较 + 四个决策区。", "\n".join(body))


def render_pm_process_roadmap() -> tuple[str, str, str]:
    body = [render_text_slot(TextSlot("title", 74, 142, 520, 38, ["路线流程：从输入到输出"], 28, INK, "700"))]
    steps = [("数据接入", ["遥感序列", "样地观测"], TEAL), ("特征提取", ["变量筛选", "指数计算"], BLUE), ("模型校准", ["拟合检验", "误差分析"], PURPLE), ("策略输出", ["风险区划", "触发阈值"], CORAL)]
    for i, (title, lines, color) in enumerate(steps):
        x = 110 + i * 280
        y = 235 if i % 2 == 0 else 305
        body.extend([rect(x, y, 190, 118, WHITE, SOFT_LINE, 12), circle(x + 34, y + 35, 18, color), text_label(x + 34, y + 41, f"S{i+1}", 12, WHITE, "700", "middle")])
        body.append(render_text_slot(TextSlot("step", x + 65, y + 22, 95, 28, [title], 18, INK, "700")))
        body.append(render_text_slot(TextSlot("step_detail", x + 34, y + 66, 128, 44, lines, 15, MUTED, "400")))
        if i < 3:
            body.append(arrow(x + 200, y + 60, x + 270, (305 if i % 2 == 0 else 235) + 60, CORAL))
    body.extend([rect(120, 545, 1040, 62, NAVY, NAVY, 31), render_text_slot(TextSlot("output", 360, 562, 560, 26, ["输出：可执行的分区管理建议"], 18, WHITE, "700", "middle"))])
    return "pm_process_roadmap", "路线流程图", wrap_svg("路线流程图", "整页 recipe：错落流程 + 阶段连接。", "\n".join(body))


def render_pm_argument_stack() -> tuple[str, str, str]:
    body = [
        rect(75, 150, 460, 410, WHITE, SOFT_LINE, 12),
        render_text_slot(TextSlot("claim", 115, 210, 310, 118, ["核心主张", "结构变化早于", "功能退化"], 24, INK, "700")),
        rect(585, 150, 625, 410, WHITE, SOFT_LINE, 12),
    ]
    rows = [("证据一", ["时间序列显示", "异常提前出现"], TEAL), ("证据二", ["样地观测支持", "局部风险集中"], BLUE), ("推论", ["先监测阈值", "再分区干预"], CORAL)]
    for i, (title, lines, color) in enumerate(rows):
        y = 205 + i * 105
        body.extend([rect(625, y, 520, 74, PANEL, SOFT_LINE, 10), circle(655, y + 37, 15, color)])
        body.append(render_text_slot(TextSlot("evidence_title", 690, y + 16, 130, 26, [title], 18, INK, "700")))
        body.append(render_text_slot(TextSlot("evidence_body", 690, y + 40, 310, 40, lines, 15, MUTED, "400")))
    return "pm_argument_stack", "论证堆叠", wrap_svg("论证堆叠", "整页 recipe：主张突出 + 证据层层推进。", "\n".join(body))


def render_pm_takeaway_panel() -> tuple[str, str, str]:
    body = [rect(84, 160, 1090, 410, WHITE, SOFT_LINE, 12)]
    rows = [("先看结构", ["平均值会掩盖风险"], TEAL), ("证据成组", ["图像模型互相支撑"], BLUE), ("阈值行动", ["给出触发条件"], CORAL), ("容量前置", ["超量内容先拆页"], GOLD)]
    for i, (title, lines, color) in enumerate(rows):
        y = 218 + i * 78
        body.extend([circle(140, y + 14, 22, color), text_label(140, y + 20, f"{i+1:02d}", 14, WHITE, "700", "middle")])
        body.append(render_text_slot(TextSlot("takeaway_title", 182, y - 4, 230, 30, [title], 21, INK, "700")))
        body.append(render_text_slot(TextSlot("takeaway_body", 182, y + 30, 360, 26, lines, 16, MUTED, "400")))
        if i < 3:
            body.append(f'<line x1="182" y1="{y+58}" x2="1110" y2="{y+58}" stroke="{LINE}"/>')
    body.extend([rect(260, 610, 760, 46, NAVY, NAVY, 23), render_text_slot(TextSlot("action", 410, 622, 460, 24, ["布局是可验证的内容容器"], 18, WHITE, "700", "middle"))])
    return "pm_takeaway_panel", "结论建议面板", wrap_svg("结论建议面板", "整页 recipe：编号结论 + 行动提示。", "\n".join(body))


RENDERERS: dict[str, Callable[[], tuple[str, str, str]]] = {
    "pm_overview_mosaic": render_pm_overview_mosaic,
    "pm_evidence_split": render_pm_evidence_split,
    "pm_causal_map": render_pm_causal_map,
    "pm_metric_dashboard": render_pm_metric_dashboard,
    "pm_comparison_matrix": render_pm_comparison_matrix,
    "pm_process_roadmap": render_pm_process_roadmap,
    "pm_argument_stack": render_pm_argument_stack,
    "pm_takeaway_panel": render_pm_takeaway_panel,
}


def build_preview_project(output_dir: str | Path, *, clean: bool = True) -> Path:
    project = Path(output_dir)
    if project.exists() and clean:
        shutil.rmtree(project)
    for rel in ["sources", "images", "templates", "svg_output", "notes", "exports", "reports"]:
        (project / rel).mkdir(parents=True, exist_ok=True)

    registry = load_page_recipes()
    recipe_ids = [recipe["recipe_id"] for recipe in recipes(registry)]
    notes: list[str] = []
    for index, recipe_id in enumerate(recipe_ids, start=1):
        renderer = RENDERERS[recipe_id]
        stem, title, svg = renderer()
        svg_name = f"{index:02d}_{stem}.svg"
        (project / "svg_output" / svg_name).write_text(svg, encoding="utf-8")
        notes.append(f"# {Path(svg_name).stem}\n\n{title} page recipe preview.\n")

    (project / "notes" / "total.md").write_text("\n---\n\n".join(notes), encoding="utf-8")
    (project / "project_info.json").write_text(json.dumps({"name": "page_recipe_preview", "format": "ppt169"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (project / "design_spec.md").write_text("# PPT Master Page Recipe Preview\n\nEight whole-page layout recipes rendered as editable SVG pages.\n", encoding="utf-8")
    color_values = {
        "background": BG,
        "ink": INK,
        "muted": MUTED,
        "navy": NAVY,
        "teal": TEAL,
        "blue": BLUE,
        "purple": PURPLE,
        "coral": CORAL,
        "gold": GOLD,
        "line": LINE,
        "soft_line": SOFT_LINE,
        "panel": PANEL,
        "white": WHITE,
        "orange_soft": ORANGE_SOFT,
        "orange_line": ORANGE_LINE,
        "teal_soft": TEAL_SOFT,
        "teal_line": TEAL_LINE,
        "evidence_bg": "#DDEEF7",
        "evidence_line": "#BFD7EA",
        "blob_green": "#99D5C9",
        "blob_blue": "#7CC3E7",
        "blob_gold": "#F3C575",
        "blob_coral": "#E8897D",
    }
    color_lines = "\n".join(f"- {key}: {value}" for key, value in color_values.items())
    spec_lock = (
        "# Spec Lock\n\n"
        "## canvas\n"
        "- width: 1280\n"
        "- height: 720\n"
        "- route: ppt_master_page_recipe_preview\n\n"
        "## colors\n"
        f"{color_lines}\n\n"
        "## typography\n"
        "- font_family: Microsoft YaHei, Arial\n"
        "- title: 30\n"
        "- body: 20\n"
        "- caption: 14\n"
    )
    (project / "spec_lock.md").write_text(spec_lock, encoding="utf-8")
    (project / "deck_execution_lock.json").write_text(json.dumps({"mode": "ppt_master_page_recipe_preview", "pages": recipe_ids}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a PPT Master page recipe preview project.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "outputs" / "page_recipe_preview_project"))
    parser.add_argument("--no-clean", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project = build_preview_project(args.output_dir, clean=not args.no_clean)
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
