#!/usr/bin/env python3
"""Render every Academic General shell and body variant as an editable PPTX."""

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
TEMPLATE = ROOT / "templates" / "layouts" / "academic_general"
FIGURE = TEMPLATE / "assets" / "figure_placeholder.svg"
DEFAULT_OUTPUT = ROOT / "output" / "academic_general_template_gallery"


def _content_shell(section: str, title: str, message: str) -> dict[str, str]:
    return {
        "SECTION_NUM": section,
        "PAGE_TITLE": title,
        "LOGO": "EASYSLIDES",
        "KEY_MESSAGE": message,
        "SOURCE": "Template preview",
        "SECTION_NAME": "Academic General",
    }


def _content_slide(
    page: str,
    section: str,
    title: str,
    message: str,
    variant: str,
    payload: dict[str, str],
) -> dict:
    return {
        "page": page,
        "role": "content",
        "body_variant_id": variant,
        "shell_payload": _content_shell(section, title, message),
        "slot_payload": payload,
    }


def build_plan() -> dict:
    slides: list[dict] = [
        {
            "page": "P01",
            "role": "cover",
            "shell_payload": {
                "LOGO": "EASYSLIDES",
                "TITLE": "Academic General",
                "SUBTITLE": "A bounded component template for research talks",
                "AUTHOR": "Template Preview",
                "ADVISOR": "Seminars, project updates, and conference talks",
                "INSTITUTION": "EasySlides",
                "DATE": "2026",
            },
        },
        {
            "page": "P02",
            "role": "toc",
            "shell_payload": {
                "LOGO": "EASYSLIDES",
                "TOC_ITEM_1_TITLE": "Question and scope",
                "TOC_ITEM_2_TITLE": "Evidence and method",
                "TOC_ITEM_3_TITLE": "Results and comparison",
                "TOC_ITEM_4_TITLE": "Decision and next step",
                "TOC_ITEM_5_TITLE": "Appendix",
                "TOC_ITEM_6_TITLE": "References",
                "TOC_ITEM_1_DESC": "What deserves attention",
                "TOC_ITEM_2_DESC": "How the claim is tested",
                "TOC_ITEM_3_DESC": "What the material shows",
                "TOC_ITEM_4_DESC": "What follows from it",
                "PAGE_NUM": "02",
            },
        },
        {
            "page": "P03",
            "role": "chapter",
            "shell_payload": {
                "CHAPTER_NUM": "01",
                "CHAPTER_TITLE": "Evidence-led reasoning",
                "CHAPTER_DESC": "Choose a page form that matches the judgment.",
                "TITLE": "Evidence-led reasoning",
            },
        },
        _content_slide(
            "P04",
            "01",
            "A figure becomes useful when its claim is explicit",
            "One visual evidence source can be paired with three concise observations.",
            "figure_evidence",
            {
                "FIGURE": str(FIGURE),
                "FIGURE_CAPTION": "Illustrative trend with two highlighted observations.",
                "EVIDENCE_01": "A clear visual anchor frames the result.",
                "EVIDENCE_02": "Each observation stays short and auditable.",
                "EVIDENCE_03": "The caption explains why the figure matters.",
            },
        ),
        _content_slide(
            "P05",
            "02",
            "Comparison separates different kinds of evidence",
            "Two approaches can be contrasted before their combined implication is stated.",
            "comparison_synthesis",
            {
                "LEFT_TITLE": "Broad coverage",
                "LEFT_BODY": "Maps reproducible patterns across a large sample.",
                "RIGHT_TITLE": "Mechanistic depth",
                "RIGHT_BODY": "Explains why a specific pattern appears in each case.",
                "SYNTHESIS": "Use both when the argument needs scale and causal explanation.",
            },
        ),
        _content_slide(
            "P06",
            "03",
            "A process page makes the reasoning sequence visible",
            "Ordered steps prevent source material from becoming an unstructured list.",
            "process_outcome",
            {
                "STEP_01_NUMBER": "01",
                "STEP_01_TITLE": "Extract",
                "STEP_01_BODY": "Keep the claims, figures, and citations from the supplied material.",
                "STEP_02_NUMBER": "02",
                "STEP_02_TITLE": "Arrange",
                "STEP_02_BODY": "Choose the reviewed page form that fits the intended judgment.",
                "STEP_03_NUMBER": "03",
                "STEP_03_TITLE": "Verify",
                "STEP_03_BODY": "Check text fit, component bounds, and editable output.",
                "SYNTHESIS": "A reliable workflow turns raw material into a defensible presentation.",
            },
        ),
        _content_slide(
            "P07",
            "04",
            "Metrics need evidence before they become conclusions",
            "A compact dashboard captures attention, then gives the reader its basis.",
            "metrics_evidence",
            {
                "METRIC_01_VALUE": "86%",
                "METRIC_01_LABEL": "Coverage",
                "METRIC_02_VALUE": "18",
                "METRIC_02_LABEL": "Studies",
                "METRIC_03_VALUE": "3.2x",
                "METRIC_03_LABEL": "Effect size",
                "EVIDENCE_01_INDEX": "01",
                "EVIDENCE_01_LABEL": "Cross-source agreement",
                "EVIDENCE_01_DETAIL": "Independent materials point toward the same mechanism.",
                "EVIDENCE_02_INDEX": "02",
                "EVIDENCE_02_LABEL": "Decision relevance",
                "EVIDENCE_02_DETAIL": "The measured change is large enough to guide the next action.",
            },
        ),
        _content_slide(
            "P08",
            "05",
            "A text-rich page should still read as an argument",
            "Dense material works when every row advances a single claim.",
            "evidence_argument",
            {
                "SYNTHESIS": "The conclusion remains visible while the supporting evidence stays inspectable.",
                "EVIDENCE_01_INDEX": "01",
                "EVIDENCE_01_LABEL": "Observation",
                "EVIDENCE_01_DETAIL": "The response appears consistently across the independent measurements.",
                "EVIDENCE_02_INDEX": "02",
                "EVIDENCE_02_LABEL": "Explanation",
                "EVIDENCE_02_DETAIL": "The proposed mechanism accounts for both direction and magnitude.",
                "EVIDENCE_03_INDEX": "03",
                "EVIDENCE_03_LABEL": "Boundary",
                "EVIDENCE_03_DETAIL": "The finding applies under the stated sampling and timing conditions.",
            },
        ),
        _content_slide(
            "P09",
            "06",
            "Decision matrix compares tradeoffs",
            "Comparable criteria make a recommendation easier to inspect and revise.",
            "table_decision",
            {
                "HEAD_01": "Option A",
                "HEAD_02": "Option B",
                "HEAD_03": "Option C",
                "ROW_01_01": "High coverage",
                "ROW_01_02": "Moderate coverage",
                "ROW_01_03": "Focused coverage",
                "ROW_02_01": "Low depth",
                "ROW_02_02": "Balanced depth",
                "ROW_02_03": "High depth",
                "ROW_03_01": "Fast setup",
                "ROW_03_02": "Moderate setup",
                "ROW_03_03": "Slow setup",
                "CONCLUSION": "Select the option that best matches the evidence needed for the decision.",
            },
        ),
        {
            "page": "P10",
            "role": "content",
            "body_variant_id": "open_component_composition",
            "shell_payload": _content_shell(
                "07",
                "Local components support a deliberate custom arrangement",
                "Explicit composition remains local, bounded, and reviewable.",
            ),
            "body_components": [
                {
                    "component_id": "metric_tile",
                    "instance_id": "components",
                    "frame": {"x": 52, "y": 135, "width": 368, "height": 190},
                    "slot_payload": {"VALUE": "9", "LABEL": "local components"},
                },
                {
                    "component_id": "metric_tile",
                    "instance_id": "variants",
                    "frame": {"x": 456, "y": 135, "width": 368, "height": 190},
                    "slot_payload": {"VALUE": "7", "LABEL": "reviewed variants"},
                },
                {
                    "component_id": "metric_tile",
                    "instance_id": "fallbacks",
                    "frame": {"x": 860, "y": 135, "width": 368, "height": 190},
                    "slot_payload": {"VALUE": "0", "LABEL": "global fallbacks"},
                },
                {
                    "component_id": "evidence_row",
                    "instance_id": "bounded_choice",
                    "frame": {"x": 52, "y": 370, "width": 1176, "height": 135},
                    "slot_payload": {
                        "INDEX": "01",
                        "LABEL": "Bounded choice",
                        "DETAIL": "Only registered Academic General components can be placed inside the body canvas.",
                    },
                },
                {
                    "component_id": "conclusion_bar",
                    "instance_id": "custom_conclusion",
                    "frame": {"x": 52, "y": 575, "width": 1176, "height": 75},
                    "slot_payload": {"SYNTHESIS": "Freedom works when the template still owns the visual language and geometry."},
                },
            ],
        },
        {
            "page": "P11",
            "role": "ending",
            "shell_payload": {
                "LOGO": "EASYSLIDES",
                "THANK_YOU": "Thank you",
                "ENDING_SUBTITLE": "A consistent shell, an evidence-led body, and editable output.",
                "CONTACT_INFO": "Template preview",
                "EMAIL": "contact@example.org",
                "INSTITUTION": "EasySlides",
                "COPYRIGHT": "Academic General",
                "PAGE_NUM": "11",
            },
        },
    ]
    return {
        "schema_version": "easyslides.deck_plan.v1",
        "deck_id": "academic-general-template-gallery",
        "template_id": "academic_general",
        "slides": slides,
    }


def render_gallery(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    template_ir = compile_template(TEMPLATE)["template_ir"]
    plan = build_plan()
    (output / "academic_general_gallery_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    slide_ir = compile_slides(plan, template_ir)
    (output / "academic_general_gallery_slide_ir.json").write_text(
        json.dumps(slide_ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = render_slide_ir_to_pptx(
        slide_ir,
        output / "academic_general_template_gallery.pptx",
        svg_output_dir=output / "svg",
    )
    (output / "academic_general_gallery_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = render_gallery(args.out.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
