#!/usr/bin/env python3
"""Select EasySlides component assets for page content."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.component_registry import DEFAULT_OUTPUT, load_component_registry
except ModuleNotFoundError:  # pragma: no cover
    from component_registry import DEFAULT_OUTPUT, load_component_registry


SCHEMA_VERSION = "easyslides.component_selection.v1"
FORM_SELECTION_SCHEMA_VERSION = "easyslides.form_selection.v1"

# This is deliberately a small reasoning catalogue, not a second component
# library.  It gives the planner alternatives from different visual families;
# the existing registry remains responsible for finding the executable asset.
FORM_CATALOG: tuple[dict[str, Any], ...] = (
    {"form_id": "card_grid", "family": "card", "shapes": {"parallel_points", "supporting_points", "three_findings", "four_modules", "risk_set"}},
    {"form_id": "labeled_list", "family": "list", "shapes": {"parallel_points", "supporting_points", "definition", "text_panel"}},
    {"form_id": "pillar_diagram", "family": "diagram", "shapes": {"parallel_points", "four_modules", "matrix", "taxonomy"}},
    {"form_id": "flow_chain", "family": "diagram", "shapes": {"workflow", "process", "causal_chain", "sequence"}},
    {"form_id": "timeline", "family": "timeline", "shapes": {"workflow", "process", "timeline", "sequence"}},
    {"form_id": "roadmap", "family": "roadmap", "shapes": {"workflow", "process", "timeline", "milestones"}},
    {"form_id": "split_compare", "family": "comparison", "shapes": {"comparison", "two_sides", "before_after"}},
    {"form_id": "comparison_table", "family": "table", "shapes": {"comparison", "matrix", "table", "benchmark_table"}},
    {"form_id": "dumbbell", "family": "chart", "shapes": {"comparison", "benchmark_summary", "metrics"}},
    {"form_id": "metric_strip", "family": "metric", "shapes": {"metric_set", "metrics", "kpi_summary", "benchmark_summary"}},
    {"form_id": "native_chart", "family": "chart", "shapes": {"metric_set", "metrics", "trend", "distribution", "benchmark_summary"}},
    {"form_id": "evidence_split", "family": "evidence", "shapes": {"image_evidence", "figure_explanation", "result_interpretation"}},
    {"form_id": "figure_focus", "family": "figure", "shapes": {"image_evidence", "figure_explanation"}},
    {"form_id": "statement", "family": "statement", "shapes": {"key_takeaway", "definition", "conclusion", "quote"}},
    {"form_id": "quote_panel", "family": "quote", "shapes": {"quote", "key_takeaway"}},
)


def _as_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item)}


def _range_contains(selection: dict[str, Any], item_count: int) -> bool:
    if "item_count_min" not in selection and "item_count_max" not in selection:
        return True
    minimum = int(selection.get("item_count_min", 1))
    maximum = int(selection.get("item_count_max", minimum))
    return minimum <= item_count <= maximum


def _template_id(asset: dict[str, Any]) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    return str(metadata.get("template_id") or "")


def _asset_form_tokens(asset: dict[str, Any]) -> tuple[set[str], set[str]]:
    selection = asset.get("selection") if isinstance(asset.get("selection"), dict) else {}
    families = {str(value) for value in selection.get("form_families", []) if str(value)}
    family = selection.get("form_family")
    if family:
        families.add(str(family))
    form_ids = {str(value) for value in selection.get("form_ids", []) if str(value)}
    form_id = selection.get("form_id")
    if form_id:
        form_ids.add(str(form_id))
    asset_id = str(asset.get("asset_id") or "")
    granularity = str(asset.get("granularity") or "")
    if granularity == "chart_asset" or asset_id.startswith("chart/"):
        families.add("chart")
    elif granularity == "page_recipe" or "flow" in asset_id or "timeline" in asset_id:
        families.add("diagram")
    elif granularity in {"card_component", "component_package"} or asset_id.startswith("card/"):
        families.add("card")
    elif granularity == "page_module":
        families.add("layout")
    return families, form_ids


def _confidence_rank(value: str | None) -> int:
    return {"": 0, "low": 1, "medium": 2, "high": 3}.get(str(value or "").strip().lower(), 0)


def select_form_candidates(
    *,
    content_shape: str | None = None,
    page_role: str | None = None,
    item_count: int | None = None,
    preferred_form: str | None = None,
    avoid_families: list[str] | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Generate divergent visual forms before selecting an executable asset."""
    shape = str(content_shape or "").strip()
    avoided = {str(value).strip() for value in (avoid_families or []) if str(value).strip()}
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(FORM_CATALOG):
        if shape and shape not in item["shapes"]:
            continue
        family = str(item["family"])
        if family in avoided:
            continue
        score = 10 if shape and shape in item["shapes"] else 1
        if preferred_form and item["form_id"] == preferred_form:
            score += 100
        if item_count is not None and item["family"] == "card" and item_count > 5:
            score -= 2
        rows.append(
            {
                "form_id": item["form_id"],
                "family": family,
                "score": score,
                "reason": f"{item['form_id']} expresses {shape or 'the content'} as a {family} form",
                "catalog_index": index,
            }
        )
    if not rows:
        rows = [
            {"form_id": "statement", "family": "statement", "score": 1, "reason": "safe fallback for an unclassified content shape", "catalog_index": -1},
            {"form_id": "split_compare", "family": "comparison", "score": 0, "reason": "divergent fallback alternative", "catalog_index": -1},
            {"form_id": "flow_chain", "family": "diagram", "score": 0, "reason": "divergent fallback alternative", "catalog_index": -1},
        ]
    if len({str(row["family"]) for row in rows}) < 2:
        existing = {str(row["family"]) for row in rows}
        for item in FORM_CATALOG:
            family = str(item["family"])
            if family in existing or family in avoided:
                continue
            rows.append(
                {
                    "form_id": item["form_id"],
                    "family": family,
                    "score": 0,
                    "reason": f"divergent alternative for {shape or 'the content'}",
                    "catalog_index": int(item["form_id"] == "statement"),
                }
            )
            existing.add(family)
            if len(existing) >= 2:
                break
    rows.sort(key=lambda row: (-int(row["score"]), int(row["catalog_index"]), row["form_id"]))
    # Keep the top candidate from each family first, so a 3-row result cannot
    # silently become three visual variants of the same card family.
    selected: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for row in rows:
        if row["family"] in seen_families:
            continue
        selected.append(row)
        seen_families.add(row["family"])
        if len(selected) >= max(2, limit):
            break
    if len(selected) < max(2, limit):
        selected.extend(row for row in rows if row not in selected)
        selected = selected[: max(2, limit)]
    chosen = selected[0] if selected else None
    runner_up = selected[1] if len(selected) > 1 else None
    return {
        "schema_version": FORM_SELECTION_SCHEMA_VERSION,
        "status": "found" if len(selected) >= 2 else "miss",
        "query": {
            "content_shape": content_shape,
            "page_role": page_role,
            "item_count": item_count,
            "preferred_form": preferred_form,
            "avoid_families": sorted(avoided),
        },
        "chosen": chosen,
        "runner_up": runner_up,
        "candidates": selected,
    }


