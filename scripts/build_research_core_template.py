#!/usr/bin/env python3
"""Build the managed ``research_core`` general-research template package.

The historic ``research-core`` pack contained six self-contained research
scenes.  They are intentionally migrated into one template package here:
their visual language stays intact, while template ownership, shells,
selection, and QA become explicit.
"""

from __future__ import annotations

from copy import deepcopy
import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from typing import Any

try:
    from scripts.component_asset_manifest import materialize_asset_manifest
    from scripts.component_gallery import render_story_svg
    from scripts.template_capabilities import derive_capability_profile
    from scripts.template_compiler import compile_template
    from scripts.template_package import build_package_manifest, rebuild_template_registry, validate_package
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from component_asset_manifest import materialize_asset_manifest
    from component_gallery import render_story_svg
    from template_capabilities import derive_capability_profile
    from template_compiler import compile_template
    from template_package import build_package_manifest, rebuild_template_registry, validate_package


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "templates" / "layouts" / "research_core"
SOURCE_PACK = ROOT / "templates" / "components" / "packages" / "research-core"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def _slot_targets(prefix: str, fields: tuple[str, ...], count: int) -> dict[str, list[str]]:
    return {field: [f"{prefix}_{index:02d}_{field.upper()}" for index in range(1, count + 1)] for field in fields}


