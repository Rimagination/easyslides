"""Source-like NSFC defense body-variant grammar.

This module captures the visual grammar distilled from the 12 source content
slides.  A variant is a reusable scene with named evidence, figure, metric,
and process slots; it is not a generic text panel with a different title.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PURPLE = "#751497"
RED = "#C00000"
INK = "#060607"
LAVENDER = "#F8EAFC"
SOFT_PURPLE = "#F0D9F6"
SOFT_GRAY = "#F5F5F7"

# All generated scene fragments use this compact primitive system. A page
# variant may be source-like, but it cannot invent a private card style.
COMPONENT_TOKENS = {
    "grid": 8,
    "rail_height": 6,
    "border": "#D5B2E0",
    "panel_fill": "#FFFFFF",
    "soft_fill": LAVENDER,
    "caption_fill": PURPLE,
    "claim_fill": PURPLE,
    "conclusion_fill": RED,
}

PRIMITIVE_CATALOG: list[dict[str, Any]] = [
    {"primitive_id": "claim_bar", "role": "page_claim", "style": "solid_primary_band"},
    {"primitive_id": "evidence_figure", "role": "visual_evidence", "style": "plain_visual_evidence"},
    {"primitive_id": "caption_bar", "role": "figure_caption", "style": "plain_figure_caption"},
    {"primitive_id": "info_panel", "role": "supporting_text", "style": "soft_panel_with_top_rail"},
    {"primitive_id": "callout_panel", "role": "named_insight", "style": "primary_header_plus_soft_body"},
    {"primitive_id": "metric_tile", "role": "quantitative_evidence", "style": "quiet_metric_tile"},
    {"primitive_id": "process_step", "role": "process_or_tag", "style": "solid_primary_step"},
    {"primitive_id": "comparison_matrix", "role": "structured_comparison", "style": "primary_header_grid"},
    {"primitive_id": "synthesis_bar", "role": "interpretation", "style": "soft_panel_with_primary_rail"},
    {"primitive_id": "conclusion_bar", "role": "page_conclusion", "style": "bold_plain_conclusion"},
]

VARIANT_RECIPES: dict[str, list[str]] = {
    "evidence_triptych": ["claim_bar", "info_panel", "evidence_figure", "caption_bar", "callout_panel", "synthesis_bar"],
    "two_track_evidence": ["claim_bar", "evidence_figure", "info_panel", "callout_panel", "synthesis_bar", "conclusion_bar"],
    "bottleneck_chain": ["claim_bar", "conclusion_bar", "evidence_figure", "caption_bar", "process_step"],
    "hotspot_metrics": ["info_panel", "evidence_figure", "caption_bar", "metric_tile", "callout_panel"],
    "hotspot_panels": ["claim_bar", "info_panel", "evidence_figure", "synthesis_bar"],
    "innovation_evidence": ["conclusion_bar", "process_step", "synthesis_bar", "evidence_figure", "caption_bar"],
    "ann_snn_comparison": ["comparison_matrix", "callout_panel", "evidence_figure", "caption_bar"],
    "plasticity_training": ["claim_bar", "conclusion_bar", "info_panel", "evidence_figure", "callout_panel"],
    "network_architecture": ["claim_bar", "info_panel", "evidence_figure", "process_step", "synthesis_bar"],
    "sensor_application": ["claim_bar", "evidence_figure", "info_panel", "process_step", "conclusion_bar"],
    "literature_result": ["info_panel", "evidence_figure", "callout_panel", "synthesis_bar"],
    "application_benefits": ["evidence_figure", "info_panel", "process_step", "metric_tile", "callout_panel", "conclusion_bar"],
}


def _text(
    slot_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    required: bool = True,
    lines: int = 1,
    chars: int = 24,
    size: int = 20,
    fill: str = INK,
    anchor: str = "middle",
    weight: str = "400",
) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "kind": "text",
        "required": required,
        "geometry": {"x": x, "y": y, "width": width, "height": height},
        "capacity": {
            "max_lines": lines,
            "max_chars_per_line": chars,
            "overflow_action": "choose_variant_or_split",
        },
        "vertical_anchor": "middle",
        "font_size": size,
        "fill": fill,
        "text_anchor": anchor,
        "font_weight": weight,
    }


def _image(
    slot_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    required: bool = False,
) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "kind": "image",
        "required": required,
        "geometry": {"x": x, "y": y, "width": width, "height": height},
        "image_fit": "contain",
    }


PRIMITIVE_ASSET_SPECS: dict[str, dict[str, Any]] = {
    "claim_bar": {
        "width": 640, "height": 64,
        "slots": [_text("TEXT", 18, 10, 604, 44, chars=34, size=22, fill="#FFFFFF")],
    },
    "evidence_figure": {
        "width": 320, "height": 210,
        "slots": [_image("FIGURE", 10, 14, 300, 176), _text("CAPTION", 10, 190, 300, 20, required=False, chars=20, size=14, fill=PURPLE)],
    },
    "caption_bar": {
        "width": 320, "height": 38,
        "slots": [_text("TEXT", 12, 4, 296, 30, chars=20, size=16, fill=PURPLE)],
    },
    "info_panel": {
        "width": 360, "height": 150,
        "slots": [_text("TITLE", 18, 16, 324, 34, chars=21, size=19, fill=PURPLE, anchor="start"), _text("BODY", 18, 62, 324, 74, lines=3, chars=24, size=16, anchor="start")],
    },
    "callout_panel": {
        "width": 360, "height": 170,
        "slots": [_text("TITLE", 18, 10, 324, 38, chars=20, size=19, fill="#FFFFFF"), _text("BODY", 18, 66, 324, 86, lines=4, chars=24, size=16, anchor="start")],
    },
    "metric_tile": {
        "width": 180, "height": 104,
        "slots": [_text("VALUE", 14, 18, 152, 38, chars=12, size=26, fill=PURPLE), _text("LABEL", 14, 64, 152, 26, chars=14, size=15)],
    },
    "process_step": {
        "width": 220, "height": 60,
        "slots": [_text("TEXT", 16, 8, 188, 44, lines=2, chars=14, size=18, fill="#FFFFFF")],
    },
    "comparison_matrix": {
        "width": 660, "height": 240,
        "slots": [_text("TITLE", 20, 10, 620, 32, chars=32, size=20, fill="#FFFFFF"), _text("LEFT", 24, 78, 190, 132, lines=5, chars=14, size=16), _text("MIDDLE", 232, 78, 190, 132, lines=5, chars=14, size=16), _text("RIGHT", 440, 78, 190, 132, lines=5, chars=14, size=16)],
    },
    "synthesis_bar": {
        "width": 640, "height": 76,
        "slots": [_text("TEXT", 24, 12, 592, 52, lines=2, chars=42, size=20, fill=PURPLE)],
    },
    "conclusion_bar": {
        "width": 640, "height": 56,
        "slots": [_text("TEXT", 18, 8, 604, 40, chars=42, size=20, fill=PURPLE, weight="700")],
    },
}


SOURCE_COMPONENT_HEIGHT = 520
CONTENT_COMPONENT_HEIGHT = 448
CONTENT_VERTICAL_COMPRESSION = CONTENT_COMPONENT_HEIGHT / SOURCE_COMPONENT_HEIGHT


COMPONENTS: dict[str, tuple[int, int, str]] = {
    "evidence_triptych": (1120, CONTENT_COMPONENT_HEIGHT, "national-need claim, relationship, and three evidence exhibits"),
    "two_track_evidence": (1120, CONTENT_COMPONENT_HEIGHT, "two strategic tracks with evidence and an application callout"),
    "bottleneck_chain": (1120, CONTENT_COMPONENT_HEIGHT, "claim, bottleneck, four connected scientific exhibits, and conclusion"),
    "hotspot_metrics": (1120, CONTENT_COMPONENT_HEIGHT, "research hotspot with hero evidence, supporting figures, and four metrics"),
    "hotspot_panels": (1120, CONTENT_COMPONENT_HEIGHT, "three linked research hotspot panels with a synthesis"),
    "innovation_evidence": (1120, CONTENT_COMPONENT_HEIGHT, "innovation claim, four-step route, and three supporting exhibits"),
    "ann_snn_comparison": (1120, CONTENT_COMPONENT_HEIGHT, "ANN/SNN comparison matrix, method objective, and two evidence figures"),
    "plasticity_training": (1120, CONTENT_COMPONENT_HEIGHT, "training mechanism comparison, callout, and device evidence"),
    "network_architecture": (1120, CONTENT_COMPONENT_HEIGHT, "formula, network architecture, module evidence, and hardware flow"),
    "sensor_application": (1120, CONTENT_COMPONENT_HEIGHT, "dual application evidence: calibrated sensor and downstream system"),
    "literature_result": (1120, CONTENT_COMPONENT_HEIGHT, "researcher profile, publication collage, and external validation"),
    "application_benefits": (1120, CONTENT_COMPONENT_HEIGHT, "transfer evidence, quantitative benefits, and application result"),
}


COMPONENT_SLOT_MODELS: dict[str, list[dict[str, Any]]] = {
    "evidence_triptych": [
        _text("CLAIM", 32, 22, 650, 44, chars=32, size=23, fill="#FFFFFF"),
        _text("RELATION_LEFT", 48, 118, 192, 70, lines=2, chars=13, size=18),
        _text("RELATION_RIGHT", 276, 118, 192, 70, lines=2, chars=13, size=18),
        _image("FIGURE_01", 28, 280, 220, 136),
        _text("FIGURE_01_CAPTION", 28, 424, 220, 34, required=False, chars=16, size=16, fill="#FFFFFF"),
        _image("FIGURE_02", 270, 280, 220, 136),
        _text("FIGURE_02_CAPTION", 270, 424, 220, 34, required=False, chars=16, size=16, fill="#FFFFFF"),
        _image("FIGURE_03", 530, 98, 300, 196),
        _text("FIGURE_03_CAPTION", 530, 302, 300, 34, required=False, chars=20, size=16, fill="#FFFFFF"),
        _text("CALLOUT_TITLE", 862, 105, 224, 42, chars=15, size=19, fill="#FFFFFF"),
        _text("CALLOUT_BODY", 862, 166, 224, 96, lines=4, chars=16, size=17, anchor="start"),
        _image("CALLOUT_FIGURE", 862, 294, 224, 146),
        _text("SYNTHESIS", 530, 372, 556, 70, lines=2, chars=35, size=20, fill=PURPLE),
    ],
    "two_track_evidence": [
        _text("TRACK_01_TITLE", 30, 22, 492, 42, chars=22, size=21, fill="#FFFFFF"),
        _image("TRACK_01_FIGURE", 30, 86, 260, 162),
        _text("TRACK_01_POINT_01", 310, 86, 212, 44, lines=2, chars=14, size=16, anchor="start"),
        _text("TRACK_01_POINT_02", 310, 145, 212, 44, lines=2, chars=14, size=16, anchor="start"),
        _text("TRACK_01_POINT_03", 310, 204, 212, 44, lines=2, chars=14, size=16, anchor="start"),
        _text("TRACK_02_TITLE", 598, 22, 492, 42, chars=22, size=21, fill="#FFFFFF"),
        _image("TRACK_02_FIGURE", 598, 86, 330, 246),
        _text("TRACK_02_CALLOUT_TITLE", 948, 88, 142, 48, lines=2, chars=10, size=17, fill="#FFFFFF"),
        _text("TRACK_02_CALLOUT_BODY", 948, 154, 142, 128, lines=5, chars=10, size=15, anchor="start"),
        _text("TRACK_01_TAKEAWAY", 30, 372, 492, 68, lines=2, chars=30, size=19, fill=PURPLE),
        _text("TRACK_02_TAKEAWAY", 598, 372, 492, 68, lines=2, chars=30, size=19, fill=PURPLE),
        _text("CONCLUSION", 180, 462, 760, 40, chars=42, size=20, fill="#FFFFFF"),
    ],
    "bottleneck_chain": [
        _text("CLAIM", 28, 20, 1064, 44, chars=42, size=22, fill="#FFFFFF"),
        _text("BOTTLENECK", 270, 84, 580, 50, chars=28, size=21, fill=PURPLE, weight="700"),
        _image("FIGURE_01", 24, 184, 238, 142),
        _text("NODE_01", 24, 338, 238, 44, lines=2, chars=16, size=17, fill="#FFFFFF"),
        _image("FIGURE_02", 300, 184, 238, 142),
        _text("NODE_02", 300, 338, 238, 44, lines=2, chars=16, size=17, fill="#FFFFFF"),
        _image("FIGURE_03", 576, 184, 238, 142),
        _text("NODE_03", 576, 338, 238, 44, lines=2, chars=16, size=17, fill="#FFFFFF"),
        _image("FIGURE_04", 852, 184, 238, 142),
        _text("NODE_04", 852, 338, 238, 44, lines=2, chars=16, size=17, fill="#FFFFFF"),
        _text("CONCLUSION", 110, 430, 900, 52, chars=48, size=22, fill="#FFFFFF"),
    ],
    "hotspot_metrics": [
        _text("THEME_TITLE", 30, 20, 390, 48, lines=2, chars=20, size=22, fill=PURPLE, anchor="start"),
        _text("THEME_BODY", 30, 78, 390, 86, lines=4, chars=25, size=16, anchor="start"),
        _image("HERO_FIGURE", 452, 20, 278, 174),
        _text("TRANSITION", 30, 206, 700, 40, chars=38, size=19, fill="#FFFFFF"),
        _image("FIGURE_01", 30, 268, 318, 160),
        _text("FIGURE_01_CAPTION", 30, 436, 318, 32, required=False, chars=20, size=16, fill="#FFFFFF"),
        _image("FIGURE_02", 374, 268, 318, 160),
        _text("FIGURE_02_CAPTION", 374, 436, 318, 32, required=False, chars=20, size=16, fill="#FFFFFF"),
        _text("METRIC_01_VALUE", 770, 40, 136, 42, chars=10, size=24, fill=PURPLE),
        _text("METRIC_01_LABEL", 770, 84, 136, 34, chars=11, size=15),
        _text("METRIC_02_VALUE", 936, 40, 136, 42, chars=10, size=24, fill=PURPLE),
        _text("METRIC_02_LABEL", 936, 84, 136, 34, chars=11, size=15),
        _text("METRIC_03_VALUE", 770, 142, 136, 42, chars=10, size=24, fill=PURPLE),
        _text("METRIC_03_LABEL", 770, 186, 136, 34, chars=11, size=15),
        _text("METRIC_04_VALUE", 936, 142, 136, 42, chars=10, size=24, fill=PURPLE),
        _text("METRIC_04_LABEL", 936, 186, 136, 34, chars=11, size=15),
        _text("CONCLUSION", 748, 278, 340, 142, lines=4, chars=21, size=18, fill="#FFFFFF"),
    ],
    "hotspot_panels": [
        _text("PANEL_01_TITLE", 30, 24, 320, 42, chars=17, size=20, fill="#FFFFFF"),
        _text("PANEL_01_BODY", 30, 84, 320, 68, lines=3, chars=20, size=16, anchor="start"),
        _image("PANEL_01_FIGURE", 30, 170, 320, 184),
        _text("PANEL_02_TITLE", 400, 24, 320, 42, chars=17, size=20, fill="#FFFFFF"),
        _text("PANEL_02_BODY", 400, 84, 320, 68, lines=3, chars=20, size=16, anchor="start"),
        _image("PANEL_02_FIGURE", 400, 170, 320, 184),
        _text("PANEL_03_TITLE", 770, 24, 320, 42, chars=17, size=20, fill="#FFFFFF"),
        _text("PANEL_03_BODY", 770, 84, 320, 68, lines=3, chars=20, size=16, anchor="start"),
        _image("PANEL_03_FIGURE", 770, 170, 320, 184),
        _text("SYNTHESIS", 150, 400, 820, 60, lines=2, chars=46, size=21, fill=PURPLE),
    ],
    "innovation_evidence": [
        _text("INNOVATION_CLAIM", 30, 20, 1060, 48, lines=2, chars=48, size=22, fill=PURPLE, weight="700"),
        _text("STEP_01", 42, 106, 214, 54, lines=2, chars=14, size=18, fill="#FFFFFF"),
        _text("STEP_02", 310, 106, 214, 54, lines=2, chars=14, size=18, fill="#FFFFFF"),
        _text("STEP_03", 578, 106, 214, 54, lines=2, chars=14, size=18, fill="#FFFFFF"),
        _text("STEP_04", 846, 106, 214, 54, lines=2, chars=14, size=18, fill="#FFFFFF"),
        _text("SUPPORTING_LINE", 184, 184, 752, 44, chars=42, size=20, fill=PURPLE),
        _image("FIGURE_01", 38, 258, 318, 152),
        _text("FIGURE_01_CAPTION", 38, 418, 318, 34, required=False, chars=20, size=16, fill="#FFFFFF"),
        _image("FIGURE_02", 401, 258, 318, 152),
        _text("FIGURE_02_CAPTION", 401, 418, 318, 34, required=False, chars=20, size=16, fill="#FFFFFF"),
        _image("FIGURE_03", 764, 258, 318, 152),
        _text("FIGURE_03_CAPTION", 764, 418, 318, 34, required=False, chars=20, size=16, fill="#FFFFFF"),
    ],
    "ann_snn_comparison": [
        _text("TABLE_TITLE", 30, 20, 690, 40, chars=32, size=21, fill="#FFFFFF"),
        _text("COLUMN_01", 30, 78, 154, 36, chars=10, size=16, fill="#FFFFFF"),
        _text("COLUMN_02", 184, 78, 268, 36, chars=12, size=16, fill="#FFFFFF"),
        _text("COLUMN_03", 452, 78, 268, 36, chars=12, size=16, fill="#FFFFFF"),
        _text("ROW_01_LABEL", 30, 114, 154, 38, chars=10, size=15),
        _text("ROW_01_ANN", 184, 114, 268, 38, chars=18, size=15),
        _text("ROW_01_SNN", 452, 114, 268, 38, chars=18, size=15),
        _text("ROW_02_LABEL", 30, 152, 154, 38, chars=10, size=15),
        _text("ROW_02_ANN", 184, 152, 268, 38, chars=18, size=15),
        _text("ROW_02_SNN", 452, 152, 268, 38, chars=18, size=15),
        _text("ROW_03_LABEL", 30, 190, 154, 38, chars=10, size=15),
        _text("ROW_03_ANN", 184, 190, 268, 38, chars=18, size=15),
        _text("ROW_03_SNN", 452, 190, 268, 38, chars=18, size=15),
        _text("ROW_04_LABEL", 30, 228, 154, 38, chars=10, size=15),
        _text("ROW_04_ANN", 184, 228, 268, 38, chars=18, size=15),
        _text("ROW_04_SNN", 452, 228, 268, 38, chars=18, size=15),
        _text("OBJECTIVE_TITLE", 764, 29, 324, 42, lines=2, chars=18, size=19, fill="#FFFFFF"),
        _text("OBJECTIVE_BODY", 764, 88, 324, 96, lines=4, chars=22, size=16, anchor="start"),
        _image("FIGURE_01", 48, 328, 310, 118),
        _text("FIGURE_01_CAPTION", 48, 454, 310, 30, required=False, chars=20, size=15, fill="#FFFFFF"),
        _image("FIGURE_02", 402, 328, 310, 118),
        _text("FIGURE_02_CAPTION", 402, 454, 310, 30, required=False, chars=20, size=15, fill="#FFFFFF"),
        _text("SYNTHESIS", 764, 244, 324, 54, lines=2, chars=24, size=20, fill=PURPLE, weight="700"),
    ],
    "plasticity_training": [
        _text("POINT_01", 30, 20, 514, 48, lines=2, chars=29, size=20, fill="#FFFFFF"),
        _text("POINT_02", 576, 20, 514, 48, lines=2, chars=29, size=20, fill=PURPLE, weight="700"),
        _text("ANN_LABEL", 30, 94, 300, 36, chars=16, size=19, fill=PURPLE),
        _image("ANN_FIGURE", 30, 138, 300, 188),
        _text("SNN_LABEL", 386, 94, 300, 36, chars=16, size=19, fill=PURPLE),
        _image("SNN_FIGURE", 386, 138, 300, 188),
        _text("CALLOUT_TITLE", 748, 94, 340, 44, chars=20, size=20, fill="#FFFFFF"),
        _text("CALLOUT_BODY", 748, 148, 340, 96, lines=4, chars=22, size=16, anchor="start"),
        _image("SUPPORT_FIGURE", 748, 270, 340, 110),
        _text("CONCLUSION", 80, 422, 960, 52, lines=2, chars=55, size=21, fill="#FFFFFF"),
    ],
    "network_architecture": [
        _text("ARCHITECTURE_CLAIM", 30, 20, 470, 52, lines=2, chars=25, size=21, fill="#FFFFFF"),
        _text("FORMULA", 30, 92, 220, 54, chars=18, size=19, fill=PURPLE),
        _image("FIGURE_01", 276, 84, 240, 142),
        _text("STAGE_01", 534, 96, 170, 42, lines=2, chars=10, size=16, fill="#FFFFFF"),
        _text("STAGE_02", 732, 96, 170, 42, lines=2, chars=10, size=16, fill="#FFFFFF"),
        _text("STAGE_03", 930, 96, 160, 42, lines=2, chars=10, size=16, fill="#FFFFFF"),
        _text("MODULE_TITLE", 30, 258, 330, 40, chars=20, size=19, fill=PURPLE),
        _image("FIGURE_02", 30, 310, 330, 132),
        _text("MODULE_BODY", 378, 310, 280, 132, lines=5, chars=18, size=16, anchor="start"),
        _text("HARDWARE_TITLE", 704, 258, 386, 40, chars=20, size=19, fill=PURPLE),
        _image("FIGURE_03", 704, 310, 386, 132),
        _text("CONCLUSION", 162, 466, 796, 34, chars=43, size=19, fill="#FFFFFF"),
    ],
    "sensor_application": [
        _text("APPLICATION_CLAIM", 30, 18, 1060, 46, lines=2, chars=50, size=21, fill="#FFFFFF"),
        _image("LEFT_FIGURE", 30, 94, 476, 230),
        _text("LEFT_TITLE", 30, 334, 476, 38, chars=25, size=19, fill=PURPLE),
        _text("LEFT_NODE_01", 30, 390, 142, 40, lines=2, chars=10, size=15, fill="#FFFFFF"),
        _text("LEFT_NODE_02", 194, 390, 142, 40, lines=2, chars=10, size=15, fill="#FFFFFF"),
        _text("LEFT_NODE_03", 358, 390, 142, 40, lines=2, chars=10, size=15, fill="#FFFFFF"),
        _image("RIGHT_FIGURE", 614, 94, 476, 230),
        _text("RIGHT_TITLE", 614, 334, 476, 38, chars=25, size=19, fill=PURPLE),
        _text("RIGHT_NODE_01", 614, 390, 142, 40, lines=2, chars=10, size=15, fill="#FFFFFF"),
        _text("RIGHT_NODE_02", 778, 390, 142, 40, lines=2, chars=10, size=15, fill="#FFFFFF"),
        _text("RIGHT_NODE_03", 942, 390, 142, 40, lines=2, chars=10, size=15, fill="#FFFFFF"),
        _text("CONCLUSION", 150, 458, 820, 38, chars=46, size=20, fill="#FFFFFF"),
    ],
    "literature_result": [
        _image("PROFILE_FIGURE", 30, 54, 164, 164),
        _text("PROFILE_NAME", 216, 58, 284, 42, chars=16, size=22, fill=PURPLE, anchor="start"),
        _text("PROFILE_CREDENTIAL", 216, 108, 284, 48, lines=2, chars=18, size=16, anchor="start"),
        _text("PROFILE_QUOTE", 216, 170, 284, 54, lines=3, chars=18, size=16, fill="#FFFFFF"),
        _image("PAPER_FIGURE_01", 536, 50, 248, 150),
        _image("PAPER_FIGURE_02", 810, 50, 280, 150),
        _image("PAPER_FIGURE_03", 30, 276, 328, 144),
        _text("VALIDATION_TITLE", 390, 274, 286, 44, chars=18, size=20, fill="#FFFFFF"),
        _text("VALIDATION_BODY", 390, 330, 286, 100, lines=5, chars=18, size=16, anchor="start"),
        _text("RESULT_TITLE", 720, 274, 370, 44, chars=22, size=20, fill="#FFFFFF"),
        _text("RESULT_BODY", 720, 330, 370, 100, lines=5, chars=24, size=16, anchor="start"),
        _text("CONCLUSION", 136, 462, 848, 40, chars=46, size=20, fill="#FFFFFF"),
    ],
    "application_benefits": [
        _image("HERO_FIGURE", 30, 26, 340, 184),
        _text("TRANSFER_CLAIM", 400, 26, 690, 48, lines=2, chars=38, size=21, fill=PURPLE, anchor="start"),
        _text("TRANSFER_BODY", 400, 88, 690, 72, lines=3, chars=44, size=16, anchor="start"),
        _text("TAG_01", 400, 176, 146, 32, chars=9, size=14, fill="#FFFFFF"),
        _text("TAG_02", 558, 176, 146, 32, chars=9, size=14, fill="#FFFFFF"),
        _text("TAG_03", 716, 176, 146, 32, chars=9, size=14, fill="#FFFFFF"),
        _text("TAG_04", 874, 176, 146, 32, chars=9, size=14, fill="#FFFFFF"),
        _text("METRIC_01_VALUE", 40, 276, 220, 56, chars=10, size=31, fill=PURPLE),
        _text("METRIC_01_LABEL", 40, 338, 220, 34, chars=14, size=16),
        _text("METRIC_02_VALUE", 286, 276, 220, 56, chars=10, size=31, fill=PURPLE),
        _text("METRIC_02_LABEL", 286, 338, 220, 34, chars=14, size=16),
        _image("RESULT_FIGURE", 658, 258, 432, 142),
        _text("RESULT_TITLE", 532, 278, 106, 40, lines=2, chars=7, size=17, fill="#FFFFFF"),
        _text("RESULT_BODY", 532, 328, 106, 62, lines=3, chars=7, size=14, fill=INK),
        _text("CONCLUSION", 120, 448, 880, 42, chars=48, size=20, fill="#FFFFFF"),
    ],
}


def _variant(
    variant_id: str,
    source_slide: int,
    section: str,
    story_role: str,
    purpose: str,
    best_for: str,
    figure_count: int,
    density: int,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "source_slides": [source_slide],
        "section": section,
        "story_roles": [story_role],
        "narrative_step": source_slide,
        "source_page_purpose": purpose,
        "density": density,
        "best_for": best_for,
        "components": [variant_id],
        "composition_profile": f"{variant_id}_scene",
        "figure_count": figure_count,
    }


BODY_VARIANTS: list[dict[str, Any]] = [
    _variant("evidence_triptych", 3, "01", "national_need_evidence", "Establish the need with a claim, relationship, and three converging exhibits.", "national-need claim supported by three independent evidence exhibits", 4, 5),
    _variant("two_track_evidence", 4, "01", "strategic_need_two_track", "Connect the need to complementary scientific and application tracks.", "two-track scientific roadmap with evidence and distinct takeaways", 2, 5),
    _variant("bottleneck_chain", 5, "01", "scientific_bottleneck", "Explain the bottleneck through four linked observations before stating the intervention.", "problem-to-bottleneck chain with four connected exhibits", 4, 5),
    _variant("hotspot_metrics", 6, "01", "research_hotspot_metrics", "Locate the research hotspot using performance evidence and quantitative indicators.", "research hotspot with figures and four decision metrics", 3, 5),
    _variant("hotspot_panels", 7, "01", "research_hotspot_synthesis", "Synthesize three hotspot directions as linked research panels.", "three-column research landscape with a synthesis", 3, 5),
    _variant("innovation_evidence", 9, "02", "innovation_overview", "State the innovation package as a four-step route backed by three exhibits.", "innovation pathway with a four-step route and three supporting figures", 3, 5),
    _variant("ann_snn_comparison", 10, "02", "method_comparison", "Contrast baseline and event-driven methods in a decision table, then show the selection rationale.", "method comparison table with two scientific figures", 2, 5),
    _variant("plasticity_training", 11, "02", "device_mechanism_training", "Relate training behavior to device plasticity through paired mechanism evidence.", "ANN/SNN mechanism comparison with device-training callout", 3, 5),
    _variant("network_architecture", 12, "02", "system_architecture", "Show formula-to-network-to-hardware architecture as one technical scene.", "layered network architecture with module and hardware flow", 3, 5),
    _variant("sensor_application", 13, "02", "application_pipeline", "Demonstrate the calibrated sensing path and the downstream system path together.", "dual-application evidence with sensor and system panels", 2, 5),
    _variant("literature_result", 14, "02", "external_validation", "Anchor the contribution in researcher, paper, and external validation evidence.", "publication collage and external validation result", 4, 5),
    _variant("application_benefits", 16, "03", "impact_and_benefits", "Close with transfer evidence, performance metrics, and practical application outcome.", "application impact with transfer evidence and quantified benefits", 2, 5),
]


COMPOSITION_PROFILES: dict[str, dict[str, Any]] = {
    f"{component_id}_scene": {
        "scene": f"source_like_{component_id}",
        "regions": [("main", (0.0, 0.0, 1.0, 1.0), 10)],
        "component_regions": {component_id: "main"},
    }
    for component_id in COMPONENTS
}


def component_slots(component_id: str) -> list[dict[str, Any]] | None:
    slots = COMPONENT_SLOT_MODELS.get(component_id)
    if slots is None:
        return None
    normalized = deepcopy(slots)
    for slot in normalized:
        slot_id = str(slot.get("slot_id") or "")
        geometry = slot.get("geometry")
        if isinstance(geometry, dict):
            geometry["y"] = round(float(geometry["y"]) * CONTENT_VERTICAL_COMPRESSION, 3)
            geometry["height"] = round(float(geometry["height"]) * CONTENT_VERTICAL_COMPRESSION, 3)
        if slot_id.endswith("CAPTION") or slot_id.startswith("NODE_"):
            slot["fill"] = PURPLE
        if slot_id == "CONCLUSION":
            slot["fill"] = PURPLE
            slot["font_weight"] = "700"
        if slot.get("kind") == "image":
            slot["content_role"] = "evidence_figure"
        elif slot_id.endswith("CAPTION"):
            slot["content_role"] = "figure_caption"
        elif slot_id in {"CONCLUSION", "SYNTHESIS", "SUPPORTING_LINE"}:
            slot["content_role"] = "supporting_takeaway"
        elif slot_id.endswith("TITLE") or "CLAIM" in slot_id or slot_id in {"BOTTLENECK", "FORMULA"}:
            slot["content_role"] = "evidence_heading"
        elif "BODY" in slot_id or slot_id.startswith(("POINT_", "NODE_", "STEP_", "STAGE_", "ROW_")):
            slot["content_role"] = "evidence_detail"
        else:
            slot["content_role"] = "data_label"
    return normalized


def _rect(x: float, y: float, w: float, h: float, fill: str, *, stroke: str = "none", opacity: float | None = None) -> str:
    extra = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"{extra}/>'


def _line(x1: float, y1: float, x2: float, y2: float, *, color: str = PURPLE, width: float = 2.0) -> str:
    return f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{color}" stroke-width="{width}"/>'


def _arrow(x1: float, y1: float, x2: float, y2: float, *, color: str = PURPLE) -> str:
    return "".join([
        _line(x1, y1, x2, y2, color=color, width=3),
        _line(x2, y2, x2 - 9, y2 - 7, color=color, width=3),
        _line(x2, y2, x2 - 9, y2 + 7, color=color, width=3),
    ])


def _frame(x: float, y: float, w: float, h: float) -> str:
    # A figure's visual language comes from the evidence itself. Do not wrap
    # it in decorative rails, outlines, or backing rectangles.
    return ""


def _info_panel(x: float, y: float, w: float, h: float) -> str:
    return _rect(x, y, w, h, COMPONENT_TOKENS["soft_fill"], stroke=COMPONENT_TOKENS["border"]) + _rect(x, y, w, COMPONENT_TOKENS["rail_height"], PURPLE)


def _claim_bar(x: float, y: float, w: float, h: float, *, emphasis: bool = False) -> str:
    return _rect(x, y, w, h, RED if emphasis else COMPONENT_TOKENS["claim_fill"])


def _caption_bar(x: float, y: float, w: float, h: float = 34) -> str:
    # Figure captions are semantic labels, not a second decorative panel.
    return ""


def _callout_panel(x: float, y: float, w: float, h: float, *, header_height: float = 56) -> str:
    return (
        _rect(x, y, w, h, COMPONENT_TOKENS["soft_fill"], stroke=COMPONENT_TOKENS["border"])
        + _rect(x, y, w, header_height, COMPONENT_TOKENS["claim_fill"])
    )


def _step_node(x: float, y: float, w: float, h: float) -> str:
    return _rect(x, y, w, h, COMPONENT_TOKENS["claim_fill"])


def _synthesis_bar(x: float, y: float, w: float, h: float) -> str:
    return _info_panel(x, y, w, h) + _rect(x, y, 8, h, PURPLE)


def _conclusion_bar(x: float, y: float, w: float, h: float) -> str:
    # Conclusions are typographic anchors, not colored containers.
    return ""


def _metric_cell(x: float, y: float) -> str:
    return _rect(x, y, 136, 82, COMPONENT_TOKENS["panel_fill"], stroke=COMPONENT_TOKENS["border"])


def _base() -> list[str]:
    # The source 1120 x 520 composition is vertically compacted so the content
    # shell can reserve a stable key-message zone without wasting page area.
    return []


def _surface(component_id: str) -> list[str]:
    s = _base()
    if component_id == "evidence_triptych":
        s += [_claim_bar(18, 14, 678, 60), _info_panel(28, 98, 472, 130), _arrow(246, 153, 264, 153), _frame(28, 280, 220, 136), _frame(270, 280, 220, 136), _caption_bar(28, 424, 220), _caption_bar(270, 424, 220), _frame(530, 98, 300, 196), _caption_bar(530, 302, 300), _callout_panel(852, 98, 242, 174), _frame(862, 294, 224, 146), _synthesis_bar(520, 360, 576, 94)]
    elif component_id == "two_track_evidence":
        s += [_claim_bar(22, 14, 508, 58), _claim_bar(590, 14, 508, 58), _frame(30, 86, 260, 162), _frame(598, 86, 330, 246), _info_panel(300, 80, 232, 178), _callout_panel(938, 80, 160, 216, header_height=64), _synthesis_bar(30, 362, 502, 90), _synthesis_bar(598, 362, 492, 90), _conclusion_bar(170, 462, 780, 40)]
    elif component_id == "bottleneck_chain":
        s += [_claim_bar(18, 12, 1084, 60), _conclusion_bar(260, 84, 600, 50), *[_frame(x, 184, 238, 142) for x in (24, 300, 576, 852)], *[_caption_bar(x, 338, 238, 44) for x in (24, 300, 576, 852)], _arrow(264, 255, 288, 255), _arrow(540, 255, 564, 255), _arrow(816, 255, 840, 255), _conclusion_bar(100, 430, 920, 52)]
    elif component_id == "hotspot_metrics":
        s += [_info_panel(20, 12, 410, 170), _frame(452, 20, 278, 174), _claim_bar(20, 202, 720, 48), _frame(30, 268, 318, 160), _frame(374, 268, 318, 160), _caption_bar(30, 436, 318, 32), _caption_bar(374, 436, 318, 32), *[_metric_cell(x, y) for y in (30, 132) for x in (770, 936)], _conclusion_bar(748, 266, 350, 166)]
    elif component_id == "hotspot_panels":
        s += [*[_claim_bar(x, 14, 340, 58) for x in (20, 390, 760)], *[_info_panel(x, 76, 340, 82) for x in (20, 390, 760)], *[_frame(x, 170, 320, 184) for x in (30, 400, 770)], _arrow(352, 262, 380, 262), _arrow(722, 262, 750, 262), _synthesis_bar(140, 394, 840, 72)]
    elif component_id == "innovation_evidence":
        s += [_conclusion_bar(18, 12, 1084, 66), *[_step_node(x, 102, 224, 62) for x in (36, 304, 572, 840)], _arrow(264, 133, 292, 133), _arrow(532, 133, 560, 133), _arrow(800, 133, 828, 133), _synthesis_bar(174, 180, 772, 52), *[_frame(x, 258, 318, 152) for x in (38, 401, 764)], *[_caption_bar(x, 418, 318) for x in (38, 401, 764)]]
    elif component_id == "ann_snn_comparison":
        s += [_claim_bar(20, 12, 710, 54), _claim_bar(30, 76, 690, 38), *[_rect(30, y, 690, 38, "#FFFFFF", stroke=COMPONENT_TOKENS["border"]) for y in (114, 152, 190, 228)], _line(184, 76, 184, 266), _line(452, 76, 452, 266), _callout_panel(754, 22, 344, 178), _frame(48, 328, 310, 118), _caption_bar(48, 454, 310, 30), _frame(402, 328, 310, 118), _caption_bar(402, 454, 310, 30), _conclusion_bar(754, 232, 344, 206)]
    elif component_id == "plasticity_training":
        s += [_claim_bar(20, 12, 534, 60), _conclusion_bar(566, 12, 534, 60), _info_panel(20, 88, 320, 46), _frame(30, 138, 300, 188), _info_panel(376, 88, 320, 46), _frame(386, 138, 300, 188), _arrow(342, 232, 372, 232), _callout_panel(738, 88, 360, 170, header_height=62), _frame(748, 270, 340, 110), _conclusion_bar(70, 414, 980, 68)]
    elif component_id == "network_architecture":
        s += [_claim_bar(20, 12, 490, 66), _info_panel(20, 84, 240, 70), _frame(276, 84, 240, 142), *[_step_node(x, 90, w, 54) for x, w in ((524, 190), (722, 190), (920, 180))], _line(714, 117, 722, 117, color=PURPLE, width=3), _line(912, 117, 920, 117, color=PURPLE, width=3), _info_panel(20, 250, 350, 54), _frame(30, 310, 330, 132), _info_panel(368, 300, 300, 152), _info_panel(694, 250, 406, 54), _frame(704, 310, 386, 132), _conclusion_bar(152, 462, 816, 42)]
    elif component_id == "sensor_application":
        s += [_claim_bar(18, 12, 1084, 62), _frame(30, 94, 476, 230), _info_panel(30, 330, 476, 46), *[_step_node(x, 386, 142, 48) for x in (30, 194, 358)], _frame(614, 94, 476, 230), _info_panel(614, 330, 476, 46), *[_step_node(x, 386, 142, 48) for x in (614, 778, 942)], _conclusion_bar(140, 450, 840, 48)]
    elif component_id == "literature_result":
        s += [_info_panel(20, 42, 490, 194), _frame(30, 54, 164, 164), _claim_bar(206, 162, 304, 70), _frame(536, 50, 248, 150), _frame(810, 50, 280, 150), _frame(30, 276, 328, 144), _callout_panel(380, 264, 306, 178, header_height=56), _callout_panel(710, 264, 390, 178, header_height=56), _conclusion_bar(126, 454, 868, 48)]
    elif component_id == "application_benefits":
        s += [_frame(30, 26, 340, 184), _info_panel(390, 16, 710, 150), *[_step_node(x, 176, 146, 32) for x in (400, 558, 716, 874)], _frame(30, 258, 240, 126), _frame(276, 258, 240, 126), _arrow(528, 324, 638, 324, color=RED), _callout_panel(522, 268, 126, 132, header_height=50), _frame(658, 258, 432, 142), _conclusion_bar(110, 438, 900, 58)]
    return s


def render_component_svg(component_id: str, width: int, height: int) -> str | None:
    slots = component_slots(component_id)
    if slots is None:
        return None
    nodes: list[str] = []
    for slot in slots:
        box = slot["geometry"]
        slot_id = str(slot["slot_id"])
        if slot["kind"] == "image":
            nodes.append(
                f'<image x="{box["x"]:.2f}" y="{box["y"]:.2f}" width="{box["width"]:.2f}" height="{box["height"]:.2f}" '
                f'preserveAspectRatio="xMidYMid meet" href="../transparent.svg" '
                f'data-slot="{slot_id}" data-slot-id="{slot_id}" data-slot-kind="image"/>'
            )
            continue
        size = int(slot.get("font_size") or 20)
        fill = str(slot.get("fill") or INK)
        anchor = str(slot.get("text_anchor") or "middle")
        weight = str(slot.get("font_weight") or "400")
        x = box["x"] + box["width"] / 2 if anchor == "middle" else box["x"] + 8
        y = box["y"] + box["height"] / 2 + size * 0.35
        nodes.append(
            f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" font-family="Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" data-slot="{slot_id}" data-slot-id="{slot_id}" '
            f'data-slot-kind="text" data-pptx-textbox="true" data-pptx-measure-text="T" '
            f'data-pptx-box-x="{box["x"]:.2f}" data-pptx-box-y="{box["y"]:.2f}" '
            f'data-pptx-box-w="{box["width"]:.2f}" data-pptx-box-h="{box["height"]:.2f}" '
            f'data-pptx-valign="middle" data-center-lock="true" data-pptx-line-height-ratio="1.150" '
            f'data-pptx-text-anchor="{anchor}">{slot_id}</text>'
        )
    surface = "\n    ".join(_surface(component_id))
    compressed_surface = (
        f'<g data-easyslides-layout="compressed_body_scene" '
        f'transform="scale(1 {CONTENT_VERTICAL_COMPRESSION:.8f})">\n    {surface}\n  </g>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" data-component="{component_id}">\n  {compressed_surface}\n  '
        + "\n  ".join(nodes)
        + "\n</svg>\n"
    )


def primitive_asset_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog_by_id = {row["primitive_id"]: row for row in PRIMITIVE_CATALOG}
    for primitive_id, spec in PRIMITIVE_ASSET_SPECS.items():
        catalog = catalog_by_id[primitive_id]
        rows.append(
            {
                **catalog,
                "asset_path": f"assets/primitives/{primitive_id}.svg",
                "geometry": {"width": spec["width"], "height": spec["height"]},
                "slots": deepcopy(spec["slots"]),
            }
        )
    return rows


def _primitive_surface(primitive_id: str, width: int, height: int) -> str:
    if primitive_id == "claim_bar":
        return _claim_bar(0, 0, width, height)
    if primitive_id == "evidence_figure":
        return _frame(10, 14, width - 20, height - 34) + _caption_bar(10, height - 20, width - 20, 20)
    if primitive_id == "caption_bar":
        return _caption_bar(0, 0, width, height)
    if primitive_id == "info_panel":
        return _info_panel(0, 0, width, height)
    if primitive_id == "callout_panel":
        return _callout_panel(0, 0, width, height)
    if primitive_id == "metric_tile":
        return _rect(0, 0, width, height, COMPONENT_TOKENS["panel_fill"], stroke=COMPONENT_TOKENS["border"])
    if primitive_id == "process_step":
        return _step_node(0, 0, width, height)
    if primitive_id == "comparison_matrix":
        return (
            _claim_bar(0, 0, width, 50)
            + _rect(12, 66, width - 24, height - 78, "#FFFFFF", stroke=COMPONENT_TOKENS["border"])
            + _line(width / 3, 66, width / 3, height - 12)
            + _line(width * 2 / 3, 66, width * 2 / 3, height - 12)
        )
    if primitive_id == "synthesis_bar":
        return _synthesis_bar(0, 0, width, height)
    if primitive_id == "conclusion_bar":
        return _conclusion_bar(0, 0, width, height)
    raise ValueError(f"unknown primitive asset {primitive_id!r}")


def render_primitive_svg(primitive_id: str) -> str:
    spec = PRIMITIVE_ASSET_SPECS[primitive_id]
    width, height = int(spec["width"]), int(spec["height"])
    nodes: list[str] = []
    for slot in spec["slots"]:
        box = slot["geometry"]
        slot_id = str(slot["slot_id"])
        if slot["kind"] == "image":
            nodes.append(
                f'<image x="{box["x"]:.2f}" y="{box["y"]:.2f}" width="{box["width"]:.2f}" height="{box["height"]:.2f}" '
                f'preserveAspectRatio="xMidYMid meet" href="../transparent.svg" '
                f'data-slot="{slot_id}" data-slot-id="{slot_id}" data-slot-kind="image"/>'
            )
            continue
        size = int(slot.get("font_size") or 20)
        fill = str(slot.get("fill") or INK)
        anchor = str(slot.get("text_anchor") or "middle")
        weight = str(slot.get("font_weight") or "400")
        x = box["x"] + box["width"] / 2 if anchor == "middle" else box["x"] + 8
        y = box["y"] + box["height"] / 2 + size * 0.35
        nodes.append(
            f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" font-family="Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" data-slot="{slot_id}" data-slot-id="{slot_id}" '
            f'data-slot-kind="text" data-pptx-textbox="true" data-pptx-measure-text="T" '
            f'data-pptx-box-x="{box["x"]:.2f}" data-pptx-box-y="{box["y"]:.2f}" '
            f'data-pptx-box-w="{box["width"]:.2f}" data-pptx-box-h="{box["height"]:.2f}" '
            f'data-pptx-valign="middle" data-center-lock="true" data-pptx-line-height-ratio="1.150" '
            f'data-pptx-text-anchor="{anchor}">{slot_id}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" data-primitive="{primitive_id}">\n  {_primitive_surface(primitive_id, width, height)}\n  '
        + "\n  ".join(nodes)
        + "\n</svg>\n"
    )
