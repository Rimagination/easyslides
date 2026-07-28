#!/usr/bin/env python3
"""Render one editable PPTX content-page example for each research_core scene."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.build_research_core_template import ROOT, SCENES, _flatten_payload, _story_payload
    from scripts.slide_compiler import compile_slides, render_slide_ir_to_pptx
    from scripts.template_compiler import compile_template
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_research_core_template import ROOT, SCENES, _flatten_payload, _story_payload
    from slide_compiler import compile_slides, render_slide_ir_to_pptx
    from template_compiler import compile_template


TEMPLATE = ROOT / "templates" / "layouts" / "research_core"
IMAGE = ROOT / "assets" / "easyslides-github-hero.png"

TITLES = {
    "three_card_summary": "Three aligned research findings",
    "process_timeline": "Method steps make the evidence traceable",
    "figure_with_notes": "One figure should carry one defensible takeaway",
    "kpi_row_3": "Three numbers establish the result at a glance",
    "comparison_pair": "Comparison clarifies where the method improves",
    "evidence_stack": "Independent observations support the conclusion",
}


def build_plan() -> dict:
    slides = []
    for index, scene in enumerate(SCENES, start=1):
        _, source_payload = _story_payload(str(scene["component_id"]))
        body = _flatten_payload(scene, source_payload)
        if scene["component_id"] == "figure_with_notes":
            body["FIGURE_IMAGE"] = str(IMAGE)
        slides.append(
            {
                "page": f"G{index:02d}",
                "role": "content",
                "story_role": scene["story_role"],
                "body_variant_id": scene["variant_id"],
                "shell_payload": {
                    "PAGE_TITLE": TITLES[str(scene["variant_id"])],
                    "KEY_MESSAGE": "A selected scene makes the slide structure explicit before visual execution.",
                    "PAGE_NUMBER": f"{index:02d}",
                },
                "slot_payload": body,
            }
        )
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "deck_id": "research-core-template-gallery",
        "template_id": "research_core",
        "slides": slides,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "projects" / "research_core_template_20260728")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    template_ir = compile_template(TEMPLATE)["template_ir"]
    plan = build_plan()
    (output / "research_core_gallery_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    slide_ir = compile_slides(plan, template_ir)
    (output / "research_core_gallery_slide_ir.json").write_text(
        json.dumps(slide_ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = render_slide_ir_to_pptx(
        slide_ir,
        output / "research_core_gallery.pptx",
        svg_output_dir=output / "svg",
    )
    (output / "research_core_gallery_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
