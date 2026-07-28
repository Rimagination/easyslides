#!/usr/bin/env python3
"""Build a unified EasySlides component asset registry.

This registry is the bridge from scattered assets to a planner-owned component
system. It indexes page recipes, card styles, SVG visual recipes, body variants,
chart templates, and exact PPTX template modules under one stable ``asset_id``
namespace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUTPUT = ROOT / "templates" / "components" / "component_registry.json"
CARD_LIBRARY_PATH = ROOT / "templates" / "cards" / "card_library.json"
VISUAL_RECIPES_PATH = ROOT / "templates" / "cards" / "visual_recipes.json"
PAGE_RECIPES_PATH = ROOT / "templates" / "page_layouts" / "ppt_master_page_recipes.json"
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
COMPONENT_PACKAGES_ROOT = ROOT / "templates" / "components" / "packages"
TEMPLATE_ASSET_BANK_PATHS = (
    ROOT / "templates" / "reference" / "template_asset_bank.json",
    ROOT / "references" / "template_asset_bank.json",
)
PPTX_DESIGN_SYSTEM_ROOT = ROOT / "templates" / "reference" / "template_asset_sources"

try:
    from scripts.body_variant_contract import canonical_component_asset_id, normalize_component_refs
    from scripts.component_package import INSTALLED_PACKAGES_ROOT, is_public_component_package, load_component_packages
    from scripts.component_asset_manifest import build_asset_manifest
    from scripts.chart_library import CHART_INDEX_PATH, load_chart_library
    from scripts.icon_library import MANIFEST_PATH, load_icon_library
    from scripts.template_component_pack import body_variant_recipe_map, expanded_catalog_components, recipe_component_asset_ids
except ModuleNotFoundError:  # pragma: no cover
    from body_variant_contract import canonical_component_asset_id, normalize_component_refs
    from component_package import INSTALLED_PACKAGES_ROOT, is_public_component_package, load_component_packages
    from component_asset_manifest import build_asset_manifest
    from chart_library import CHART_INDEX_PATH, load_chart_library
    from icon_library import MANIFEST_PATH, load_icon_library
    from template_component_pack import body_variant_recipe_map, expanded_catalog_components, recipe_component_asset_ids

SCHEMA_VERSION = "easyslides.component_registry.v1"
REPORT_SCHEMA_VERSION = "easyslides.component_registry_report.v1"


CONTENT_SHAPE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("single_metric", ("metric", "kpi", "number")),
    ("metric_set", ("metrics", "dashboard", "kpi row", "three values")),
    ("parallel_points", ("parallel", "three", "four", "cards", "categories", "contributions", "risks")),
    ("three_findings", ("three", "3 ", "findings", "contributions")),
    ("four_modules", ("four", "4 ", "quadrant", "2x2", "modules")),
    ("image_evidence", ("figure", "image", "exhibit", "visual evidence")),
    ("figure_explanation", ("figure", "notes", "image", "exhibit")),
    ("comparison", ("compare", "comparison", "versus", "before", "after", "two column")),
    ("matrix", ("matrix", "table", "quadrant")),
    ("workflow", ("workflow", "process", "pipeline", "route", "timeline", "steps")),
    ("causal_chain", ("causal", "mechanism", "chain")),
    ("argument", ("argument", "claim", "evidence", "reasoning")),
    ("takeaways", ("takeaway", "conclusion", "recommendation", "summary")),
    ("definition", ("definition", "context", "profile", "fact")),
    ("paper_summary", ("paper", "literature", "citation", "reading")),
)

PAGE_ROLE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cover", ("cover", "opening", "title")),
    ("toc", ("toc", "contents", "agenda")),
    ("chapter", ("chapter", "section", "part")),
    ("ending", ("ending", "closing", "thanks")),
    ("overview", ("overview", "executive_summary", "summary")),
    ("result", ("result", "evidence", "dashboard", "metric")),
    ("method", ("method", "workflow", "roadmap", "process")),
    ("comparison", ("comparison", "decision", "matrix")),
    ("conclusion", ("conclusion", "recommendation", "takeaway")),
    ("content", ("content", "body")),
)

BODY_VARIANT_HINTS: dict[str, dict[str, Any]] = {
    "three_card_summary": {
        "content_shapes": ["parallel_points", "three_findings", "three_contributions", "risk_set"],
        "item_count_min": 3,
        "item_count_max": 3,
        "density": "medium",
    },
    "four_quadrant_grid": {
        "content_shapes": ["parallel_points", "four_modules", "matrix", "taxonomy"],
        "item_count_min": 4,
        "item_count_max": 4,
        "density": "medium",
    },
    "figure_with_notes": {
        "content_shapes": ["image_evidence", "figure_explanation", "result_interpretation"],
        "item_count_min": 1,
        "item_count_max": 4,
        "density": "medium",
    },
    "figure_left_text_right": {
        "content_shapes": ["image_evidence", "figure_explanation"],
        "item_count_min": 1,
        "item_count_max": 4,
        "density": "medium",
    },
    "two_column_compare": {
        "content_shapes": ["comparison", "two_sides", "before_after"],
        "item_count_min": 2,
        "item_count_max": 2,
        "density": "medium",
    },
    "process_timeline": {
        "content_shapes": ["workflow", "process", "timeline"],
        "item_count_min": 3,
        "item_count_max": 5,
        "density": "medium",
    },
    "table_matrix": {
        "content_shapes": ["matrix", "table", "comparison"],
        "item_count_min": 3,
        "item_count_max": 8,
        "density": "high",
    },
    "flexible_canvas": {
        "content_shapes": ["mixed_content", "text_panel", "custom"],
        "item_count_min": 1,
        "item_count_max": 8,
        "density": "high",
    },
}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _strings(value: Iterable[Any] | None) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value if str(item)]


def _text_blob(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, dict):
            parts.append(json.dumps(value, ensure_ascii=False))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def _component_pack_metadata(package_dir: Path, packages_root: Path) -> dict[str, Any] | None:
    """Read pack provenance from the nearest parent pack.json, if present."""
    current = package_dir.resolve()
    root = packages_root.resolve()
    while True:
        manifest_path = current / "pack.json"
        if manifest_path.is_file():
            try:
                manifest = read_json(manifest_path)
            except (OSError, json.JSONDecodeError, ValueError):
                return None
            if manifest.get("schema_version") == "easyslides.component_pack.v1":
                return {
                    "pack_id": manifest.get("pack_id", ""),
                    "version": manifest.get("version", ""),
                    "display_name": manifest.get("display_name", ""),
                    "license": manifest.get("license", ""),
                    "visibility": manifest.get("visibility", "public"),
                    "replacement_template_id": manifest.get("replacement_template_id", ""),
                    "dependencies": (manifest.get("dependencies") if isinstance(manifest.get("dependencies"), dict) else {}).get("component_packs", []),
                    "design_tokens": manifest.get("design_tokens", {}),
                    "manifest_path": rel(manifest_path),
                }
        if current == root or current.parent == current:
            break
        current = current.parent
    return None


def infer_content_shapes(*values: Any) -> list[str]:
    blob = _text_blob(*values)
    shapes: list[str] = []
    for shape, needles in CONTENT_SHAPE_HINTS:
        if any(needle in blob for needle in needles):
            shapes.append(shape)
    return sorted(dict.fromkeys(shapes))


def infer_page_roles(*values: Any) -> list[str]:
    blob = _text_blob(*values)
    roles: list[str] = []
    for role, needles in PAGE_ROLE_HINTS:
        if any(needle in blob for needle in needles):
            roles.append(role)
    return sorted(dict.fromkeys(roles))


def normalize_slot(slot: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(slot, str):
        return {"slot_id": slot, "kind": "text", "required": True}

    slot_id = str(slot.get("slot_id") or slot.get("slot") or slot.get("id") or "")
    kind = str(slot.get("kind") or ("image" if slot.get("role") == "image" else "text"))
    normalized: dict[str, Any] = {
        "slot_id": slot_id,
        "kind": kind,
        "role": str(slot.get("role") or slot.get("placeholder_type") or kind),
        "required": bool(slot.get("required", False)),
    }
    if slot.get("repeated"):
        normalized["repeated"] = True
    if slot.get("geometry") is not None:
        normalized["geometry"] = slot["geometry"]
    if slot.get("image_fit"):
        normalized["image_fit"] = slot["image_fit"]
    if isinstance(slot.get("alignment"), dict):
        normalized["alignment"] = slot["alignment"]

    capacity_keys = (
        "font_size_px",
        "min_font_size_px",
        "line_height",
        "max_chars_per_line_zh",
        "max_chars_per_line",
        "max_lines",
        "overflow_action",
    )
    capacity = {key: slot[key] for key in capacity_keys if key in slot}
    if isinstance(slot.get("capacity"), dict):
        capacity.update(slot["capacity"])
    if capacity:
        normalized["capacity"] = capacity
    return normalized


def selection_from_source(
    *,
    content_shapes: Iterable[str] | None = None,
    page_roles: Iterable[str] | None = None,
    item_count_min: int | None = None,
    item_count_max: int | None = None,
    density: str | None = None,
    best_for: str = "",
    avoid_when: str = "",
) -> dict[str, Any]:
    selection: dict[str, Any] = {
        "content_shapes": sorted(dict.fromkeys(_strings(content_shapes))),
        "page_roles": sorted(dict.fromkeys(_strings(page_roles))),
    }
    if item_count_min is not None:
        selection["item_count_min"] = int(item_count_min)
    if item_count_max is not None:
        selection["item_count_max"] = int(item_count_max)
    if density:
        selection["density"] = str(density)
    if best_for:
        selection["best_for"] = best_for
    if avoid_when:
        selection["avoid_when"] = avoid_when
    return selection


def _base_asset(
    *,
    asset_id: str,
    granularity: str,
    render_backend: str,
    source_path: Path,
    selection: dict[str, Any],
    slots: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    required_gates: Iterable[str] | None = None,
    allowed_edits: Iterable[str] | None = None,
    forbidden_edits: Iterable[str] | None = None,
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "granularity": granularity,
        "render_backend": render_backend,
        "source_path": rel(source_path),
        "selection": selection,
        "slots": slots,
        "metadata": metadata or {},
        "allowed_edits": _strings(allowed_edits) or ["replace_declared_content"],
        "forbidden_edits": _strings(forbidden_edits) or ["invent_unregistered_layout"],
        "required_gates": _strings(required_gates)
        or ["component_plan_contract", "text_capacity", "visual_measure_gate"],
    }


def assets_from_card_library(path: Path = CARD_LIBRARY_PATH) -> list[dict[str, Any]]:
    payload = read_json(path)
    assets: list[dict[str, Any]] = []
    for style in payload.get("styles", []):
        if not isinstance(style, dict) or not style.get("card_id"):
            continue
        selection = style.get("selection") if isinstance(style.get("selection"), dict) else {}
        assets.append(
            _base_asset(
                asset_id=f"card/{style['card_id']}",
                granularity="card_component",
                render_backend="card_library",
                source_path=path,
                selection=selection_from_source(
                    content_shapes=selection.get("content_shapes"),
                    item_count_min=selection.get("item_count_min"),
                    item_count_max=selection.get("item_count_max"),
                    density=selection.get("density"),
                    best_for=str(selection.get("best_for") or ""),
                    avoid_when=str(selection.get("avoid_when") or ""),
                ),
                slots=[normalize_slot(slot) for slot in style.get("slots", []) if isinstance(slot, dict)],
                metadata={
                    "card_id": style["card_id"],
                    "name_zh": style.get("name_zh", ""),
                    "family": style.get("family", ""),
                    "layout": style.get("layout", {}),
                },
                required_gates=["component_plan_contract", "card_payload_capacity", "visual_measure_gate"],
            )
        )
    return assets


def assets_from_visual_recipes(path: Path = VISUAL_RECIPES_PATH) -> list[dict[str, Any]]:
    payload = read_json(path)
    assets: list[dict[str, Any]] = []
    for recipe in payload.get("recipes", []):
        if not isinstance(recipe, dict) or not recipe.get("recipe_id"):
            continue
        selection = recipe.get("selection") if isinstance(recipe.get("selection"), dict) else {}
        assets.append(
            _base_asset(
                asset_id=f"visual_recipe/{recipe['recipe_id']}",
                granularity="card_component",
                render_backend="svg_recipe",
                source_path=path,
                selection=selection_from_source(
                    content_shapes=selection.get("content_shapes"),
                    item_count_min=selection.get("item_count_min"),
                    item_count_max=selection.get("item_count_max"),
                    density=selection.get("density"),
                    best_for=str(selection.get("best_for") or ""),
                    avoid_when=str(selection.get("avoid_when") or ""),
                ),
                slots=[normalize_slot(slot) for slot in recipe.get("slots", []) if isinstance(slot, dict)],
                metadata={
                    "recipe_id": recipe["recipe_id"],
                    "name_zh": recipe.get("name_zh", ""),
                    "box": recipe.get("box", {}),
                    "layers": recipe.get("layers", []),
                },
                required_gates=["component_plan_contract", "recipe_payload_capacity", "svg_text_slots", "visual_measure_gate"],
            )
        )
    return assets


def assets_from_chart_library() -> list[dict[str, Any]]:
    """Register PPT Master-compatible chart templates as selectable assets."""
    library = load_chart_library()
    assets: list[dict[str, Any]] = []
    for chart in library.get("charts", []):
        if not isinstance(chart, dict) or not chart.get("chart_id"):
            continue
        selection = chart.get("selection") if isinstance(chart.get("selection"), dict) else {}
        assets.append(
            _base_asset(
                asset_id=str(chart["asset_id"]),
                granularity="chart_asset",
                render_backend=str(chart.get("render_backend") or "svg_template"),
                source_path=CHART_INDEX_PATH,
                selection=selection_from_source(
                    content_shapes=selection.get("content_shapes"),
                    page_roles=selection.get("page_roles"),
                    density=str(selection.get("density") or "medium"),
                    best_for=str(selection.get("best_for") or ""),
                ),
                slots=[slot for slot in chart.get("slots", []) if isinstance(slot, dict)],
                metadata={
                    "chart_id": chart["chart_id"],
                    "family": chart.get("family", ""),
                    "summary": chart.get("summary", ""),
                    "asset_path": chart.get("asset_path", ""),
                    "renderer_id": chart.get("renderer_id", "chart_svg_template"),
                    "editability": chart.get("editability", "svg_text_slots"),
                    "native_support": chart.get("native_support", "separate_native_backend"),
                    "data_model": chart.get("data_model", ""),
                    "library_id": library.get("library_id", ""),
                    "upstream": chart.get("upstream", {}),
                },
                required_gates=chart.get("required_gates") or [
                    "component_plan_contract",
                    "chart_asset_contract",
                    "chart_text_slots",
                    "visual_measure_gate",
                ],
                allowed_edits=["replace_chart_payload", "replace_declared_text"],
                forbidden_edits=["change_fixed_geometry", "invent_unregistered_layout"],
            )
        )
    return assets


def assets_from_icon_library() -> list[dict[str, Any]]:
    """Register icon families as selectable primitive asset pools."""
    library = load_icon_library(include_icons=False)
    assets: list[dict[str, Any]] = []
    for family in library.get("families", []):
        if not isinstance(family, dict) or not family.get("family"):
            continue
        family_id = str(family["family"])
        role = str(family.get("role") or "stylistic")
        content_shapes = ["icon", "generic_icon"] if role == "stylistic" else ["brand_mark", "icon"]
        page_roles = ["content", "method", "overview", "result"]
        if role == "brand":
            page_roles = ["cover", "content", "overview"]
        assets.append(
            _base_asset(
                asset_id=f"icon_family/{family_id}",
                granularity="icon_family",
                render_backend="svg_icon_library",
                source_path=MANIFEST_PATH,
                selection=selection_from_source(
                    content_shapes=content_shapes,
                    page_roles=page_roles,
                    density="low",
                    best_for=f"{family.get('display_name', family_id)}: {family.get('style', '')} icons for {role} use.",
                    avoid_when="Do not mix with another stylistic icon family in the same selection batch." if role == "stylistic" else "Do not use as a generic substitute for non-brand concepts.",
                ),
                slots=[
                    {"slot_id": "icon_name", "kind": "data", "role": "icon_token", "required": True},
                    {"slot_id": "color", "kind": "text", "role": "theme_color", "required": False},
                ],
                metadata={
                    "family": family_id,
                    "display_name": family.get("display_name", ""),
                    "style": family.get("style", ""),
                    "role": role,
                    "view_box": family.get("view_box", ""),
                    "icon_count": int(family.get("count") or 0),
                    "source": family.get("source", ""),
                    "token_prefix": f"{family_id}/",
                    "sync_script": "scripts/icon_library.py sync",
                    "search_script": "scripts/icon_library.py search",
                },
                required_gates=[
                    "component_plan_contract",
                    "icon_asset_contract",
                    "icon_style_gate",
                    "visual_measure_gate",
                ],
                allowed_edits=["choose_declared_icon", "set_theme_color"],
                forbidden_edits=["mix_stylistic_icon_families", "invent_unregistered_icon"],
            )
        )
    return assets


def assets_from_page_recipes(path: Path = PAGE_RECIPES_PATH) -> list[dict[str, Any]]:
    payload = read_json(path)
    assets: list[dict[str, Any]] = []
    for recipe in payload.get("recipes", []):
        if not isinstance(recipe, dict) or not recipe.get("recipe_id"):
            continue
        selection = recipe.get("selection") if isinstance(recipe.get("selection"), dict) else {}
        assets.append(
            _base_asset(
                asset_id=f"page_recipe/{recipe['recipe_id']}",
                granularity="page_recipe",
                render_backend="svg_page_recipe",
                source_path=path,
                selection=selection_from_source(
                    content_shapes=selection.get("content_shapes"),
                    page_roles=recipe.get("page_role"),
                    item_count_min=selection.get("item_count_min"),
                    item_count_max=selection.get("item_count_max"),
                    density=selection.get("density"),
                    best_for=str(selection.get("best_for") or ""),
                    avoid_when=str(selection.get("avoid_when") or ""),
                ),
                slots=[normalize_slot(slot) for slot in recipe.get("slots", []) if isinstance(slot, dict)],
                metadata={
                    "recipe_id": recipe["recipe_id"],
                    "name_zh": recipe.get("name_zh", ""),
                    "regions": recipe.get("regions", []),
                    "layout_intent": recipe.get("layout_intent", ""),
                },
                required_gates=["component_plan_contract", "page_payload_capacity", "svg_text_slots", "visual_measure_gate"],
            )
        )
    return assets


def assets_from_component_packages(packages_root: Path = COMPONENT_PACKAGES_ROOT) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for package_dir, package in load_component_packages(packages_root):
        if not isinstance(package, dict) or not package.get("asset_id"):
            continue
        if not is_public_component_package(package_dir):
            continue
        qa = package.get("qa") if isinstance(package.get("qa"), dict) else {}
        required_gates = qa.get("required_gates") if isinstance(qa.get("required_gates"), list) else []
        pack_metadata = _component_pack_metadata(package_dir, packages_root)
        assets.append(
            _base_asset(
                asset_id=str(package["asset_id"]),
                granularity=str(package.get("granularity") or "component_package"),
                render_backend=str(package.get("render_backend") or "component_package"),
                source_path=package_dir / "component.json",
                selection=package.get("selection") if isinstance(package.get("selection"), dict) else {},
                slots=[normalize_slot(slot) for slot in package.get("slots", []) if isinstance(slot, dict)],
                metadata={
                    "component_id": package.get("component_id", package_dir.name),
                    "display_name": package.get("display_name", ""),
                    "renderer_id": package.get("renderer_id", package.get("component_id", package_dir.name)),
                    "source_asset_id": package.get("source_asset_id", ""),
                    "render_targets": package.get("render_targets", []),
                    "input_schema": package.get("input_schema", {}),
                    "payload_contract": package.get("payload_contract", {}),
                    "stories": package.get("stories", []),
                    "preview": package.get("preview", {}),
                    "qa": qa,
                    "pack": pack_metadata,
                },
                required_gates=required_gates
                or ["component_package_contract", "component_plan_contract", "visual_measure_gate"],
            )
        )
    return assets


def media_assets_from_component_roots(packages_roots: Iterable[Path]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen_roots: set[Path] = set()
    for packages_root in packages_roots:
        root = Path(packages_root).resolve()
        if not root.exists():
            continue
        for assets_root in sorted(root.rglob("assets")):
            assets_root = assets_root.resolve()
            if assets_root in seen_roots or not assets_root.is_dir():
                continue
            if any(part in {".git", ".archive", ".staging"} for part in assets_root.relative_to(root).parts):
                continue
            seen_roots.add(assets_root)
            current = assets_root.parent
            namespace = assets_root.parent.name
            license_name = ""
            while True:
                pack_manifest = current / "pack.json"
                if pack_manifest.is_file():
                    try:
                        pack = read_json(pack_manifest)
                    except (OSError, json.JSONDecodeError, ValueError):
                        pack = {}
                    namespace = str(pack.get("pack_id") or namespace)
                    license_name = str(pack.get("license") or "")
                    break
                component_manifest = current / "component.json"
                if component_manifest.is_file():
                    try:
                        component = read_json(component_manifest)
                    except (OSError, json.JSONDecodeError, ValueError):
                        component = {}
                    namespace = str(component.get("component_id") or namespace)
                    break
                if current == root or current.parent == current:
                    break
                current = current.parent
            manifest = build_asset_manifest(assets_root, namespace=namespace)
            for row in manifest["assets"]:
                assets.append(
                    {
                        **row,
                        "path": rel(assets_root / row["path"]),
                        "license": license_name,
                        "source_root": rel(assets_root),
                    }
                )
    return sorted(assets, key=lambda item: item["asset_id"])


def _body_variant_selection(template_id: str, variant: dict[str, Any]) -> dict[str, Any]:
    variant_id = str(variant.get("variant_id") or "")
    hints = BODY_VARIANT_HINTS.get(variant_id, {})
    inferred = infer_content_shapes(variant_id, variant.get("best_for"), variant.get("layout"), variant)
    # Managed template packages already declare their semantic selection
    # vocabulary. Preserve it verbatim; name-based hints only keep legacy
    # body_variants.json files discoverable during migration.
    declared_shapes = _strings(variant.get("content_shapes"))
    content_shapes = sorted(
        dict.fromkeys(declared_shapes or (_strings(hints.get("content_shapes")) + inferred))
    )
    return selection_from_source(
        content_shapes=content_shapes,
        page_roles=_strings(variant.get("story_roles")),
        item_count_min=variant.get("min_items", hints.get("item_count_min", 1)),
        item_count_max=variant.get("max_items", hints.get("item_count_max", 8)),
        density=str(variant.get("density") or hints.get("density") or "medium"),
        best_for=str(variant.get("best_for") or f"{template_id} body variant {variant_id}"),
    )


def assets_from_template_component_catalogs(
    layouts_root: Path = LAYOUTS_ROOT,
) -> list[dict[str, Any]]:
    """Register renderable components owned by a template pack."""
    assets: list[dict[str, Any]] = []
    if not layouts_root.exists():
        return assets
    for path in sorted(layouts_root.glob("*/component_catalog.json")):
        payload = read_json(path)
        template_id = str(payload.get("template_id") or path.parent.name)
        for component in expanded_catalog_components(path.parent, payload):
            if not isinstance(component, dict):
                continue
            asset_id = canonical_component_asset_id(
                template_id,
                component.get("asset_id") or component.get("component_id"),
            )
            if not asset_id:
                continue
            selection = component.get("selection") if isinstance(component.get("selection"), dict) else {}
            qa = component.get("qa") if isinstance(component.get("qa"), dict) else {}
            assets.append(
                _base_asset(
                    asset_id=asset_id,
                    granularity="template_component",
                    render_backend=str(component.get("render_backend") or "template_svg_component"),
                    source_path=path,
                    selection=selection_from_source(
                        content_shapes=infer_content_shapes(
                            component.get("component_id"),
                            component.get("description"),
                            selection.get("archetypes"),
                        ),
                        page_roles=selection.get("page_roles"),
                        density=str(selection.get("density") or "medium"),
                        best_for=str(component.get("description") or component.get("component_id") or ""),
                    ),
                    slots=[
                        normalize_slot(slot)
                        for slot in component.get("slots", [])
                        if isinstance(slot, (dict, str))
                    ],
                    metadata={
                        "template_id": template_id,
                        "component_id": component.get("component_id", asset_id.rsplit("/", 1)[-1]),
                        "renderer_id": component.get("renderer_id", ""),
                        "asset_path": component.get("asset_path", ""),
                        "asset_status": component.get("asset_status", ""),
                        "classification": component.get("classification", "template_scoped"),
                        "reuse_policy": component.get("reuse_policy", ""),
                        "geometry": component.get("geometry", {}),
                        "qa": qa,
                    },
                    required_gates=qa.get("required_gates")
                    or [
                        "component_plan_contract",
                        "body_variant_component_contract",
                        "component_geometry",
                        "visual_measure_gate",
                    ],
                    allowed_edits=["replace_declared_component_slots"],
                    forbidden_edits=["change_template_component_geometry"],
                )
            )
    return assets


def assets_from_body_variants(layouts_root: Path = LAYOUTS_ROOT) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    if not layouts_root.exists():
        return assets
    for path in sorted(layouts_root.glob("*/body_variants.json")):
        payload = read_json(path)
        template_id = str(payload.get("template_id") or path.parent.name)
        recipe_map = body_variant_recipe_map(path.parent) if (path.parent / "component_pack.json").is_file() else {}
        for variant in payload.get("variants", []):
            if not isinstance(variant, dict) or not variant.get("variant_id"):
                continue
            variant_id = str(variant["variant_id"])
            slots = [normalize_slot(slot) for slot in variant.get("slots", []) if isinstance(slot, str)]
            component_refs = normalize_component_refs(variant, template_id)
            recipe = recipe_map.get(variant_id, {})
            assets.append(
                _base_asset(
                    asset_id=f"body_variant/{template_id}/{variant_id}",
                    granularity="body_variant",
                    render_backend="template_body_variant",
                    source_path=path,
                    selection=_body_variant_selection(template_id, variant),
                    slots=slots,
                    metadata={
                        "template_id": template_id,
                        "variant_id": variant_id,
                        "content_area": payload.get("content_area", {}),
                        "layout": variant.get("layout", ""),
                        "composition_mode": (
                            "ordered_component_refs"
                            if component_refs
                            else str(variant.get("composition_mode") or "open_content_area")
                        ),
                        "component_refs": component_refs,
                        "component_recipe": recipe,
                        "component_dependency_asset_ids": recipe_component_asset_ids(recipe, template_id) if recipe else [],
                    },
                    required_gates=[
                        "component_plan_contract",
                        "body_variant_contract",
                        "body_variant_component_contract",
                        "template_tokens",
                        "visual_measure_gate",
                    ],
                )
            )
    return assets


def _density_from_metrics(metrics: dict[str, Any]) -> str:
    text_count = int(metrics.get("text_count") or 0)
    shape_count = int(metrics.get("shape_count") or 0)
    if text_count >= 7 or shape_count >= 35:
        return "high"
    if text_count <= 3 and shape_count <= 12:
        return "low"
    return "medium"


def _page_module_roles(page_type: str) -> list[str]:
    roles = infer_page_roles(page_type)
    if not roles and page_type.endswith("_candidate"):
        roles = infer_page_roles(page_type.replace("_candidate", ""))
    return roles or ["content"]


def assets_from_template_asset_bank(paths: Iterable[Path] = TEMPLATE_ASSET_BANK_PATHS) -> list[dict[str, Any]]:
    bank_path = next((path for path in paths if path.exists()), None)
    if not bank_path:
        return []
    payload = read_json(bank_path)
    assets: list[dict[str, Any]] = []
    for template in payload.get("templates", []):
        if not isinstance(template, dict):
            continue
        template_id = str(template.get("template_id") or "")
        for page in template.get("pages", []):
            if not isinstance(page, dict) or not page.get("module_id"):
                continue
            page_type = str(page.get("page_type") or "")
            metrics = page.get("metrics") if isinstance(page.get("metrics"), dict) else {}
            text_count = int(metrics.get("text_count") or 1)
            search_values = [page_type, page.get("text_samples"), page.get("search_hints"), page.get("assets")]
            assets.append(
                _base_asset(
                    asset_id=f"page_module/{page['module_id']}",
                    granularity="page_module",
                    render_backend="flat_svg_template_module",
                    source_path=bank_path,
                    selection=selection_from_source(
                        content_shapes=infer_content_shapes(*search_values),
                        page_roles=_page_module_roles(page_type),
                        item_count_min=1,
                        item_count_max=max(1, min(text_count, 12)),
                        density=_density_from_metrics(metrics),
                        best_for=f"Exact template reuse module from {template_id}, source slide {page.get('source_slide_index')}",
                        avoid_when="Content that requires moving or recoloring fixed source geometry.",
                    ),
                    slots=[normalize_slot(slot) for slot in page.get("slots", []) if isinstance(slot, dict)],
                    metadata={
                        "template_id": template_id,
                        "module_id": page.get("module_id"),
                        "module_basename": page.get("module_basename"),
                        "source_slide_index": page.get("source_slide_index"),
                        "page_type": page_type,
                        "source": page.get("source", {}),
                        "metrics": metrics,
                    },
                    allowed_edits=(page.get("reuse_contract") or {}).get("allowed_edits", []),
                    forbidden_edits=(page.get("reuse_contract") or {}).get("forbidden_edits", []),
                    required_gates=["component_plan_contract", "template_module_fit", "visual_measure_gate"],
                )
            )
    return assets


def assets_from_pptx_design_system_packs(
    roots: Iterable[Path] | None = None,
) -> list[dict[str, Any]]:
    """Index declarative Phase 3 source-template fragments.

    These assets are discoverable by planning, but their renderer is explicitly
    ``source_template_projection`` until a reviewed native renderer mapping is
    available. They must not be treated as executable component packages.
    """
    requested_roots = list(roots or [])
    search_roots = [PPTX_DESIGN_SYSTEM_ROOT]
    search_roots.extend(Path(root) for root in requested_roots)
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in search_roots:
        root = Path(root)
        if not root.exists():
            continue
        for fragment_path in sorted(root.rglob("component_registry_fragment.json")):
            try:
                fragment = read_json(fragment_path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if fragment.get("schema_version") != "easyslides.component_registry_fragment.v1":
                continue
            template_id = str(fragment.get("template_id") or fragment_path.parent.name)
            for source_asset in fragment.get("assets") or []:
                if not isinstance(source_asset, dict) or not source_asset.get("asset_id"):
                    continue
                asset_id = str(source_asset["asset_id"])
                if asset_id in seen:
                    continue
                seen.add(asset_id)
                metadata = dict(source_asset.get("metadata") or {})
                metadata.update(
                    {
                        "template_id": template_id,
                        "source_pack": str(fragment_path.parent / "design_system_pack.json"),
                        "installability": "source_template_only",
                    }
                )
                assets.append(
                    _base_asset(
                        asset_id=asset_id,
                        granularity="pptx_source_component",
                        render_backend="source_template_projection",
                        source_path=fragment_path,
                        selection=source_asset.get("selection") if isinstance(source_asset.get("selection"), dict) else {},
                        slots=[normalize_slot(slot) for slot in source_asset.get("slots", []) if isinstance(slot, dict)],
                        metadata=metadata,
                        required_gates=source_asset.get("required_gates") or [
                            "source_template_contract",
                            "text_capacity",
                            "visual_measure_gate",
                            "cross_material_smoke_test",
                        ],
                        allowed_edits=source_asset.get("allowed_edits") or ["replace_declared_slots"],
                        forbidden_edits=source_asset.get("forbidden_edits") or ["change_fixed_chrome"],
                    )
                )
    return sorted(assets, key=lambda item: item["asset_id"])


def build_component_registry(
    *,
    include_template_asset_bank: bool = True,
    packages_root: Path = COMPONENT_PACKAGES_ROOT,
    additional_packages_roots: Iterable[Path] | None = None,
    source_design_system_roots: Iterable[Path] | None = None,
) -> dict[str, Any]:
    package_roots = [Path(packages_root)]
    extra_roots = [INSTALLED_PACKAGES_ROOT] if additional_packages_roots is None else list(additional_packages_roots)
    package_roots.extend(Path(path) for path in extra_roots if Path(path) not in package_roots)
    assets: list[dict[str, Any]] = []
    for package_root in package_roots:
        assets.extend(assets_from_component_packages(package_root))
    assets.extend(assets_from_page_recipes())
    assets.extend(assets_from_card_library())
    assets.extend(assets_from_visual_recipes())
    assets.extend(assets_from_chart_library())
    assets.extend(assets_from_icon_library())
    assets.extend(assets_from_template_component_catalogs())
    assets.extend(assets_from_body_variants())
    assets.extend(assets_from_pptx_design_system_packs(source_design_system_roots))
    if include_template_asset_bank:
        assets.extend(assets_from_template_asset_bank())
    assets.sort(key=lambda item: item["asset_id"])

    component_packs: list[dict[str, Any]] = []
    for packages_root_item in package_roots:
        if not packages_root_item.exists():
            continue
        for manifest_path in sorted(packages_root_item.rglob("pack.json")):
            if any(part in {".git", ".archive", ".staging"} for part in manifest_path.relative_to(packages_root_item).parts):
                continue
            try:
                manifest = read_json(manifest_path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if manifest.get("schema_version") != "easyslides.component_pack.v1":
                continue
            component_packs.append(
                {
                    "pack_id": manifest.get("pack_id", ""),
                    "version": manifest.get("version", ""),
                    "display_name": manifest.get("display_name", ""),
                    "path": rel(manifest_path.parent),
                    "component_count": len(manifest.get("components", [])) if isinstance(manifest.get("components"), list) else 0,
                    "dependencies": (manifest.get("dependencies") if isinstance(manifest.get("dependencies"), dict) else {}).get("component_packs", []),
                    "design_tokens": manifest.get("design_tokens", {}),
                }
            )

    counts: dict[str, int] = {}
    for asset in assets:
        counts[asset["granularity"]] = counts.get(asset["granularity"], 0) + 1

    media_assets = media_assets_from_component_roots(package_roots)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/component_registry.py",
        "selection_policy": {
            "default": "Match page role and content shape first, then item count, density, template affinity, and granularity.",
            "overflow_rule": "Payloads must pass component-specific capacity validation before rendering.",
        },
        "source_paths": {
            "component_packages": [rel(path) for path in package_roots],
            "page_recipes": rel(PAGE_RECIPES_PATH),
            "card_library": rel(CARD_LIBRARY_PATH),
            "visual_recipes": rel(VISUAL_RECIPES_PATH),
            "chart_library": rel(CHART_INDEX_PATH),
            "icon_library": rel(MANIFEST_PATH),
            "layouts_root": rel(LAYOUTS_ROOT),
            "template_component_catalogs": rel(LAYOUTS_ROOT),
            "template_asset_bank": rel(next((path for path in TEMPLATE_ASSET_BANK_PATHS if path.exists()), TEMPLATE_ASSET_BANK_PATHS[0])),
            "pptx_design_system_root": [
                rel(path)
                for path in [PPTX_DESIGN_SYSTEM_ROOT, *(Path(item) for item in (source_design_system_roots or []))]
            ],
        },
        "asset_count": len(assets),
        "counts_by_granularity": dict(sorted(counts.items())),
        "component_packs": component_packs,
        "media_asset_count": len(media_assets),
        "media_assets": media_assets,
        "assets": assets,
    }


def validate_component_registry(registry: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if registry.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "COMPONENT-REGISTRY-SCHEMA", "message": f"schema_version must be {SCHEMA_VERSION}", "path": "schema_version"})
    assets = registry.get("assets")
    if not isinstance(assets, list) or not assets:
        issues.append({"code": "COMPONENT-REGISTRY-ASSETS", "message": "assets must be a non-empty list", "path": "assets"})
        assets = []
    seen: set[str] = set()
    for index, asset in enumerate(assets):
        path = f"assets[{index}]"
        if not isinstance(asset, dict):
            issues.append({"code": "COMPONENT-REGISTRY-ASSET", "message": "asset must be an object", "path": path})
            continue
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id:
            issues.append({"code": "COMPONENT-REGISTRY-ASSET-ID", "message": "asset_id is required", "path": f"{path}.asset_id"})
        elif asset_id in seen:
            issues.append({"code": "COMPONENT-REGISTRY-ASSET-ID", "message": f"duplicate asset_id {asset_id!r}", "path": f"{path}.asset_id"})
        seen.add(asset_id)
        for key in ("granularity", "render_backend", "selection", "slots", "required_gates"):
            if key not in asset:
                issues.append({"code": "COMPONENT-REGISTRY-ASSET-FIELD", "message": f"{key} is required", "path": f"{path}.{key}"})
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict) or asset.get("granularity") != "body_variant":
            continue
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        refs = metadata.get("component_refs")
        if not isinstance(refs, list):
            continue
        for ref_index, ref in enumerate(refs):
            ref_path = f"assets[{index}].metadata.component_refs[{ref_index}]"
            if not isinstance(ref, dict):
                issues.append(
                    {
                        "code": "COMPONENT-REGISTRY-COMPOSITION",
                        "message": "component reference must be an object",
                        "path": ref_path,
                    }
                )
                continue
            target_id = str(ref.get("asset_id") or "")
            if not target_id:
                issues.append(
                    {
                        "code": "COMPONENT-REGISTRY-COMPOSITION",
                        "message": "component reference asset_id is required",
                        "path": f"{ref_path}.asset_id",
                    }
                )
            elif bool(ref.get("required", True)) and target_id not in seen:
                issues.append(
                    {
                        "code": "COMPONENT-REGISTRY-COMPOSITION",
                        "message": f"required component reference {target_id!r} is not registered",
                        "path": f"{ref_path}.asset_id",
                    }
                )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "asset_count": len(assets),
    }


def load_component_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_OUTPUT
    if registry_path.exists():
        registry = read_json(registry_path)
        # Keep older generated registries compatible while independently
        # generated chart, icon, and template component catalogs evolve.
        registered = {
            str(asset.get("asset_id"))
            for asset in registry.get("assets", [])
            if isinstance(asset, dict) and asset.get("asset_id")
        }
        catalog_assets = [
            asset
            for asset in [
                *assets_from_template_component_catalogs(),
                *assets_from_chart_library(),
                *assets_from_icon_library(),
            ]
            if asset["asset_id"] not in registered
        ]
        if catalog_assets:
            registry["assets"] = sorted(
                [asset for asset in registry.get("assets", []) if isinstance(asset, dict)] + catalog_assets,
                key=lambda item: str(item.get("asset_id") or ""),
            )
            counts: dict[str, int] = {}
            for asset in registry["assets"]:
                counts[str(asset.get("granularity") or "")] = counts.get(str(asset.get("granularity") or ""), 0) + 1
            registry["asset_count"] = len(registry["assets"])
            registry["counts_by_granularity"] = dict(sorted(counts.items()))
            source_paths = registry.get("source_paths") if isinstance(registry.get("source_paths"), dict) else {}
            source_paths["chart_library"] = rel(CHART_INDEX_PATH)
            source_paths["icon_library"] = rel(MANIFEST_PATH)
            source_paths["template_component_catalogs"] = rel(LAYOUTS_ROOT)
            registry["source_paths"] = source_paths
        return registry
    return build_component_registry()


def write_component_registry(
    output: str | Path = DEFAULT_OUTPUT,
    *,
    packages_root: Path = COMPONENT_PACKAGES_ROOT,
    additional_packages_roots: Iterable[Path] | None = None,
    source_design_system_roots: Iterable[Path] | None = None,
) -> Path:
    output_path = Path(output)
    registry = build_component_registry(
        packages_root=packages_root,
        additional_packages_roots=additional_packages_roots,
        source_design_system_roots=source_design_system_roots,
    )
    report = validate_component_registry(registry)
    if report["status"] != "pass":
        raise ValueError(f"component registry is invalid: {report['issues']}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and inspect the unified EasySlides component registry.")
    parser.add_argument("--registry", default=str(DEFAULT_OUTPUT), help="Path to component_registry.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build component_registry.json.")
    build.add_argument("--output", default=str(DEFAULT_OUTPUT))
    build.add_argument("--no-template-asset-bank", action="store_true")
    build.add_argument("--source-design-system-root", action="append", help="Additional root containing component_registry_fragment.json files.")

    validate = subparsers.add_parser("validate", help="Validate a registry file or freshly built registry.")
    validate.add_argument("--json", action="store_true")

    list_parser = subparsers.add_parser("list", help="List registered assets.")
    list_parser.add_argument("--granularity")
    list_parser.add_argument("--json", action="store_true")
    return parser


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        source_roots = [Path(path) for path in args.source_design_system_root] if args.source_design_system_root else None
        registry = build_component_registry(
            include_template_asset_bank=not args.no_template_asset_bank,
            source_design_system_roots=source_roots,
        )
        report = validate_component_registry(registry)
        if report["status"] != "pass":
            _print_json(report)
            return 1
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output)
        return 0

    if args.command == "validate":
        registry = load_component_registry(args.registry)
        report = validate_component_registry(registry)
        if args.json:
            _print_json(report)
        else:
            print(f"Component registry: {report['status']} ({report['issue_count']} issue(s), {report['asset_count']} assets)")
            for item in report["issues"]:
                print(f"- {item['code']}: {item['message']} [{item.get('path', '$')}]")
        return 0 if report["status"] == "pass" else 1

    if args.command == "list":
        registry = load_component_registry(args.registry)
        rows = [
            {
                "asset_id": asset["asset_id"],
                "granularity": asset["granularity"],
                "render_backend": asset["render_backend"],
            }
            for asset in registry.get("assets", [])
            if not args.granularity or asset.get("granularity") == args.granularity
        ]
        if args.json:
            _print_json(rows)
        else:
            for row in rows:
                print(f"{row['asset_id']}\t{row['granularity']}\t{row['render_backend']}")
        return 0 if rows else 1

    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