def score_asset(
    asset: dict[str, Any],
    *,
    page_role: str | None = None,
    content_shape: str | None = None,
    item_count: int | None = None,
    density: str | None = None,
    evidence_type: str | None = None,
    editable_target: str | None = None,
    visual_complexity: str | None = None,
    preferred_granularity: str | None = None,
    template_id: str | None = None,
    form_family: str | None = None,
    form_id: str | None = None,
    narrative_role: str | None = None,
    evidence_confidence: str | None = None,
    material_types: list[str] | None = None,
    recent_asset_ids: list[str] | None = None,
    recent_form_families: list[str] | None = None,
    avoid: set[str] | None = None,
) -> tuple[int, list[str]] | None:
    selection = asset.get("selection") if isinstance(asset.get("selection"), dict) else {}
    score = 0
    reasons: list[str] = []
    avoid = avoid or set()

    if asset.get("asset_id") in avoid:
        score -= 8
        reasons.append("explicitly avoided")

    if preferred_granularity:
        if asset.get("granularity") == preferred_granularity:
            score += 5
            reasons.append("preferred granularity")
        else:
            score -= 3

    if template_id:
        asset_template = _template_id(asset)
        if asset_template == template_id:
            score += 5
            reasons.append("template match")
        elif asset_template and asset.get("granularity") in {"body_variant", "page_module"}:
            score -= 2

    if page_role:
        page_roles = _as_set(selection.get("page_roles"))
        if page_role in page_roles:
            score += 6
            reasons.append("page role match")
        elif page_roles:
            score -= 2

    if content_shape:
        content_shapes = _as_set(selection.get("content_shapes"))
        if content_shape in content_shapes:
            score += 8
            reasons.append("content shape match")
        else:
            return None

    if item_count is not None:
        if _range_contains(selection, item_count):
            score += 4
            reasons.append("item count fits")
            if selection.get("item_count_min") == selection.get("item_count_max") == item_count:
                score += 1
                reasons.append("exact item count")
        else:
            return None

    if density:
        if selection.get("density") == density:
            score += 2
            reasons.append("density match")
        elif selection.get("density"):
            score -= 1

    if evidence_type:
        evidence_types = _as_set(selection.get("evidence_types"))
        if evidence_type in evidence_types:
            score += 3
            reasons.append("evidence type match")
        elif evidence_types:
            score -= 1

    if editable_target:
        editable_targets = _as_set(selection.get("editable_targets"))
        if editable_target in editable_targets:
            score += 2
            reasons.append("editable target match")
        elif editable_targets:
            score -= 1

    if visual_complexity:
        if selection.get("visual_complexity") == visual_complexity:
            score += 2
            reasons.append("visual complexity match")
        elif selection.get("visual_complexity"):
            score -= 1

    if form_family or form_id:
        families, form_ids = _asset_form_tokens(asset)
        if form_family:
            if form_family in families:
                score += 4
                reasons.append("form family match")
            elif families:
                score -= 1
        if form_id:
            if form_id in form_ids:
                score += 6
                reasons.append("form id match")

    if narrative_role:
        narrative_roles = _as_set(selection.get("narrative_roles") or selection.get("story_roles"))
        if narrative_role in narrative_roles:
            score += 4
            reasons.append("narrative role match")
        elif narrative_roles:
            score -= 1

    if material_types:
        requested_materials = {str(item) for item in material_types if str(item)}
        supported_materials = _as_set(selection.get("material_types"))
        if requested_materials & supported_materials:
            score += 3
            reasons.append("material type match")
        elif supported_materials:
            score -= 2

    if evidence_confidence:
        minimum = str(selection.get("minimum_evidence_confidence") or "")
        if minimum:
            if _confidence_rank(evidence_confidence) >= _confidence_rank(minimum):
                score += 2
                reasons.append("evidence confidence fits")
            else:
                score -= 4
                reasons.append("evidence confidence below component minimum")

    recent_asset_ids = recent_asset_ids or []
    if asset.get("asset_id") in recent_asset_ids:
        score -= 12
        reasons.append("recent asset reuse penalty")
    recent_form_families = set(recent_form_families or [])
    if recent_form_families:
        families, _ = _asset_form_tokens(asset)
        if families & recent_form_families:
            score -= 3
            reasons.append("recent visual family reuse penalty")

    if not reasons:
        reasons.append("fallback registry candidate")
    return score, reasons


