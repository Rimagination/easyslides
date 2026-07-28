#!/usr/bin/env python3
"""Derive semantic distillation contracts from a PPTX source graph.

This module is intentionally conservative. The source graph is factual; this
layer adds explicit, reviewable interpretations for identity, layout, source-
scoped components, slots, asset provenance, and adaptation policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSIONS = {
    "identity": "easyslides.identity_spec.v1",
    "layout": "easyslides.layout_spec.v1",
    "components": "easyslides.pptx_component_catalog.v1",
    "candidates": "easyslides.pptx_component_candidates.v1",
    "slots": "easyslides.pptx_slot_contracts.v1",
    "assets": "easyslides.asset_provenance.v1",
    "policy": "easyslides.adaptation_policy.v1",
    "review": "easyslides.review_queue.v1",
}

CLASSIFICATION_STATES = ("fixed", "replaceable", "hybrid", "unknown")
PAGE_ROLE_MAP = (
    ("cover", "cover"),
    ("toc", "toc"),
    ("chapter", "chapter"),
    ("ending", "ending"),
)


def _stable_hash(value: Any, length: int = 10) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()[:length]


def _slug(value: Any, fallback: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or fallback


def _iter_parts(graph: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    parts = graph.get("parts") if isinstance(graph.get("parts"), dict) else {}
    for role in ("masters", "layouts", "slides"):
        for part in parts.get(role) or []:
            if isinstance(part, dict):
                yield role[:-1], part


def _iter_nodes(graph: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any], dict[str, Any]]]:
    for part_role, part in _iter_parts(graph):
        for node in part.get("nodes") or []:
            if isinstance(node, dict):
                yield part_role, part, node


def _manifest_slide_map(manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(manifest, dict):
        return result
    for item in manifest.get("slides") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("slidePath")
        if path:
            result[str(path)] = item
    return result


def _page_role(page_type: Any) -> str:
    value = str(page_type or "").lower()
    for needle, role in PAGE_ROLE_MAP:
        if needle in value:
            return role
    return "content"


def _theme(graph: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    themes = graph.get("themes") or []
    if themes and isinstance(themes[0], dict) and isinstance(themes[0].get("theme"), dict):
        return themes[0]["theme"]
    if isinstance(manifest, dict) and isinstance(manifest.get("theme"), dict):
        return manifest["theme"]
    return {"colors": {}, "fonts": {}}


def _children_by_parent(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    children: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, _, node in _iter_nodes(graph):
        parent_id = node.get("parent_object_id")
        if parent_id:
            children[str(parent_id)].append(node)
    return children


def _classify_node(part_role: str, node: dict[str, Any], children: dict[str, list[dict[str, Any]]]) -> tuple[str, str]:
    if part_role in {"master", "layout"}:
        return "fixed", "master_or_layout_chrome"
    if node.get("kind") == "group" and children.get(str(node.get("object_id"))):
        return "hybrid", "group_contains_child_objects"
    if isinstance(node.get("placeholder"), dict):
        return "replaceable", "native_placeholder"
    if node.get("kind") == "picture" and node.get("relationships"):
        return "replaceable", "slide_image_relationship"
    return "unknown", "slide_object_without_replacement_evidence"


def _node_signature(node: dict[str, Any]) -> str:
    return _stable_hash(
        {
            "kind": node.get("kind"),
            "placeholder": node.get("placeholder"),
            "style": node.get("style"),
            "text_layout": node.get("text_layout"),
        }
    )


def _object_summary(part_role: str, part: dict[str, Any], node: dict[str, Any], classification: str, basis: str) -> dict[str, Any]:
    return {
        "object_id": node.get("object_id"),
        "part_role": part_role,
        "part_id": part.get("id"),
        "part_path": part.get("path"),
        "kind": node.get("kind"),
        "name": node.get("name"),
        "shape_id": node.get("shape_id"),
        "geometry": node.get("geometry"),
        "style": node.get("style"),
        "placeholder": node.get("placeholder"),
        "classification": classification,
        "classification_basis": basis,
    }


def _role_for_node(node: dict[str, Any]) -> str:
    placeholder = node.get("placeholder") if isinstance(node.get("placeholder"), dict) else {}
    placeholder_type = placeholder.get("type")
    if placeholder_type:
        return _slug(placeholder_type)
    if node.get("kind") == "picture":
        return "image"
    if node.get("text"):
        return "text"
    return _slug(node.get("kind"), "object")


def _slot_for_node(
    *,
    slide: dict[str, Any],
    node: dict[str, Any],
    component_id: str,
) -> dict[str, Any]:
    slide_id = str(slide.get("id") or "slide")
    role = _role_for_node(node)
    object_suffix = _slug(node.get("shape_id") or node.get("order"), "object")
    kind = "image" if node.get("kind") == "picture" else "text" if node.get("text") else "object"
    text = node.get("text") if isinstance(node.get("text"), dict) else {}
    line_count = max(1, int(text.get("line_count") or 1))
    char_count = int(text.get("char_count") or 0)
    capacity: dict[str, Any] = {
        "max_lines": line_count,
        "overflow_action": "choose_lower_density_then_split_across_slides",
    }
    if char_count:
        capacity["max_chars_per_line"] = max(1, int((char_count + line_count - 1) / line_count))
    return {
        "slot_id": f"{slide_id}_{role}_{object_suffix}",
        "role": role,
        "kind": kind,
        "required": bool(node.get("placeholder")),
        "source_object_id": node.get("object_id"),
        "source_component_id": component_id,
        "source_slide_id": slide_id,
        "geometry": node.get("geometry"),
        "alignment": {
            "vertical": "middle" if kind == "text" else None,
            "center_lock": kind == "text",
            "rule": "text_center_y_matches_container_center_y" if kind == "text" else None,
            "severity": "error" if kind == "text" else None,
            "source_observed_anchor": (node.get("text_layout") or {}).get("vertical_anchor"),
        },
        "capacity": capacity,
        "replacement": {
            "preserve_geometry": True,
            "preserve_parent_transform": True,
            "preserve_layer_order": True,
            "image_fit": "contain" if kind == "image" else None,
        },
    }


def _identity_spec(
    *,
    template_id: str,
    graph: dict[str, Any],
    manifest: dict[str, Any] | None,
    classified: list[tuple[str, dict[str, Any], dict[str, Any], str, str]],
) -> dict[str, Any]:
    theme = _theme(graph, manifest)
    fixed_chrome = [
        _object_summary(role, part, node, classification, basis)
        for role, part, node, classification, basis in classified
        if classification == "fixed"
    ]
    return {
        "schema_version": SCHEMA_VERSIONS["identity"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "status": "derived_with_review" if graph.get("status") != "ready" else "derived",
        "canvas": graph.get("canvas") or {},
        "theme": {
            "colors": theme.get("colors") or {},
            "fonts": theme.get("fonts") or {},
            "themes": graph.get("themes") or [],
        },
        "identity_must_preserve": [
            "canvas_ratio",
            "theme_colors_and_typography",
            "master_and_layout_chrome",
            "source_page_geometry_and_layer_order",
            "cover_chapter_and_ending_treatment",
        ],
        "fixed_chrome": fixed_chrome,
        "protected_surfaces": [
            {"part_id": part.get("id"), "part_role": role, "part_path": part.get("path"), "reason": "native_inheritance_surface"}
            for role, part in _iter_parts(graph)
            if role in {"master", "layout"}
        ],
        "inference_policy": {
            "source_graph_is_factual": True,
            "unresolved_objects_remain_unknown": True,
            "semantic_edits_require_review_queue_entry": True,
        },
    }


def _layout_spec(
    *,
    template_id: str,
    graph: dict[str, Any],
    manifest: dict[str, Any] | None,
    classified: list[tuple[str, dict[str, Any], dict[str, Any], str, str]],
) -> dict[str, Any]:
    slide_map = _manifest_slide_map(manifest)
    node_by_part: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for role, part, node, _, _ in classified:
        node_by_part[str(part.get("id"))].append(node)
    layouts: list[dict[str, Any]] = []
    for role, part in _iter_parts(graph):
        if role != "layout":
            continue
        placeholders = [
            {
                "object_id": node.get("object_id"),
                "placeholder": node.get("placeholder"),
                "geometry": node.get("geometry"),
            }
            for node in node_by_part[str(part.get("id"))]
            if node.get("placeholder")
        ]
        layouts.append(
            {
                "layout_id": part.get("id"),
                "source_part": part.get("path"),
                "master_id": part.get("parent_id"),
                "used_by_slides": part.get("used_by_slides") or [],
                "placeholders": placeholders,
                "node_order": [node.get("object_id") for node in node_by_part[str(part.get("id"))]],
                "spatial_contract": {
                    "preserve_geometry": True,
                    "preserve_parent_transform": True,
                    "preserve_layer_order": True,
                },
            }
        )
    slides: list[dict[str, Any]] = []
    for role, part in _iter_parts(graph):
        if role != "slide":
            continue
        source_item = slide_map.get(str(part.get("path")), {})
        index = int(part.get("index") or source_item.get("index") or len(slides) + 1)
        page_type = source_item.get("pageType") or "content_candidate"
        slides.append(
            {
                "slide_id": part.get("id"),
                "index": index,
                "source_part": part.get("path"),
                "layout_id": part.get("layout_id"),
                "master_id": part.get("master_id"),
                "page_role": _page_role(page_type),
                "page_type_evidence": page_type,
                "node_order": [node.get("object_id") for node in node_by_part[str(part.get("id"))]],
                "unresolved_node_count": sum(
                    1
                    for row_role, row_part, node, classification, _ in classified
                    if row_part is part and classification == "unknown"
                ),
                "spatial_contract": {
                    "preserve_geometry": True,
                    "preserve_parent_transform": True,
                    "preserve_layer_order": True,
                },
            }
        )
    return {
        "schema_version": SCHEMA_VERSIONS["layout"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "canvas": graph.get("canvas") or {},
        "inheritance": {
            "slide_to_layout": {item["slide_id"]: item.get("layout_id") for item in slides},
            "layout_to_master": {item["layout_id"]: item.get("master_id") for item in layouts},
        },
        "layouts": layouts,
        "slides": sorted(slides, key=lambda item: int(item.get("index") or 0)),
        "hard_geometry_invariants": [
            {"rule": "text_center_y_matches_container_center_y", "scope": "all_text_slots", "severity": "error"},
            {"rule": "preserve_parent_transform", "scope": "all_editable_objects", "severity": "error"},
        ],
    }


def _component_catalog(
    *,
    template_id: str,
    graph: dict[str, Any],
    classified: list[tuple[str, dict[str, Any], dict[str, Any], str, str]],
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: defaultdict[str, list[tuple[str, dict[str, Any], dict[str, Any], str, str]]] = defaultdict(list)
    component_ids: dict[str, str] = {}
    for row in classified:
        signature = _node_signature(row[2])
        component_ids[signature] = f"pptx_{_slug(row[2].get('kind'), 'object')}_{signature}"
        grouped[signature].append(row)
    slots_by_object = {str(slot.get("source_object_id")): slot for slot in slots}
    components: list[dict[str, Any]] = []
    for signature, rows in sorted(grouped.items()):
        classifications = {row[3] for row in rows}
        classification = next(iter(classifications)) if len(classifications) == 1 else "hybrid"
        first = rows[0]
        component_id = component_ids[signature]
        components.append(
            {
                "component_id": component_id,
                "asset_id": f"pptx/{template_id}/{component_id}",
                "scope": "source_template",
                "classification": classification,
                "classification_basis": sorted({row[4] for row in rows}),
                "signature": signature,
                "kind": first[2].get("kind"),
                "name_examples": sorted({str(row[2].get("name")) for row in rows if row[2].get("name")}),
                "style_contract": first[2].get("style") or {},
                "instances": [
                    {
                        "object_id": row[2].get("object_id"),
                        "part_id": row[1].get("id"),
                        "part_role": row[0],
                        "part_path": row[1].get("path"),
                        "geometry": row[2].get("geometry"),
                    }
                    for row in rows
                ],
                "slot_contract_ids": [
                    slot.get("slot_id")
                    for row in rows
                    for slot in [slots_by_object.get(str(row[2].get("object_id")))]
                    if slot
                ],
                "reuse_policy": {
                    "template_scoped": True,
                    "promote_to_global_registry": classification in {"fixed", "replaceable"}
                    and not any(row[0] == "slide" and row[3] == "unknown" for row in rows),
                    "requires_visual_review": True,
                },
            }
        )
    counts = Counter(item["classification"] for item in components)
    return {
        "schema_version": SCHEMA_VERSIONS["components"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "scope": "source_template",
        "components": components,
        "counts_by_classification": dict(sorted(counts.items())),
        "classification_states": list(CLASSIFICATION_STATES),
        "promotion_rule": "promote_only_after_visual_and_cross_material_review",
    }


def _component_candidates(*, template_id: str, catalog: dict[str, Any]) -> dict[str, Any]:
    """Turn factual component signatures into conservative promotion candidates.

    Candidates are not installed packages. They record why a source-derived
    element may become a template primitive or component after renderer and
    visual evidence exist.
    """
    candidates: list[dict[str, Any]] = []
    for component in catalog.get("components", []):
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("component_id") or "")
        if not component_id:
            continue
        classification = str(component.get("classification") or "unknown")
        kind = str(component.get("kind") or "object")
        instances = component.get("instances") if isinstance(component.get("instances"), list) else []
        repeated = len(instances) >= 2
        renderable_kind = kind in {"shape", "connector", "group", "picture"}
        if classification == "unknown":
            candidate_type = "review_required"
            status = "review_required"
            rationale = "Source graph cannot prove whether this slide object is fixed or replaceable."
        elif classification == "replaceable":
            candidate_type = "slot_contract"
            status = "template_scoped"
            rationale = "This is a declared replaceable slot; preserve its geometry instead of promoting a visual component."
        elif repeated and renderable_kind:
            candidate_type = "template_component" if kind in {"group", "picture"} else "template_primitive"
            status = "candidate"
            rationale = "Repeated renderable source geometry can become a template-scoped asset after visual verification."
        else:
            candidate_type = "source_scoped_reference"
            status = "review_required"
            rationale = "The source element is one-off or has insufficient repetition evidence for reusable promotion."
        candidates.append(
            {
                "candidate_id": f"candidate/{template_id}/{component_id}",
                "source_component_id": component_id,
                "asset_id": component.get("asset_id"),
                "candidate_type": candidate_type,
                "status": status,
                "rationale": rationale,
                "scope": "template_only",
                "classification": classification,
                "kind": kind,
                "instance_count": len(instances),
                "slot_contract_ids": component.get("slot_contract_ids", []),
                "style_contract": component.get("style_contract", {}),
                "promotion_requirements": [
                    "renderer_governance",
                    "template_geometry",
                    "text_center_y_matches_container_center_y",
                    "visual_diff",
                    "cross_material_smoke",
                    "cross_renderer_visual_regression",
                ],
                "forbidden_until_promoted": ["global_marketplace_publish", "executable_plugin_code", "geometry_reconstruction_outside_declared_slots"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSIONS["candidates"],
        "template_id": template_id,
        "source": "component_catalog.json",
        "promotion_policy": "candidate_only_until_all_required_promotion_evidence_passes",
        "candidates": candidates,
        "summary": {
            "candidate_count": sum(item["status"] == "candidate" for item in candidates),
            "review_required_count": sum(item["status"] == "review_required" for item in candidates),
            "slot_contract_count": sum(item["candidate_type"] == "slot_contract" for item in candidates),
        },
    }


def _slot_contracts(*, template_id: str, graph: dict[str, Any], classified: list[tuple[str, dict[str, Any], dict[str, Any], str, str]], component_ids: dict[str, str]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for role, part, node, classification, _ in classified:
        if role != "slide" or classification not in {"replaceable", "hybrid"}:
            continue
        signature = _node_signature(node)
        slide = {"id": part.get("id")}
        slots.append(_slot_for_node(slide=slide, node=node, component_id=component_ids[signature]))
    return slots


def _asset_provenance(template_id: str, graph: dict[str, Any]) -> dict[str, Any]:
    role_by_target: defaultdict[str, set[str]] = defaultdict(set)
    for part_role, part in _iter_parts(graph):
        background_target = ((part.get("background") or {}).get("asset_target"))
        if background_target:
            role_by_target[str(background_target)].add("background")
        for node in part.get("nodes") or []:
            for relationship in node.get("relationships") or []:
                if relationship.get("type", "").endswith("/image"):
                    role_by_target[str(relationship.get("target"))].add(f"{part_role}_image")
    assets = []
    for asset in graph.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        target = str(asset.get("part_path") or asset.get("name") or "")
        assets.append(
            {
                **asset,
                "template_id": template_id,
                "source_part": asset.get("part_path"),
                "roles": sorted(role_by_target.get(target, set())),
                "derived_asset": asset.get("name"),
                "license_status": "unknown_requires_review",
            }
        )
    return {
        "schema_version": SCHEMA_VERSIONS["assets"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "assets": assets,
        "rules": [
            "preserve_source_part_and_sha256",
            "do_not_promote_unknown_license_assets_without_review",
            "keep_background_assets_separate_from_replaceable_media",
        ],
    }


def _review_queue(
    *,
    template_id: str,
    graph: dict[str, Any],
    classified: list[tuple[str, dict[str, Any], dict[str, Any], str, str]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for role, part, node, classification, basis in classified:
        if classification != "unknown":
            continue
        severity = "high" if node.get("kind") in {"graphic_frame", "connector"} else "medium"
        items.append(
            {
                "review_id": f"review_{_stable_hash(node.get('object_id'))}",
                "status": "open",
                "severity": severity,
                "category": "semantic_classification",
                "object_id": node.get("object_id"),
                "part_id": part.get("id"),
                "part_role": role,
                "part_path": part.get("path"),
                "classification": classification,
                "reason": basis,
                "suggested_action": "classify_as_fixed_replaceable_or_hybrid_after_visual_review",
                "evidence": {"name": node.get("name"), "kind": node.get("kind"), "geometry": node.get("geometry")},
            }
        )
    if graph.get("status") != "ready":
        items.insert(
            0,
            {
                "review_id": "review_source_graph_evidence_level",
                "status": "open",
                "severity": "high",
                "category": "source_evidence",
                "reason": "source_graph_is_not_native_ooxml_ready",
                "suggested_action": "rerun_against_the_original_pptx_before_promoting_components",
            },
        )
    counts = Counter(item["severity"] for item in items)
    return {
        "schema_version": SCHEMA_VERSIONS["review"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "status": "open" if items else "clear",
        "summary": {"open_count": len(items), "by_severity": dict(sorted(counts.items()))},
        "items": items,
    }


def _adaptation_policy(template_id: str, graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSIONS["policy"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "default_mode": "mirror",
        "modes": {
            "mirror": {
                "preserve": ["slide_count", "slide_order", "canvas", "geometry", "layer_order", "identity"],
                "allow": ["declared_slot_content", "declared_asset_replacement"],
            },
            "layout": {
                "preserve": ["page_role", "spatial_contract", "component_relationships", "identity"],
                "allow": ["controlled_page_count_change", "density_variant_selection", "declared_slot_replacement"],
            },
            "design-system": {
                "preserve": ["identity_tokens", "component_contracts", "slot_alignment_rules"],
                "allow": ["new_page_compositions_after_review", "global_component_promotion_after_qa"],
            },
        },
        "hard_rules": [
            {"rule": "text_center_y_matches_container_center_y", "severity": "error"},
            {"rule": "preserve_parent_transform", "severity": "error"},
            {"rule": "unknown_objects_require_review", "severity": "error"},
        ],
    }


def validate_slot_contracts(contract: dict[str, Any]) -> dict[str, Any]:
    """Fail closed when a text slot loses the vertical-center invariant."""
    issues: list[dict[str, str]] = []
    slots = contract.get("slots") if isinstance(contract.get("slots"), list) else []
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict) or slot.get("kind") != "text":
            continue
        alignment = slot.get("alignment") if isinstance(slot.get("alignment"), dict) else {}
        if alignment.get("vertical") != "middle":
            issues.append({"code": "PPTX-CONTROL-TEXT-VERTICAL-MISALIGN", "path": f"slots[{index}].alignment.vertical"})
        if alignment.get("center_lock") is not True:
            issues.append({"code": "PPTX-CONTROL-TEXT-CENTER-LOCK-MISSING", "path": f"slots[{index}].alignment.center_lock"})
        if alignment.get("severity") != "error":
            issues.append({"code": "PPTX-CONTROL-TEXT-RULE-NOT-HARD", "path": f"slots[{index}].alignment.severity"})
    return {
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "rule": "text_center_y_matches_container_center_y",
    }


def build_semantic_specs(
    *,
    template_id: str,
    graph: dict[str, Any],
    manifest: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build all Phase 2 derived contracts without writing files."""
    children = _children_by_parent(graph)
    classified: list[tuple[str, dict[str, Any], dict[str, Any], str, str]] = []
    for part_role, part, node in _iter_nodes(graph):
        classification, basis = _classify_node(part_role, node, children)
        classified.append((part_role, part, node, classification, basis))

    component_kinds: dict[str, str] = {}
    for _, _, node, _, _ in classified:
        component_kinds.setdefault(_node_signature(node), str(node.get("kind") or "object"))
    component_ids = {
        signature: f"pptx_{_slug(kind, 'object')}_{signature}"
        for signature, kind in component_kinds.items()
    }
    slots = _slot_contracts(template_id=template_id, graph=graph, classified=classified, component_ids=component_ids)
    slot_contracts = {
        "schema_version": SCHEMA_VERSIONS["slots"],
        "template_id": template_id,
        "source_graph_schema": graph.get("schema_version"),
        "source": "derived_from_source_graph",
        "replacement_rule": "replace_declared_slots_preserve_template_geometry",
        "slots": slots,
        "hard_geometry_invariants": [
            {"rule": "text_center_y_matches_container_center_y", "scope": "all_text_slots", "severity": "error"},
            {"rule": "preserve_parent_transform", "scope": "all_slots", "severity": "error"},
        ],
    }
    slot_contracts["validation"] = validate_slot_contracts(slot_contracts)
    component_catalog = _component_catalog(
        template_id=template_id,
        graph=graph,
        classified=classified,
        slots=slots,
    )
    return {
        "identity_spec": _identity_spec(template_id=template_id, graph=graph, manifest=manifest, classified=classified),
        "layout_spec": _layout_spec(template_id=template_id, graph=graph, manifest=manifest, classified=classified),
        "component_catalog": component_catalog,
        "component_candidates": _component_candidates(template_id=template_id, catalog=component_catalog),
        "slot_contracts": slot_contracts,
        "asset_provenance": _asset_provenance(template_id, graph),
        "adaptation_policy": _adaptation_policy(template_id, graph),
        "review_queue": _review_queue(template_id=template_id, graph=graph, classified=classified),
    }


def write_semantic_specs(output_dir: Path, specs: dict[str, dict[str, Any]]) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, payload in specs.items():
        path = output_dir / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths[name] = path
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 2 PPTX distillation contracts from source_graph.json.")
    parser.add_argument("source_graph", help="Path to source_graph.json")
    parser.add_argument("--output-dir", required=True, help="Output directory for semantic contract JSON files")
    parser.add_argument("--template-id", required=True, help="Template id")
    parser.add_argument("--manifest", help="Optional manifest.json for page type evidence")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    graph = json.loads(Path(args.source_graph).read_text(encoding="utf-8-sig"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig")) if args.manifest else None
    paths = write_semantic_specs(
        Path(args.output_dir),
        build_semantic_specs(template_id=args.template_id, graph=graph, manifest=manifest),
    )
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
