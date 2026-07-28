#!/usr/bin/env python3
"""Validate template-scoped component packs and expand their primitive assets."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "easyslides.template_component_pack.v1"
REPORT_SCHEMA_VERSION = "easyslides.template_component_pack_report.v1"
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
PACK_ID_RE = re.compile(r"^template/[a-z0-9][a-z0-9._-]{1,63}/components$")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _safe_file(template_dir: Path, value: object) -> Path | None:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        return None
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    candidate = (template_dir / relative).resolve()
    try:
        candidate.relative_to(template_dir.resolve())
    except ValueError:
        return None
    return candidate


def _token_value(tokens: dict[str, Any], dotted_path: str) -> Any:
    value: Any = tokens
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def expanded_catalog_components(template_dir: Path, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Return scene components plus primitive components without duplicating slots."""
    rows = [dict(component) for component in catalog.get("components", []) if isinstance(component, dict)]
    primitive_path = _safe_file(template_dir, catalog.get("primitive_manifest"))
    if primitive_path is None or not primitive_path.is_file():
        return rows
    try:
        primitive_payload = read_json(primitive_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return rows
    for primitive in primitive_payload.get("primitives", []):
        if not isinstance(primitive, dict):
            continue
        primitive_id = str(primitive.get("primitive_id") or "")
        if not primitive_id:
            continue
        rows.append(
            {
                "asset_id": f"component/{catalog.get('template_id') or template_dir.name}/{primitive_id}",
                "component_id": primitive_id,
                "asset_path": primitive.get("asset_path", ""),
                "asset_status": "renderable_svg",
                "render_backend": "template_svg_component",
                "renderer_id": "source_template_projection",
                "classification": "template_scoped_primitive",
                "reuse_policy": "template_primitive_composed_by_body_variant_recipe",
                "description": str(primitive.get("role") or primitive_id),
                "slots": primitive.get("slots", []),
                "selection": {
                    "page_roles": ["content"],
                    "archetypes": [str(primitive.get("role") or primitive_id)],
                    "density": "dense_research_defense",
                },
                "geometry": primitive.get("geometry", {}),
                "qa": {
                    "required_gates": [
                        "template_component_pack_contract",
                        "asset_manifest",
                        "component_geometry",
                        "vertical_center_alignment",
                    ],
                    "alignment_invariants": [
                        {
                            "rule": "text_center_y_matches_container_center_y",
                            "scope": "text_in_container",
                            "severity": "error",
                        }
                    ],
                },
            }
        )
    return rows


def _recipe_payload(template_dir: Path, pack: dict[str, Any]) -> dict[str, Any]:
    entrypoints = pack.get("entrypoints") if isinstance(pack.get("entrypoints"), dict) else {}
    recipe_path = _safe_file(template_dir, entrypoints.get("recipes"))
    if recipe_path is None or not recipe_path.is_file():
        return {}
    return read_json(recipe_path)


def body_variant_recipe_map(template_dir: str | Path, pack: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return source-derived composition recipes keyed by body-variant id."""
    directory = Path(template_dir).resolve()
    active_pack = pack if isinstance(pack, dict) else read_json(directory / "component_pack.json")
    try:
        payload = _recipe_payload(directory, active_pack)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for recipe in payload.get("recipes", []):
        if not isinstance(recipe, dict):
            continue
        variant_id = str(recipe.get("variant_id") or "")
        scene_component = str(recipe.get("scene_component") or "")
        primitives = [str(value) for value in recipe.get("primitives", []) if str(value)]
        if variant_id and scene_component:
            rows[variant_id] = {
                "variant_id": variant_id,
                "scene_component": scene_component,
                "primitives": primitives,
                "source_slides": list(recipe.get("source_slides") or []),
            }
    return rows


def recipe_component_asset_ids(recipe: dict[str, Any], template_id: str) -> list[str]:
    """Return a stable, deduplicated dependency sequence for a recipe."""
    names = [recipe.get("scene_component"), *(recipe.get("primitives") or [])]
    asset_ids: list[str] = []
    for name in names:
        component_id = str(name or "")
        asset_id = component_id if component_id.startswith("component/") else f"component/{template_id}/{component_id}"
        if component_id and asset_id not in asset_ids:
            asset_ids.append(asset_id)
    return asset_ids


def validate_template_component_pack(template_dir: str | Path) -> dict[str, Any]:
    template_dir = Path(template_dir).resolve()
    pack_path = template_dir / "component_pack.json"
    issues: list[dict[str, str]] = []
    pack: dict[str, Any] = {}
    if not pack_path.is_file():
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("TEMPLATE-COMPONENT-PACK-MISSING", "component_pack.json is required", "component_pack.json")],
        }
    try:
        pack = read_json(pack_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("TEMPLATE-COMPONENT-PACK-JSON", str(exc), "component_pack.json")],
        }

    if pack.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))
    if not PACK_ID_RE.fullmatch(str(pack.get("pack_id") or "")):
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-ID", "pack_id must be template/<template_id>/components", "pack_id"))
    if str(pack.get("template_id") or "") != template_dir.name:
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-TEMPLATE", "template_id must match the template directory", "template_id"))
    if not SEMVER_RE.fullmatch(str(pack.get("version") or "")):
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-VERSION", "version must use semantic versioning", "version"))
    for key in ("display_name", "description", "license"):
        if not isinstance(pack.get(key), str) or not pack[key].strip():
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-FIELD", f"{key} is required", key))

    dependencies = pack.get("dependencies") if isinstance(pack.get("dependencies"), dict) else None
    component_packs = dependencies.get("component_packs") if isinstance(dependencies, dict) else None
    if not isinstance(component_packs, list):
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-DEPENDENCIES", "dependencies.component_packs must be a list", "dependencies.component_packs"))
        component_packs = []
    seen_dependencies: set[str] = set()
    for index, dependency in enumerate(component_packs):
        path = f"dependencies.component_packs[{index}]"
        if not isinstance(dependency, dict):
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-DEPENDENCIES", "dependency must be an object", path))
            continue
        dependency_id = str(dependency.get("pack_id") or "")
        if not dependency_id or dependency_id in seen_dependencies:
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-DEPENDENCIES", "dependency pack_id must be unique and non-empty", f"{path}.pack_id"))
        seen_dependencies.add(dependency_id)
        if not isinstance(dependency.get("version_range"), str) or not dependency["version_range"].strip():
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-DEPENDENCIES", "dependency version_range is required", f"{path}.version_range"))

    token_contract = pack.get("design_tokens") if isinstance(pack.get("design_tokens"), dict) else None
    token_source: Path | None = None
    if not isinstance(token_contract, dict):
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-TOKENS", "design_tokens must be an object", "design_tokens"))
    else:
        required_tokens = token_contract.get("required")
        if not isinstance(required_tokens, list) or not required_tokens:
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-TOKENS", "design_tokens.required must be non-empty", "design_tokens.required"))
            required_tokens = []
        token_source = _safe_file(template_dir, token_contract.get("source"))
        if token_source is None or not token_source.is_file():
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-TOKENS", "design token source is missing", "design_tokens.source"))
        else:
            try:
                tokens = read_json(token_source)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                issues.append(_issue("TEMPLATE-COMPONENT-PACK-TOKENS", str(exc), "design_tokens.source"))
                tokens = {}
            for token in required_tokens:
                if not isinstance(token, str) or _token_value(tokens, token) is None:
                    issues.append(_issue("TEMPLATE-COMPONENT-PACK-TOKENS", f"required token {token!r} is missing", "design_tokens.required"))

    entrypoints = pack.get("entrypoints") if isinstance(pack.get("entrypoints"), dict) else {}
    expected = {"catalog": "component_catalog.json", "primitives": "component_primitives.json", "recipes": "body_variant_recipes.json"}
    sources: dict[str, Path] = {}
    for key, expected_name in expected.items():
        source = _safe_file(template_dir, entrypoints.get(key))
        if source is None or not source.is_file():
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-ENTRYPOINT", f"{key} entrypoint is missing", f"entrypoints.{key}"))
        else:
            sources[key] = source
            if source.name != expected_name:
                issues.append(_issue("TEMPLATE-COMPONENT-PACK-ENTRYPOINT", f"{key} must point to {expected_name}", f"entrypoints.{key}"))

    catalog = read_json(sources["catalog"]) if "catalog" in sources else {}
    components = expanded_catalog_components(template_dir, catalog)
    component_ids = {str(component.get("component_id") or "") for component in components}
    body_variants_path = template_dir / "body_variants.json"
    variant_ids = set()
    if body_variants_path.is_file():
        variant_ids = {
            str(row.get("variant_id") or "")
            for row in read_json(body_variants_path).get("variants", [])
            if isinstance(row, dict)
        }
    recipes = _recipe_payload(template_dir, pack)
    recipe_rows = recipes.get("recipes") if isinstance(recipes.get("recipes"), list) else []
    recipe_variant_ids: set[str] = set()
    for index, recipe in enumerate(recipe_rows):
        path = f"recipes[{index}]"
        if not isinstance(recipe, dict):
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-RECIPE", "recipe must be an object", path))
            continue
        variant_id = str(recipe.get("variant_id") or "")
        recipe_variant_ids.add(variant_id)
        if not variant_id or variant_id not in variant_ids:
            issues.append(_issue("TEMPLATE-COMPONENT-PACK-RECIPE", "recipe variant_id must exist in body_variants.json", f"{path}.variant_id"))
        for component_id in [recipe.get("scene_component"), *(recipe.get("primitives") or [])]:
            if str(component_id or "") not in component_ids:
                issues.append(_issue("TEMPLATE-COMPONENT-PACK-RECIPE", f"recipe references unknown component {component_id!r}", path))
    if variant_ids and recipe_variant_ids != variant_ids:
        issues.append(_issue("TEMPLATE-COMPONENT-PACK-RECIPE", "recipes must cover every body variant exactly once", "recipes"))

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "pack_id": str(pack.get("pack_id") or ""),
        "version": str(pack.get("version") or ""),
        "component_count": len(components),
        "primitive_count": max(0, len(components) - len(catalog.get("components", []))),
        "recipe_count": len(recipe_rows),
        "dependencies": component_packs,
        "token_source": str(token_source.relative_to(template_dir)) if token_source else "",
    }