def select_components(
    *,
    page_role: str | None = None,
    content_shape: str | None = None,
    item_count: int | None = None,
    density: str | None = None,
    evidence_type: str | None = None,
    editable_target: str | None = None,
    visual_complexity: str | None = None,
    preferred_granularity: str | None = None,
    template_id: str | None = None,
    form_family: str | None = None,
    form_id: str | None = None,
    narrative_role: str | None = None,
    evidence_confidence: str | None = None,
    material_types: list[str] | None = None,
    recent_asset_ids: list[str] | None = None,
    recent_form_families: list[str] | None = None,
    avoid: list[str] | None = None,
    limit: int = 10,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_component_registry()
    rows: list[dict[str, Any]] = []
    for asset in registry.get("assets", []):
        if not isinstance(asset, dict):
            continue
        scored = score_asset(
            asset,
            page_role=page_role,
            content_shape=content_shape,
            item_count=item_count,
            density=density,
            evidence_type=evidence_type,
            editable_target=editable_target,
            visual_complexity=visual_complexity,
            preferred_granularity=preferred_granularity,
            template_id=template_id,
            form_family=form_family,
            form_id=form_id,
            narrative_role=narrative_role,
            evidence_confidence=evidence_confidence,
            material_types=material_types,
            recent_asset_ids=recent_asset_ids,
            recent_form_families=recent_form_families,
            avoid=set(avoid or []),
        )
        if scored is None:
            continue
        score, reasons = scored
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        rows.append(
            {
                "asset_id": asset["asset_id"],
                "score": score,
                "granularity": asset["granularity"],
                "render_backend": asset["render_backend"],
                "renderer_id": metadata.get("renderer_id", ""),
                "source_path": asset.get("source_path", ""),
                "reason": reasons,
                "selection": asset.get("selection", {}),
                "required_gates": asset.get("required_gates", []),
            }
        )
    rows.sort(key=lambda row: (-int(row["score"]), row["asset_id"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "query": {
            "page_role": page_role,
            "content_shape": content_shape,
            "item_count": item_count,
            "density": density,
            "evidence_type": evidence_type,
            "editable_target": editable_target,
            "visual_complexity": visual_complexity,
            "preferred_granularity": preferred_granularity,
            "template_id": template_id,
            "form_family": form_family,
            "form_id": form_id,
            "narrative_role": narrative_role,
            "evidence_confidence": evidence_confidence,
            "material_types": list(material_types or []),
            "recent_asset_ids": list(recent_asset_ids or []),
            "recent_form_families": list(recent_form_families or []),
            "avoid": list(avoid or []),
        },
        "status": "found" if rows else "miss",
        "matches": rows[: max(limit, 0)],
        "match_count": len(rows),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select EasySlides components from the unified registry.")
    parser.add_argument("--registry", default=str(DEFAULT_OUTPUT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    query = subparsers.add_parser("query")
    query.add_argument("--page-role")
    query.add_argument("--content-shape")
    query.add_argument("--item-count", type=int)
    query.add_argument("--density")
    query.add_argument("--evidence-type")
    query.add_argument("--editable-target")
    query.add_argument("--visual-complexity")
    query.add_argument("--preferred-granularity")
    query.add_argument("--template-id")
    query.add_argument("--form-family")
    query.add_argument("--form-id")
    query.add_argument("--avoid", action="append", default=[])
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = load_component_registry(args.registry)
    if args.command == "query":
        result = select_components(
            page_role=args.page_role,
            content_shape=args.content_shape,
            item_count=args.item_count,
            density=args.density,
            evidence_type=args.evidence_type,
            editable_target=args.editable_target,
            visual_complexity=args.visual_complexity,
            preferred_granularity=args.preferred_granularity,
            template_id=args.template_id,
            form_family=args.form_family,
            form_id=args.form_id,
            avoid=args.avoid,
            limit=args.limit,
            registry=registry,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for row in result["matches"]:
                print(f"{row['asset_id']}\t{row['score']}\t{', '.join(row['reason'])}")
        return 0 if result["status"] == "found" else 1
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
