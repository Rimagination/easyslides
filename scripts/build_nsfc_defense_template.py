#!/usr/bin/env python3
"""Build the canonical nsfc_defense template from the distilled NSFC deck.

The source deck is used as a page-geometry reference. Visible source text and
content figures become named slots, while the repeated scientific background,
cover treatment, header motif, and page-specific compositions are retained.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from nsfc_source_like_body_variants import (
    BODY_VARIANTS as SOURCE_LIKE_BODY_VARIANTS,
    COMPONENTS as SOURCE_LIKE_COMPONENTS,
    COMPONENT_TOKENS,
    COMPOSITION_PROFILES as SOURCE_LIKE_COMPOSITION_PROFILES,
    PRIMITIVE_CATALOG,
    VARIANT_RECIPES,
    component_slots as source_like_component_slots,
    primitive_asset_manifest,
    render_component_svg as render_source_like_component_svg,
    render_primitive_svg,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "templates" / "reference" / "template_asset_sources" / "nsfc_defense_distilled"
OUT = ROOT / "templates" / "layouts" / "nsfc_defense"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

COMMON_SOURCE_ASSETS = {
    "image1_fx_1bd44e6e.webp",  # repeated neuron texture
    "image2.png",  # cover/ending campus wash
    "image3_fx_5b7698dc.jpeg",  # cover/ending purple sky
    "image4.png",  # cover/ending bird motif
    "image5.png",  # cover/ending bird motif
    "image6.png",  # cover/ending mask
    "image7.png",  # cover/ending cloud mask
    "image8.png",  # cover/ending cloud mask
    "image9.jpg",  # repeated circuit header motif
}

PAGE_META: dict[int, dict[str, Any]] = {
    1: {"id": "01_cover", "role": "cover", "archetype": "cover", "section": ""},
    2: {"id": "02_agenda", "role": "agenda", "archetype": "section_roadmap", "section": ""},
    3: {"id": "03_need_triptych", "role": "content", "archetype": "national_need_evidence_triptych", "section": "01"},
    4: {"id": "04_need_two_track", "role": "content", "archetype": "national_need_two_track", "section": "01"},
    5: {"id": "05_bottleneck_chain", "role": "content", "archetype": "bottleneck_evidence_chain", "section": "01"},
    6: {"id": "06_hotspot_metrics", "role": "content", "archetype": "research_hotspot_metrics", "section": "01"},
    7: {"id": "07_hotspot_panels", "role": "content", "archetype": "research_hotspot_panels", "section": "01"},
    8: {"id": "08_chapter_innovation", "role": "chapter", "archetype": "chapter_divider", "section": "02"},
    9: {"id": "09_innovation_evidence", "role": "content", "archetype": "innovation_three_evidence", "section": "02"},
    10: {"id": "10_ann_snn_compare", "role": "content", "archetype": "ann_snn_comparison", "section": "02"},
    11: {"id": "11_plasticity_training", "role": "content", "archetype": "nonlinearity_training", "section": "02"},
    12: {"id": "12_network_architecture", "role": "content", "archetype": "network_architecture", "section": "02"},
    13: {"id": "13_sensor_application", "role": "content", "archetype": "calibrated_sensor_application", "section": "02"},
    14: {"id": "14_literature_result", "role": "content", "archetype": "international_literature_result", "section": "02"},
    15: {"id": "15_chapter_application", "role": "chapter", "archetype": "chapter_divider", "section": "03"},
    16: {"id": "16_application_benefits", "role": "content", "archetype": "application_metrics_impact", "section": "03"},
    17: {"id": "17_ending", "role": "ending", "archetype": "ending", "section": ""},
}

SHELLS: dict[str, dict[str, Any]] = {
    "cover": {"id": "01_cover", "source_slide": 1, "role": "cover", "archetype": "cover"},
    "toc": {"id": "02_toc", "source_slide": 2, "role": "toc", "archetype": "section_roadmap"},
    "chapter": {"id": "03_chapter", "source_slide": 8, "role": "chapter", "archetype": "chapter_divider"},
    "content": {"id": "04_content", "source_slide": 3, "role": "content", "archetype": "evidence_triptych_default"},
    "ending": {"id": "05_ending", "source_slide": 17, "role": "ending", "archetype": "ending"},
}

# Source shells mix editable values with fixed field labels. Keep that
# distinction explicit: DATE is a single value, while the three nearby labels
# describe its peer fields. Use the shared title/date vocabulary where it
# applies so this template interoperates with the rest of the catalog.
SHELL_TEXT_SPECS: dict[int, dict[int, dict[str, Any]]] = {
    1: {
        1: {"slot_id": "TITLE", "role": "project_title", "required": True},
        2: {"slot_id": "PROJECT_TYPE", "role": "project_type"},
        3: {"slot_id": "SUBTITLE", "role": "presentation_subtitle"},
        4: {"static": True, "role": "affiliation_label"},
        5: {"slot_id": "AFFILIATION", "role": "affiliation"},
        6: {"static": True, "role": "presenter_label"},
        7: {"slot_id": "PRESENTER", "role": "presenter"},
        8: {"static": True, "role": "presentation_date_label"},
        9: {"slot_id": "DATE", "role": "presentation_date"},
    },
    2: {
        1: {"slot_id": "TOC_ITEM_01_TITLE", "role": "toc_item_title"},
        2: {"static": True, "role": "toc_item_index"},
        3: {"slot_id": "TOC_ITEM_02_TITLE", "role": "toc_item_title"},
        4: {"static": True, "role": "toc_item_index"},
        5: {"slot_id": "TOC_ITEM_03_TITLE", "role": "toc_item_title"},
        6: {"static": True, "role": "toc_item_index"},
        7: {"static": True, "role": "toc_side_label", "preserve_source_geometry": True},
    },
    17: {
        1: {"slot_id": "CLOSING_TITLE", "role": "closing_title", "required": True},
        2: {"slot_id": "CLOSING_SUBTITLE", "role": "closing_subtitle"},
        3: {"static": True, "role": "affiliation_label"},
        4: {"slot_id": "AFFILIATION", "role": "affiliation"},
        5: {"static": True, "role": "presenter_label"},
        6: {"slot_id": "PRESENTER", "role": "presenter"},
        7: {"static": True, "role": "presentation_date_label"},
        8: {"slot_id": "DATE", "role": "presentation_date"},
    },
}

# The content shell owns only the NSFC chrome and the title. Every body variant
# composes its own scene inside this neutral canvas instead of inheriting the
# source slide's evidence grid.
CONTENT_BODY_CANVAS = {"x": 64.0, "y": 116.0, "width": 1152.0, "height": 548.0}
CONTENT_CLEAR_REGION = {"x": 0.0, "y": 100.0, "width": 1280.0, "height": 620.0}


LEGACY_COMPOSITION_PROFILES: dict[str, dict[str, Any]] = {
    "triptych_board": {
        "scene": "parallel_evidence_board",
        "regions": [
            ("claim", (0.025, 0.02, 0.95, 0.10), 30),
            ("main", (0.025, 0.17, 0.95, 0.72), 10),
            ("caption", (0.69, 0.91, 0.27, 0.08), 40),
        ],
        "component_regions": {
            "key_point_bar": "claim",
            "evidence_triptych": "main",
            "image_caption_strip": "caption",
        },
    },
    "two_track_scene": {
        "scene": "dual_track_evidence",
        "regions": [
            ("main", (0.025, 0.17, 0.95, 0.62), 10),
            ("emphasis", (0.72, 0.04, 0.24, 0.10), 30),
            ("caption", (0.025, 0.84, 0.33, 0.09), 40),
        ],
        "component_regions": {
            "two_track_evidence": "main",
            "red_emphasis": "emphasis",
            "image_caption_strip": "caption",
        },
    },
    "bottleneck_story": {
        "scene": "claim_to_bottleneck_chain",
        "regions": [
            ("claim", (0.025, 0.03, 0.60, 0.10), 30),
            ("emphasis", (0.65, 0.03, 0.30, 0.10), 30),
            ("main", (0.025, 0.20, 0.95, 0.58), 10),
        ],
        "component_regions": {
            "key_point_bar": "claim",
            "red_emphasis": "emphasis",
            "bottleneck_chain": "main",
        },
    },
    "metric_aside": {
        "scene": "metric_led_hotspot",
        "regions": [
            ("main", (0.025, 0.14, 0.62, 0.70), 10),
            ("emphasis", (0.68, 0.14, 0.27, 0.14), 20),
            ("caption", (0.68, 0.84, 0.27, 0.09), 40),
        ],
        "component_regions": {
            "hotspot_metrics": "main",
            "red_emphasis": "emphasis",
            "image_caption_strip": "caption",
        },
    },
    "panel_footer": {
        "scene": "multi_panel_synthesis",
        "regions": [
            ("main", (0.025, 0.14, 0.95, 0.62), 10),
            ("caption", (0.025, 0.80, 0.35, 0.10), 40),
            ("emphasis", (0.70, 0.80, 0.27, 0.10), 40),
        ],
        "component_regions": {
            "hotspot_panels": "main",
            "image_caption_strip": "caption",
            "red_emphasis": "emphasis",
        },
    },
    "innovation_aside": {
        "scene": "innovation_with_takeaway",
        "regions": [
            ("main", (0.025, 0.18, 0.72, 0.68), 10),
            ("emphasis", (0.77, 0.27, 0.20, 0.10), 30),
            ("caption", (0.025, 0.88, 0.28, 0.08), 40),
        ],
        "component_regions": {
            "innovation_evidence": "main",
            "red_emphasis": "emphasis",
            "image_caption_strip": "caption",
        },
    },
    "comparison_focus": {
        "scene": "comparison_focal_plane",
        "regions": [
            ("main", (0.025, 0.13, 0.95, 0.66), 10),
            ("emphasis", (0.35, 0.84, 0.30, 0.10), 40),
        ],
        "component_regions": {
            "ann_snn_comparison": "main",
            "red_emphasis": "emphasis",
        },
    },
    "training_flow": {
        "scene": "claim_to_training_flow",
        "regions": [
            ("claim", (0.025, 0.03, 0.95, 0.10), 30),
            ("main", (0.025, 0.19, 0.95, 0.60), 10),
            ("emphasis", (0.025, 0.84, 0.28, 0.10), 40),
        ],
        "component_regions": {
            "key_point_bar": "claim",
            "architecture_flow": "main",
            "red_emphasis": "emphasis",
        },
    },
    "architecture_footer": {
        "scene": "architecture_with_annotations",
        "regions": [
            ("main", (0.025, 0.13, 0.95, 0.65), 10),
            ("caption", (0.025, 0.84, 0.36, 0.10), 40),
            ("emphasis", (0.72, 0.84, 0.23, 0.10), 40),
        ],
        "component_regions": {
            "architecture_flow": "main",
            "image_caption_strip": "caption",
            "red_emphasis": "emphasis",
        },
    },
    "split_application": {
        "scene": "dual_exhibit_application",
        "regions": [
            ("primary", (0.025, 0.16, 0.44, 0.66), 10),
            ("secondary", (0.51, 0.16, 0.44, 0.66), 11),
            ("caption", (0.34, 0.86, 0.32, 0.09), 40),
        ],
        "component_regions": {
            "two_track_evidence": "primary",
            "application_metrics": "secondary",
            "image_caption_strip": "caption",
        },
    },
    "literature_aside": {
        "scene": "literature_validation_aside",
        "regions": [
            ("main", (0.025, 0.14, 0.64, 0.70), 10),
            ("emphasis", (0.72, 0.20, 0.23, 0.13), 30),
            ("caption", (0.025, 0.87, 0.32, 0.08), 40),
        ],
        "component_regions": {
            "literature_result": "main",
            "red_emphasis": "emphasis",
            "image_caption_strip": "caption",
        },
    },
    "benefit_stack": {
        "scene": "application_impact_stack",
        "regions": [
            ("main", (0.025, 0.16, 0.58, 0.68), 10),
            ("emphasis", (0.65, 0.27, 0.30, 0.17), 30),
            ("caption", (0.65, 0.63, 0.30, 0.09), 40),
        ],
        "component_regions": {
            "application_metrics": "main",
            "red_emphasis": "emphasis",
            "image_caption_strip": "caption",
        },
    },
}

LEGACY_BODY_VARIANTS: list[dict[str, Any]] = [
    {
        "variant_id": "evidence_triptych",
        "source_slides": [3],
        "section": "01",
        "story_roles": ["national_need_evidence"],
        "narrative_step": 1,
        "source_page_purpose": "Establish the national strategic need with three converging evidence streams.",
        "density": 4,
        "best_for": "three parallel exhibits establishing national need or research evidence",
        "components": ["key_point_bar", "evidence_triptych", "image_caption_strip"],
        "composition_profile": "triptych_board",
        "figure_count": 3,
    },
    {
        "variant_id": "two_track_evidence",
        "source_slides": [4],
        "section": "01",
        "story_roles": ["strategic_need_two_track"],
        "narrative_step": 2,
        "source_page_purpose": "Connect the strategic need to two concrete research and application tracks.",
        "density": 4,
        "best_for": "two research tracks, comparison across scales, or two evidence pathways",
        "components": ["two_track_evidence", "image_caption_strip", "red_emphasis"],
        "composition_profile": "two_track_scene",
        "figure_count": 2,
    },
    {
        "variant_id": "bottleneck_chain",
        "source_slides": [5],
        "section": "01",
        "story_roles": ["scientific_bottleneck"],
        "narrative_step": 3,
        "source_page_purpose": "Explain the material and mechanism bottlenecks that justify the research intervention.",
        "density": 4,
        "best_for": "problem to bottleneck to research intervention chains",
        "components": ["bottleneck_chain", "key_point_bar", "red_emphasis"],
        "composition_profile": "bottleneck_story",
        "figure_count": 4,
    },
    {
        "variant_id": "hotspot_metrics",
        "source_slides": [6],
        "section": "01",
        "story_roles": ["research_hotspot_metrics"],
        "narrative_step": 4,
        "source_page_purpose": "Use performance metrics and representative exhibits to map the research hotspot.",
        "density": 4,
        "best_for": "research hotspot pages with four quantitative indicators and exhibits",
        "components": ["hotspot_metrics", "red_emphasis", "image_caption_strip"],
        "composition_profile": "metric_aside",
        "figure_count": 3,
    },
    {
        "variant_id": "hotspot_panels",
        "source_slides": [7],
        "section": "01",
        "story_roles": ["research_hotspot_synthesis"],
        "narrative_step": 5,
        "source_page_purpose": "Synthesize multiple hotspot directions into a linked multi-panel research landscape.",
        "density": 4,
        "best_for": "three-column research hotspot synthesis with a dominant center exhibit",
        "components": ["hotspot_panels", "image_caption_strip", "red_emphasis"],
        "composition_profile": "panel_footer",
        "figure_count": 4,
    },
    {
        "variant_id": "innovation_evidence",
        "source_slides": [9],
        "section": "02",
        "story_roles": ["innovation_overview"],
        "narrative_step": 1,
        "source_page_purpose": "State the innovation package before expanding the individual technical routes.",
        "density": 4,
        "best_for": "innovation statement supported by three material, device, or system exhibits",
        "components": ["innovation_evidence", "image_caption_strip", "red_emphasis"],
        "composition_profile": "innovation_aside",
        "figure_count": 3,
    },
    {
        "variant_id": "ann_snn_comparison",
        "source_slides": [10],
        "section": "02",
        "story_roles": ["method_comparison"],
        "narrative_step": 2,
        "source_page_purpose": "Compare ANN and SNN approaches and establish the method-selection rationale.",
        "density": 5,
        "best_for": "baseline comparison, ANN/SNN distinction, or method matrix",
        "components": ["ann_snn_comparison", "red_emphasis"],
        "composition_profile": "comparison_focus",
        "figure_count": 2,
    },
    {
        "variant_id": "plasticity_training",
        "source_slides": [11],
        "section": "02",
        "story_roles": ["device_mechanism_training"],
        "narrative_step": 3,
        "source_page_purpose": "Link device nonlinearity and plasticity to the training mechanism and observed behavior.",
        "density": 5,
        "best_for": "nonlinearity, plasticity, training rule, or algorithm-to-device explanation",
        "components": ["architecture_flow", "key_point_bar", "red_emphasis"],
        "composition_profile": "training_flow",
        "figure_count": 3,
    },
    {
        "variant_id": "network_architecture",
        "source_slides": [12],
        "section": "02",
        "story_roles": ["system_architecture"],
        "narrative_step": 4,
        "source_page_purpose": "Explain the layered memristive network architecture, signals, and hardware flow.",
        "density": 5,
        "best_for": "equations, layered network architecture, and hardware or data flow",
        "components": ["architecture_flow", "image_caption_strip", "red_emphasis"],
        "composition_profile": "architecture_footer",
        "figure_count": 3,
    },
    {
        "variant_id": "sensor_application",
        "source_slides": [13],
        "section": "02",
        "story_roles": ["application_pipeline"],
        "narrative_step": 5,
        "source_page_purpose": "Demonstrate how the calibrated sensing neuron becomes an application pipeline.",
        "density": 4,
        "best_for": "calibrated sensor, device array, or application pipeline evidence",
        "components": ["two_track_evidence", "application_metrics", "image_caption_strip"],
        "composition_profile": "split_application",
        "figure_count": 3,
    },
    {
        "variant_id": "literature_result",
        "source_slides": [14],
        "section": "02",
        "story_roles": ["external_validation"],
        "narrative_step": 6,
        "source_page_purpose": "Ground the technical contribution in an external literature or publication result.",
        "density": 3,
        "best_for": "international literature, researcher profile, or external validation result",
        "components": ["literature_result", "image_caption_strip", "red_emphasis"],
        "composition_profile": "literature_aside",
        "figure_count": 4,
    },
    {
        "variant_id": "application_benefits",
        "source_slides": [16],
        "section": "03",
        "story_roles": ["impact_and_benefits"],
        "narrative_step": 1,
        "source_page_purpose": "Close the scientific story with application metrics, transfer evidence, and societal benefit.",
        "density": 4,
        "best_for": "application metrics, social benefits, transfer outcomes, or closing evidence",
        "components": ["application_metrics", "red_emphasis", "image_caption_strip"],
        "composition_profile": "benefit_stack",
        "figure_count": 3,
    },
]

LEGACY_COMPONENTS = {
    "nsfc_header": (1280, 80, "purple header with right-side circuit motif"),
    "section_roadmap": (640, 430, "three-stage agenda with active section"),
    "chapter_divider": (640, 430, "large section number and active roadmap"),
    "key_point_bar": (1120, 86, "white bordered claim bar with red emphasis"),
    "evidence_triptych": (1120, 430, "three exhibit panels with caption strips"),
    "two_track_evidence": (1120, 430, "two parallel research tracks with figure evidence"),
    "bottleneck_chain": (1120, 430, "problem chain with sequential evidence nodes"),
    "hotspot_metrics": (1120, 430, "research hotspot, exhibit, and four KPI cells"),
    "hotspot_panels": (1120, 430, "three evidence columns with arrows and figures"),
    "innovation_evidence": (1120, 430, "innovation claim plus three evidence panels"),
    "ann_snn_comparison": (1120, 520, "comparison table plus objective and two exhibits"),
    "architecture_flow": (1120, 520, "equation, layered network, and hardware flow"),
    "literature_result": (1120, 430, "researcher/profile, paper evidence, and outcome"),
    "application_metrics": (1120, 520, "application case with two metrics and impact exhibit"),
    "image_caption_strip": (320, 54, "purple image caption strip"),
    "red_emphasis": (240, 54, "red conclusion or metric emphasis"),
}

LEGACY_SMALL_COMPONENTS = {"key_point_bar", "image_caption_strip", "red_emphasis"}

# V2 replaces the earlier generic component combinations with a source-like
# scene per content variant. The legacy declarations above remain only as
# provenance for the first distilled draft; all emitted assets use this
# canonical evidence-first grammar.
BODY_VARIANTS = SOURCE_LIKE_BODY_VARIANTS
COMPONENTS = SOURCE_LIKE_COMPONENTS
COMPOSITION_PROFILES = SOURCE_LIKE_COMPOSITION_PROFILES
SMALL_COMPONENTS: set[str] = set()


def _component_slots(component_id: str, width: int, height: int) -> list[dict[str, Any]]:
    source_like_slots = source_like_component_slots(component_id)
    if source_like_slots is not None:
        return source_like_slots
    if component_id == "nsfc_header":
        return []
    if component_id in SMALL_COMPONENTS:
        slot_id = "TEXT"
        box = {"x": 18.0, "y": 6.0, "width": float(width - 36), "height": float(max(36, height - 12))}
        return [
            {
                "slot_id": slot_id,
                "kind": "text",
                "required": True,
                "geometry": box,
                "capacity": {
                    "max_lines": 1,
                    "max_chars_per_line": 42 if component_id == "key_point_bar" else 20,
                    "overflow_action": "choose_variant_or_split",
                },
                "vertical_anchor": "middle",
            }
        ]
    if component_id == "ann_snn_comparison":
        return [
            {
                "slot_id": "TITLE",
                "kind": "text",
                "required": True,
                "geometry": {"x": 24.0, "y": 4.0, "width": float(width - 48), "height": 48.0},
                "capacity": {"max_lines": 1, "max_chars_per_line": 28, "overflow_action": "choose_variant_or_split"},
                "vertical_anchor": "middle",
            },
            {
                "slot_id": "BASELINE_TITLE",
                "kind": "text",
                "required": True,
                "geometry": {"x": 42.0, "y": 86.0, "width": 470.0, "height": 38.0},
                "capacity": {"max_lines": 1, "max_chars_per_line": 16, "overflow_action": "choose_variant_or_split"},
                "vertical_anchor": "middle",
            },
            {
                "slot_id": "BASELINE_BODY",
                "kind": "text",
                "required": True,
                "geometry": {"x": 42.0, "y": 306.0, "width": 470.0, "height": 56.0},
                "capacity": {"max_lines": 2, "max_chars_per_line": 24, "overflow_action": "choose_variant_or_split"},
                "vertical_anchor": "middle",
            },
            {
                "slot_id": "FIGURE_01",
                "kind": "image",
                "required": False,
                "geometry": {"x": 48.0, "y": 132.0, "width": 458.0, "height": 162.0},
                "image_fit": "contain",
            },
            {
                "slot_id": "EVENT_TITLE",
                "kind": "text",
                "required": True,
                "geometry": {"x": 608.0, "y": 86.0, "width": 470.0, "height": 38.0},
                "capacity": {"max_lines": 1, "max_chars_per_line": 16, "overflow_action": "choose_variant_or_split"},
                "vertical_anchor": "middle",
            },
            {
                "slot_id": "EVENT_BODY",
                "kind": "text",
                "required": True,
                "geometry": {"x": 608.0, "y": 306.0, "width": 470.0, "height": 56.0},
                "capacity": {"max_lines": 2, "max_chars_per_line": 24, "overflow_action": "choose_variant_or_split"},
                "vertical_anchor": "middle",
            },
            {
                "slot_id": "FIGURE_02",
                "kind": "image",
                "required": False,
                "geometry": {"x": 614.0, "y": 132.0, "width": 458.0, "height": 162.0},
                "image_fit": "contain",
            },
            {
                "slot_id": "SYNTHESIS",
                "kind": "text",
                "required": True,
                "geometry": {"x": 72.0, "y": 424.0, "width": 976.0, "height": 64.0},
                "capacity": {"max_lines": 1, "max_chars_per_line": 42, "overflow_action": "choose_variant_or_split"},
                "vertical_anchor": "middle",
            },
        ]
    body_y = min(72.0, float(height) * 0.18)
    return [
        {
            "slot_id": "TITLE",
            "kind": "text",
            "required": True,
            "geometry": {"x": 24.0, "y": 4.0, "width": float(width - 48), "height": float(min(48, height * 0.13))},
            "capacity": {"max_lines": 1, "max_chars_per_line": 28, "overflow_action": "choose_variant_or_split"},
            "vertical_anchor": "middle",
        },
        {
            "slot_id": "BODY",
            "kind": "text",
            "required": True,
            "geometry": {
                "x": 36.0,
                "y": body_y + 12.0,
                "width": float(width - 72),
                "height": float(max(48, height - body_y - 38)),
            },
            "capacity": {"max_lines": 5, "max_chars_per_line": 42, "overflow_action": "choose_variant_or_split"},
            "vertical_anchor": "middle",
        },
    ]


def _composition_profile(variant: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(variant.get("composition_profile") or "")
    profile = COMPOSITION_PROFILES.get(profile_id)
    if profile is None:
        raise ValueError(f"body variant {variant.get('variant_id')!r} has no composition profile")
    return profile


def _canvas_frame(normalized: tuple[float, float, float, float]) -> dict[str, float]:
    x, y, width, height = normalized
    return {
        "x": round(CONTENT_BODY_CANVAS["x"] + x * CONTENT_BODY_CANVAS["width"], 2),
        "y": round(CONTENT_BODY_CANVAS["y"] + y * CONTENT_BODY_CANVAS["height"], 2),
        "width": round(width * CONTENT_BODY_CANVAS["width"], 2),
        "height": round(height * CONTENT_BODY_CANVAS["height"], 2),
    }


def _variant_regions(variant: dict[str, Any]) -> list[dict[str, Any]]:
    """Materialize a distinct composition scene inside the open body canvas."""
    profile = _composition_profile(variant)
    return [
        {
            "region_id": region_id,
            "frame": _canvas_frame(normalized),
            "coordinate_space": "body_canvas",
            "normalized_frame": {
                "x": normalized[0],
                "y": normalized[1],
                "width": normalized[2],
                "height": normalized[3],
            },
            "z_index": z_index,
            "fit": "contain",
        }
        for region_id, normalized, z_index in profile["regions"]
    ]


def _variant_slots_and_bindings(
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], dict[str, str]]:
    slots: list[dict[str, Any]] = []
    bindings: dict[str, dict[str, str]] = {}
    regions: dict[str, str] = {}
    profile = _composition_profile(variant)
    large_index = 0
    for component_id in variant.get("components", []):
        width, height, _description = COMPONENTS[component_id]
        component_slots = _component_slots(component_id, width, height)
        if component_id == "key_point_bar":
            prefix, region_id = "CLAIM", "claim"
        elif component_id == "image_caption_strip":
            prefix, region_id = "CAPTION", "caption"
        elif component_id == "red_emphasis":
            prefix, region_id = "EMPHASIS", "emphasis"
        else:
            large_index += 1
            # A body variant now owns one complete source-like scene. Expose
            # its semantic local names directly so a deck plan can express
            # FIGURE_01, STEP_02, or METRIC_01_VALUE instead of opaque
            # PRIMARY_* indirection.
            prefix = "" if len([item for item in variant.get("components", []) if item not in SMALL_COMPONENTS]) == 1 else ("PRIMARY" if large_index == 1 else f"SECONDARY_{large_index - 1}")
            region_id = "main" if len([item for item in variant.get("components", []) if item not in SMALL_COMPONENTS]) == 1 else ("primary" if large_index == 1 else "secondary")
        profile_region = str(profile["component_regions"].get(component_id) or "")
        if not profile_region:
            raise ValueError(
                f"composition profile {variant.get('composition_profile')!r} does not place {component_id!r}"
            )
        region_id = profile_region
        instance_bindings: dict[str, str] = {}
        for component_slot in component_slots:
            component_slot_id = str(component_slot["slot_id"])
            target_slot = (
                component_slot_id
                if not prefix
                else prefix if component_slot_id == "TEXT" else f"{prefix}_{component_slot_id}"
            )
            slots.append(
                {
                    "slot_id": target_slot,
                    "kind": component_slot.get("kind", "text"),
                    "required": bool(component_slot.get("required", True)),
                    "capacity": component_slot.get("capacity", {}),
                }
            )
            instance_bindings[component_slot_id] = target_slot
        bindings[component_id] = instance_bindings
        regions[component_id] = region_id
    return slots, bindings, regions


def _component_role(component_id: str, variant_id: str) -> str:
    if component_id == variant_id:
        return "primary_body"
    return {
        "key_point_bar": "claim",
        "image_caption_strip": "caption",
        "red_emphasis": "emphasis",
        "application_metrics": "metrics",
        "architecture_flow": "primary_body",
        "two_track_evidence": "primary_body",
    }.get(component_id, "supporting_evidence")


def _variant_component_refs(variant: dict[str, Any]) -> list[dict[str, Any]]:
    _slots, bindings, regions = _variant_slots_and_bindings(variant)
    return [
        {
            "asset_id": f"component/nsfc_defense/{component_id}",
            "instance_id": component_id,
            "role": _component_role(component_id, str(variant["variant_id"])),
            "order": index,
            "required": True,
            "region": regions[component_id],
            "slot_bindings": bindings[component_id],
        }
        for index, component_id in enumerate(variant.get("components", []), start=1)
    ]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _basename(href: str) -> str:
    return href.replace("\\", "/").rsplit("/", 1)[-1]


def _box(node: ET.Element, parent: ET.Element | None = None) -> dict[str, float]:
    x = node.get("data-pptx-box-x")
    y = node.get("data-pptx-box-y")
    w = node.get("data-pptx-box-w")
    h = node.get("data-pptx-box-h")
    if all(value is not None for value in (x, y, w, h)):
        return {"x": _float(x), "y": _float(y), "width": _float(w), "height": _float(h)}
    if parent is not None:
        text_children = [child for child in list(parent) if _local(child.tag) == "text"]
        rects = [
            child
            for child in list(parent)
            if _local(child.tag) == "rect"
            and all(child.get(key) is not None for key in ("x", "y", "width", "height"))
            and child.get("fill") == "none"
        ]
        if rects and len(text_children) == 1:
            rect = rects[0]
            return {
                "x": _float(rect.get("x")),
                "y": _float(rect.get("y")),
                "width": _float(rect.get("width")),
                "height": _float(rect.get("height")),
            }
    text = "".join(node.itertext()).strip()
    font_size = _float(node.get("font-size"), 24.0)
    has_cjk = any("\u3400" <= char <= "\u9fff" for char in text)
    char_width = font_size if has_cjk else font_size * 0.62
    width = max(20.0, min(320.0, max(1, len(text)) * char_width + font_size * 0.5))
    anchor = (node.get("text-anchor") or "start").lower()
    x = _float(node.get("x"))
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    return {
        "x": x,
        "y": max(0.0, _float(node.get("y")) - _float(node.get("font-size"), 24.0)),
        "width": width,
        "height": max(24.0, font_size * 1.3),
    }


def _page_candidates(distilled: dict[str, Any], index: int, kind: str) -> list[dict[str, Any]]:
    rows = [
        item
        for item in distilled.get("slot_candidates", [])
        if isinstance(item, dict)
        and int(item.get("source_slide") or 0) == index
        and str(item.get("kind") or "") == kind
    ]
    return rows


def _capacity(name: str, candidate: dict[str, Any] | None) -> dict[str, Any]:
    source = candidate.get("capacity") if isinstance(candidate, dict) else {}
    source = source if isinstance(source, dict) else {}
    if name in {"TITLE", "CLOSING_TITLE", "CHAPTER_TITLE"}:
        default_lines, default_chars = 2, 28
    elif name in {"PROJECT_TYPE", "SUBTITLE"}:
        default_lines, default_chars = 2, 28
    elif name in {"AFFILIATION", "PRESENTER", "DATE"}:
        default_lines, default_chars = 1, 16
    elif name.startswith("TOC_ITEM_"):
        default_lines, default_chars = 1, 22
    elif name.startswith("PAGE_TITLE"):
        default_lines, default_chars = 1, 24
    elif name.startswith("KEY_MESSAGE") or name.startswith("BODY_TEXT"):
        default_lines, default_chars = 3, 32
    else:
        default_lines, default_chars = 2, 24
    return {
        "max_lines": int(source.get("lines") or default_lines),
        "max_chars_per_line": int(source.get("max_chars_per_line") or default_chars),
        "overflow_action": "split_or_choose_page_variant",
    }


def _center_text_node(node: ET.Element, box: dict[str, float], *, source_line_count: int) -> None:
    font_size = _float(node.get("font-size"), 24.0)
    line_height_ratio = max(0.75, min(1.25, box["height"] / max(1.0, font_size * source_line_count)))
    # The native renderer reads data-pptx-box-* only for explicit text boxes.
    # Without this flag it auto-sizes from the glyphs and silently breaks the
    # declared vertical-center invariant.
    node.set("data-pptx-textbox", "true")
    node.set("data-center-lock", "true")
    node.set("data-pptx-valign", "middle")
    node.set("data-pptx-box-x", f"{box['x']:.2f}")
    node.set("data-pptx-box-y", f"{box['y']:.2f}")
    node.set("data-pptx-box-w", f"{box['width']:.2f}")
    node.set("data-pptx-box-h", f"{box['height']:.2f}")
    node.set("data-pptx-measure-text", "T")
    node.set("data-pptx-line-height-ratio", f"{line_height_ratio:.3f}")
    anchor = node.get("text-anchor") or "start"
    node.set("data-pptx-text-anchor", anchor)
    if anchor == "middle":
        node.set("x", f"{box['x'] + box['width'] / 2:.2f}")
    elif anchor == "end":
        node.set("x", f"{box['x'] + box['width']:.2f}")
    else:
        node.set("x", f"{box['x']:.2f}")
    center_y = box["y"] + box["height"] / 2
    node.set("y", f"{center_y + font_size * 0.35:.2f}")


def _placeholder_text(node: ET.Element, slot_id: str, box: dict[str, float]) -> None:
    source_line_count = max(1, sum(1 for child in list(node) if _local(child.tag) == "tspan"))
    font_size = _float(node.get("font-size"), 24.0)
    if slot_id == "TITLE":
        label = "项目名称"
    elif slot_id == "PROJECT_TYPE":
        label = "项目类别"
    elif slot_id == "SUBTITLE":
        label = "答辩主题"
    elif slot_id == "AFFILIATION":
        label = "单位名称"
    elif slot_id == "PRESENTER":
        label = "汇报人"
    elif slot_id == "DATE":
        label = "汇报日期"
    elif slot_id.startswith("TOC_ITEM_"):
        label = "章节标题"
    elif slot_id == "CHAPTER_TITLE":
        label = "章节标题"
    elif slot_id == "CHAPTER_DESC":
        label = "章节说明"
    elif slot_id == "CLOSING_TITLE":
        label = "致谢"
    elif slot_id == "CLOSING_SUBTITLE":
        label = "致意"
    elif slot_id.startswith("PAGE_TITLE"):
        label = "页面标题"
    elif slot_id.startswith("BODY_TEXT_"):
        label = "B" + slot_id.rsplit("_", 1)[-1]
    elif slot_id.startswith("KEY_MESSAGE"):
        label = "KEY"
    elif slot_id.startswith(("SUBTITLE", "CHAPTER_DESC")):
        label = "SUB"
    elif slot_id.startswith("CONTACT"):
        label = "CONTACT"
    elif slot_id.startswith("DATE"):
        label = "DATE"
    else:
        label = "T"
    if len(label) * font_size * 0.62 > box["width"] * 0.82:
        label = label[:1]
    for child in list(node):
        node.remove(child)
    node.text = label
    node.set("data-slot", slot_id)
    node.set("data-slot-id", slot_id)
    node.set("data-slot-kind", "text")
    node.set("data-slot-placeholder", "{{" + slot_id + "}}")
    _center_text_node(node, box, source_line_count=source_line_count)


def _lock_static_text(node: ET.Element, box: dict[str, float], role: str) -> None:
    """Preserve source labels as fixed chrome while applying the text invariant."""
    source_text = "".join(node.itertext()).strip()
    source_line_count = max(1, sum(1 for child in list(node) if _local(child.tag) == "tspan"))
    for child in list(node):
        node.remove(child)
    node.text = source_text
    for key in ("data-slot", "data-slot-id", "data-slot-kind", "data-slot-placeholder"):
        node.attrib.pop(key, None)
    node.set("data-easyslides-static-text", "true")
    node.set("data-easyslides-static-role", role)
    _center_text_node(node, box, source_line_count=source_line_count)


def _preserve_static_source_text(node: ET.Element, role: str) -> None:
    """Keep decorative source text fixed while giving it an explicit text frame."""
    for key in ("data-slot", "data-slot-id", "data-slot-kind", "data-slot-placeholder"):
        node.attrib.pop(key, None)
    text = "".join(node.itertext()).strip()
    font_size = _float(node.get("font-size"), 24.0)
    tspans = [child for child in list(node) if _local(child.tag) == "tspan"]
    line_count = max(1, len(tspans))
    line_step = font_size * 1.2
    for child in tspans[1:]:
        dy = _float(child.get("dy"), 0.0)
        if dy > 0:
            line_step = dy
            break
    max_line_chars = max(
        [len("".join(child.itertext()).strip()) for child in tspans] or [len(text), 1]
    )
    width = max(font_size, min(320.0, max_line_chars * font_size + font_size * 0.5))
    anchor = (node.get("text-anchor") or "start").lower()
    x = _float(node.get("x"))
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    box = {
        "x": x,
        "y": max(0.0, _float(node.get("y")) - font_size * 0.85),
        "width": width,
        "height": max(font_size * 1.25, font_size + (line_count - 1) * line_step),
    }
    node.set("data-easyslides-static-text", "true")
    node.set("data-easyslides-static-role", role)
    node.set("data-easyslides-static-geometry", "source_fidelity")
    node.set("data-pptx-textbox", "true")
    node.set("data-pptx-box-x", f"{box['x']:.2f}")
    node.set("data-pptx-box-y", f"{box['y']:.2f}")
    node.set("data-pptx-box-w", f"{box['width']:.2f}")
    node.set("data-pptx-box-h", f"{box['height']:.2f}")
    node.set("data-pptx-valign", "top")
    node.set("data-pptx-measure-text", "T")
    node.set("data-pptx-line-height-ratio", f"{line_step / max(font_size, 1.0):.3f}")
    node.set("data-pptx-text-anchor", anchor)


def _image_box(node: ET.Element, parent: ET.Element | None) -> dict[str, float]:
    candidate = parent if parent is not None and _local(parent.tag) == "svg" and parent.get("x") is not None else node
    width = _float(candidate.get("width"), 1.0)
    height = _float(candidate.get("height"), 1.0)
    return {
        "x": _float(candidate.get("x")),
        "y": _float(candidate.get("y")),
        "width": width,
        "height": height,
    }


def _svg_vertical_bounds(node: ET.Element) -> tuple[float, float] | None:
    """Approximate an SVG subtree's y extent for content-shell cleanup."""
    values: list[float] = []
    for child in node.iter():
        tag = _local(child.tag)
        if tag in {"rect", "image"}:
            y = _float(child.get("y"))
            values.extend([y, y + _float(child.get("height"))])
        elif tag == "line":
            values.extend([_float(child.get("y1")), _float(child.get("y2"))])
        elif tag == "text":
            y = _float(child.get("data-pptx-box-y"), _float(child.get("y")))
            values.extend([y, y + _float(child.get("data-pptx-box-h"), _float(child.get("font-size"), 24.0))])
        elif tag == "path":
            path = child.get("d") or ""
            for match in re.finditer(
                r"[MmLl]\s*([-+]?\d*\.?\d+)\s*[ ,]\s*([-+]?\d*\.?\d+)",
                path,
            ):
                values.append(_float(match.group(2)))
            for match in re.finditer(r"[Vv]\s*([-+]?\d*\.?\d+)", path):
                values.append(_float(match.group(1)))
    return (min(values), max(values)) if values else None


