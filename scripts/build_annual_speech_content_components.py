#!/usr/bin/env python3
"""Build component-rich content-page candidates for the archived annual speech template.

The faithful ``04_content.svg`` remains untouched.  This helper creates three
development-only body variants that keep the annual speech visual tokens while
declaring reusable component assets and named text slots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


DEFAULT_TEMPLATE_DIR = Path(
    r"F:\Archive\projects\easyslides\nonlegacy-templates-20260802\templates\layouts\annual_speech_2025_distilled_5shell"
)

DEEP = "#441351"
PRIMARY = "#912C8D"
ACCENT = "#BF4BE7"
PALE = "#F8EAFC"
BORDER = "#E6D5EC"
TEXT = "#262626"
MUTED = "#6A5B70"


def _slot(
    slot_id: str,
    text: str,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    size: float,
    color: str = TEXT,
    weight: str = "normal",
    anchor: str = "start",
    box_x: float | None = None,
    box_y: float | None = None,
    box_w: float | None = None,
    box_h: float | None = None,
    letter_spacing: float | None = None,
) -> str:
    attrs = [
        'data-pptx-textbox="true"',
        f'data-pptx-box-x="{box_x if box_x is not None else x}"',
        f'data-pptx-box-y="{box_y if box_y is not None else y}"',
        f'data-pptx-box-w="{box_w if box_w is not None else width}"',
        f'data-pptx-box-h="{box_h if box_h is not None else height}"',
        'data-pptx-valign="middle"',
        f'data-slot="{slot_id}"',
        f'data-slot-id="{slot_id}"',
        'data-slot-kind="text"',
        f'data-slot-placeholder="{{{{{slot_id}}}}}"',
    ]
    if letter_spacing is not None:
        attrs.append(f'letter-spacing="{letter_spacing}px"')
    joined_attrs = " ".join(attrs)
    return (
        f'<text x="{x}" y="{y + height * 0.72}" text-anchor="{anchor}" '
        f'font-family="Microsoft YaHei, Segoe UI, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" {joined_attrs}>'
        f'<tspan fill="{color}" font-size="{size}" font-weight="{weight}">{escape(text)}</tspan></text>'
    )


def _common_open(variant_id: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" width="1280" height="720" viewBox="0 0 1280 720" data-template-variant="{variant_id}">
<defs>
  <linearGradient id="annual_component_gradient" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0.2" stop-color="{DEEP}" stop-opacity="0.08"/>
    <stop offset="0.94" stop-color="{DEEP}" stop-opacity="0.76"/>
  </linearGradient>
</defs>
<image href="assets/image6.png" x="0" y="0" width="1280" height="720" preserveAspectRatio="none"/>
<g id="annual_top_photo" data-component-id="hero_image" data-component-kind="image">
  <svg x="-0.13" y="0" width="1280" height="300" viewBox="0 0.33541 1 0.42085" preserveAspectRatio="none"><image href="assets/image7.jpeg" x="0" y="0" width="1" height="1" preserveAspectRatio="none"/></svg>
  <rect x="-0.13" y="0" width="1279.87" height="300" fill="url(#annual_component_gradient)"/>
</g>
<rect x="0" y="300" width="1280" height="420" fill="#FFFFFF"/>
<g id="annual_brand_mark" data-component-id="brand_mark" data-component-kind="image">
  <svg x="1055.04" y="36" width="185.22" height="71.65" viewBox="0 0.20586 1 0.51594" preserveAspectRatio="none"><image href="assets/image8.png" x="0" y="0" width="1" height="1" preserveAspectRatio="none"/></svg>
</g>
<g id="annual_content_header" data-component-id="content_header" data-component-kind="shell">
  {_slot("KEY_MESSAGE", "核心观点", x=61.59, y=320, width=681.22, height=30, size=19, color=DEEP, weight="bold", letter_spacing=2.2)}
  {_slot("PAGE_TITLE", "页面标题", x=58.7, y=350, width=665.64, height=58, size=46, color=TEXT, weight="bold", box_x=58.7, box_y=350, box_w=665.64, box_h=58)}
</g>
<line x1="70" y1="424" x2="1210" y2="424" stroke="{DEEP}" stroke-opacity="0.79" stroke-width="4" stroke-linecap="round"/>
'''


def _common_close() -> str:
    return f'''<g id="annual_content_meta" data-component-id="content_meta" data-component-kind="shell">
  {_slot("PRESENTER", "姓名", x=71.19, y=650, width=250, height=30, size=14, color=TEXT, weight="bold", box_x=61.59, box_y=646, box_w=280, box_h=34)}
  {_slot("DATE", "日期", x=370, y=650, width=250, height=30, size=14, color=TEXT, weight="bold", box_x=360, box_y=646, box_w=280, box_h=34)}
</g>
<rect x="0" y="701.4" width="1280" height="18.17" fill="{DEEP}"/>
</svg>
'''


def _metric_card(index: int, x: float, value: str, label: str, note: str) -> str:
    return f'''<g id="metric_card_{index:02d}" data-component-id="metric_card" data-component-asset="assets/components/annual_speech/metric_card.svg" data-component-kind="card">
  <rect x="{x}" y="450" width="350" height="126" rx="14" fill="{PALE}" stroke="{BORDER}" stroke-width="2"/>
  <rect x="{x}" y="450" width="8" height="126" rx="4" fill="{PRIMARY}"/>
  {_slot(f"METRIC_{index:02d}_VALUE", value, x=x + 24, y=464, width=118, height=40, size=27, color=PRIMARY, weight="bold", box_x=x + 18, box_y=460, box_w=130, box_h=44)}
  {_slot(f"METRIC_{index:02d}_LABEL", label, x=x + 164, y=466, width=158, height=28, size=15, color=DEEP, weight="bold", box_x=x + 154, box_y=462, box_w=174, box_h=34)}
  {_slot(f"METRIC_{index:02d}_NOTE", note, x=x + 24, y=520, width=302, height=28, size=12, color=MUTED, box_x=x + 18, box_y=514, box_w=320, box_h=34)}
</g>
'''


def _evidence_callout(label: str = "证据提示", body: str = "用一条可追溯证据收束页面结论") -> str:
    return f'''<g id="evidence_callout" data-component-id="evidence_callout" data-component-asset="assets/components/annual_speech/evidence_callout.svg" data-component-kind="callout">
  <rect x="60" y="596" width="1160" height="48" rx="12" fill="{PALE}" stroke="{BORDER}"/>
  <rect x="60" y="596" width="8" height="48" rx="4" fill="{ACCENT}"/>
  {_slot("EVIDENCE_LABEL", label, x=88, y=605, width=110, height=28, size=13, color=PRIMARY, weight="bold", box_x=82, box_y=602, box_w=122, box_h=32)}
  {_slot("EVIDENCE_TEXT", body, x=222, y=605, width=940, height=28, size=13, color=MUTED, box_x=214, box_y=602, box_w=970, box_h=32)}
</g>
'''


def build_metrics() -> str:
    return (
        _common_open("content_components_metrics")
        + '<g id="metrics_composition" data-component-id="metric_strip" data-component-asset="assets/components/annual_speech/metric_strip.svg" data-component-kind="composition">\n'
        + _metric_card(1, 60, "12项", "年度成果", "完成关键节点")
        + _metric_card(2, 445, "86%", "推进进度", "较计划稳定提升")
        + _metric_card(3, 830, "24家", "合作网络", "形成协同机制")
        + '</g>\n'
        + _evidence_callout()
        + _common_close()
    )


def _comparison_panel(index: int, x: float, title: str, body: str, accent: str) -> str:
    return f'''<g id="comparison_panel_{index:02d}" data-component-id="comparison_panel" data-component-kind="panel">
  <rect x="{x}" y="450" width="550" height="126" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <rect x="{x}" y="450" width="8" height="126" rx="4" fill="{accent}"/>
  {_slot(f"COMPARE_{index:02d}_TITLE", title, x=x + 28, y=466, width=468, height=28, size=16, color=DEEP, weight="bold", box_x=x + 24, box_y=462, box_w=482, box_h=34)}
  <line x1="{x + 28}" y1="505" x2="{x + 522}" y2="505" stroke="{BORDER}"/>
  {_slot(f"COMPARE_{index:02d}_BODY", body, x=x + 28, y=518, width=478, height=38, size=12, color=MUTED, box_x=x + 24, box_y=512, box_w=490, box_h=48)}
</g>
'''


def build_comparison() -> str:
    return (
        _common_open("content_components_comparison")
        + '<g id="comparison_composition" data-component-id="comparison_pair" data-component-asset="assets/components/annual_speech/comparison_pair.svg" data-component-kind="composition">\n'
        + _comparison_panel(1, 60, "当前基础", "已有资源形成稳定底座，重点在于统一口径。", PRIMARY)
        + _comparison_panel(2, 670, "下一步动作", "围绕关键指标推进协同，强化证据闭环。", ACCENT)
        + '</g>\n'
        + _evidence_callout("综合判断", "对比组件适合呈现现状—动作、基线—目标等双栏关系")
        + _common_close()
    )


def _matrix_card(index: int, x: float, title: str, body: str) -> str:
    return f'''<g id="matrix_card_{index:02d}" data-component-id="matrix_card" data-component-kind="card">
  <rect x="{x}" y="450" width="260" height="126" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>
  <circle cx="{x + 34}" cy="484" r="16" fill="{PALE}" stroke="{ACCENT}"/>
  <text x="{x + 34}" y="489" text-anchor="middle" font-family="Microsoft YaHei, Segoe UI, sans-serif" font-size="12" font-weight="bold" fill="{PRIMARY}">{index:02d}</text>
  {_slot(f"MATRIX_{index:02d}_TITLE", title, x=x + 62, y=469, width=170, height=28, size=14, color=DEEP, weight="bold", box_x=x + 56, box_y=462, box_w=190, box_h=34)}
  {_slot(f"MATRIX_{index:02d}_BODY", body, x=x + 20, y=520, width=220, height=34, size=12, color=MUTED, box_x=x + 16, box_y=512, box_w=228, box_h=46)}
</g>
'''


def build_matrix() -> str:
    xs = [60, 360, 660, 960]
    labels = [
        ("目标", "方向清晰"),
        ("资源", "基础扎实"),
        ("协同", "机制联动"),
        ("证据", "结果可追溯"),
    ]
    return (
        _common_open("content_components_matrix")
        + '<g id="matrix_composition" data-component-id="four_card_grid" data-component-asset="assets/components/annual_speech/four_card_grid.svg" data-component-kind="composition">\n'
        + "".join(_matrix_card(i, x, title, body) for i, (x, (title, body)) in enumerate(zip(xs, labels), start=1))
        + '</g>\n'
        + _evidence_callout("页面结论", "四卡矩阵适合把一页内容拆成并列的四个判断维度")
        + _common_close()
    )


def _component_catalog() -> dict:
    return {
        "schema_version": "easyslides.semantic_component_catalog.v1",
        "template_id": "annual_speech_2025_distilled_5shell",
        "selection_policy": "content_body_variant_then_template_scoped_component",
        "components": [
            {
                "asset_id": "component/annual_speech_2025_distilled_5shell/metric_strip",
                "component_id": "metric_strip",
                "asset_path": "assets/components/annual_speech/metric_strip.svg",
                "asset_status": "renderable_svg",
                "reuse_policy": "template_scoped_body_variant_only",
                "category": "metric_set",
                "geometry": {"width": 1160, "height": 126},
                "slots": [
                    "METRIC_01_VALUE", "METRIC_01_LABEL", "METRIC_01_NOTE",
                    "METRIC_02_VALUE", "METRIC_02_LABEL", "METRIC_02_NOTE",
                    "METRIC_03_VALUE", "METRIC_03_LABEL", "METRIC_03_NOTE",
                ],
            },
            {
                "asset_id": "component/annual_speech_2025_distilled_5shell/metric_card",
                "component_id": "metric_card",
                "asset_path": "assets/components/annual_speech/metric_card.svg",
                "asset_status": "renderable_svg",
                "reuse_policy": "template_scoped_body_variant_only",
                "category": "metric_card",
                "geometry": {"width": 350, "height": 126},
                "slots": ["VALUE", "LABEL", "NOTE"],
            },
            {
                "asset_id": "component/annual_speech_2025_distilled_5shell/comparison_pair",
                "component_id": "comparison_pair",
                "asset_path": "assets/components/annual_speech/comparison_pair.svg",
                "asset_status": "renderable_svg",
                "reuse_policy": "template_scoped_body_variant_only",
                "category": "comparison",
                "geometry": {"width": 1160, "height": 126},
                "slots": ["COMPARE_01_TITLE", "COMPARE_01_BODY", "COMPARE_02_TITLE", "COMPARE_02_BODY"],
            },
            {
                "asset_id": "component/annual_speech_2025_distilled_5shell/four_card_grid",
                "component_id": "four_card_grid",
                "asset_path": "assets/components/annual_speech/four_card_grid.svg",
                "asset_status": "renderable_svg",
                "reuse_policy": "template_scoped_body_variant_only",
                "category": "evidence_matrix",
                "geometry": {"width": 1160, "height": 126},
                "slots": [
                    "MATRIX_01_TITLE", "MATRIX_01_BODY", "MATRIX_02_TITLE", "MATRIX_02_BODY",
                    "MATRIX_03_TITLE", "MATRIX_03_BODY", "MATRIX_04_TITLE", "MATRIX_04_BODY",
                ],
            },
            {
                "asset_id": "component/annual_speech_2025_distilled_5shell/evidence_callout",
                "component_id": "evidence_callout",
                "asset_path": "assets/components/annual_speech/evidence_callout.svg",
                "asset_status": "renderable_svg",
                "reuse_policy": "template_scoped_body_variant_only",
                "category": "evidence",
                "geometry": {"width": 1160, "height": 48},
                "slots": ["EVIDENCE_LABEL", "EVIDENCE_TEXT"],
            },
        ],
        "symbols": [],
        "unknown_component_count": 0,
    }


def _body_variants(existing: dict) -> dict:
    generated_ids = {
        "content_components_metrics",
        "content_components_comparison",
        "content_components_matrix",
    }
    variants = [
        row for row in existing.get("variants", [])
        if isinstance(row, dict) and row.get("variant_id") not in generated_ids
    ]
    variants.extend(
        [
            {
                "variant_id": "content_components_metrics",
                "shell_id": "content",
                "shell": "04_content.svg",
                "preview_svg": "body_variants/04_content_components_metrics.svg",
                "source_slides": [],
                "source_page_ids": [],
                "components": {"text_slots": 13, "image_slots": 3},
                "visual_profile": "component_rich",
                "best_for": "指标摘要与证据收束",
                "selection": {"route": "canonical_shell_then_body_variant", "density": ["balanced"]},
                "composition_mode": "ordered_component_refs",
                "slots": [
                    "METRIC_01_VALUE", "METRIC_01_LABEL", "METRIC_01_NOTE",
                    "METRIC_02_VALUE", "METRIC_02_LABEL", "METRIC_02_NOTE",
                    "METRIC_03_VALUE", "METRIC_03_LABEL", "METRIC_03_NOTE",
                    "EVIDENCE_LABEL", "EVIDENCE_TEXT",
                ],
                "component_refs": [
                    {
                        "asset_id": "component/annual_speech_2025_distilled_5shell/metric_strip",
                        "instance_id": "metrics", "role": "metric_set", "order": 1, "required": True,
                        "slot_bindings": {
                            "METRIC_01_VALUE": "METRIC_01_VALUE", "METRIC_01_LABEL": "METRIC_01_LABEL", "METRIC_01_NOTE": "METRIC_01_NOTE",
                            "METRIC_02_VALUE": "METRIC_02_VALUE", "METRIC_02_LABEL": "METRIC_02_LABEL", "METRIC_02_NOTE": "METRIC_02_NOTE",
                            "METRIC_03_VALUE": "METRIC_03_VALUE", "METRIC_03_LABEL": "METRIC_03_LABEL", "METRIC_03_NOTE": "METRIC_03_NOTE",
                        },
                    },
                    {
                        "asset_id": "component/annual_speech_2025_distilled_5shell/evidence_callout",
                        "instance_id": "evidence", "role": "evidence", "order": 2, "required": True,
                        "slot_bindings": {"EVIDENCE_LABEL": "EVIDENCE_LABEL", "EVIDENCE_TEXT": "EVIDENCE_TEXT"},
                    },
                ],
                "layout_id": "content",
            },
            {
                "variant_id": "content_components_comparison",
                "shell_id": "content",
                "shell": "04_content.svg",
                "preview_svg": "body_variants/04_content_components_comparison.svg",
                "source_slides": [],
                "source_page_ids": [],
                "components": {"text_slots": 9, "image_slots": 3},
                "visual_profile": "component_rich",
                "best_for": "现状—动作或基线—目标对比",
                "selection": {"route": "canonical_shell_then_body_variant", "density": ["balanced"]},
                "composition_mode": "ordered_component_refs",
                "slots": ["COMPARE_01_TITLE", "COMPARE_01_BODY", "COMPARE_02_TITLE", "COMPARE_02_BODY", "EVIDENCE_LABEL", "EVIDENCE_TEXT"],
                "component_refs": [
                    {
                        "asset_id": "component/annual_speech_2025_distilled_5shell/comparison_pair",
                        "instance_id": "comparison", "role": "comparison", "order": 1, "required": True,
                        "slot_bindings": {
                            "COMPARE_01_TITLE": "COMPARE_01_TITLE", "COMPARE_01_BODY": "COMPARE_01_BODY",
                            "COMPARE_02_TITLE": "COMPARE_02_TITLE", "COMPARE_02_BODY": "COMPARE_02_BODY",
                        },
                    },
                    {
                        "asset_id": "component/annual_speech_2025_distilled_5shell/evidence_callout",
                        "instance_id": "evidence", "role": "evidence", "order": 2, "required": True,
                        "slot_bindings": {"EVIDENCE_LABEL": "EVIDENCE_LABEL", "EVIDENCE_TEXT": "EVIDENCE_TEXT"},
                    },
                ],
                "layout_id": "content",
            },
            {
                "variant_id": "content_components_matrix",
                "shell_id": "content",
                "shell": "04_content.svg",
                "preview_svg": "body_variants/04_content_components_matrix.svg",
                "source_slides": [],
                "source_page_ids": [],
                "components": {"text_slots": 13, "image_slots": 3},
                "visual_profile": "component_rich",
                "best_for": "四个并列判断维度或证据矩阵",
                "selection": {"route": "canonical_shell_then_body_variant", "density": ["balanced"]},
                "composition_mode": "ordered_component_refs",
                "slots": [
                    "MATRIX_01_TITLE", "MATRIX_01_BODY", "MATRIX_02_TITLE", "MATRIX_02_BODY",
                    "MATRIX_03_TITLE", "MATRIX_03_BODY", "MATRIX_04_TITLE", "MATRIX_04_BODY",
                    "EVIDENCE_LABEL", "EVIDENCE_TEXT",
                ],
                "component_refs": [
                    {
                        "asset_id": "component/annual_speech_2025_distilled_5shell/four_card_grid",
                        "instance_id": "matrix", "role": "evidence_matrix", "order": 1, "required": True,
                        "slot_bindings": {
                            "MATRIX_01_TITLE": "MATRIX_01_TITLE", "MATRIX_01_BODY": "MATRIX_01_BODY",
                            "MATRIX_02_TITLE": "MATRIX_02_TITLE", "MATRIX_02_BODY": "MATRIX_02_BODY",
                            "MATRIX_03_TITLE": "MATRIX_03_TITLE", "MATRIX_03_BODY": "MATRIX_03_BODY",
                            "MATRIX_04_TITLE": "MATRIX_04_TITLE", "MATRIX_04_BODY": "MATRIX_04_BODY",
                        },
                    },
                    {
                        "asset_id": "component/annual_speech_2025_distilled_5shell/evidence_callout",
                        "instance_id": "evidence", "role": "evidence", "order": 2, "required": True,
                        "slot_bindings": {"EVIDENCE_LABEL": "EVIDENCE_LABEL", "EVIDENCE_TEXT": "EVIDENCE_TEXT"},
                    },
                ],
                "layout_id": "content",
            },
        ]
    )
    existing["variants"] = variants
    return existing


def _write_component_assets(component_dir: Path) -> None:
    component_dir.mkdir(parents=True, exist_ok=True)
    assets = {
        "metric_strip.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="126" viewBox="0 0 1160 126"><rect width="1160" height="126" rx="14" fill="#FFFFFF" fill-opacity="0"/></svg>\n',
        "metric_card.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="350" height="126" viewBox="0 0 350 126"><rect x="1" y="1" width="348" height="124" rx="14" fill="{PALE}" stroke="{BORDER}" stroke-width="2"/><rect width="8" height="126" rx="4" fill="{PRIMARY}"/></svg>\n',
        "comparison_pair.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="126" viewBox="0 0 1160 126"><rect x="1" y="1" width="548" height="124" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect x="611" y="1" width="548" height="124" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/><rect width="8" height="126" rx="4" fill="{PRIMARY}"/><rect x="611" width="8" height="126" rx="4" fill="{ACCENT}"/></svg>\n',
        "four_card_grid.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="126" viewBox="0 0 1160 126">' + ''.join(f'<rect x="{x}" y="1" width="258" height="124" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="2"/>' for x in (1, 301, 601, 901)) + '</svg>\n',
        "evidence_callout.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="48" viewBox="0 0 1160 48"><rect width="1160" height="48" rx="12" fill="{PALE}" stroke="{BORDER}"/><rect width="8" height="48" rx="4" fill="{ACCENT}"/></svg>\n',
    }
    for name, content in assets.items():
        (component_dir / name).write_text(content, encoding="utf-8")


def build(template_dir: Path) -> dict:
    template_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "04_content_components_metrics.svg": build_metrics(),
        "04_content_components_comparison.svg": build_comparison(),
        "04_content_components_matrix.svg": build_matrix(),
    }
    preview_dir = template_dir / "body_variants"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in outputs.items():
        (preview_dir / filename).write_text(content, encoding="utf-8")
    _write_component_assets(template_dir / "assets" / "components" / "annual_speech")
    (template_dir / "component_catalog.json").write_text(
        json.dumps(_component_catalog(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    body_path = template_dir / "body_variants.json"
    existing = json.loads(body_path.read_text(encoding="utf-8-sig"))
    updated = _body_variants(existing)
    body_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "pass", "template_dir": str(template_dir), "variants": list(outputs)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.template_dir.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
