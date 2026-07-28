"""Build a visual regression deck for the source-like NSFC body variants."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]

DISPLAY_NAMES = {
    "evidence_triptych": "证据三联",
    "two_track_evidence": "双轨证据",
    "bottleneck_chain": "瓶颈链路",
    "hotspot_metrics": "热点指标",
    "hotspot_panels": "热点拼板",
    "innovation_evidence": "创新证据",
    "ann_snn_comparison": "方法比较",
    "plasticity_training": "机制训练",
    "network_architecture": "系统架构",
    "sensor_application": "应用管线",
    "literature_result": "外部验证",
    "application_benefits": "应用效益",
}

PURPLE = (117, 20, 151)
RED = (192, 0, 0)
BLUE = (38, 104, 176)
GREEN = (20, 140, 112)
LAVENDER = (248, 234, 252)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (960, 560), "white")
    return image, ImageDraw.Draw(image)


def _save_chart(path: Path, kind: str) -> None:
    image, draw = _canvas()
    if kind == "curve":
        draw.rectangle((70, 44, 900, 500), outline=PURPLE, width=5)
        draw.line((120, 430, 840, 430), fill=(80, 80, 80), width=3)
        draw.line((120, 430, 120, 90), fill=(80, 80, 80), width=3)
        points = [(120 + index * 70, int(420 - 280 * (1 - math.exp(-index / 3)))) for index in range(11)]
        draw.line(points, fill=RED, width=8)
        draw.line([(x, min(430, y + 54)) for x, y in points], fill=BLUE, width=6)
        for x, y in points[::2]:
            draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=RED)
    elif kind == "network":
        columns = [(150, 4), (430, 6), (720, 3)]
        nodes: list[tuple[int, int]] = []
        for x, count in columns:
            column = [(x, 100 + index * (340 // max(1, count - 1))) for index in range(count)]
            nodes.append(column)
        for source in nodes[0]:
            for target in nodes[1]:
                draw.line((*source, *target), fill=(190, 160, 205), width=3)
        for source in nodes[1]:
            for target in nodes[2]:
                draw.line((*source, *target), fill=(190, 160, 205), width=3)
        for group, color in zip(nodes, (PURPLE, BLUE, RED)):
            for x, y in group:
                draw.ellipse((x - 22, y - 22, x + 22, y + 22), fill=color, outline="white", width=3)
    elif kind == "heatmap":
        for row in range(9):
            for col in range(14):
                intensity = (row * 19 + col * 11) % 100
                color = (240 - intensity, 230 - intensity // 2, 255 - intensity // 3)
                x, y = 90 + col * 54, 60 + row * 48
                draw.rectangle((x, y, x + 48, y + 42), fill=color, outline="white")
        draw.line((100, 470, 840, 120), fill=RED, width=7)
    elif kind == "micro":
        draw.rectangle((0, 0, 960, 560), fill=(25, 40, 75))
        for index in range(42):
            x = 70 + (index * 107) % 820
            y = 50 + (index * 73) % 420
            radius = 12 + (index * 7) % 32
            color = (120 + (index * 11) % 90, 50 + (index * 17) % 100, 170 + (index * 13) % 70)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=5)
    elif kind == "device":
        draw.rectangle((60, 70, 900, 470), outline=PURPLE, width=5)
        for index, color in enumerate((PURPLE, BLUE, GREEN, RED)):
            x = 140 + index * 176
            draw.rounded_rectangle((x, 120, x + 110, 390), radius=12, fill=color)
            draw.rectangle((x + 14, 156, x + 96, 350), fill="white")
        draw.line((120, 428, 840, 428), fill=(70, 70, 70), width=4)
    else:
        draw.rectangle((60, 60, 900, 500), outline=PURPLE, width=5)
        points = [(130, 410), (280, 270), (470, 340), (640, 160), (820, 230)]
        draw.line(points, fill=PURPLE, width=8)
        for x, y in points:
            draw.ellipse((x - 25, y - 25, x + 25, y + 25), fill=RED, outline="white", width=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _ensure_figures(figure_dir: Path) -> list[Path]:
    figures = [
        ("response_curve.png", "curve"),
        ("network_architecture.png", "network"),
        ("spatial_signal.png", "heatmap"),
        ("material_micrograph.png", "micro"),
        ("sensor_device.png", "device"),
        ("evidence_pathway.png", "pathway"),
    ]
    paths: list[Path] = []
    for name, kind in figures:
        path = figure_dir / name
        _save_chart(path, kind)
        paths.append(path.resolve())
    return paths


def _value(slot_id: str, variant_id: str, index: int) -> str:
    exact = {
        "CLAIM": "国家需求正在推动低功耗智能感知技术演进",
        "RELATION_LEFT": "环境感知\n多源数据",
        "RELATION_RIGHT": "类脑计算\n闭环决策",
        "CALLOUT_TITLE": "关键挑战",
        "CALLOUT_BODY": "复杂环境中，信号随时间漂移，传统模型难以同时兼顾精度、功耗与可解释性。",
        "SYNTHESIS": "以可校准器件连接感知、计算与决策，形成可验证的技术闭环。",
        "TRACK_01_TITLE": "科学问题与机理路径",
        "TRACK_02_TITLE": "工程应用与系统路径",
        "TRACK_01_TAKEAWAY": "从材料响应中提炼稳定的可学习表征。",
        "TRACK_02_TAKEAWAY": "将低功耗感知直接转译为场景决策能力。",
        "CONCLUSION": "形成从证据、机理到系统验证的连续研究链路。",
        "BOTTLENECK": "现有器件响应不稳定，限制实时学习与工程部署",
        "THEME_TITLE": "研究热点: 可校准神经形态感知",
        "THEME_BODY": "围绕器件响应、事件编码和系统协同，研究正在从单点性能走向端到端效能。",
        "TRANSITION": "性能突破需要同时回答速度、能耗、稳定性与泛化能力。",
        "PANEL_01_TITLE": "材料与器件",
        "PANEL_02_TITLE": "感知与编码",
        "PANEL_03_TITLE": "系统与应用",
        "PANEL_01_BODY": "通过可逆调控获得稳定响应窗口。",
        "PANEL_02_BODY": "用事件驱动编码保留关键动态变化。",
        "PANEL_03_BODY": "将器件特性映射为可部署的系统能力。",
        "INNOVATION_CLAIM": "创新不止替代模型，而是建立材料、算法与系统的协同设计路线。",
        "SUPPORTING_LINE": "以可解释的器件行为支持可验证的智能决策。",
        "TABLE_TITLE": "模型选择不是替代关系，而是面向任务的性能匹配",
        "COLUMN_01": "维度",
        "COLUMN_02": "ANN",
        "COLUMN_03": "SNN",
        "OBJECTIVE_TITLE": "目标解法",
        "OBJECTIVE_BODY": "以事件驱动的表示减少冗余计算，并保留动态响应中的关键时间信息。",
        "POINT_01": "训练规则应与器件响应曲线协同设计",
        "POINT_02": "非线性和可塑性决定可学习窗口",
        "ANN_LABEL": "连续激活模型",
        "SNN_LABEL": "事件驱动模型",
        "CALLOUT_TITLE": "训练映射",
        "CALLOUT_BODY": "通过脉冲幅值、宽度和频率控制，将器件状态更新映射为稳定的学习规则。",
        "ARCHITECTURE_CLAIM": "从器件方程到网络架构，再到硬件执行的统一设计",
        "FORMULA": "state(t+1) = f(input, state)",
        "MODULE_TITLE": "网络模块",
        "MODULE_BODY": "将器件状态、局部连接和时序信号压缩为可训练的网络单元。",
        "HARDWARE_TITLE": "硬件执行路径",
        "APPLICATION_CLAIM": "将校准感知神经元嵌入真实场景，形成感知到响应的闭环应用。",
        "LEFT_TITLE": "校准感知单元",
        "RIGHT_TITLE": "多模态应用系统",
        "PROFILE_NAME": "领域合作研究团队",
        "PROFILE_CREDENTIAL": "外部文献与同行结果\n提供独立验证证据",
        "PROFILE_QUOTE": "关键结论在不同材料体系与任务设置中得到复现。",
        "VALIDATION_TITLE": "论文与数据证据",
        "VALIDATION_BODY": "以公开发表结果和可复现实验，对方法边界和优势进行交叉验证。",
        "RESULT_TITLE": "外部评价",
        "RESULT_BODY": "结果表明，系统在动态条件下保持可解释的性能增益。",
        "TRANSFER_CLAIM": "从实验室原型走向可部署的低功耗环境感知方案",
        "TRANSFER_BODY": "通过标准化封装、接口设计和应用验证，将核心技术转化为可评价、可复用的工程能力。",
        "RESULT_TITLE": "应用结果",
        "RESULT_BODY": "在复杂环境测试中保持稳定响应与快速报警能力。",
    }
    if slot_id in exact:
        return exact[slot_id]
    if slot_id.startswith("TRACK_01_POINT_"):
        return ["机理识别", "参数校准", "稳定性验证"][int(slot_id[-1]) - 1]
    if slot_id.startswith("TRACK_02_CALLOUT"):
        return "应用优势" if slot_id.endswith("TITLE") else "面向连续监测任务，建立低延迟、低功耗和可维护的部署策略。"
    if slot_id.startswith("NODE_"):
        return f"证据 {slot_id[-2:]}: 关键限制"
    if slot_id.startswith("STEP_"):
        return f"步骤 {slot_id[-2:]}\n协同设计"
    if slot_id.startswith("ROW_"):
        row = int(slot_id[4:6])
        column = slot_id.rsplit("_", 1)[-1]
        values = {
            "LABEL": ["信息表示", "时间动态", "计算模式", "部署目标"],
            "ANN": ["连续值", "弱时序", "密集计算", "高精度拟合"],
            "SNN": ["离散脉冲", "强时序", "事件计算", "低功耗响应"],
        }
        return values[column][row - 1]
    if slot_id.startswith("METRIC_") and slot_id.endswith("VALUE"):
        metric_index = int(slot_id.split("_")[1]) - 1
        return ["98.1%", "115 fJ", "1.2 ms", "10^9"][metric_index]
    if slot_id.startswith("METRIC_") and slot_id.endswith("LABEL"):
        metric_index = int(slot_id.split("_")[1]) - 1
        return ["识别准确率", "单次能耗", "响应延迟", "等效操作数"][metric_index]
    if slot_id.startswith("STAGE_"):
        return f"阶段 {slot_id[-2:]}\n信号处理"
    if slot_id.startswith("LEFT_NODE_"):
        return ["传感输入", "自适应校准", "事件输出"][int(slot_id[-1]) - 1]
    if slot_id.startswith("RIGHT_NODE_"):
        return ["融合编码", "状态判断", "反馈控制"][int(slot_id[-1]) - 1]
    if slot_id.startswith("TAG_"):
        return ["封装", "接口", "标定", "验证"][int(slot_id[-1]) - 1]
    if slot_id.endswith("CAPTION"):
        return "代表性实验结果"
    return f"{DISPLAY_NAMES.get(variant_id, variant_id)} 证据 {index:02d}"


def _payload(variant: dict[str, Any], figures: list[Path]) -> dict[str, str]:
    payload: dict[str, str] = {}
    figure_index = 0
    variant_id = str(variant["variant_id"])
    for index, slot in enumerate(variant.get("slots", []), start=1):
        slot_id = str(slot["slot_id"])
        if slot.get("kind") == "image":
            payload[slot_id] = str(figures[figure_index % len(figures)])
            figure_index += 1
        else:
            payload[slot_id] = _value(slot_id, variant_id, index)
    return payload


def build_plan(template_dir: Path, figure_dir: Path) -> dict[str, Any]:
    template = json.loads((template_dir / "template.json").read_text(encoding="utf-8"))
    variants = json.loads((template_dir / "body_variants.json").read_text(encoding="utf-8"))["variants"]
    figures = _ensure_figures(figure_dir)
    slides: list[dict[str, Any]] = []
    for index, variant in enumerate(variants, start=1):
        variant_id = str(variant["variant_id"])
        slides.append(
            {
                "page": f"BV{index:02d}",
                "role": "content",
                "section": str(variant["section"]),
                "story_role": str(variant["story_roles"][0]),
                "body_variant_id": variant_id,
                "shell_payload": {"PAGE_TITLE": f"V{index:02d} {DISPLAY_NAMES[variant_id]}"},
                "slot_payload": _payload(variant, figures),
            }
        )
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "deck_id": f"{template['template_id']}-source-like-body-variant-audit",
        "template_id": template["template_id"],
        "slides": slides,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a visual source-like body-variant audit deck plan.")
    parser.add_argument("--template", default="nsfc_defense")
    parser.add_argument("--out", required=True)
    parser.add_argument("--figure-dir", required=True)
    args = parser.parse_args()
    template_dir = (ROOT / "templates" / "layouts" / args.template).resolve()
    output = Path(args.out).resolve()
    plan = build_plan(template_dir, Path(args.figure_dir).resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "template_id": args.template, "slide_count": len(plan["slides"]), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