def _contains_slot(node: ET.Element, slot_id: str) -> bool:
    return any(
        str(child.get("data-slot") or child.get("data-slot-id") or "") == slot_id
        for child in node.iter()
    )


def _write_clean_page(index: int, source_svg: Path, destination: Path, distilled: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.parse(source_svg).getroot()
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    text_candidates = _page_candidates(distilled, index, "text")
    text_nodes = [node for node in root.iter() if _local(node.tag) == "text"]
    slots: list[dict[str, Any]] = []
    used_text_names: set[str] = set()
    for position, node in enumerate(text_nodes, start=1):
        candidate = text_candidates[position - 1] if position <= len(text_candidates) else None
        spec = SHELL_TEXT_SPECS.get(index, {}).get(position)
        box = _box(node, parents.get(node))
        if spec and spec.get("static"):
            role = str(spec.get("role") or "fixed_label")
            if spec.get("preserve_source_geometry"):
                _preserve_static_source_text(node, role)
            else:
                _lock_static_text(node, box, role)
            continue
        proposed = (
            str(spec.get("slot_id") or "")
            if spec
            else str(candidate.get("slot") or f"TEXT_{position:02d}")
            if candidate
            else f"TEXT_{position:02d}"
        )
        if not proposed:
            raise ValueError(f"source slide {index} text position {position} has no semantic slot id")
        slot_id = proposed
        suffix = 2
        while slot_id in used_text_names:
            slot_id = f"{proposed}_{suffix:02d}"
            suffix += 1
        used_text_names.add(slot_id)
        if index == 4 and slot_id == "BODY_TEXT_15":
            # This label points to an external arrow control whose center is
            # slightly below the source text box center. Preserve the source
            # relationship while enforcing the template's vertical lock.
            box["y"] = 535.705
        if index == 1 and slot_id in {"TITLE", "PROJECT_TYPE", "SUBTITLE"}:
            # The cover's project name, report subject, and presentation
            # subtitle are all title-level content and must share the same
            # horizontal centerline, independent of their source alignment.
            node.set("text-anchor", "middle")
        if index == 17 and slot_id in {"CLOSING_TITLE", "CLOSING_SUBTITLE"}:
            # The source artwork uses short Chinese closing words. Reserve a
            # wider centered box so the same shell accepts common English
            # closings without violating the text-fit contract.
            box["x"] = 440.0
            box["width"] = 400.0
        _placeholder_text(node, slot_id, box)
        slots.append(
            {
                "slot_id": slot_id,
                "kind": "text",
                "role": str(spec.get("role") or slot_id.lower()) if spec else slot_id.lower(),
                "required": bool(spec.get("required", False)) if spec else slot_id in {"PAGE_TITLE", "CLOSING_TITLE"},
                "geometry": box,
                "capacity": _capacity(slot_id, candidate),
                "line_height_ratio": _float(node.get("data-pptx-line-height-ratio"), 1.25),
                "text_anchor": node.get("data-pptx-text-anchor", "start"),
                "source_position": position,
            }
        )

    image_index = 0
    for node in list(root.iter()):
        if _local(node.tag) != "image":
            continue
        href = node.get("href") or node.get(f"{{{XLINK_NS}}}href") or ""
        filename = _basename(href)
        for key in ("href", f"{{{XLINK_NS}}}href"):
            if key in node.attrib:
                node.set(key, f"assets/{filename}") if filename in COMMON_SOURCE_ASSETS else node.set(key, "assets/figure_placeholder.svg")
        if filename in COMMON_SOURCE_ASSETS:
            continue
        image_index += 1
        slot_id = f"FIGURE_{image_index:02d}"
        box = _image_box(node, parents.get(node))
        node.set("data-slot", slot_id)
        node.set("data-slot-id", slot_id)
        node.set("data-slot-kind", "image")
        slots.append(
            {
                "slot_id": slot_id,
                "kind": "image",
                "role": "scientific_exhibit",
                "required": False,
                "geometry": box,
                "image_fit": "contain",
                "source_position": image_index,
            }
        )

    for node in root.iter():
        node.attrib.pop("data-name", None)
        node.attrib.pop("data-pptx-prst", None)
        node.attrib.pop("data-pptx-adj1", None)
        node.attrib.pop("data-pptx-adj2", None)

    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return slots


def _open_content_shell(path: Path, source_slots: list[dict[str, Any]]) -> None:
    """Remove source-body placeholders so the content shell is chrome plus title only."""
    public_slots = {"PAGE_TITLE"}
    shadow_slots = {
        str(slot.get("slot_id") or "")
        for slot in source_slots
        if str(slot.get("slot_id") or "") not in public_slots
    }
    root = ET.parse(path).getroot()
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    for node in list(root.iter()):
        slot_id = str(node.get("data-slot") or node.get("data-slot-id") or "")
        if slot_id in shadow_slots:
            parent = parents.get(node)
            if parent is not None:
                parent.remove(node)
    # The content shell keeps only top chrome and PAGE_TITLE. Leaving source
    # body shapes behind a white cover makes native geometry QA associate new
    # component text with obsolete containers, despite their being invisible.
    for child in list(root):
        if _local(child.tag) == "defs" or _contains_slot(child, "PAGE_TITLE"):
            continue
        bounds = _svg_vertical_bounds(child)
        if bounds is not None and bounds[1] >= CONTENT_CLEAR_REGION["y"] - 0.5:
            root.remove(child)
    # Source body geometry is not reliably attached to a text/image slot. Keep
    # it as provenance only and cover it with the open composition surface.
    root.append(
        ET.Element(
            f"{{{SVG_NS}}}rect",
            {
                "x": str(CONTENT_CLEAR_REGION["x"]),
                "y": str(CONTENT_CLEAR_REGION["y"]),
                "width": str(CONTENT_CLEAR_REGION["width"]),
                "height": str(CONTENT_CLEAR_REGION["height"]),
                "fill": "#FFFFFF",
                "data-easyslides-open-body-canvas": "true",
            },
        )
    )
    root.set("data-easyslides-shell-policy", "open_body_canvas_body_variant_required")
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _write_chapter_shell(path: Path) -> list[dict[str, Any]]:
    """Turn the source navigation duplicate into a distinct chapter divider."""
    root = ET.parse(path).getroot()
    remove_ids = {
        "shape-14", "shape-21", "shape-23", "shape-18", "shape-19",
        "shape-20", "shape-15", "shape-17", "shape-24", "shape-25",
        "shape-26", "shape-27", "shape-29", "shape-30", "shape-31",
        "shape-67", "shape-66",
    }
    for parent in root.iter():
        for child in list(parent):
            if child.get("id") in remove_ids:
                parent.remove(child)

    for node in root.iter():
        if node.get("data-slot-id") == "BODY_TEXT_06":
            node.set("data-pptx-fixed-chrome", "true")
            for key in ("data-slot", "data-slot-id", "data-slot-kind", "data-slot-placeholder"):
                node.attrib.pop(key, None)
            node.text = "汇"
            for child in list(node):
                node.remove(child)
            for char in "报答辩":
                tspan = ET.SubElement(node, f"{{{SVG_NS}}}tspan", {"x": node.get("x", "330.74"), "dy": "100.8"})
                tspan.text = char

    group = ET.Element(f"{{{SVG_NS}}}g", {"id": "chapter-shell-title"})
    ET.SubElement(group, f"{{{SVG_NS}}}line", {
        "x1": "590", "y1": "258", "x2": "690", "y2": "258",
        "stroke": "#751497", "stroke-width": "4", "stroke-linecap": "round",
    })
    title = ET.SubElement(group, f"{{{SVG_NS}}}text", {
        "x": "640", "y": "365", "text-anchor": "middle",
        "font-family": "Arial, sans-serif", "font-size": "64", "fill": "#751497",
    })
    title_box = {"x": 320.0, "y": 285.0, "width": 640.0, "height": 96.0}
    _placeholder_text(title, "CHAPTER_TITLE", title_box)
    subtitle = ET.SubElement(group, f"{{{SVG_NS}}}text", {
        "x": "640", "y": "445", "text-anchor": "middle",
        "font-family": "Arial, sans-serif", "font-size": "28", "fill": "#9A9A9A",
    })
    subtitle_box = {"x": 380.0, "y": 410.0, "width": 520.0, "height": 56.0}
    _placeholder_text(subtitle, "CHAPTER_DESC", subtitle_box)
    root.append(group)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return [
        {
            "slot_id": "CHAPTER_TITLE",
            "kind": "text",
            "role": "chapter_title",
            "required": True,
            "geometry": title_box,
            "capacity": {"max_lines": 1, "max_chars_per_line": 20, "overflow_action": "shorten_or_split"},
            "source_position": 1,
        },
        {
            "slot_id": "CHAPTER_DESC",
            "kind": "text",
            "role": "chapter_description",
            "required": False,
            "geometry": subtitle_box,
            "capacity": {"max_lines": 1, "max_chars_per_line": 28, "overflow_action": "shorten_or_drop"},
            "source_position": 2,
        },
    ]


def _write_component_svg(path: Path, width: int, height: int, component_id: str) -> None:
    source_like_svg = render_source_like_component_svg(component_id, width, height)
    if source_like_svg is not None:
        path.write_text(source_like_svg, encoding="utf-8")
        return
    accent = "#C00000" if component_id == "red_emphasis" else "#751497"
    component_slots = _component_slots(component_id, width, height)
    text_nodes: list[str] = []
    for slot in component_slots:
        box = slot["geometry"]
        slot_id = slot["slot_id"]
        if str(slot.get("kind") or "text") == "image":
            text_nodes.append(
                f'  <image x="{box["x"]:.2f}" y="{box["y"]:.2f}" width="{box["width"]:.2f}" height="{box["height"]:.2f}" '
                f'preserveAspectRatio="xMidYMid meet" href="../transparent.svg" '
                f'data-slot="{slot_id}" data-slot-id="{slot_id}" data-slot-kind="image"/>'
            )
            continue
        font_size = 24 if slot_id in {"TEXT", "TITLE"} else (20 if slot_id.endswith("_BODY") else 22 if slot_id.endswith("_TITLE") else 28)
        fill = "#FFFFFF" if slot_id in {"TEXT", "TITLE"} else "#060607"
        anchor = "middle"
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2 + font_size * 0.35
        label = {"TEXT": "关键信息", "TITLE": "模块标题", "BODY": "内容摘要"}.get(slot_id, slot_id)
        body_layout = (
            f' data-easyslides-layout="evidence_rows" data-easyslides-component="{component_id}"'
            if slot_id == "BODY" and component_id not in SMALL_COMPONENTS
            else ""
        )
        text_nodes.append(
            f'  <text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
            f'font-family="Arial, sans-serif" font-size="{font_size}" fill="{fill}" '
            f'data-slot="{slot_id}" data-slot-id="{slot_id}" data-slot-kind="text" '
            f'data-pptx-textbox="true" data-pptx-measure-text="T" '
            f'data-pptx-box-x="{box["x"]:.2f}" data-pptx-box-y="{box["y"]:.2f}" '
            f'data-pptx-box-w="{box["width"]:.2f}" data-pptx-box-h="{box["height"]:.2f}" '
            f'data-pptx-valign="middle" data-center-lock="true" '
            f'data-pptx-line-height-ratio="1.150" data-pptx-text-anchor="{anchor}"{body_layout}>{label}</text>'
        )
    if component_id in SMALL_COMPONENTS:
        surfaces = f'  <rect width="{width}" height="{height}" fill="{accent}" stroke="{accent}"/>'
    elif component_id == "ann_snn_comparison":
        surfaces = '''  <rect width="1120" height="520" fill="#FFFFFF" stroke="#751497" stroke-opacity="0.5"/>
  <rect width="1120" height="56" fill="#751497"/>
  <path d="M 24 78 H 1096" stroke="#C00000" stroke-width="3" opacity="0.85"/>
  <rect x="24" y="80" width="510" height="302" fill="#FBF5FC" stroke="#751497" stroke-opacity="0.34"/>
  <rect x="586" y="80" width="510" height="302" fill="#FFFFFF" stroke="#751497" stroke-opacity="0.34"/>
  <rect x="24" y="80" width="510" height="44" fill="#F0D9F6"/>
  <rect x="586" y="80" width="510" height="44" fill="#EEEAF8"/>
  <path d="M 552 228 H 568" stroke="#751497" stroke-width="4"/>
  <path d="M 568 228 l-10 -8 M 568 228 l-10 8" stroke="#751497" stroke-width="4" fill="none"/>
  <rect x="56" y="406" width="1008" height="94" fill="#FFF8F8" stroke="#C00000" stroke-opacity="0.55"/>
  <rect x="56" y="406" width="9" height="94" fill="#C00000"/>'''
    else:
        surfaces = f'''  <rect width="{width}" height="{height}" fill="#FFFFFF" stroke="{accent}" stroke-opacity="0.5"/>
  <rect width="{width}" height="{min(56, height)}" fill="{accent}"/>
  <path d="M 24 {min(78, height - 12)} H {max(30, width - 24)}" stroke="#C00000" stroke-width="3" opacity="0.85"/>
  <path d="M 26 {min(92, height - 8)} H {max(30, width - 26)}" stroke="#751497" stroke-width="1" opacity="0.18"/>'''
    body = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" data-component="{component_id}">
{surfaces}
{chr(10).join(text_nodes)}
</svg>'''
    path.write_text(body, encoding="utf-8")


def _copy_assets() -> None:
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in COMMON_SOURCE_ASSETS:
        source = SOURCE / "assets" / name
        if source.is_file():
            shutil.copy2(source, assets / name)
    (assets / "transparent.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1"><rect width="1" height="1" fill="none"/></svg>\n',
        encoding="utf-8",
    )
    (assets / "figure_placeholder.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220" viewBox="0 0 320 220"><rect x="1" y="1" width="318" height="218" fill="#F8EAFC" stroke="#751497" stroke-opacity="0.35" stroke-dasharray="8 6"/><path d="M40 170 L100 110 L145 150 L200 82 L280 170" fill="none" stroke="#751497" stroke-width="4" opacity="0.45"/></svg>\n',
        encoding="utf-8",
    )
    components = assets / "components"
    components.mkdir(parents=True, exist_ok=True)
    for component_id, (width, height, _description) in COMPONENTS.items():
        _write_component_svg(components / f"{component_id}.svg", width, height, component_id)
    primitives = assets / "primitives"
    primitives.mkdir(parents=True, exist_ok=True)
    for primitive in primitive_asset_manifest():
        primitive_id = str(primitive["primitive_id"])
        (primitives / f"{primitive_id}.svg").write_text(render_primitive_svg(primitive_id), encoding="utf-8")


def _write_contracts(slides: list[dict[str, Any]], distilled: dict[str, Any]) -> None:
    page_rows = []
    public_slot_models: dict[str, list[dict[str, Any]]] = {}
    for slide in slides:
        shell = SHELLS[slide["shell_id"]]
        source_meta = PAGE_META[slide["source_slide"]]
        variants = [variant["variant_id"] for variant in BODY_VARIANTS] if slide["shell_id"] == "content" else []
        shell_regions = (
            [
                {"region_id": "title", "frame": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 100.0}, "z_index": 0},
                {
                    "region_id": "body_canvas",
                    "frame": CONTENT_BODY_CANVAS,
                    "z_index": 10,
                    "fit": "contain",
                    "purpose": "body_variant_composition_only",
                },
            ]
            if slide["shell_id"] == "content"
            else [{"region_id": "canvas", "frame": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 720.0}, "z_index": 0}]
        )
        source_slots = list(slide["slots"])
        public_slots = source_slots
        shadow_slots: list[dict[str, Any]] = []
        if slide["shell_id"] == "content":
            public_slots = [slot for slot in source_slots if slot["slot_id"] == "PAGE_TITLE"]
            if len(public_slots) != 1:
                raise ValueError("content shell must expose exactly one PAGE_TITLE public slot")
            shadow_slots = [slot for slot in source_slots if slot["slot_id"] != "PAGE_TITLE"]
        public_slot_models[slide["shell_id"]] = public_slots
        page_rows.append(
            {
                "id": shell["id"],
                "page_id": slide["shell_id"],
                "layout_id": slide["shell_id"],
                "svg": f"{shell['id']}.svg",
                "source_slide": slide["source_slide"],
                "source_page_id": source_meta["id"],
                "story_role": shell["role"],
                "role": shell["role"],
                "page_archetype": shell["archetype"],
                "density_score": 4 if shell["role"] == "content" else 2,
                "slots": [slot["slot_id"] for slot in public_slots],
                "role_fit": [shell["role"], shell["archetype"]],
                "best_for": slide["best_for"],
                "avoid": (
                    "direct body payload; select a body variant"
                    if slide["shell_id"] == "content"
                    else slide["avoid"]
                ),
                "body_variants": variants,
                "regions": shell_regions,
                "body_canvas": CONTENT_BODY_CANVAS if slide["shell_id"] == "content" else None,
                "content_shell_policy": (
                    "source_guided_body_variant_required"
                    if slide["shell_id"] == "content"
                    else "fixed_shell"
                ),
                "legacy_shadow_slots": shadow_slots,
            }
        )
    slot_models = public_slot_models
    source_shell_by_slide = {1: "cover", 2: "toc", 8: "chapter", 15: "chapter", 17: "ending"}
    variant_by_source = {
        source_slide: variant["variant_id"]
        for variant in BODY_VARIANTS
        for source_slide in variant["source_slides"]
    }
    source_guidance_by_slide = {
        source_slide: {
            "section": variant["section"],
            "story_roles": variant["story_roles"],
            "narrative_step": variant["narrative_step"],
            "source_page_purpose": variant["source_page_purpose"],
            "required_components": variant["components"],
        }
        for variant in BODY_VARIANTS
        for source_slide in variant["source_slides"]
    }
    source_page_roster = []
    for source_slide in range(1, 18):
        meta = PAGE_META[source_slide]
        source_page_roster.append(
            {
                "source_slide": source_slide,
                "source_page_id": meta["id"],
                "source_archetype": meta["archetype"],
                "section": meta["section"],
                "canonical_shell": source_shell_by_slide.get(source_slide, "content"),
                "body_variant": variant_by_source.get(source_slide),
                "preserved_as": "shell" if source_slide in source_shell_by_slide else "body_variant",
                **source_guidance_by_slide.get(source_slide, {}),
            }
        )
    variant_rows = []
    for variant in BODY_VARIANTS:
        variant_slots, _bindings, _regions = _variant_slots_and_bindings(variant)
        variant_rows.append(
            {
                **{key: value for key, value in variant.items() if key != "components"},
                "page_id": "content",
                "layout_id": "content",
                "shell": "04_content.svg",
                "composition_mode": str(
                    variant.get("composition_mode")
                    or "ordered_component_refs"
                ),
                "composition_contract": "regions_required",
                "composition_scene": _composition_profile(variant)["scene"],
                "coordinate_space": "body_canvas",
                "content_shapes": [
                    str(variant["variant_id"]),
                    "comparison" if "comparison" in str(variant["variant_id"]) else "evidence",
                ],
                "slots": variant_slots,
                "regions": _variant_regions(variant),
                "clear_region": CONTENT_CLEAR_REGION,
                "component_refs": _variant_component_refs(variant),
                "selection_key": ["story_role", "content_shape", "section", "density", "evidence_count"],
                "slot_policy": "bind_variant_slots_to_component_local_slots",
            }
        )
    layouts = {
        "schema_version": "easyslides.nsfc_defense.layouts.v1",
        "template_id": "nsfc_defense",
        "mode": "semantic",
        "replication_mode": "slot_guided_mirror",
        "global_contract": {
            "source_geometry_policy": "preserve_source_chrome_compose_source_guided_body_variants",
            "content_organization": "claim_evidence_consequence",
            "visual_density": "dense_research_defense",
            "canonical_shell_policy": "evidence_driven_three_to_five_stable_shells",
            "canonical_shell_minimum": 3,
            "canonical_shell_limit": 5,
            "required_shell_roles": ["cover", "content", "ending"],
            "optional_shell_roles": ["toc", "chapter"],
            "active_shell_roles": ["cover", "toc", "chapter", "content", "ending"],
        },
        "canvas": {"width": 1280, "height": 720, "format": "ppt169"},
        "style_system": "nsfc_defense",
        "colors": {
            "primary": "#751497",
            "emphasis": "#C00000",
            "surface": "#F8EAFC",
            "ink": "#060607",
        },
        "layouts": page_rows,
        "pages": page_rows,
        "shells": page_rows,
        "body_variants": "body_variants.json",
        "component_primitives": "component_primitives.json",
        "body_variant_recipes": "body_variant_recipes.json",
        "source_page_roster": "source_page_roster.json",
        "content_shell_contract": {
            "shell_id": "content",
            "policy": "source_guided_body_variant_required",
            "public_slots": ["PAGE_TITLE"],
            "body_canvas": CONTENT_BODY_CANVAS,
            "clear_region": CONTENT_CLEAR_REGION,
            "legacy_source_slots": "shadow_metadata_only",
            "body_component_policy": "forbidden",
        },
        "shell_profile": {
            "policy": "evidence_driven_three_to_five_stable_shells",
            "minimum_shell_count": 3,
            "maximum_shell_count": 5,
            "required_shell_roles": ["cover", "content", "ending"],
            "optional_shell_roles": ["toc", "chapter"],
            "active_shell_roles": ["cover", "toc", "chapter", "content", "ending"],
            "active_shell_count": len(SHELLS),
            "toc_present": True,
            "chapter_present": True,
        },
        "slot_models": slot_models,
        "text_fit_policy": {
            "schema_version": "easyslides.template_text_fit_policy.v1",
            "overflow_strategy_order": ["use_declared_capacity", "choose_same_archetype_variant", "split_across_slides", "shrink_font_with_floor"],
        },
    }
    (OUT / "layouts.json").write_text(json.dumps(layouts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "body_variants.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.nsfc_defense.body_variants.v1",
                "template_id": "nsfc_defense",
                "source_shell": "04_content.svg",
                "content_area": CONTENT_BODY_CANVAS,
                "coordinate_space": "body_canvas",
                "clear_region": CONTENT_CLEAR_REGION,
                "selection_policy": "match_required_story_role_then_source_archetype_density_and_evidence",
                "composition_contract": "regions_required",
                "body_component_policy": "forbidden",
                "variants": variant_rows,
                "constraint": "The content shell owns chrome only. Each page must select a source-derived body variant whose section and story_role match the intended narrative step. Direct body_components are forbidden.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "component_primitives.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.nsfc_defense.component_primitives.v1",
                "template_id": "nsfc_defense",
                "tokens": COMPONENT_TOKENS,
                "primitives": primitive_asset_manifest(),
                "rule": "Body scenes may compose declared primitives only; private card styles are forbidden.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "body_variant_recipes.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.nsfc_defense.body_variant_recipes.v1",
                "template_id": "nsfc_defense",
                "recipes": [
                    {
                        "variant_id": variant["variant_id"],
                        "scene_component": variant["components"][0],
                        "primitives": VARIANT_RECIPES[variant["variant_id"]],
                        "source_slides": variant["source_slides"],
                    }
                    for variant in BODY_VARIANTS
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "source_page_roster.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.nsfc_defense.source_page_roster.v1",
                "template_id": "nsfc_defense",
                "source_template_id": "nsfc_defense_distilled",
                "source_slide_count": 17,
                "canonical_shell_count": len(SHELLS),
                "body_variant_count": len(BODY_VARIANTS),
                "shell_profile": {
                    "policy": "evidence_driven_three_to_five_stable_shells",
                    "required_shell_roles": ["cover", "content", "ending"],
                    "optional_shell_roles": ["toc", "chapter"],
                    "active_shell_roles": ["cover", "toc", "chapter", "content", "ending"],
                    "active_shell_count": len(SHELLS),
                },
                "pages": source_page_roster,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    catalog = {
        "schema_version": "easyslides.nsfc_defense.page_catalog.v1",
        "template_id": "nsfc_defense",
        "selection_policy": "canonical_shell + required_story_role + source_derived_body_variant + section + density + evidence_count",
        "pages": page_rows,
        "body_variants": variant_rows,
        "source_pages": source_page_roster,
    }
    (OUT / "page_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    story = {
        "schema_version": "easyslides.story_structure.v1",
        "template_id": "nsfc_defense",
        "default_scenario": "national_natural_science_foundation_defense",
        "narrative_logic": [
            "national_need_and_problem",
            "innovation_and_technical_content",
            "application_and_social_benefits",
        ],
        "recommended_flow": [
            {"page_id": key, "svg": value["id"] + ".svg", "story_role": value["role"], "archetype": value["archetype"]}
            for key, value in SHELLS.items()
        ],
        "sections": [
            {
                "section": "01",
                "title": "立项背景和研究思路",
                "narrative": "national need -> two research tracks -> bottleneck -> hotspot metrics -> hotspot synthesis",
                "source_slides": [3, 4, 5, 6, 7],
            },
            {
                "section": "02",
                "title": "创新点和主要技术内容",
                "narrative": "innovation overview -> method comparison -> device mechanism and training -> system architecture -> application pipeline -> external validation",
                "source_slides": [9, 10, 11, 12, 13, 14],
            },
            {
                "section": "03",
                "title": "应用推广和经济社会效益",
                "narrative": "application metrics -> technology transfer evidence -> societal benefit",
                "source_slides": [16],
            },
        ],
        "canonical_content_sequence": [
            {
                "section": variant["section"],
                "story_role": variant["story_roles"][0],
                "body_variant_id": variant["variant_id"],
                "source_slides": variant["source_slides"],
                "source_page_purpose": variant["source_page_purpose"],
                "required_components": variant["components"],
            }
            for variant in BODY_VARIANTS
        ],
        "generation_contract": {
            "content_page_requires": ["section", "story_role", "body_variant_id", "PAGE_TITLE", "slot_payload"],
            "body_component_policy": "forbidden",
            "selection_rule": "story_role and section must match the selected source-derived body variant",
            "new_layout_rule": "A new content composition requires a reviewed source-page evidence record and a registered body variant; it cannot be assembled ad hoc.",
        },
        "default_body_variant_sequence": [variant["variant_id"] for variant in BODY_VARIANTS],
    }
    (OUT / "story_structure.json").write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    slot_layouts = []
    flat_slots = []
    for slide in slides:
        shell = SHELLS[slide["shell_id"]]
        public_slots = public_slot_models[slide["shell_id"]]
        slot_details = []
        for slot in public_slots:
            flat_slots.append(
                {
                    **slot,
                    "shell_id": slide["shell_id"],
                    "source_slide_id": f"slide-{slide['source_slide']:02d}",
                    "replacement": {
                        "preserve_geometry": True,
                        "preserve_layer_order": True,
                    },
                }
            )
            detail = {
                "slot_id": slot["slot_id"],
                "role": slot.get("role", slot["slot_id"].lower()),
                "kind": slot.get("kind", "text"),
                "required": bool(slot.get("required", False)),
                "geometry": dict(slot.get("geometry") or {}),
            }
            capacity = slot.get("capacity")
            if isinstance(capacity, dict):
                for key in ("max_lines", "max_chars_per_line", "overflow_action"):
                    if capacity.get(key) is not None:
                        detail[key] = capacity[key]
            if slot.get("vertical_anchor"):
                detail["vertical_anchor"] = slot["vertical_anchor"]
            slot_details.append(detail)
        slot_layouts.append(
            {
                "layout_id": slide["shell_id"],
                "page_id": shell["id"],
                "svg_path": f"{shell['id']}.svg",
                "slot_model": shell["role"],
                "source_slide_id": f"slide-{slide['source_slide']:02d}",
                "slots": [slot["slot_id"] for slot in public_slots],
                "text_slots": [
                    slot["slot_id"]
                    for slot in public_slots
                    if slot.get("kind", "text") == "text"
                ],
                "image_slots": [
                    slot["slot_id"]
                    for slot in public_slots
                    if slot.get("kind") == "image"
                ],
                "replacement": "replace_declared_slots_preserve_template_geometry",
                "slot_details": slot_details,
            }
        )
    slot_contract = {
        "schema_version": "easyslides.template_slot_contracts.v1",
        "template_id": "nsfc_defense",
        "source_template_id": "nsfc_defense_distilled",
        "source": "derived_from_nsfc_defense_source_page_geometry_with_five_shell_projection",
        "replacement_rule": "replace_declared_slots_preserve_template_geometry",
        "private_clone_required": False,
        "text_fit_policy": {
            "schema_version": "easyslides.template_text_fit_policy.v1",
            "overflow_strategy_order": [
                "use_declared_capacity",
                "choose_same_archetype_variant",
                "split_across_slides",
                "shrink_font_with_floor",
            ],
        },
        "hard_geometry_invariants": ["text_center_y_matches_container_center_y", "preserve_parent_transform", "declared_slots_stay_inside_canvas"],
        "layouts": slot_layouts,
        "slots": flat_slots,
        "validation": {"unknown_slots": "fail", "missing_required_slots": "fail", "overflow": "split_or_choose_page_variant"},
    }
    (OUT / "slot_contracts.json").write_text(json.dumps(slot_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    geometry_pages = []
    for slide in slides:
        shell = SHELLS[slide["shell_id"]]
        public_slots = public_slot_models[slide["shell_id"]]
        geometry_pages.append(
            {
                "id": shell["id"],
                "page_id": slide["shell_id"],
                "svg": f"{shell['id']}.svg",
                "source_slide": slide["source_slide"],
                "story_role": shell["role"],
                "page_archetype": shell["archetype"],
                "content_bounds": {"x": 0, "y": 0, "width": 1280, "height": 720},
                "protected_regions": [{"id": "source_page_chrome", "x": 0, "y": 0, "width": 1280, "height": 720, "policy": "preserve_geometry"}],
                "containers": [slot["geometry"] | {"id": slot["slot_id"], "slot_id": slot["slot_id"], "kind": slot["kind"]} for slot in public_slots],
            }
        )
    (OUT / "geometry_contract.json").write_text(
        json.dumps({"schema_version": "easyslides.nsfc_defense.geometry_contract.v1", "template_id": "nsfc_defense", "canvas": {"width": 1280, "height": 720}, "hard_invariants": ["text_center_y_matches_container_center_y", "native_pptx_text_must_fit_declared_geometry"], "pages": geometry_pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    projection_pages = []
    for slide in slides:
        shell = SHELLS[slide["shell_id"]]
        public_slots = public_slot_models[slide["shell_id"]]
        projection_pages.append(
            {
                "projection_id": f"nsfc_defense/{slide['shell_id']}",
                "slide_id": slide["shell_id"],
                "source_slide_id": f"slide-{slide['source_slide']:02d}",
                "source_slide": slide["source_slide"],
                "source_svg": f"{shell['id']}.svg",
                "source_svg_exists": True,
                "status": "ready",
                "slots": [slot["slot_id"] for slot in public_slots],
                "hard_geometry_invariants": ["text_center_y_matches_container_center_y", "preserve_parent_transform"],
            }
        )
    (OUT / "projection_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.source_template_projection.v1",
                "template_id": "nsfc_defense",
                "source_template_id": "nsfc_defense_distilled",
                "renderer": "scripts.source_template_renderer.project_source_template_svg",
                "replacement_policy": "named_slots_only",
                "pages": projection_pages,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    component_rows = []
    archetypes = {shell["archetype"] for shell in SHELLS.values()} | {variant["variant_id"] for variant in BODY_VARIANTS}
    for component_id, (width, height, description) in COMPONENTS.items():
        component_rows.append(
            {
                "asset_id": f"component/nsfc_defense/{component_id}",
                "component_id": component_id,
                "asset_path": f"assets/components/{component_id}.svg",
                "asset_status": "renderable_svg",
                "render_backend": "template_svg_component",
                "renderer_id": "svg_fragment",
                "classification": "template_scoped",
                "reuse_policy": "nsfc_defense_shell_or_body_variant",
                "description": description,
                "slots": _component_slots(component_id, width, height),
                "selection": {"page_roles": ["content", "agenda", "chapter"], "archetypes": sorted(archetypes), "density": "dense_research_defense"},
                "geometry": {"width": width, "height": height},
                "qa": {"required_gates": ["asset_manifest", "component_geometry", "vertical_center_alignment"]},
            }
        )
    (OUT / "component_catalog.json").write_text(
        json.dumps({"schema_version": "easyslides.nsfc_defense.component_catalog.v1", "template_id": "nsfc_defense", "selection_policy": "body_variant_recipe_then_declared_slot_capacity", "primitive_manifest": "component_primitives.json", "recipe_manifest": "body_variant_recipes.json", "components": component_rows, "symbols": [], "unknown_component_count": 0}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    template = {
        "schema_version": "easyslides.template_pack.v1",
        "template_id": "nsfc_defense",
        "display_name": "NSFC Defense",
        "description": "National Natural Science Foundation defense template distilled from a dense research-defense deck.",
        "mode": "slot_guided_mirror",
        "source_template_id": "nsfc_defense_distilled",
        "replication_mode": "slot_guided_mirror",
        "recommended_template_route": "source_template_projection",
        "output_contract": "editable-native-pptx",
        "style_system": "nsfc_defense",
        "layout_source_format": "svg",
        "runtime_source_of_truth": "source_chrome_open_body_canvas_body_variants_and_named_slots",
        "scenarios": ["national_natural_science_foundation_defense", "research_defense", "scientific_project_report"],
        "roles": ["cover", "agenda", "chapter", "content", "ending"],
        "layout_count": len(SHELLS),
        "variant_count": len(BODY_VARIANTS),
        "component_asset_model": {
            "primitive_manifest": "component_primitives.json",
            "recipe_manifest": "body_variant_recipes.json",
            "policy": "standard_primitives_composed_by_source_like_scene_recipes",
        },
        "primary_color": "#751497",
        "emphasis_color": "#C00000",
        "content_organization": ["national_need", "technical_innovation", "application_benefits"],
        "page_selection_inputs": ["canonical_shell", "body_variant", "section", "density", "evidence_count"],
        "forbidden_selection_inputs": ["dom_order_only"],
    }
    (OUT / "template.json").write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "qa_policy.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.template_qa_policy.v1",
                "template_id": "nsfc_defense",
                "promotion_policy": "fail_closed",
                "alignment_invariants": [
                    "text_center_y_matches_container_center_y",
                    "declared_slots_stay_inside_canvas",
                    "component_regions_stay_inside_canvas",
                    "content_shell_public_slots_are_title_only",
                    "body_variant_regions_stay_inside_body_canvas",
                ],
                "required_gates": [
                    "template_compile",
                    "slide_composition",
                    "body_variant_component_contract",
                    "svg_quality",
                    "svg_text_slots",
                    "template_geometry_svg",
                    "asset_manifest",
                    "template_geometry_pptx",
                    "pptx_text_layout",
                    "render_diff",
                    "cross_material_smoke",
                    "human_visual_review",
                ],
                "cross_material": {"minimum_material_sets": 3, "max_pages_per_set": 8},
                "vertical_center_tolerance_px": 1.0,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_docs() -> None:
    (OUT / "design_spec.md").write_text(
        """---
template_id: nsfc_defense
canvas: ppt169
mode: slot_guided_mirror
category: academic_research
summary: NSFC defense template distilled from a dense research-defense deck.
keywords: [nsfc, defense, research, national_need, innovation, application, evidence]
primary_color: '#751497'
canvas_format: ppt169
replication_mode: slot_guided_mirror
---

# NSFC Defense

`nsfc_defense` is the canonical template for National Natural Science Foundation
defense decks. It preserves the source deck's purple chrome, title treatment,
and scientific visual grammar while rebuilding each source-derived content
composition inside a controlled body canvas.

## Narrative organization

1. **National need and problem**: establish the national demand, bottleneck,
   research hotspot, and quantitative technical target.
2. **Innovation and technical content**: compare baselines, state innovation,
   show equations or architectures, and connect material/device work to system
   behavior.
3. **Application and social benefits**: present application evidence, papers or
   international results, metrics, and technology transfer outcomes.

Each content page follows `claim -> evidence -> consequence`. Dense pages are
intentional: keep five stable shells and choose a body variant with the right
evidence shape instead of creating a new shell for every source page. Every
body variant is tied to a source slide, a section, a narrative role, and an
ordered component composition. Content pages are not a free-form component
stage: a plan must name the matching `section`, `story_role`, and
`body_variant_id`.

## Visual grammar

- 1280 x 720 canvas with purple gradient header and a restrained circuit motif.
- White research panels over a very light neuron texture.
- `#751497` is structural; `#C00000` is reserved for conclusions, risks, and
  decisive metrics.
- Source-style Chinese bold/medium typography, large section titles, compact
  image captions, purple arrows, bordered white panels, and multi-panel exhibits.
- Cover, agenda, chapter divider, content, and ending are the five stable shells.
- The content shell preserves only the page title and fixed chrome. Its
  `body_canvas` is cleared before a body variant places its components.
- The source deck's dense evidence forms live in `body_variants.json`. Each
  variant declares a distinct `composition_scene`, regions, and component map.

## Page archetypes

See `layouts.json`, `body_variants.json`, `source_page_roster.json`,
`page_catalog.json`, and `story_structure.json`. The roster contains five
stable shells and twelve source-derived body variants, including research-
hotspot KPI pages, ANN/SNN comparison, equation/network architecture,
literature result, and application-benefit pages.

## Slot policy

Use `slot_contracts.json`. The content shell exposes `PAGE_TITLE` only; body
material enters through the selected body's variant slots and component-local
bindings. Source-page body slots are retained as provenance-only shadow
metadata, never as direct generation targets. Text is vertically center-locked
to its declared box. Direct `body_components` are forbidden. A composition
outside this catalog requires a reviewed source-page evidence record and a new
registered body variant; it is not an ad hoc page assembly operation.
""",
        encoding="utf-8",
    )
    (OUT / "rules.md").write_text(
        """# NSFC Defense Rules

- Select one of the five canonical shells, then choose a source-derived body
  variant by section, story role, density, evidence count, and source archetype.
- Preserve header treatment, chapter navigation, purple identity, and red
  emphasis semantics. The content shell owns chrome, not a fixed body grid.
- Build content as `claim -> evidence -> consequence`.
- Use at least one figure, equation, table, metric group, or literature exhibit
  on a dense content page; do not collapse scientific evidence into body text.
- Red is for decisive conclusions, warnings, and measured outcomes; it is not a
  general accent color.
- The content shell exposes `PAGE_TITLE` only. All body material must enter
  through a selected body variant and stay inside its `body_canvas` regions.
- Every content-page plan must provide `section`, `story_role`, and
  `body_variant_id`; they must match the variant's source narrative contract.
- Direct `body_components` are forbidden. New compositions require source-page
  evidence and a reviewed `body_variants.json` entry.
- Moving or resizing source chrome requires a new reviewed shell; routine
  content variation belongs in `body_variants.json` and its composition scene.
- Text boxes must declare geometry and vertical alignment. Their center Y must
  match their container center Y within geometry QA tolerance.
- Overflow action order: choose a lower-density body variant, split evidence,
  then shrink within the declared font floor.
- Run SVG, native PPTX, visual, and cross-material checks before promotion.
""",
        encoding="utf-8",
    )
    (OUT / "spec_lock.md").write_text(
        """# NSFC Defense Spec Lock

- Template id: `nsfc_defense`
- Source family: `nsfc_defense_distilled`
- Runtime binding: source chrome plus body-variant component slots
- Canvas: 1280 x 720, `ppt169`
- Fixed identity: purple research-defense chrome, neuron texture, circuit header,
  red conclusion emphasis, dense white evidence panels, and source page roster.
- Allowed edits: page-title replacement and source-guided body-variant
  composition inside the controlled content body canvas.
- Forbidden edits: direct replacement of legacy body slots, DOM-order-only
  replacement, arbitrary chrome geometry changes, generic card substitution for
  scientific exhibits, direct body-component placement, and unreviewed new
  source-derived variants or shells.
- Hard text rule: text center Y equals its declared container center Y.
""",
        encoding="utf-8",
    )
    (OUT / "template_status.json").write_text(
        json.dumps({"schema_version": "easyslides.template_status.v1", "template_id": "nsfc_defense", "status": "review", "production_eligible": False, "source_template_id": "nsfc_defense_distilled", "reason": "source-derived body variants require final native PPTX and cross-material review", "canonical_shell_count": len(SHELLS), "body_variant_count": len(BODY_VARIANTS)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "links.json").write_text(
        json.dumps({"template_id": "nsfc_defense", "source_template": "templates/reference/template_asset_sources/nsfc_defense_distilled", "runtime_template_dir": "templates/layouts/nsfc_defense", "projection_manifest": "templates/layouts/nsfc_defense/projection_manifest.json", "renderer": "source_template_projection", "native_pptx_route": "scripts/svg_to_pptx.py"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8-sig"))
    distilled = json.loads((SOURCE / "distilled_spec.json").read_text(encoding="utf-8-sig"))
    if OUT.exists():
        for child in OUT.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    _copy_assets()
    slides: list[dict[str, Any]] = []
    for shell_id, shell in SHELLS.items():
        index = shell["source_slide"]
        meta = PAGE_META[index]
        source_svg = SOURCE / "svg" / f"slide_{index:02d}.svg"
        target_svg = OUT / f"{meta['id']}.svg"
        slots = _write_clean_page(index, source_svg, target_svg, distilled)
        final_svg = OUT / f"{shell['id']}.svg"
        target_svg.rename(final_svg)
        if shell_id == "chapter":
            slots = _write_chapter_shell(final_svg)
        elif shell_id == "content":
            _open_content_shell(final_svg, slots)
        slides.append({"shell_id": shell_id, "source_slide": index, "slots": slots, "best_for": meta["archetype"], "avoid": "sparse content that leaves the source-derived evidence grid empty" if meta["role"] == "content" else "content that requires moving fixed source chrome"})
    _write_contracts(slides, distilled)
    _write_docs()
    try:
        from scripts.component_asset_manifest import materialize_asset_manifest
        materialize_asset_manifest(OUT, namespace="nsfc_defense")
    except ImportError:
        from component_asset_manifest import materialize_asset_manifest
        materialize_asset_manifest(OUT, namespace="nsfc_defense")
    try:
        from scripts.template_package import build_package_manifest
    except ImportError:
        from template_package import build_package_manifest
    package = build_package_manifest(OUT, version="0.2.0", status="review", examples=["templates/layouts/nsfc_defense/04_content.svg"])
    package["capability_level"] = "production"
    package["production_eligible"] = False
    package["runtime_contract"] = "compiled/template_ir.json"
    package["dependency_lock"] = "compiled/template.lock.json"
    (OUT / "template_package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        from scripts.template_compiler import compile_template
        from scripts.template_package import rebuild_template_registry, validate_package
    except ImportError:
        from template_compiler import compile_template
        from template_package import rebuild_template_registry, validate_package
    validation = validate_package(OUT)
    if validation.get("status") != "pass":
        raise ValueError(f"generated nsfc_defense package is invalid: {validation.get('issues')}")
    compiled = compile_template(OUT, write=True)
    registry = rebuild_template_registry(repo_root=ROOT, write=True)
    result = {
        "status": "pass",
        "manifest": package,
        "validation": validation,
        "compile": {
            "status": compiled["status"],
            "capability_level": compiled["capability_level"],
            "source_digest": compiled["source_digest"],
        },
        "registry": registry,
    }
    public_slot_count = sum(
        1 if slide["shell_id"] == "content" else len(slide["slots"])
        for slide in slides
    )
    return {"template_dir": str(OUT), "slide_count": len(slides), "slot_count": public_slot_count, "package": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical nsfc_defense template.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Built nsfc_defense: {result['template_dir']} ({result['slide_count']} pages, {result['slot_count']} slots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
