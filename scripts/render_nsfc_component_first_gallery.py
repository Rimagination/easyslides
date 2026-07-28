#!/usr/bin/env python3
"""Render one NSFC content-page example for every reviewed component scene."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.slide_compiler import compile_slides, render_slide_ir_to_pptx
    from scripts.template_compiler import compile_template
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from slide_compiler import compile_slides, render_slide_ir_to_pptx
    from template_compiler import compile_template


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "layouts" / "nsfc_defense"
SOURCE_ASSETS = ROOT / "templates" / "reference" / "template_asset_sources" / "nsfc_defense_distilled" / "assets"
IMAGE_POOL = [SOURCE_ASSETS / name for name in ("image10.jpg", "image11.webp", "image12.jpg", "image15.png", "image18.jpeg")]


def _sample_text(slot_id: str) -> str:
    if "VALUE" in slot_id:
        return "98.1%"
    if "DETAIL" in slot_id:
        return "以跨尺度数据验证机制与效应。"
    if "CONCLUSION" in slot_id:
        return "可解释判断"
    if "STATEMENT" in slot_id or "TAKEAWAY" in slot_id:
        return "监测、机制和人群证据需要形成闭环"
    if "TITLE" in slot_id:
        return "核心结果"
    if "CAPTION" in slot_id:
        return "图示证据"
    if "CONNECTOR" in slot_id:
        return "连接"
    if "COLUMN" in slot_id:
        return "比较维度"
    if "ROW" in slot_id:
        return "证据条件"
    if "LABEL" in slot_id or "TAG" in slot_id:
        return "关键证据"
    return "研究证据"


def build_plan(template_ir: dict) -> dict:
    titles = {
        "need_relationship_evidence": "需求证据闭环",
        "dual_track_evidence": "双轨研究路径",
        "evidence_chain": "关键瓶颈链条",
        "metric_dashboard": "技术指标看板",
        "three_evidence_track": "创新证据轨道",
        "comparison_evidence": "方法比较边界",
        "application_system": "系统应用链路",
        "literature_transfer": "验证与转化",
    }
    slides = []
    for index, variant in enumerate(template_ir["body_variants"], start=1):
        guidance = variant.get("source_guidance") or {}
        allowed_sections = [
            str(value)
            for value in guidance.get("sections", [])
            if str(value).strip()
        ]
        section = allowed_sections[0] if allowed_sections else str(guidance.get("section") or "")
        payload = {}
        for slot in variant["slots"]:
            slot_id = str(slot["slot_id"])
            if slot["kind"] == "image":
                payload[slot_id] = str(IMAGE_POOL[(index - 1) % len(IMAGE_POOL)])
            else:
                payload[slot_id] = _sample_text(slot_id)
        slides.append(
            {
                "page": f"G{index:02d}",
                "role": "content",
                "section": section,
                "story_role": variant["selection"]["story_roles"][0],
                "body_variant_id": variant["variant_id"],
                "shell_payload": {
                    "PAGE_TITLE": titles.get(variant["variant_id"], "内容证据页"),
                    "KEY_MESSAGE": "以可检验的证据组织研究判断",
                },
                "slot_payload": payload,
            }
        )
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "deck_id": "nsfc-component-first-gallery",
        "template_id": "nsfc_defense",
        "slides": slides,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "projects" / "nsfc_component_first_reorg_20260728")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    template_ir = compile_template(TEMPLATE)["template_ir"]
    plan = build_plan(template_ir)
    (output / "component_first_gallery_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    slide_ir = compile_slides(plan, template_ir)
    (output / "component_first_gallery_slide_ir.json").write_text(
        json.dumps(slide_ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = render_slide_ir_to_pptx(
        slide_ir,
        output / "nsfc_component_first_gallery.pptx",
        svg_output_dir=output / "svg",
    )
    (output / "component_first_gallery_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