SCENES: tuple[dict[str, Any], ...] = (
    {
        "component_id": "three_card_summary",
        "variant_id": "three_card_summary",
        "story_role": "parallel_summary",
        "content_shapes": ["parallel_points", "three_findings", "three_contributions", "risk_set"],
        "density": "medium",
        "item_count": 3,
        "slot_targets": _slot_targets("CARD", ("title", "body"), 3),
    },
    {
        "component_id": "process_timeline",
        "variant_id": "process_timeline",
        "story_role": "method_pipeline",
        "content_shapes": ["workflow", "method_pipeline", "procedure", "process", "timeline"],
        "density": "medium",
        "item_count": 4,
        "slot_targets": _slot_targets("STEP", ("title", "body"), 4),
    },
    {
        "component_id": "figure_with_notes",
        "variant_id": "figure_with_notes",
        "story_role": "figure_interpretation",
        "content_shapes": ["figure_with_notes", "single_exhibit", "result_interpretation", "image_evidence", "figure_explanation"],
        "density": "medium",
        "item_count": 1,
        "slot_targets": {
            "image": ["FIGURE_IMAGE"],
            "takeaway": ["FIGURE_TAKEAWAY"],
            "bullets": ["FIGURE_NOTES"],
        },
        "extra_slots": [
            {
                "slot_id": "FIGURE_CAPTION",
                "kind": "text",
                "role": "caption",
                "required": False,
                "capacity": {
                    "font_size_px": 13,
                    "min_font_size_px": 12,
                    "line_height": 1.2,
                    "max_chars_per_line_zh": 34,
                    "max_lines": 1,
                    "overflow_action": "move_to_notes",
                },
                "alignment": {"vertical": "middle", "text_center_y": "container_center_y"},
            }
        ],
    },
    {
        "component_id": "kpi_row_3",
        "variant_id": "kpi_row_3",
        "story_role": "metric_summary",
        "content_shapes": ["metric_set", "three_numbers", "dashboard_summary"],
        "density": "low",
        "item_count": 3,
        "slot_targets": _slot_targets("METRIC", ("metric", "label", "note"), 3),
    },
    {
        "component_id": "comparison_pair",
        "variant_id": "comparison_pair",
        "story_role": "comparison",
        "content_shapes": ["two_sides", "before_after", "method_comparison", "domestic_foreign"],
        "density": "medium",
        "item_count": 2,
        "slot_targets": {
            "title": ["LEFT_TITLE", "RIGHT_TITLE"],
            "body": ["LEFT_BODY", "RIGHT_BODY"],
            "synthesis": ["SYNTHESIS"],
        },
    },
    {
        "component_id": "evidence_stack",
        "variant_id": "evidence_stack",
        "story_role": "evidence_chain",
        "content_shapes": ["evidence_list", "supporting_points", "paper_findings"],
        "density": "high",
        "item_count": 3,
        "slot_targets": {
            "claim": ["EVIDENCE_CLAIM"],
            "evidence": ["EVIDENCE_01", "EVIDENCE_02", "EVIDENCE_03"],
        },
    },
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _local_name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _story_payload(component_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    component_dir = SOURCE_PACK / "components" / component_id
    component = _read_json(component_dir / "component.json")
    story = _read_json(component_dir / "stories" / "default.json")
    payload = story.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{component_id} default story has no object payload")
    return component, payload


def _make_text_slot(node: ET.Element, slot_id: str) -> None:
    node.set("data-slot", slot_id)
    node.set("data-slot-kind", "text")
    node.set("data-pptx-textbox", "true")
    node.set("data-pptx-valign", "middle")
    node.set("data-center-lock", "true")


def _nodes_with_source_slot(root: ET.Element, source_slot: str) -> list[ET.Element]:
    return [node for node in root.iter() if node.attrib.get("data-slot-id") == source_slot]


def _add_figure_image_and_caption(root: ET.Element) -> None:
    children = list(root)
    placeholder_nodes: list[ET.Element] = []
    caption: ET.Element | None = None
    figure_frame: ET.Element | None = None
    for node in children:
        tag = _local_name(node)
        text = "".join(node.itertext()).strip()
        if tag == "rect" and node.attrib.get("x") == "122" and node.attrib.get("y") == "198":
            figure_frame = node
        if tag == "text" and text in {"FIGURE", "preserve aspect ratio | source-linked"}:
            placeholder_nodes.append(node)
        if tag == "text" and node.attrib.get("x") == "858" and node.attrib.get("y") == "560":
            caption = node
    for node in placeholder_nodes:
        root.remove(node)
    image = ET.Element(
        f"{{{SVG_NS}}}image",
        {
            "x": "122",
            "y": "198",
            "width": "610",
            "height": "322",
            "preserveAspectRatio": "xMidYMid meet",
            "data-slot": "FIGURE_IMAGE",
            "data-slot-kind": "image",
        },
    )
    insert_at = list(root).index(figure_frame) + 1 if figure_frame is not None else 0
    root.insert(insert_at, image)
    if caption is None:
        raise ValueError("figure scene is missing its caption node")
    _make_text_slot(caption, "FIGURE_CAPTION")
    caption.set("data-pptx-box-x", "858")
    caption.set("data-pptx-box-y", "540")
    caption.set("data-pptx-box-w", "306")
    caption.set("data-pptx-box-h", "28")


def _component_svg(scene: dict[str, Any]) -> tuple[ET.Element, dict[str, Any], dict[str, Any]]:
    component_id = str(scene["component_id"])
    component, payload = _story_payload(component_id)
    rendered = render_story_svg(component_id, "default", payload, "pass", renderer_id=component_id)
    root = ET.fromstring(rendered)
    children = list(root)
    if len(children) < 9:
        raise ValueError(f"unexpected gallery shell for {component_id}")
    for child in children[:8]:
        root.remove(child)

    slot_targets = scene["slot_targets"]
    for source_slot, target_slots in slot_targets.items():
        if source_slot == "image":
            continue
        nodes = _nodes_with_source_slot(root, source_slot)
        if len(nodes) != len(target_slots):
            raise ValueError(
                f"{component_id} expects {len(target_slots)} rendered {source_slot} slots, got {len(nodes)}"
            )
        for node, target in zip(nodes, target_slots):
            _make_text_slot(node, target)

    if component_id == "figure_with_notes":
        _add_figure_image_and_caption(root)

    root.set("viewBox", "0 0 1280 720")
    root.set("width", "1280")
    root.set("height", "720")
    return root, component, payload


def _node_geometry(node: ET.Element) -> dict[str, float]:
    def number(*names: str, fallback: str = "0") -> float:
        raw = next((node.attrib[name] for name in names if name in node.attrib), fallback)
        return float(raw)

    if _local_name(node) == "image":
        return {
            "x": number("x"),
            "y": number("y"),
            "width": number("width"),
            "height": number("height"),
        }
    return {
        "x": number("data-pptx-box-x", "x"),
        "y": number("data-pptx-box-y", "y"),
        "width": number("data-pptx-box-w", "width", fallback="1"),
        "height": number("data-pptx-box-h", "height", fallback="1"),
    }


def _scene_slots(root: ET.Element, component: dict[str, Any], scene: dict[str, Any]) -> list[dict[str, Any]]:
    source_slots = {
        str(slot.get("slot_id") or ""): slot
        for slot in component.get("slots", [])
        if isinstance(slot, dict) and slot.get("slot_id")
    }
    source_by_target = {
        target: source_slot
        for source_slot, targets in scene["slot_targets"].items()
        for target in targets
    }
    slots: list[dict[str, Any]] = []
    for node in root.iter():
        target = str(node.attrib.get("data-slot") or "")
        if not target:
            continue
        source_slot = source_by_target.get(target, "")
        source = deepcopy(source_slots.get(source_slot, {}))
        if source:
            source.pop("repeated", None)
            source["slot_id"] = target
        else:
            source = next(
                deepcopy(slot)
                for slot in scene.get("extra_slots", [])
                if slot.get("slot_id") == target
            )
        source["kind"] = str(node.attrib.get("data-slot-kind") or source.get("kind") or "text")
        source["geometry"] = _node_geometry(node)
        source["vertical_anchor"] = "middle"
        source["style_policy"] = "template_locked"
        slots.append(source)
    seen = [str(slot["slot_id"]) for slot in slots]
    if len(seen) != len(set(seen)):
        raise ValueError(f"duplicate generated scene slots for {scene['component_id']}")
    return slots


def _text_slot(
    slot_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    size: int,
    fill: str,
    weight: str,
    anchor: str = "start",
    required: bool = True,
    max_lines: int = 1,
    max_chars: int = 40,
) -> tuple[str, dict[str, Any]]:
    text_x = x if anchor == "start" else x + width / 2
    text_anchor = "start" if anchor == "start" else "middle"
    svg = (
        f'<text data-slot="{slot_id}" data-slot-kind="text" data-pptx-textbox="true" '
        f'data-pptx-box-x="{x}" data-pptx-box-y="{y}" data-pptx-box-w="{width}" '
        f'data-pptx-box-h="{height}" data-pptx-valign="middle" data-center-lock="true" '
        f'x="{text_x}" y="{y + height / 2}" text-anchor="{text_anchor}" '
        f'font-family="Aptos, Segoe UI, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f'<tspan x="{text_x}" y="{y + height / 2}">{slot_id}</tspan></text>'
    )
    contract = {
        "slot_id": slot_id,
        "kind": "text",
        "required": required,
        "role": slot_id.lower(),
        "capacity": {
            "max_lines": max_lines,
            "max_chars_per_line": max_chars,
            "single_line_required": max_lines == 1,
            "overflow_action": "shorten_or_split",
        },
        "geometry": {"x": x, "y": y, "width": width, "height": height},
        "vertical_anchor": "middle",
    }
    return svg, contract


def _shells() -> tuple[list[dict[str, Any]], dict[str, str]]:
    cover_title, cover_title_slot = _text_slot("TITLE", 96, 220, 1040, 92, size=48, fill="#172033", weight="800", max_lines=2, max_chars=26)
    cover_subtitle, cover_subtitle_slot = _text_slot("SUBTITLE", 96, 334, 940, 42, size=22, fill="#4B5B6D", weight="500", max_chars=48)
    cover_meta, cover_meta_slot = _text_slot("PRESENTER", 96, 570, 700, 32, size=16, fill="#617083", weight="600", max_chars=48)
    toc_title, toc_title_slot = _text_slot("PAGE_TITLE", 70, 44, 760, 36, size=28, fill="#FFFFFF", weight="800", max_chars=30)
    toc_1, toc_1_slot = _text_slot("SECTION_01", 150, 190, 850, 52, size=28, fill="#172033", weight="800", max_chars=28)
    toc_2, toc_2_slot = _text_slot("SECTION_02", 150, 320, 850, 52, size=28, fill="#172033", weight="800", max_chars=28)
    toc_3, toc_3_slot = _text_slot("SECTION_03", 150, 450, 850, 52, size=28, fill="#172033", weight="800", max_chars=28)
    chapter_no, chapter_no_slot = _text_slot("CHAPTER_NO", 96, 190, 320, 50, size=24, fill="#8FB9D7", weight="800", max_chars=12)
    chapter_title, chapter_title_slot = _text_slot("CHAPTER_TITLE", 96, 274, 920, 90, size=48, fill="#FFFFFF", weight="800", max_lines=2, max_chars=26)
    content_title, content_title_slot = _text_slot("PAGE_TITLE", 70, 41, 760, 36, size=28, fill="#FFFFFF", weight="800", max_chars=28)
    content_message, content_message_slot = _text_slot("KEY_MESSAGE", 70, 78, 930, 22, size=14, fill="#B7C3D3", weight="600", max_lines=1, max_chars=56)
    page_number, page_number_slot = _text_slot("PAGE_NUMBER", 1092, 660, 108, 24, size=14, fill="#617083", weight="800", anchor="end", max_chars=4)
    page_number_slot["role"] = "page_number"
    page_number_slot["content_role"] = "navigation"
    page_number_slot["value_policy"] = "automatic_slide_index"
    ending_title, ending_title_slot = _text_slot("CLOSING", 160, 276, 960, 76, size=46, fill="#FFFFFF", weight="800", anchor="middle", max_lines=2, max_chars=28)
    ending_subtitle, ending_subtitle_slot = _text_slot("SUBTITLE", 240, 382, 800, 34, size=18, fill="#B7C3D3", weight="600", anchor="middle", required=False, max_chars=48)

    shared_header = '<rect x="38" y="30" width="1204" height="86" rx="18" fill="#172033"/><rect x="38" y="98" width="1204" height="18" fill="#172033"/>'
    shells = {
        "01_cover.svg": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#F7F8FA"/><rect x="38" y="30" width="1204" height="660" rx="18" fill="#FFFFFF" stroke="#D7DDE5"/>
  <rect x="38" y="30" width="1204" height="12" rx="6" fill="#1C75BC"/><circle cx="1080" cy="210" r="144" fill="#EAF3FA"/><circle cx="1080" cy="210" r="92" fill="#C9DFF0"/>
  {cover_title}{cover_subtitle}<line x1="96" y1="426" x2="512" y2="426" stroke="#1C75BC" stroke-width="6"/>{cover_meta}
</svg>''',
        "02_toc.svg": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#F7F8FA"/><rect x="38" y="30" width="1204" height="660" rx="18" fill="#FFFFFF" stroke="#D7DDE5"/>{shared_header}{toc_title}
  <circle cx="102" cy="216" r="24" fill="#1C75BC"/><text x="102" y="224" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" font-size="18" font-weight="800" fill="#FFFFFF">01</text>{toc_1}
  <circle cx="102" cy="346" r="24" fill="#0F766E"/><text x="102" y="354" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" font-size="18" font-weight="800" fill="#FFFFFF">02</text>{toc_2}
  <circle cx="102" cy="476" r="24" fill="#145F8F"/><text x="102" y="484" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" font-size="18" font-weight="800" fill="#FFFFFF">03</text>{toc_3}
</svg>''',
        "03_chapter.svg": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#172033"/><rect x="38" y="30" width="1204" height="660" rx="18" fill="#172033" stroke="#334155"/><rect x="96" y="156" width="150" height="10" rx="5" fill="#1C75BC"/>
  {chapter_no}{chapter_title}<circle cx="1080" cy="418" r="154" fill="#145F8F" opacity="0.55"/><circle cx="1080" cy="418" r="92" fill="#1C75BC" opacity="0.55"/>
</svg>''',
        "04_content.svg": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#F7F8FA"/><rect x="38" y="30" width="1204" height="660" rx="18" fill="#FFFFFF" stroke="#D7DDE5"/>{shared_header}{content_title}{content_message}{page_number}
</svg>''',
        "05_ending.svg": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#172033"/><rect x="38" y="30" width="1204" height="660" rx="18" fill="#172033" stroke="#334155"/><rect x="444" y="210" width="392" height="10" rx="5" fill="#1C75BC"/>
  {ending_title}{ending_subtitle}<circle cx="640" cy="504" r="48" fill="#145F8F"/><path d="M620 504 L636 520 L666 484" fill="none" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
</svg>''',
    }
    shell_rows = [
        {"shell_id": "cover", "role": "cover", "svg": "01_cover.svg", "slots": [cover_title_slot, cover_subtitle_slot, cover_meta_slot]},
        {"shell_id": "toc", "role": "agenda", "svg": "02_toc.svg", "slots": [toc_title_slot, toc_1_slot, toc_2_slot, toc_3_slot]},
        {"shell_id": "chapter", "role": "chapter", "svg": "03_chapter.svg", "slots": [chapter_no_slot, chapter_title_slot]},
        {
            "shell_id": "content",
            "role": "content",
            "svg": "04_content.svg",
            "slots": [content_title_slot, content_message_slot, page_number_slot],
            "body_canvas": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 720.0},
            "content_shell_policy": "template_scene_variant_required",
        },
        {"shell_id": "ending", "role": "ending", "svg": "05_ending.svg", "slots": [ending_title_slot, ending_subtitle_slot]},
    ]
    return shell_rows, shells


def _flatten_payload(scene: dict[str, Any], source_payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    items = source_payload.get("items") if isinstance(source_payload.get("items"), list) else []
    for source_slot, targets in scene["slot_targets"].items():
        if source_slot == "image":
            continue
        if len(targets) == 1 and source_slot in source_payload:
            result[targets[0]] = source_payload[source_slot]
            continue
        for index, target in enumerate(targets):
            item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
            result[target] = item.get(source_slot, "")
    if scene["component_id"] == "figure_with_notes":
        result["FIGURE_CAPTION"] = source_payload.get("caption") or source_payload.get("source") or "Source-linked figure"
    return result


def _build_documents(scenes: list[dict[str, Any]], shells: list[dict[str, Any]]) -> None:
    layouts = {
        "schema_version": "easyslides.research_core.layouts.v1",
        "template_id": "research_core",
        "canvas": {"format": "ppt169", "width": 1280, "height": 720},
        "shells": shells,
        "layouts": shells,
    }
    _write_json(OUT / "layouts.json", layouts)
    variants = []
    recipes = []
    catalog_components = []
    roster = []
    for index, scene in enumerate(scenes, start=1):
        component_id = str(scene["component_id"])
        root, source_component, source_payload = _component_svg(scene)
        scene_path = OUT / "assets" / "components" / "scenes" / f"{component_id}.svg"
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(root).write(scene_path, encoding="utf-8", xml_declaration=True)
        slots = _scene_slots(root, source_component, scene)
        asset_id = f"component/research_core/{component_id}"
        catalog_components.append(
            {
                "asset_id": asset_id,
                "component_id": component_id,
                "asset_path": f"assets/components/scenes/{component_id}.svg",
                "asset_status": "renderable_svg",
                "render_backend": "template_svg_component",
                "renderer_id": "research_core_scene",
                "classification": "template_scoped_body_scene",
                "reuse_policy": "research_core_body_variant_only",
                "category": "research_scene",
                "description": str(source_component.get("display_name") or component_id),
                "slots": slots,
                "selection": {"page_roles": ["content"], "density": scene["density"]},
                "geometry": {"width": 1280, "height": 720},
                "provenance": {
                    "source_pack": "research-core",
                    "source_component": component_id,
                    "style_mutation_policy": "preserve_research_core_visual_tokens_and_text_geometry",
                },
                "qa": {
                    "required_gates": ["asset_manifest", "component_geometry", "vertical_center_alignment"],
                    "alignment_invariants": [{"rule": "text_center_y_matches_container_center_y", "scope": "text_in_container", "severity": "error"}],
                },
            }
        )
        regions = [
            {
                "region_id": "scene",
                "frame": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 720.0},
                "coordinate_space": "body_canvas",
                "z_index": 20,
                "fit": "contain",
            }
        ]
        variants.append(
            {
                "variant_id": scene["variant_id"],
                "shell_id": "content",
                "composition_mode": "ordered_component_refs",
                "best_for": str(source_component.get("selection", {}).get("best_for") or component_id),
                "content_shapes": scene["content_shapes"],
                "story_roles": [scene["story_role"]],
                "density": scene["density"],
                "min_items": scene["item_count"],
                "max_items": scene["item_count"],
                "slots": slots,
                "regions": regions,
                # The source-derived scene keeps a full-slide coordinate system,
                # so the non-rendered clear constraint must cover that same canvas.
                "clear_region": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 720.0},
                "coordinate_space": "body_canvas",
                "composition_scene": f"research_core_{component_id}",
                "component_refs": [
                    {
                        "asset_id": asset_id,
                        "instance_id": "scene",
                        "role": "body_scene",
                        "order": 1,
                        "required": True,
                        "region": "scene",
                        "slot_bindings": {slot["slot_id"]: slot["slot_id"] for slot in slots},
                    }
                ],
            }
        )
        recipes.append({"variant_id": scene["variant_id"], "scene_component": component_id, "primitives": [], "source_slides": []})
        roster.append(
            {
                "scene": component_id,
                "variant_id": scene["variant_id"],
                "source_pack": "research-core",
                "content_shapes": scene["content_shapes"],
                "default_payload": _flatten_payload(scene, source_payload),
            }
        )

    _write_json(
        OUT / "body_variants.json",
        {
            "schema_version": "easyslides.research_core.body_variants.v1",
            "template_id": "research_core",
            "coordinate_space": "body_canvas",
            "content_area": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 720.0},
            "composition_contract": "regions_required",
            "variants": variants,
            "constraint": "Content pages select one reviewed research_core scene; direct body_components are forbidden.",
        },
    )
    _write_json(
        OUT / "component_catalog.json",
        {
            "schema_version": "easyslides.research_core.component_catalog.v1",
            "template_id": "research_core",
            "selection_policy": "template_body_variant_then_template_scoped_scene",
            "primitive_manifest": "component_primitives.json",
            "recipe_manifest": "body_variant_recipes.json",
            "components": catalog_components,
            "symbols": [],
            "unknown_component_count": 0,
        },
    )
    _write_json(OUT / "component_primitives.json", {"schema_version": "easyslides.research_core.component_primitives.v1", "template_id": "research_core", "primitives": []})
    _write_json(OUT / "body_variant_recipes.json", {"schema_version": "easyslides.research_core.body_variant_recipes.v1", "template_id": "research_core", "recipes": recipes})
    _write_json(
        OUT / "component_pack.json",
        {
            "schema_version": "easyslides.template_component_pack.v1",
            "pack_id": "template/research_core/components",
            "template_id": "research_core",
            "version": "1.0.0",
            "display_name": "Research Core Template Scenes",
            "description": "Template-scoped general research scenes migrated from the historic research-core component source.",
            "license": "MIT",
            "scope": "template",
            "dependencies": {"component_packs": []},
            "design_tokens": {"source": "design_tokens.json", "required": ["color.primary", "surface.canvas", "surface.panel", "text.primary", "typography.title.font_size_px", "layout.grid_px"]},
            "entrypoints": {"catalog": "component_catalog.json", "primitives": "component_primitives.json", "recipes": "body_variant_recipes.json"},
            "qa": {"required_gates": ["template_component_pack_contract", "component_catalog", "body_variant_component_contract", "vertical_center_alignment"]},
        },
    )
    _write_json(
        OUT / "design_tokens.json",
        {
            "schema_version": "easyslides.template_design_tokens.v1",
            "color": {"primary": "#1C75BC", "secondary": "#0F766E", "ink": "#172033", "inverse": "#FFFFFF"},
            "surface": {"canvas": "#F7F8FA", "panel": "#FFFFFF", "soft": "#EAF3FA"},
            "text": {"primary": "#172033", "secondary": "#4B5B6D", "inverse": "#FFFFFF"},
            "typography": {"title": {"font_size_px": 28, "line_height": 1.16}, "body": {"font_size_px": 18, "line_height": 1.28}, "caption": {"font_size_px": 14, "line_height": 1.2}},
            "layout": {"grid_px": 8, "header_height_px": 86, "border_px": 1},
        },
    )
    _write_json(
        OUT / "template.json",
        {
            "schema_version": "easyslides.template_pack.v1",
            "template_id": "research_core",
            "display_name": "General Research Briefing",
            "description": "A general research-report template with six controlled evidence and analysis scenes.",
            "mode": "template_scene_composition",
            "recommended_template_route": "template_scene_composition",
            "output_contract": "editable-native-pptx",
            "style_system": "research_core",
            "layout_source_format": "svg",
            "runtime_source_of_truth": "template_chrome_plus_reviewed_scene_variants",
            "scenarios": ["single_paper_report", "lab_progress", "technical_report", "conference_talk", "workshop_training"],
            "roles": ["cover", "agenda", "chapter", "content", "ending"],
            "layout_count": 5,
            "variant_count": len(scenes),
            "component_asset_model": {"policy": "template_scoped_body_scenes_only", "recipe_manifest": "body_variant_recipes.json"},
            "content_information_hierarchy": ["running_title", "central_message", "body_variant", "page_number"],
            "page_selection_inputs": ["scenario", "content_shape", "story_role", "item_count", "density"],
            "forbidden_selection_inputs": ["global_component_fallback", "dom_order_only"],
        },
    )
    _write_json(
        OUT / "qa_policy.json",
        {
            "schema_version": "easyslides.template_qa_policy.v1",
            "template_id": "research_core",
            "promotion_policy": "fail_closed",
            "alignment_invariants": ["text_center_y_matches_container_center_y", "declared_slots_stay_inside_canvas", "component_regions_stay_inside_canvas", "content_shell_owns_running_title_key_message_and_page_number"],
            "required_gates": ["template_compile", "slide_composition", "body_variant_component_contract", "svg_quality", "svg_text_slots", "template_geometry_svg", "asset_manifest", "template_geometry_pptx", "pptx_text_layout", "cross_material_smoke", "human_visual_review"],
            "vertical_center_tolerance_px": 1.0,
        },
    )
    _write_json(OUT / "source_page_roster.json", {"schema_version": "easyslides.research_core.scene_roster.v1", "template_id": "research_core", "source": "templates/components/packages/research-core", "scenes": roster})
    _write_json(
        OUT / "geometry_contract.json",
        {
            "schema_version": "easyslides.research_core.geometry_contract.v1",
            "template_id": "research_core",
            "canvas": {"width": 1280, "height": 720},
            "hard_invariants": ["text_center_y_matches_container_center_y", "declared_slots_stay_inside_canvas"],
            "pages": [{"page_id": shell["shell_id"], "svg": shell["svg"], "regions": shell.get("regions", [])} for shell in shells],
        },
    )
    _write_json(
        OUT / "slot_contracts.json",
        {
            "schema_version": "easyslides.template_slot_contracts.v1",
            "template_id": "research_core",
            "replacement_rule": "replace_declared_slots_preserve_template_geometry",
            "text_fit_policy": {"overflow_strategy_order": ["choose_declared_scene", "split_content", "shorten_within_capacity"]},
            "layouts": [{"layout_id": shell["shell_id"], "slots": [slot["slot_id"] for slot in shell["slots"]]} for shell in shells],
        },
    )
    (OUT / "design_spec.md").write_text(
        "# General Research Briefing\n\n"
        "`research_core` is a complete general-research template package, not a global component pack. "
        "It uses five stable shells and six controlled content scenes for parallel findings, workflows, figures, metrics, comparisons, and evidence chains. "
        "The content shell owns the running title, central message, and page number; one declared scene owns the evidence area.\n",
        encoding="utf-8",
    )
    (OUT / "rules.md").write_text(
        "# Research Core Rules\n\n"
        "- Select this template explicitly after scenario clarification.\n"
        "- Every content slide selects exactly one declared body variant.\n"
        "- Keep the running title on one line and use the secondary header line for the concise central message.\n"
        "- Do not import components from another template or global package.\n"
        "- Text inside visual containers remains vertically centered.\n",
        encoding="utf-8",
    )


def _write_qa_assets() -> None:
    """Provide a neutral local image for required-image composition smoke tests."""
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "figure_placeholder.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1"><rect width="1" height="1" fill="none"/></svg>\n',
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    shells, shell_svgs = _shells()
    for name, content in shell_svgs.items():
        (OUT / name).write_text(content + "\n", encoding="utf-8")
    _build_documents(list(SCENES), shells)
    _write_qa_assets()
    _write_json(OUT / "capability_profile.json", derive_capability_profile(OUT))
    materialize_asset_manifest(OUT, namespace="research_core")
    package = build_package_manifest(OUT, version="1.0.0", status="review", examples=["templates/layouts/research_core/04_content.svg"])
    package["capability_level"] = "production"
    package["production_eligible"] = False
    package["runtime_contract"] = "compiled/template_ir.json"
    package["selection"] = {
        "user_selectable": True,
        "selection_mode": "explicit_or_clarified",
        "display_category": "general_research",
        "forbid_implicit_global_component_mix": True,
    }
    _write_json(OUT / "template_package.json", package)
    validation = validate_package(OUT)
    if validation["status"] != "pass":
        raise ValueError(f"research_core package is invalid: {validation['issues']}")
    compile_report = compile_template(OUT, write=True)
    registry = rebuild_template_registry(repo_root=ROOT, write=True)
    return {
        "status": "pass",
        "template_dir": str(OUT),
        "shell_count": len(shells),
        "scene_variant_count": len(SCENES),
        "validation": validation,
        "compile": {"status": compile_report["status"], "source_digest": compile_report["source_digest"]},
        "registry": {"template_count": registry["template_count"], "package_count": registry["package_count"]},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build()
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Built research_core: {report['template_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
