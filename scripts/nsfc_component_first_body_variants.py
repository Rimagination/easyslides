"""Component-first content grammar for the NSFC defense template.

The original NSFC deck is the visual authority.  This module does not draw a
new purple card system: it turns selected, repeated source fragments into
editable leaf components and defines a small set of source-led page scenes.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMPONENT_DIR = (
    ROOT
    / "templates"
    / "components"
    / "source_templates"
    / "nsfc_defense_distilled_kit"
    / "components"
    / "source_faithful"
)
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _text(
    slot_id: str,
    *,
    chars: int,
    lines: int = 1,
    required: bool = True,
    box: tuple[float, float, float, float] | None = None,
    center_caption: bool = False,
    text_layout: str | None = None,
) -> dict[str, Any]:
    slot: dict[str, Any] = {
        "slot_id": slot_id,
        "kind": "text",
        "required": required,
        "capacity": {
            "max_lines": lines,
            "max_chars_per_line": chars,
            "overflow_action": "choose_variant_or_split",
        },
        "box": box,
        "center_caption": center_caption,
    }
    if text_layout:
        slot["text_layout"] = text_layout
    return slot


def _image(slot_id: str, *, required: bool = True) -> dict[str, Any]:
    return {"slot_id": slot_id, "kind": "image", "required": required}


# These are leaf components.  ``numbered_insight`` and the page header remain
# page-local/source-chrome records and are deliberately absent from this list.
COMPONENT_SPECS: list[dict[str, Any]] = [
    {
        "component_id": "statement_panel",
        "source_file": "statement_panel.svg",
        "category": "statement",
        "description": "Source statement panel for a short evidence heading.",
        "slots": [_text("STATEMENT", chars=34)],
    },
    {
        "component_id": "vertical_key_tag",
        "source_file": "vertical_key_tag.svg",
        "category": "label",
        "description": "Source vertical key-point tag.",
        # The source label is a narrow purple tag. Its editable copy must be
        # deliberately stacked in two-character Chinese units, never left to
        # Office's arbitrary glyph-level wrapping.
        "slots": [_text("TAG", chars=2, lines=3, text_layout="balanced_cjk_stack")],
    },
    {
        "component_id": "relationship_arrow_label",
        "source_file": "relationship_arrow_label.svg",
        "category": "connector",
        "description": "Source relationship arrow with two endpoint labels.",
        "slots": [
            _text("LEFT_LABEL", chars=10),
            _text("RIGHT_LABEL", chars=18),
            _text("CONNECTOR_LABEL", chars=4),
        ],
    },
    {
        "component_id": "image_footer_card",
        "source_file": "image_footer_card.svg",
        "category": "media_card",
        "description": "Source image card with a centered footer caption.",
        "slots": [
            _image("IMAGE"),
            _text("CAPTION", chars=12, center_caption=True),
        ],
    },
    {
        "component_id": "research_track_card",
        "source_file": "research_track_card.svg",
        "category": "media_card",
        "description": "Source research-track image card with a centered caption.",
        "slots": [
            _image("IMAGE"),
            _text("CAPTION", chars=12, center_caption=True),
        ],
    },
    {
        "component_id": "callout_media_panel",
        "source_file": "callout_media_panel.svg",
        "category": "callout",
        "description": "Source callout panel with title, short note, and media.",
        "slots": [
            _text("TITLE", chars=12),
            _text("DETAIL", chars=14, lines=3),
            _image("IMAGE"),
        ],
    },
    {
        "component_id": "evidence_tile",
        "source_file": "evidence_tile.svg",
        "category": "evidence",
        "description": "Source evidence tile with image and label.",
        "slots": [_image("IMAGE"), _text("LABEL", chars=10)],
    },
    {
        "component_id": "metric_tile",
        "source_file": "metric_tile.svg",
        "category": "metric",
        "description": "Source metric tile for one measured result.",
        "slots": [
            _text("VALUE", chars=8, box=(813.58, 432.01, 127.06, 46.0)),
            _text("LABEL", chars=10, box=(813.58, 480.0, 127.06, 39.25)),
        ],
    },
    {
        "component_id": "metric_group_header",
        "source_file": "metric_group_header.svg",
        "category": "label",
        "description": "Source metric-group header.",
        "slots": [_text("TITLE", chars=16)],
    },
    {
        "component_id": "comparison_matrix",
        "source_file": "comparison_matrix.svg",
        "category": "matrix",
        "description": "Source three-column comparison matrix.",
        "slots": [
            _text("COLUMN_01", chars=8),
            _text("COLUMN_02", chars=10),
            _text("COLUMN_03", chars=10),
            _text("ROW_01_LABEL", chars=8),
            _text("ROW_01_LEFT", chars=10),
            _text("ROW_01_RIGHT", chars=10),
            _text("ROW_02_LABEL", chars=8),
            _text("ROW_02_LEFT", chars=10),
            _text("ROW_02_RIGHT", chars=10),
            _text("ROW_03_LABEL", chars=8),
            _text("ROW_03_LEFT", chars=10),
            _text("ROW_03_RIGHT", chars=10),
            _text("CONCLUSION_LABEL", chars=8),
            # The source conclusion box is visually compact.  A longer claim
            # belongs in the page-level key message, not in this matrix label.
            _text("CONCLUSION", chars=8),
        ],
    },
    {
        "component_id": "media_caption_card",
        "source_file": "media_caption_card.svg",
        "category": "media_card",
        "description": "Source tall media card with centered caption.",
        "slots": [_image("IMAGE"), _text("CAPTION", chars=8, center_caption=True)],
    },
    {
        "component_id": "application_metric_card",
        "source_file": "application_metric_card.svg",
        "category": "metric",
        "description": "Source application outcome card.",
        "slots": [
            _text("LABEL", chars=14),
            _text("VALUE", chars=8),
            _text("TITLE", chars=12),
        ],
    },
    {
        "component_id": "vertical_feature_image_panel",
        "source_file": "vertical_feature_image_panel.svg",
        "category": "media_panel",
        "description": "Source feature image panel with an identity label.",
        "slots": [_text("LABEL", chars=2, lines=4, text_layout="balanced_cjk_stack"), _image("IMAGE")],
    },
]

_MATERIALIZED_SLOT_CACHE: dict[str, list[dict[str, Any]]] = {}


def _read_view_box(root: ET.Element) -> tuple[float, float, float, float]:
    values = [float(value) for value in root.attrib["viewBox"].replace(",", " ").split()]
    if len(values) != 4:
        raise ValueError("source component needs a four-value viewBox")
    return values[0], values[1], values[2], values[3]


def _parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


def _float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _source_text_box(
    node: ET.Element,
    parents: dict[ET.Element, ET.Element],
    view_box: tuple[float, float, float, float],
    explicit: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float]:
    if explicit is not None:
        return explicit
    raw = (
        node.attrib.get("data-pptx-box-x"),
        node.attrib.get("data-pptx-box-y"),
        node.attrib.get("data-pptx-box-w"),
        node.attrib.get("data-pptx-box-h"),
    )
    if all(value is not None for value in raw):
        return tuple(_float(value) for value in raw)  # type: ignore[return-value]
    parent = parents.get(node)
    if parent is not None:
        for child in parent:
            if child.tag.rsplit("}", 1)[-1] != "rect" or child.attrib.get("fill") != "none":
                continue
            if all(key in child.attrib for key in ("x", "y", "width", "height")):
                return (
                    _float(child.attrib.get("x")),
                    _float(child.attrib.get("y")),
                    _float(child.attrib.get("width")),
                    _float(child.attrib.get("height")),
                )
    _vx, vy, width, _height = view_box
    font_size = _float(node.attrib.get("font-size"), 24.0)
    x = _float(node.attrib.get("x"))
    y = _float(node.attrib.get("y"))
    return x, max(vy, y - font_size), max(font_size * 1.4, width - (x - _vx)), font_size * 1.4


def _local_geometry(
    box: tuple[float, float, float, float], view_box: tuple[float, float, float, float]
) -> dict[str, float]:
    vx, vy, _width, _height = view_box
    return {
        "x": round(box[0] - vx, 2),
        "y": round(box[1] - vy, 2),
        "width": round(box[2], 2),
        "height": round(box[3], 2),
    }


def _image_source_box(
    node: ET.Element,
    parents: dict[ET.Element, ET.Element],
) -> tuple[float, float, float, float]:
    """Use an enclosing SVG viewport when a source image is normalized to 1x1."""
    width = _float(node.attrib.get("width"))
    height = _float(node.attrib.get("height"))
    if width > 1.01 or height > 1.01:
        return (
            _float(node.attrib.get("x")),
            _float(node.attrib.get("y")),
            width,
            height,
        )
    parent = parents.get(node)
    while parent is not None:
        if parent.tag.rsplit("}", 1)[-1] == "svg":
            parent_width = _float(parent.attrib.get("width"))
            parent_height = _float(parent.attrib.get("height"))
            if parent_width > 1.01 or parent_height > 1.01:
                return (
                    _float(parent.attrib.get("x")),
                    _float(parent.attrib.get("y")),
                    parent_width,
                    parent_height,
                )
        parent = parents.get(parent)
    return (
        _float(node.attrib.get("x")),
        _float(node.attrib.get("y")),
        max(width, 1.0),
        max(height, 1.0),
    )


def _clip_hidden_root_rectangles(
    root: ET.Element,
    view_box: tuple[float, float, float, float],
) -> int:
    """Materialize SVG root clipping for native PPTX rectangle conversion.

    Imported source fragments may use ``overflow=hidden`` with a background
    rectangle that deliberately extends beyond the root viewBox. Browsers clip
    that excess, whereas DrawingML has no equivalent group clip and would draw
    it outside the declared component frame. Clamping only the previously
    invisible rectangle area preserves the visible source component exactly.
    """
    if root.attrib.get("overflow", "visible").lower() != "hidden":
        return 0
    vx, vy, width, height = view_box
    right = vx + width
    bottom = vy + height
    clipped = 0
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "rect":
            continue
        try:
            x = float(node.attrib["x"])
            y = float(node.attrib["y"])
            rect_width = float(node.attrib["width"])
            rect_height = float(node.attrib["height"])
        except (KeyError, TypeError, ValueError):
            continue
        clipped_left = max(x, vx)
        clipped_top = max(y, vy)
        clipped_right = min(x + rect_width, right)
        clipped_bottom = min(y + rect_height, bottom)
        if clipped_right <= clipped_left or clipped_bottom <= clipped_top:
            continue
        if (
            abs(clipped_left - x) <= 0.01
            and abs(clipped_top - y) <= 0.01
            and abs(clipped_right - (x + rect_width)) <= 0.01
            and abs(clipped_bottom - (y + rect_height)) <= 0.01
        ):
            continue
        node.set("x", f"{clipped_left:.2f}")
        node.set("y", f"{clipped_top:.2f}")
        node.set("width", f"{clipped_right - clipped_left:.2f}")
        node.set("height", f"{clipped_bottom - clipped_top:.2f}")
        clipped += 1
    return clipped


def _placeholder_text(node: ET.Element, slot: dict[str, Any], box: tuple[float, float, float, float]) -> None:
    for child in list(node):
        node.remove(child)
    node.text = str(slot["slot_id"])
    if slot.get("center_caption"):
        node.set("text-anchor", "middle")
        node.set("x", f"{box[0] + box[2] / 2:.2f}")
    anchor = node.attrib.get("text-anchor", "start")
    node.set("data-slot", str(slot["slot_id"]))
    node.set("data-slot-id", str(slot["slot_id"]))
    node.set("data-slot-kind", "text")
    node.set("data-pptx-textbox", "true")
    node.set("data-pptx-measure-text", "T")
    node.set("data-pptx-box-x", f"{box[0]:.2f}")
    node.set("data-pptx-box-y", f"{box[1]:.2f}")
    node.set("data-pptx-box-w", f"{box[2]:.2f}")
    node.set("data-pptx-box-h", f"{box[3]:.2f}")
    node.set("data-pptx-valign", "middle")
    node.set("data-center-lock", "true")
    node.set("data-pptx-line-height-ratio", "1.150")
    node.set("data-pptx-text-anchor", anchor)
    text_layout = str(slot.get("text_layout") or "").strip()
    if text_layout:
        capacity = slot.get("capacity") if isinstance(slot.get("capacity"), dict) else {}
        node.set("data-easyslides-layout", text_layout)
        node.set("data-easyslides-wrap-max-chars", str(int(capacity.get("max_chars_per_line") or 1)))
        node.set("data-easyslides-wrap-max-lines", str(int(capacity.get("max_lines") or 1)))
        # Positional tspans below are the only allowed line breaks for stacked
        # labels. Prevent native PowerPoint from inserting a second, accidental
        # wrap inside an already planned line.
        node.set("data-pptx-no-wrap", "true")


def materialize_component_assets(target_dir: Path) -> list[dict[str, Any]]:
    """Copy source visuals and expose only declared text/image payload slots."""
    target_dir.mkdir(parents=True, exist_ok=True)
    component_rows: list[dict[str, Any]] = []
    _MATERIALIZED_SLOT_CACHE.clear()
    for spec in COMPONENT_SPECS:
        source = SOURCE_COMPONENT_DIR / str(spec["source_file"])
        root = ET.parse(source).getroot()
        view_box = _read_view_box(root)
        native_viewport_rect_clips = _clip_hidden_root_rectangles(root, view_box)
        parents = _parent_map(root)
        text_nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "text"]
        image_nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "image"]
        text_index = image_index = 0
        slot_rows: list[dict[str, Any]] = []
        for raw_slot in spec["slots"]:
            slot = deepcopy(raw_slot)
            if slot["kind"] == "text":
                if text_index >= len(text_nodes):
                    raise ValueError(f"{spec['component_id']} has too few source text nodes")
                node = text_nodes[text_index]
                text_index += 1
                box = _source_text_box(node, parents, view_box, slot.pop("box", None))
                _placeholder_text(node, slot, box)
                slot["geometry"] = _local_geometry(box, view_box)
                slot["vertical_anchor"] = "middle"
                slot["style_policy"] = "source_locked"
                slot.pop("center_caption", None)
            else:
                if image_index >= len(image_nodes):
                    raise ValueError(f"{spec['component_id']} has too few source image nodes")
                node = image_nodes[image_index]
                image_index += 1
                node.set("href", "../transparent.svg")
                node.set(f"{{{XLINK_NS}}}href", "../transparent.svg")
                node.set("data-slot", str(slot["slot_id"]))
                node.set("data-slot-id", str(slot["slot_id"]))
                node.set("data-slot-kind", "image")
                slot["geometry"] = _local_geometry(_image_source_box(node, parents), view_box)
                slot["image_fit"] = "source_locked"
            slot_rows.append({key: value for key, value in slot.items() if key != "box"})
        root.set("data-easyslides-asset-status", "source_derived_editable")
        root.set("data-easyslides-style-policy", "source_locked")
        if native_viewport_rect_clips:
            root.set(
                "data-easyslides-native-viewport-rect-clips",
                str(native_viewport_rect_clips),
            )
        target = target_dir / f"{spec['component_id']}.svg"
        ET.register_namespace("", SVG_NS)
        ET.register_namespace("xlink", XLINK_NS)
        ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
        component_rows.append(
            {
                "asset_id": f"component/nsfc_defense/{spec['component_id']}",
                "component_id": spec["component_id"],
                "asset_path": f"assets/components/source_derived/{spec['component_id']}.svg",
                "asset_status": "renderable_svg",
                "render_backend": "template_svg_component",
                "renderer_id": "svg_fragment",
                "classification": "template_scoped_source_derived_leaf",
                "reuse_policy": "nsfc_defense_body_variant_only",
                "category": spec["category"],
                "description": spec["description"],
                "slots": slot_rows,
                "selection": {"page_roles": ["content"], "density": "dense_research_defense"},
                "geometry": {"width": view_box[2], "height": view_box[3]},
                "provenance": {
                    "source_asset": source.relative_to(ROOT).as_posix(),
                    "source_component_id": spec["component_id"],
                    "style_mutation_policy": "forbid_color_font_size_geometry_crop_and_layer_order_changes",
                    "native_viewport_policy": "clip_only_previously_hidden_rectangle_extents",
                },
                "qa": {"required_gates": ["asset_manifest", "component_geometry", "vertical_center_alignment"]},
            }
        )
        _MATERIALIZED_SLOT_CACHE[str(spec["component_id"])] = deepcopy(slot_rows)
    return component_rows


def source_component_dimensions() -> dict[str, tuple[int, int, str]]:
    rows: dict[str, tuple[int, int, str]] = {}
    for spec in COMPONENT_SPECS:
        root = ET.parse(SOURCE_COMPONENT_DIR / str(spec["source_file"])).getroot()
        _vx, _vy, width, height = _read_view_box(root)
        rows[str(spec["component_id"])] = (round(width), round(height), str(spec["description"]))
    return rows


COMPONENTS = source_component_dimensions()


def component_slots(component_id: str) -> list[dict[str, Any]] | None:
    cached = _MATERIALIZED_SLOT_CACHE.get(component_id)
    if cached is not None:
        return deepcopy(cached)
    for spec in COMPONENT_SPECS:
        if spec["component_id"] == component_id:
            return deepcopy(spec["slots"])
    return None


def _profile(scene: str, regions: list[tuple[str, tuple[float, float, float, float], int]]) -> dict[str, Any]:
    return {"scene": scene, "regions": regions}


COMPOSITION_PROFILES: dict[str, dict[str, Any]] = {
    "need_relationship_evidence": _profile(
        "source_component_need_relationship",
        [
            ("statement", (0.00, 0.00, 1.00, 0.18), 10),
            ("relationship", (0.01, 0.21, 0.64, 0.12), 20),
            ("track_one", (0.00, 0.38, 0.31, 0.62), 20),
            ("track_two", (0.32, 0.38, 0.31, 0.62), 20),
            ("callout", (0.68, 0.20, 0.30, 0.80), 20),
        ],
    ),
    "dual_track_evidence": _profile(
        "source_component_dual_track",
        [
            ("statement", (0.00, 0.00, 1.00, 0.18), 10),
            ("track_one", (0.00, 0.27, 0.43, 0.70), 20),
            ("track_two", (0.45, 0.27, 0.43, 0.70), 20),
            ("key_tag", (0.89, 0.30, 0.09, 0.55), 20),
        ],
    ),
    "evidence_chain": _profile(
        "source_component_evidence_chain",
        [
            ("statement", (0.10, 0.00, 0.90, 0.18), 10),
            ("key_tag", (0.00, 0.30, 0.10, 0.48), 20),
            ("evidence_one", (0.12, 0.30, 0.20, 0.62), 20),
            ("evidence_two", (0.34, 0.30, 0.20, 0.62), 20),
            ("evidence_three", (0.56, 0.30, 0.20, 0.62), 20),
            ("evidence_four", (0.78, 0.30, 0.20, 0.62), 20),
        ],
    ),
    "metric_dashboard": _profile(
        "source_component_metric_dashboard",
        [
            ("metric_header", (0.00, 0.02, 0.37, 0.13), 10),
            ("metric_one", (0.00, 0.19, 0.18, 0.27), 20),
            ("metric_two", (0.19, 0.19, 0.18, 0.27), 20),
            ("metric_three", (0.00, 0.49, 0.18, 0.27), 20),
            ("metric_four", (0.19, 0.49, 0.18, 0.27), 20),
            # This wide feature panel is native to the source deck.  Do not
            # force the unrelated metric and portrait-card components below it.
            ("feature", (0.40, 0.08, 0.60, 0.57), 20),
        ],
    ),
    "three_evidence_track": _profile(
        "source_component_three_evidence",
        [
            ("statement", (0.00, 0.00, 1.00, 0.18), 10),
            ("relationship", (0.15, 0.22, 0.70, 0.12), 20),
            ("evidence_one", (0.00, 0.43, 0.31, 0.55), 20),
            ("evidence_two", (0.34, 0.43, 0.31, 0.55), 20),
            ("evidence_three", (0.68, 0.43, 0.31, 0.55), 20),
        ],
    ),
    "comparison_evidence": _profile(
        "source_component_comparison",
        [
            ("statement", (0.00, 0.00, 1.00, 0.15), 10),
            ("matrix", (0.00, 0.20, 1.00, 0.76), 20),
        ],
    ),
    "application_system": _profile(
        "source_component_application_system",
        [
            ("application_metric", (0.00, 0.00, 0.41, 0.38), 20),
            ("feature", (0.44, 0.00, 0.56, 0.38), 20),
            ("callout", (0.00, 0.42, 0.30, 0.58), 20),
            ("media", (0.35, 0.42, 0.25, 0.58), 20),
            ("track", (0.65, 0.42, 0.35, 0.58), 20),
        ],
    ),
    "literature_transfer": _profile(
        "source_component_literature_transfer",
        [
            ("statement", (0.00, 0.00, 1.00, 0.18), 10),
            ("track", (0.00, 0.30, 0.32, 0.68), 20),
            ("media", (0.36, 0.30, 0.22, 0.68), 20),
            ("callout", (0.64, 0.20, 0.36, 0.80), 20),
        ],
    ),
}


def _instance(
    instance_id: str,
    component_id: str,
    region: str,
    bindings: dict[str, str],
    role: str,
) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "component_id": component_id,
        "region": region,
        "slot_bindings": bindings,
        "role": role,
    }


def _variant(
    variant_id: str,
    *,
    source_slides: list[int],
    section: str,
    story_roles: list[str],
    purpose: str,
    instances: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "source_slides": source_slides,
        "section": section,
        "story_roles": story_roles,
        "narrative_step": purpose,
        "source_page_purpose": purpose,
        "composition_profile": variant_id,
        "composition_mode": "ordered_component_refs",
        "components": list(dict.fromkeys(item["component_id"] for item in instances)),
        "component_instances": instances,
        "density": "dense_research_defense",
        "evidence_count": sum(1 for item in instances if item["role"] in {"evidence", "metric", "comparison"}),
    }


BODY_VARIANTS: list[dict[str, Any]] = [
    _variant(
        "need_relationship_evidence",
        source_slides=[3], section="01", story_roles=["national_need_evidence"],
        purpose="State the need, show its relationship, then ground it in two research tracks.",
        instances=[
            _instance("statement", "statement_panel", "statement", {"STATEMENT": "STATEMENT"}, "statement"),
            _instance("relationship", "relationship_arrow_label", "relationship", {"LEFT_LABEL": "FOUNDATION_LABEL", "RIGHT_LABEL": "APPLICATION_LABEL", "CONNECTOR_LABEL": "CONNECTOR_LABEL"}, "connector"),
            _instance("track_one", "image_footer_card", "track_one", {"IMAGE": "TRACK_01_IMAGE", "CAPTION": "TRACK_01_CAPTION"}, "evidence"),
            _instance("track_two", "research_track_card", "track_two", {"IMAGE": "TRACK_02_IMAGE", "CAPTION": "TRACK_02_CAPTION"}, "evidence"),
            _instance("callout", "callout_media_panel", "callout", {"TITLE": "CALLOUT_TITLE", "DETAIL": "CALLOUT_DETAIL", "IMAGE": "CALLOUT_IMAGE"}, "evidence"),
        ],
    ),
    _variant(
        "dual_track_evidence",
        source_slides=[4], section="01", story_roles=["two_research_tracks"],
        purpose="Compare two parallel tracks without losing their visual evidence.",
        instances=[
            _instance("statement", "statement_panel", "statement", {"STATEMENT": "STATEMENT"}, "statement"),
            _instance("track_one", "image_footer_card", "track_one", {"IMAGE": "TRACK_01_IMAGE", "CAPTION": "TRACK_01_CAPTION"}, "evidence"),
            _instance("track_two", "research_track_card", "track_two", {"IMAGE": "TRACK_02_IMAGE", "CAPTION": "TRACK_02_CAPTION"}, "evidence"),
            _instance("key_tag", "vertical_key_tag", "key_tag", {"TAG": "KEY_TAG"}, "label"),
        ],
    ),
    _variant(
        "evidence_chain",
        source_slides=[5], section="01", story_roles=["bottleneck_chain"],
        purpose="Use a compact evidence chain to make one bottleneck visible.",
        instances=[
            _instance("statement", "statement_panel", "statement", {"STATEMENT": "STATEMENT"}, "statement"),
            _instance("key_tag", "vertical_key_tag", "key_tag", {"TAG": "CHAIN_TAG"}, "label"),
            *[_instance(f"evidence_{index}", "evidence_tile", f"evidence_{name}", {"IMAGE": f"EVIDENCE_{index}_IMAGE", "LABEL": f"EVIDENCE_{index}_LABEL"}, "evidence") for index, name in enumerate(["one", "two", "three", "four"], start=1)],
        ],
    ),
    _variant(
        "metric_dashboard",
        source_slides=[6], section="01", story_roles=["research_hotspot_metrics"],
        purpose="Combine source metric tiles with one source-sized feature exhibit.",
        instances=[
            _instance("metric_header", "metric_group_header", "metric_header", {"TITLE": "METRIC_GROUP_TITLE"}, "label"),
            *[_instance(f"metric_{index}", "metric_tile", f"metric_{name}", {"VALUE": f"METRIC_{index}_VALUE", "LABEL": f"METRIC_{index}_LABEL"}, "metric") for index, name in enumerate(["one", "two", "three", "four"], start=1)],
            _instance("feature", "vertical_feature_image_panel", "feature", {"LABEL": "FEATURE_LABEL", "IMAGE": "FEATURE_IMAGE"}, "evidence"),
        ],
    ),
    _variant(
        "three_evidence_track",
        source_slides=[7, 9], section="02", story_roles=["innovation_evidence", "three_evidence_tracks"],
        purpose="Show one innovation through three visual evidence tracks.",
        instances=[
            _instance("statement", "statement_panel", "statement", {"STATEMENT": "STATEMENT"}, "statement"),
            _instance("relationship", "relationship_arrow_label", "relationship", {"LEFT_LABEL": "LEFT_LABEL", "RIGHT_LABEL": "RIGHT_LABEL", "CONNECTOR_LABEL": "CONNECTOR_LABEL"}, "connector"),
            *[_instance(f"evidence_{index}", "image_footer_card", f"evidence_{name}", {"IMAGE": f"EVIDENCE_{index}_IMAGE", "CAPTION": f"EVIDENCE_{index}_CAPTION"}, "evidence") for index, name in enumerate(["one", "two", "three"], start=1)],
        ],
    ),
    _variant(
        "comparison_evidence",
        source_slides=[10, 11], section="02", story_roles=["method_comparison", "mechanism_comparison"],
        purpose="Use the source comparison matrix for a bounded technical contrast.",
        instances=[
            _instance("statement", "statement_panel", "statement", {"STATEMENT": "STATEMENT"}, "statement"),
            _instance("matrix", "comparison_matrix", "matrix", {slot: slot for slot in ["COLUMN_01", "COLUMN_02", "COLUMN_03", "ROW_01_LABEL", "ROW_01_LEFT", "ROW_01_RIGHT", "ROW_02_LABEL", "ROW_02_LEFT", "ROW_02_RIGHT", "ROW_03_LABEL", "ROW_03_LEFT", "ROW_03_RIGHT", "CONCLUSION_LABEL", "CONCLUSION"]}, "comparison"),
        ],
    ),
    _variant(
        "application_system",
        source_slides=[12, 13], section="02", story_roles=["system_architecture", "application_pipeline"],
        purpose="Connect quantified performance, system evidence, and an application use case.",
        instances=[
            _instance("application_metric", "application_metric_card", "application_metric", {"LABEL": "APPLICATION_LABEL", "VALUE": "APPLICATION_VALUE", "TITLE": "APPLICATION_TITLE"}, "metric"),
            _instance("feature", "vertical_feature_image_panel", "feature", {"LABEL": "FEATURE_LABEL", "IMAGE": "FEATURE_IMAGE"}, "evidence"),
            _instance("callout", "callout_media_panel", "callout", {"TITLE": "CALLOUT_TITLE", "DETAIL": "CALLOUT_DETAIL", "IMAGE": "CALLOUT_IMAGE"}, "evidence"),
            _instance("media", "media_caption_card", "media", {"IMAGE": "MEDIA_IMAGE", "CAPTION": "MEDIA_CAPTION"}, "evidence"),
            _instance("track", "research_track_card", "track", {"IMAGE": "TRACK_IMAGE", "CAPTION": "TRACK_CAPTION"}, "evidence"),
        ],
    ),
    _variant(
        "literature_transfer",
        source_slides=[14, 16], section="03", story_roles=["external_validation", "application_benefits"],
        purpose="Close with external evidence and a concrete transfer result.",
        instances=[
            _instance("statement", "statement_panel", "statement", {"STATEMENT": "STATEMENT"}, "statement"),
            _instance("track", "research_track_card", "track", {"IMAGE": "TRACK_IMAGE", "CAPTION": "TRACK_CAPTION"}, "evidence"),
            _instance("media", "media_caption_card", "media", {"IMAGE": "MEDIA_IMAGE", "CAPTION": "MEDIA_CAPTION"}, "evidence"),
            _instance("callout", "callout_media_panel", "callout", {"TITLE": "CALLOUT_TITLE", "DETAIL": "CALLOUT_DETAIL", "IMAGE": "CALLOUT_IMAGE"}, "evidence"),
        ],
    ),
]


def component_recipe_map() -> dict[str, list[str]]:
    return {
        str(variant["variant_id"]): [
            str(item["component_id"]) for item in variant["component_instances"]
        ]
        for variant in BODY_VARIANTS
    }
