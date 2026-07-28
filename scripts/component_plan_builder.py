#!/usr/bin/env python3
"""Build EasySlides component_plan.json from deck_plan.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.component_plan_contract import SCHEMA_VERSION, validate_component_plan
    from scripts.component_registry import DEFAULT_OUTPUT, infer_content_shapes, load_component_registry
    from scripts.component_selector import select_components, select_form_candidates
    from scripts.template_capabilities import asset_allowed_for_template, load_template_capability
except ModuleNotFoundError:  # pragma: no cover
    from component_plan_contract import SCHEMA_VERSION, validate_component_plan
    from component_registry import DEFAULT_OUTPUT, infer_content_shapes, load_component_registry
    from component_selector import select_components, select_form_candidates
    from template_capabilities import asset_allowed_for_template, load_template_capability


REPORT_SCHEMA_VERSION = "easyslides.component_plan_builder_report.v1"
BUILDER_NAME = "scripts/component_plan_builder.py"
DIRECT_MATCH_SCORE = 100

RHYTHM_DENSITY = {
    "anchor": "low",
    "breathing": "medium",
    "dense": "high",
}
PAGE_MODULE_ROLES = {"cover", "toc", "chapter", "ending"}
PAGE_RECIPE_SHAPES = {
    "argument",
    "causal_chain",
    "comparison",
    "matrix",
    "metric_set",
    "metrics",
    "sequence",
    "takeaways",
    "workflow",
}
CONTENT_SHAPE_ALIASES = {
    "card": "parallel_points",
    "cards": "parallel_points",
    "figure": "image_evidence",
    "image": "image_evidence",
    "result_figure": "image_evidence",
    "table": "matrix",
    "process": "workflow",
    "procedure": "workflow",
    "timeline": "workflow",
    "method": "workflow",
    "key_finding": "key_takeaway",
    "text": "definition",
}
NUMBERED_SLOT_RE = re.compile(r"^(?:CARD|STEP|DATA|IMAGE|CAPTION|BLOCK|BADGE)_(\d+)(?:_|$)")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _asset_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(asset["asset_id"]): asset
        for asset in registry.get("assets", [])
        if isinstance(asset, dict) and asset.get("asset_id")
    }


def _known_content_shapes(registry: dict[str, Any]) -> set[str]:
    shapes: set[str] = set()
    for asset in registry.get("assets", []):
        if not isinstance(asset, dict):
            continue
        selection = asset.get("selection") if isinstance(asset.get("selection"), dict) else {}
        for shape in selection.get("content_shapes") or []:
            if _is_nonempty_string(shape):
                shapes.add(str(shape))
    return shapes


def _plan_template_id(plan: dict[str, Any]) -> str:
    template_id = plan.get("template_id")
    if _is_nonempty_string(template_id):
        return str(template_id).strip()
    template = plan.get("template")
    if isinstance(template, dict):
        for key in ("template_id", "id"):
            if _is_nonempty_string(template.get(key)):
                return str(template[key]).strip()
    return ""


def _layout_parts(layout_id: Any) -> tuple[str, str]:
    if not _is_nonempty_string(layout_id):
        return "", ""
    value = str(layout_id).strip()
    if "/" in value:
        left, right = value.split("/", 1)
        return left.strip(), right.rsplit("/", 1)[-1].strip()
    if ":" in value:
        left, right = value.split(":", 1)
        return left.strip(), right.rsplit(":", 1)[-1].strip()
    return "", value


def _layout_template_id(slide: dict[str, Any], registry: dict[str, Any]) -> str:
    template_from_layout, variant = _layout_parts(slide.get("layout_id"))
    if not template_from_layout or not variant:
        return ""
    assets = _asset_map(registry)
    if f"body_variant/{template_from_layout}/{variant}" in assets:
        return template_from_layout
    for asset in assets.values():
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        if metadata.get("template_id") == template_from_layout:
            return template_from_layout
    return ""


def _slide_template_id(slide: dict[str, Any], plan_template_id: str, registry: dict[str, Any]) -> str:
    if _is_nonempty_string(slide.get("template_id")):
        return str(slide["template_id"]).strip()
    layout_template = _layout_template_id(slide, registry)
    if layout_template:
        return layout_template
    return plan_template_id


def _numbered_slot_count(payload: dict[str, Any]) -> int | None:
    numbers: set[int] = set()
    for key in payload:
        match = NUMBERED_SLOT_RE.match(str(key))
        if match:
            numbers.add(int(match.group(1)))
    if numbers:
        return max(numbers)
    return None


def _item_count(slide: dict[str, Any]) -> int:
    requirements = _as_dict(slide.get("component_requirements"))
    for source in (slide, requirements):
        value = source.get("item_count")
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit() and int(value) > 0:
            return int(value)

    for key in ("component_payload", "body_payload", "slot_payload"):
        payload = slide.get(key)
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list) and items:
                return len(items)
            numbered = _numbered_slot_count(payload)
            if numbered:
                return numbered

    evidence_sources = slide.get("evidence_sources")
    if isinstance(evidence_sources, list) and evidence_sources:
        return len(evidence_sources)
    return 1


def _density(slide: dict[str, Any]) -> str:
    if _is_nonempty_string(slide.get("density")):
        return str(slide["density"]).strip()
    rhythm = str(slide.get("rhythm") or "").strip()
    return RHYTHM_DENSITY.get(rhythm, "")


def _first_nonempty(*values: Any) -> str:
    for value in values:
        if _is_nonempty_string(value):
            return str(value).strip()
    return ""


def _evidence_type(slide: dict[str, Any]) -> str:
    requirements = _as_dict(slide.get("component_requirements"))
    explicit = _first_nonempty(requirements.get("evidence_type"), slide.get("evidence_type"))
    if explicit:
        return explicit
    evidence_sources = slide.get("evidence_sources")
    if isinstance(evidence_sources, list):
        for source in evidence_sources:
            if not isinstance(source, dict):
                continue
            value = _first_nonempty(source.get("evidence_type"), source.get("kind"), source.get("type"))
            if value:
                return value
    if _is_nonempty_string(slide.get("chart_id")):
        return "chart"
    return ""


def _editable_target(slide: dict[str, Any]) -> str:
    requirements = _as_dict(slide.get("component_requirements"))
    return _first_nonempty(requirements.get("editable_target"), slide.get("editable_target"))


def _visual_complexity(slide: dict[str, Any]) -> str:
    requirements = _as_dict(slide.get("component_requirements"))
    return _first_nonempty(requirements.get("visual_complexity"), slide.get("visual_complexity"))


def _narrative_role(slide: dict[str, Any]) -> str:
    requirements = _as_dict(slide.get("component_requirements"))
    return _first_nonempty(
        requirements.get("narrative_role"),
        requirements.get("story_role"),
        slide.get("narrative_role"),
        slide.get("story_role"),
        slide.get("role"),
    )


def _evidence_confidence(slide: dict[str, Any]) -> str:
    requirements = _as_dict(slide.get("component_requirements"))
    explicit = _first_nonempty(requirements.get("evidence_confidence"), slide.get("evidence_confidence"))
    if explicit:
        return explicit.lower()
    sources = slide.get("evidence_sources")
    if isinstance(sources, list) and sources:
        return "high" if len(sources) >= 2 else "medium"
    if slide.get("chart_data") or slide.get("table_data"):
        return "medium"
    return "low"


def _material_types(slide: dict[str, Any]) -> list[str]:
    requirements = _as_dict(slide.get("component_requirements"))
    explicit = requirements.get("material_types") or slide.get("material_types")
    values = [str(item).strip() for item in explicit] if isinstance(explicit, list) else []
    if slide.get("chart_data") or slide.get("chart_id"):
        values.append("chart")
    if slide.get("table_data"):
        values.append("table")
    if slide.get("image") or slide.get("image_path") or slide.get("media_refs"):
        values.append("image")
    if slide.get("evidence_sources"):
        values.append("evidence")
    if not values:
        values.append("text")
    return sorted({value for value in values if value})


def _content_shape(slide: dict[str, Any], item_count: int, registry: dict[str, Any]) -> str:
    known = _known_content_shapes(registry)
    if (_is_nonempty_string(slide.get("icon_family")) or _is_nonempty_string(slide.get("icon_library"))) and "icon" in known:
        return "icon"
    if _is_nonempty_string(slide.get("chart_id")) and "chart" in known:
        return "chart"
    raw = slide.get("content_shape") or slide.get("evidence_shape")
    if _is_nonempty_string(raw):
        value = str(raw).strip()
        if value in known:
            return value
        if value in {"card", "cards"} and item_count == 4:
            return "four_modules" if "four_modules" in known else "matrix"
        alias = CONTENT_SHAPE_ALIASES.get(value.lower())
        if alias and alias in known:
            return alias

    inferred = infer_content_shapes(
        slide.get("layout_id"),
        slide.get("role"),
        slide.get("action_title"),
        slide.get("claim"),
        slide.get("chart_id"),
        slide.get("evidence_sources"),
    )
    for shape in inferred:
        if shape in known:
            return shape
    return str(raw).strip() if _is_nonempty_string(raw) else ""


def _has_template_body_variant(template_id: str, registry: dict[str, Any]) -> bool:
    if not template_id:
        return False
    for asset in registry.get("assets", []):
        if not isinstance(asset, dict) or asset.get("granularity") != "body_variant":
            continue
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        if metadata.get("template_id") == template_id:
            return True
    return False


def _has_template_page_module(template_id: str, registry: dict[str, Any]) -> bool:
    if not template_id:
        return False
    for asset in registry.get("assets", []):
        if not isinstance(asset, dict) or asset.get("granularity") != "page_module":
            continue
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        if metadata.get("template_id") == template_id:
            return True
    return False


def _selection_range_contains(selection: dict[str, Any], item_count: int) -> bool:
    if "item_count_min" not in selection and "item_count_max" not in selection:
        return True
    minimum = int(selection.get("item_count_min", 1))
    maximum = int(selection.get("item_count_max", minimum))
    return minimum <= item_count <= maximum


def _has_matching_component_package(content_shape: str, item_count: int, registry: dict[str, Any]) -> bool:
    if not content_shape:
        return False
    for asset in registry.get("assets", []):
        if not isinstance(asset, dict) or asset.get("granularity") != "component_package":
            continue
        selection = asset.get("selection") if isinstance(asset.get("selection"), dict) else {}
        content_shapes = {str(item) for item in selection.get("content_shapes") or [] if str(item)}
        if content_shape in content_shapes and _selection_range_contains(selection, item_count):
            return True
    return False


def _direct_asset(
    slide: dict[str, Any],
    template_id: str,
    registry: dict[str, Any],
    capability: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve direct asset requests without letting them bypass a template profile."""
    assets = _asset_map(registry)

    def allowed_or_reason(asset: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        allowed, reason = asset_allowed_for_template(asset, capability)
        if allowed:
            return asset, None
        return None, f"{asset['asset_id']}: {reason}"

    requirements = _as_dict(slide.get("component_requirements"))
    explicit_asset_id = _first_nonempty(requirements.get("selected_asset_id"), slide.get("selected_asset_id"))
    if explicit_asset_id:
        asset = assets.get(explicit_asset_id)
        if asset:
            return allowed_or_reason(asset)
    icon_family = slide.get("icon_family") or slide.get("icon_library")
    if _is_nonempty_string(icon_family):
        icon_asset = assets.get(f"icon_family/{str(icon_family).strip()}")
        if icon_asset:
            return allowed_or_reason(icon_asset)
    chart_id = slide.get("chart_id")
    if _is_nonempty_string(chart_id):
        chart_asset = assets.get(f"chart/{str(chart_id).strip()}")
        if chart_asset:
            return allowed_or_reason(chart_asset)
    layout_id = slide.get("layout_id")
    layout_template, variant = _layout_parts(layout_id)
    candidates: list[str] = []
    if layout_template and variant:
        candidates.append(f"body_variant/{layout_template}/{variant}")
    if template_id and variant:
        candidates.append(f"body_variant/{template_id}/{variant}")
    if _is_nonempty_string(layout_id):
        value = str(layout_id).strip()
        candidates.extend(
            [
                f"page_module/{value}",
                f"page_module/{value.replace('/', '_').replace(':', '_')}",
                f"page_module/{value.rsplit('/', 1)[-1].rsplit(':', 1)[-1]}",
            ]
        )
    for asset_id in candidates:
        asset = assets.get(asset_id)
        if asset:
            return allowed_or_reason(asset)
    return None, None


def _preferred_granularity(
    slide: dict[str, Any],
    *,
    template_id: str,
    content_shape: str,
    item_count: int,
    registry: dict[str, Any],
    capability: dict[str, Any] | None,
    default: str | None = None,
) -> str:
    requirements = _as_dict(slide.get("component_requirements"))
    explicit = requirements.get("preferred_granularity") or slide.get("preferred_granularity")
    if _is_nonempty_string(explicit):
        return str(explicit).strip()
    if _is_nonempty_string(default):
        return str(default).strip()
    direct, _ = _direct_asset(slide, template_id, registry, capability)
    if direct:
        return str(direct["granularity"])
    if str(slide.get("role") or "") in PAGE_MODULE_ROLES:
        return "page_module" if _has_template_page_module(template_id, registry) else "page_recipe"
    if _has_template_body_variant(template_id, registry) and (
        isinstance(slide.get("slot_payload"), dict) or isinstance(slide.get("body_payload"), dict)
    ):
        return "body_variant"
    if _has_matching_component_package(content_shape, item_count, registry):
        return "component_package"
    if content_shape in PAGE_RECIPE_SHAPES or item_count >= 4:
        return "page_recipe"
    return "card_component"


def _avoid_assets(slide: dict[str, Any]) -> list[str]:
    requirements = _as_dict(slide.get("component_requirements"))
    avoid = requirements.get("avoid") or requirements.get("avoid_assets") or []
    if isinstance(avoid, str):
        return [avoid]
    if isinstance(avoid, list):
        return [str(item) for item in avoid if str(item)]
    return []


def _raw_payload(slide: dict[str, Any], asset_id: str) -> dict[str, Any]:
    component_payload = slide.get("component_payload")
    if isinstance(component_payload, dict):
        return component_payload

    if asset_id.startswith("chart/"):
        for key in ("chart_payload", "chart_data", "data"):
            payload = slide.get(key)
            if isinstance(payload, dict):
                return payload
        return {}

    if asset_id.startswith("icon_family/"):
        payload = slide.get("icon_payload")
        if isinstance(payload, dict):
            return payload
        icon_name = slide.get("icon_name") or slide.get("icon")
        if isinstance(icon_name, str) and icon_name.strip():
            return {"icon_name": icon_name.strip(), "color": slide.get("icon_color", "")}
        return {}

    if asset_id.startswith("body_variant/"):
        for key in ("slot_payload", "body_payload"):
            payload = slide.get(key)
            if isinstance(payload, dict):
                return payload
        return {}

    body_payload = slide.get("body_payload")
    if isinstance(body_payload, dict):
        return body_payload
    items = slide.get("items")
    if isinstance(items, list):
        return {"items": items}
    return {}


def _composition_for_asset(
    asset: dict[str, Any],
    registry: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    refs = [
        dict(ref)
        for ref in metadata.get("component_refs", [])
        if isinstance(ref, dict) and ref.get("asset_id")
    ]
    gates = {str(gate) for gate in asset.get("required_gates", []) if str(gate)}
    assets = _asset_map(registry)
    for ref in refs:
        target = assets.get(str(ref["asset_id"]))
        if not target:
            continue
        gates.update(str(gate) for gate in target.get("required_gates", []) if str(gate))
    recipe_dependencies = [
        str(asset_id)
        for asset_id in metadata.get("component_dependency_asset_ids", [])
        if str(asset_id)
    ]
    for asset_id in recipe_dependencies:
        target = assets.get(asset_id)
        if target:
            gates.update(str(gate) for gate in target.get("required_gates", []) if str(gate))
    if refs:
        gates.add("body_variant_component_contract")
    if recipe_dependencies:
        gates.add("template_component_pack_contract")
    return (
        str(metadata.get("composition_mode") or ("ordered_component_refs" if refs else "open_content_area")),
        refs,
        sorted(gates),
    )


def _recipe_dependencies_for_asset(asset: dict[str, Any]) -> list[str]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    return [
        str(asset_id)
        for asset_id in metadata.get("component_dependency_asset_ids", [])
        if str(asset_id)
    ]


def _selected_from_direct(
    asset: dict[str, Any],
    slide: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    asset_id = str(asset["asset_id"])
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    composition_mode, component_refs, required_gates = _composition_for_asset(asset, registry)
    return {
        "asset_id": asset_id,
        "granularity": asset.get("granularity", ""),
        "render_backend": asset.get("render_backend", ""),
        "renderer_id": metadata.get("renderer_id", ""),
        "score": DIRECT_MATCH_SCORE,
        "selection_reason": ["explicit layout_id asset"],
        "required_gates": required_gates,
        "composition_mode": composition_mode,
        "component_refs": component_refs,
        "component_dependency_asset_ids": _recipe_dependencies_for_asset(asset),
        "payload": _raw_payload(slide, asset_id),
    }


def _selected_from_match(match: dict[str, Any], slide: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(match["asset_id"])
    asset = _asset_map(registry).get(asset_id, {})
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    composition_mode, component_refs, required_gates = _composition_for_asset(asset, registry)
    return {
        "asset_id": asset_id,
        "granularity": match.get("granularity", ""),
        "render_backend": match.get("render_backend", ""),
        "renderer_id": match.get("renderer_id") or metadata.get("renderer_id", ""),
        "score": int(match.get("score", 0)),
        "selection_reason": list(match.get("reason", [])),
        "required_gates": sorted(
            set(required_gates)
            | {str(gate) for gate in match.get("required_gates", []) if str(gate)}
        ),
        "composition_mode": composition_mode,
        "component_refs": component_refs,
        "component_dependency_asset_ids": _recipe_dependencies_for_asset(asset),
        "payload": _raw_payload(slide, asset_id),
    }


def _template_allowed_match(
    match: dict[str, Any],
    template_id: str,
    registry: dict[str, Any],
    capability: dict[str, Any] | None,
) -> bool:
    asset = _asset_map(registry).get(str(match.get("asset_id") or ""))
    if not asset:
        return False
    allowed, _ = asset_allowed_for_template(asset, capability)
    return allowed


def _template_filtered_matches(
    matches: list[dict[str, Any]],
    *,
    template_id: str,
    registry: dict[str, Any],
    capability: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    return [
        match
        for match in matches
        if _template_allowed_match(match, template_id, registry, capability)
    ]


def _select_for_slide(
    slide: dict[str, Any],
    *,
    index: int,
    plan_template_id: str,
    registry: dict[str, Any],
    limit: int,
    default_preferred_granularity: str | None,
    recent_asset_ids: list[str],
    recent_form_families: list[str],
) -> dict[str, Any]:
    page = str(slide.get("page") or f"P{index + 1:02d}")
    template_id = _slide_template_id(slide, plan_template_id, registry)
    capability = load_template_capability(template_id)
    item_count = _item_count(slide)
    content_shape = _content_shape(slide, item_count, registry)
    density = _density(slide)
    evidence_type = _evidence_type(slide)
    editable_target = _editable_target(slide)
    visual_complexity = _visual_complexity(slide)
    narrative_role = _narrative_role(slide)
    evidence_confidence = _evidence_confidence(slide)
    material_types = _material_types(slide)
    preferred_granularity = _preferred_granularity(
        slide,
        template_id=template_id,
        content_shape=content_shape,
        item_count=item_count,
        registry=registry,
        capability=capability,
        default=default_preferred_granularity,
    )
    form_selection = select_form_candidates(
        content_shape=content_shape or None,
        page_role=str(slide.get("role") or "") or None,
        item_count=item_count,
        preferred_form=str(slide.get("preferred_form") or slide.get("chosen_form") or "") or None,
        avoid_families=list(slide.get("avoid_form_families") or []) if isinstance(slide.get("avoid_form_families"), list) else [],
        limit=3,
    )
    chosen_form = form_selection.get("chosen") if isinstance(form_selection.get("chosen"), dict) else {}
    query = {
        "page_role": str(slide.get("role") or "") or None,
        "content_shape": content_shape or None,
        "item_count": item_count,
        "density": density or None,
        "evidence_type": evidence_type or None,
        "editable_target": editable_target or None,
        "visual_complexity": visual_complexity or None,
        "preferred_granularity": preferred_granularity or None,
        "template_id": template_id or None,
        "template_capability": {
            "status": capability.get("status", "pass") if capability else "not_applicable",
            "composition_mode": (capability.get("composition") or {}).get("mode", "untemplated") if capability else "untemplated",
            "generation_enabled": capability.get("generation_enabled", True) if capability else True,
        },
        "form_family": str(slide.get("form_family") or chosen_form.get("family") or "") or None,
        "form_id": str(slide.get("chosen_form") or "") or None,
        "narrative_role": narrative_role or None,
        "evidence_confidence": evidence_confidence or None,
        "material_types": material_types,
        "recent_asset_ids": recent_asset_ids,
        "recent_form_families": recent_form_families,
        "avoid": _avoid_assets(slide),
    }

    direct, direct_block_reason = _direct_asset(slide, template_id, registry, capability)
    selected_assets: list[dict[str, Any]]
    selection_candidates: list[dict[str, Any]]
    selection_status = "found"
    if capability and capability.get("status") == "fail":
        selection_candidates = []
        selected_assets = []
        selection_status = "blocked"
        direct_block_reason = "template capability profile is invalid or missing"
    elif capability and capability.get("generation_enabled") is not True:
        selection_candidates = []
        selected_assets = []
        selection_status = "blocked"
        direct_block_reason = "template is source-scoped or non-template and cannot receive automatic component composition"
    elif direct_block_reason:
        selection_candidates = []
        selected_assets = []
        selection_status = "blocked"
    elif (
        capability
        and bool((capability.get("composition") or {}).get("requires_declared_body_variant"))
        and str(slide.get("role") or "") not in PAGE_MODULE_ROLES
        and not direct
        and not _is_nonempty_string(slide.get("layout_id"))
    ):
        selection_candidates = []
        selected_assets = []
        selection_status = "blocked"
        direct_block_reason = "template requires a declared body variant or page module for content composition"
    elif direct:
        selection_candidates = [_selected_from_direct(direct, slide, registry)]
        selected_assets = selection_candidates
        query["direct_asset_id"] = direct["asset_id"]
    else:
        selector_limit = max(limit, 50)
        selector_query = {key: value for key, value in query.items() if key != "template_capability"}
        selection = select_components(limit=selector_limit, registry=registry, **selector_query)
        matches = _template_filtered_matches(
            selection.get("matches", []),
            template_id=template_id,
            registry=registry,
            capability=capability,
        )
        if (selection["status"] != "found" or not matches) and content_shape:
            fallback_query = dict(selector_query)
            fallback_query["content_shape"] = None
            selection = select_components(limit=selector_limit, registry=registry, **fallback_query)
            matches = _template_filtered_matches(
                selection.get("matches", []),
                template_id=template_id,
                registry=registry,
                capability=capability,
            )
            query["fallback_content_shape"] = None
        selection_candidates = [
            _selected_from_match(match, slide, registry)
            for match in matches
        ]
        selected_assets = selection_candidates
        if not selection_candidates:
            selection_status = "miss"

    return {
        "page": page,
        "source_slide_index": index,
        "role": str(slide.get("role") or ""),
        "content_shape": content_shape,
        "item_count": item_count,
        "density": density,
        "narrative_context": {
            "narrative_role": narrative_role,
            "evidence_confidence": evidence_confidence,
            "material_types": material_types,
            "recent_asset_ids": recent_asset_ids,
            "recent_form_families": recent_form_families,
        },
        "selection_status": selection_status,
        "selection_block_reason": direct_block_reason or "",
        "selection_query": query,
        "form_selection": form_selection,
        "selected_assets": selected_assets[: max(limit, 1)],
        "selection_candidates": selection_candidates[:3],
    }


def build_component_plan(
    deck_plan: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    limit: int = 1,
    preferred_granularity: str | None = None,
) -> dict[str, Any]:
    """Return a component plan with selected assets for every deck-plan slide."""
    registry = registry or load_component_registry()
    slides = deck_plan.get("slides") if isinstance(deck_plan, dict) else []
    if not isinstance(slides, list):
        slides = []
    plan_template_id = _plan_template_id(deck_plan)
    component_slides: list[dict[str, Any]] = []
    recent_asset_ids: list[str] = []
    recent_form_families: list[str] = []
    for index, slide in enumerate(slides):
        component_slide = _select_for_slide(
            slide if isinstance(slide, dict) else {},
            index=index,
            plan_template_id=plan_template_id,
            registry=registry,
            limit=limit,
            default_preferred_granularity=preferred_granularity,
            recent_asset_ids=recent_asset_ids[-2:],
            recent_form_families=recent_form_families[-2:],
        )
        component_slides.append(component_slide)
        selected = component_slide.get("selected_assets") or []
        if selected and isinstance(selected[0], dict) and selected[0].get("asset_id"):
            recent_asset_ids.append(str(selected[0]["asset_id"]))
        chosen = component_slide.get("form_selection", {}).get("chosen") if isinstance(component_slide.get("form_selection"), dict) else {}
        if isinstance(chosen, dict) and chosen.get("family"):
            recent_form_families.append(str(chosen["family"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(deck_plan.get("schema_version") or ""),
        "generated_by": BUILDER_NAME,
        "template_id": plan_template_id,
        "slide_count": len(component_slides),
        "slides": component_slides,
    }


def build_report(
    component_plan: dict[str, Any],
    *,
    output: Path | None = None,
    validation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slides = [slide for slide in component_plan.get("slides", []) if isinstance(slide, dict)]
    misses = [slide.get("page", "") for slide in slides if slide.get("selection_status") != "found"]
    validation_status = validation_report.get("status") if isinstance(validation_report, dict) else "skipped"
    status = "fail" if misses or validation_status == "fail" else "pass"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": status,
        "output": str(output) if output else "",
        "slide_count": len(slides),
        "selected_asset_count": sum(len(slide.get("selected_assets", [])) for slide in slides),
        "miss_pages": misses,
        "validation_status": validation_status,
        "validation_report": validation_report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build EasySlides component_plan.json from deck_plan.json.")
    parser.add_argument("deck_plan", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", type=Path, help="Write component_plan.json to this path.")
    parser.add_argument("--limit", type=int, default=1, help="Number of selected assets to keep per slide.")
    parser.add_argument("--preferred-granularity", help="Default component granularity when slides do not specify one.")
    parser.add_argument("--validate", action="store_true", help="Validate the generated component plan.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable builder report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        deck_plan = _read_json(args.deck_plan)
        registry = load_component_registry(args.registry)
        component_plan = build_component_plan(
            deck_plan,
            registry=registry,
            limit=args.limit,
            preferred_granularity=args.preferred_granularity,
        )
    except Exception as exc:
        print(f"failed to build component plan: {exc}", file=sys.stderr)
        return 1

    output = args.write
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(component_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validation_report = None
    if args.validate:
        validation_report = validate_component_plan(
            component_plan,
            registry=registry,
            deck_plan_path=args.deck_plan,
        )
    report = build_report(component_plan, output=output, validation_report=validation_report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Component plan builder: {report['status']} ({report['slide_count']} slide(s))")
        if output:
            print(f"Output: {output}")
        for page in report["miss_pages"]:
            print(f"- miss: {page}")
        if validation_report and validation_report["status"] == "fail":
            for item in validation_report["issues"]:
                print(f"- {item['code']}: {item['message']} [{item['path']}]")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
