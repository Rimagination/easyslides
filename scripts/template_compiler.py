#!/usr/bin/env python3
"""Compile an EasySlides template package into one deterministic runtime IR.

The compiler makes ownership explicit:

- ``template_package.json`` owns package identity, version, capabilities, and
  entrypoints.
- ``layouts.json`` owns public shells and shell slots.
- ``body_variants.json`` owns content composition.
- ``component_catalog.json`` and component packages own reusable modules.
- ``qa_policy.json`` owns promotion requirements.

Compatibility sidecars are projections of those sources.  Runtime code should
consume ``compiled/template_ir.json`` instead of reconciling the source files
independently.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.body_variant_contract import normalize_component_refs
    from scripts.template_component_pack import (
        body_variant_recipe_map,
        expanded_catalog_components,
        recipe_component_asset_ids,
        validate_template_component_pack,
    )
    from scripts.template_capabilities import validate_capability_profile
except ModuleNotFoundError:  # pragma: no cover
    from body_variant_contract import normalize_component_refs
    from template_component_pack import body_variant_recipe_map, expanded_catalog_components, recipe_component_asset_ids, validate_template_component_pack
    from template_capabilities import validate_capability_profile


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
COMPONENT_REGISTRY = ROOT / "templates" / "components" / "component_registry.json"
TEMPLATE_IR_SCHEMA = "easyslides.template_ir.v1"
TEMPLATE_LOCK_SCHEMA = "easyslides.template_lock.v1"
COMPILE_REPORT_SCHEMA = "easyslides.template_compile_report.v1"
CAPABILITY_LEVELS = ("shell", "semantic", "composable", "production")
DEFAULT_SOURCE_OF_TRUTH = {
    "package": "template_package.json",
    "shells": "layouts.json",
    "body_variants": "body_variants.json",
    "components": "component_catalog.json",
    "component_pack": "component_pack.json",
    "design_tokens": "design_tokens.json",
    "qa": "qa_policy.json",
    "provenance": "source_page_roster.json",
}


class TemplateCompileError(ValueError):
    """Raised when canonical template sources cannot form an executable IR."""


def read_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise TemplateCompileError(f"missing required template source: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise TemplateCompileError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TemplateCompileError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_source_path(template_dir: Path, value: object, *, required: bool) -> Path | None:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        if required:
            raise TemplateCompileError("canonical source path is empty")
        return None
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise TemplateCompileError(f"canonical source must be a safe relative path: {raw}")
    resolved = (template_dir / relative).resolve()
    try:
        resolved.relative_to(template_dir.resolve())
    except ValueError as exc:
        raise TemplateCompileError(f"canonical source escapes template package: {raw}") from exc
    if required and not resolved.is_file():
        raise TemplateCompileError(f"canonical source does not exist: {raw}")
    return resolved if resolved.is_file() else None


def _frame(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        frame = {
            "x": float(value.get("x", 0)),
            "y": float(value.get("y", 0)),
            "width": float(value.get("width", value.get("w", 0))),
            "height": float(value.get("height", value.get("h", 0))),
        }
    except (TypeError, ValueError):
        return None
    if frame["width"] <= 0 or frame["height"] <= 0:
        return None
    return frame


def _slot_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for slot in value:
        if isinstance(slot, str) and slot:
            rows.append({"slot_id": slot, "kind": "text", "required": True})
        elif isinstance(slot, dict):
            slot_id = str(slot.get("slot_id") or slot.get("id") or slot.get("slot") or "")
            if not slot_id:
                continue
            row = dict(slot)
            row["slot_id"] = slot_id
            row.setdefault("kind", "text")
            row.setdefault("required", True)
            rows.append(row)
    return rows


def _normalize_regions(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        source = [
            {"region_id": str(region_id), **(region if isinstance(region, dict) else {})}
            for region_id, region in value.items()
        ]
    elif isinstance(value, list):
        source = [dict(region) for region in value if isinstance(region, dict)]
    else:
        source = []
    regions: list[dict[str, Any]] = []
    for index, region in enumerate(source, start=1):
        region_id = str(region.get("region_id") or region.get("id") or f"region_{index:02d}")
        region_frame = _frame(region.get("frame") if isinstance(region.get("frame"), dict) else region)
        if not region_frame:
            continue
        normalized = {
            "region_id": region_id,
            "frame": region_frame,
            "z_index": int(region.get("z_index") or index * 10),
            "fit": str(region.get("fit") or "contain"),
            "allow_overlap": bool(region.get("allow_overlap", False)),
        }
        for key in ("coordinate_space", "normalized_frame", "purpose"):
            if key in region:
                normalized[key] = region[key]
        regions.append(normalized)
    return regions


def _infer_capability_level(
    package: dict[str, Any],
    *,
    has_variants: bool,
    has_components: bool,
    has_qa: bool,
) -> str:
    explicit = str(package.get("capability_level") or "").strip().lower()
    if explicit:
        if explicit not in CAPABILITY_LEVELS:
            raise TemplateCompileError(
                f"capability_level must be one of {', '.join(CAPABILITY_LEVELS)}"
            )
        return explicit
    if has_variants and has_components and has_qa:
        return "production"
    if has_variants and has_components:
        return "composable"
    if has_variants:
        return "semantic"
    return "shell"


def _validate_capability_sources(
    level: str,
    *,
    variants_path: Path | None,
    components_path: Path | None,
    qa_path: Path | None,
) -> None:
    rank = CAPABILITY_LEVELS.index(level)
    missing: list[str] = []
    if rank >= CAPABILITY_LEVELS.index("semantic") and variants_path is None:
        missing.append("body_variants.json")
    if rank >= CAPABILITY_LEVELS.index("composable") and components_path is None:
        missing.append("component_catalog.json")
    if rank >= CAPABILITY_LEVELS.index("production") and qa_path is None:
        missing.append("qa_policy.json")
    if missing:
        raise TemplateCompileError(
            f"capability_level {level!r} requires canonical source(s): {', '.join(missing)}"
        )


def _global_component_map() -> dict[str, dict[str, Any]]:
    payload = read_json(COMPONENT_REGISTRY, required=False)
    return {
        str(asset.get("asset_id")): asset
        for asset in payload.get("assets", [])
        if isinstance(asset, dict) and asset.get("asset_id")
    }


def _local_component_map(
    template_dir: Path,
    template_id: str,
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("components", []):
        if not isinstance(item, dict):
            continue
        component_id = str(item.get("component_id") or "")
        asset_id = str(item.get("asset_id") or (f"component/{template_id}/{component_id}" if component_id else ""))
        if not asset_id:
            continue
        row = dict(item)
        row["asset_id"] = asset_id
        row["component_id"] = component_id or asset_id.rsplit("/", 1)[-1]
        row["scope"] = "template"
        result[asset_id] = row
    return result


def _component_runtime_record(
    template_dir: Path,
    asset_id: str,
    asset: dict[str, Any],
) -> dict[str, Any]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    asset_path = str(asset.get("asset_path") or metadata.get("asset_path") or "")
    scope = str(asset.get("scope") or ("template" if asset_id.startswith(f"component/{template_dir.name}/") else "global"))
    record: dict[str, Any] = {
        "asset_id": asset_id,
        "scope": scope,
        "renderer_id": str(asset.get("renderer_id") or metadata.get("renderer_id") or ""),
        "render_backend": str(asset.get("render_backend") or metadata.get("render_backend") or ""),
        "slots": _slot_rows(asset.get("slots")),
        "geometry": asset.get("geometry") if isinstance(asset.get("geometry"), dict) else metadata.get("geometry", {}),
        "required_gates": list(
            asset.get("required_gates")
            or (asset.get("qa", {}).get("required_gates") if isinstance(asset.get("qa"), dict) else [])
            or []
        ),
    }
    if asset_path:
        if scope == "template":
            source = _safe_source_path(template_dir, asset_path, required=True)
        else:
            source = Path(str(asset.get("source_path") or metadata.get("source_path") or asset_path))
            if not source.is_absolute():
                source = (ROOT / source).resolve()
            if not source.is_file():
                source = None
        if source:
            record["asset_path"] = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source)
            record["sha256"] = _sha256(source)
    return record


def _shell_rows(
    template_dir: Path,
    layouts: dict[str, Any],
    body_variants: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = layouts.get("shells") or layouts.get("layouts") or layouts.get("pages")
    if not isinstance(rows, list) or not rows:
        raise TemplateCompileError("layouts.json must define a non-empty shells/layouts/pages list")
    slot_models = layouts.get("slot_models") if isinstance(layouts.get("slot_models"), dict) else {}
    content_area = _frame(body_variants.get("content_area"))
    shells: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source in enumerate(rows, start=1):
        if not isinstance(source, dict):
            continue
        shell_id = str(
            source.get("shell_id")
            or source.get("page_id")
            or source.get("layout_id")
            or source.get("id")
            or f"shell_{index:02d}"
        )
        if shell_id in seen:
            raise TemplateCompileError(f"duplicate shell_id {shell_id!r}")
        seen.add(shell_id)
        role = str(source.get("role") or source.get("story_role") or shell_id)
        svg_path = str(source.get("svg") or source.get("svg_path") or "")
        svg = _safe_source_path(template_dir, svg_path, required=True)
        declared_slots = source.get("slots")
        if declared_slots and all(isinstance(slot, str) for slot in declared_slots):
            model = slot_models.get(shell_id) or slot_models.get(str(source.get("layout_id") or ""))
            if isinstance(model, list):
                declared_slots = model
        regions = _normalize_regions(source.get("regions"))
        if role == "content" and content_area and not any(
            row["region_id"] in {"content", "body_canvas"} for row in regions
        ):
            regions.append(
                {
                    "region_id": "body_canvas",
                    "frame": content_area,
                    "z_index": 10,
                    "fit": "contain",
                    "allow_overlap": False,
                }
            )
        if not regions:
            canvas = layouts.get("canvas") if isinstance(layouts.get("canvas"), dict) else {}
            regions = [
                {
                    "region_id": "canvas",
                    "frame": {
                        "x": 0.0,
                        "y": 0.0,
                        "width": float(canvas.get("width") or 1280),
                        "height": float(canvas.get("height") or 720),
                    },
                    "z_index": 0,
                    "fit": "contain",
                    "allow_overlap": False,
                }
            ]
        shells.append(
            {
                "shell_id": shell_id,
                "role": role,
                "archetype": str(source.get("page_archetype") or source.get("archetype") or ""),
                "svg_path": svg.relative_to(ROOT).as_posix() if svg and svg.is_relative_to(ROOT) else str(svg),
                "slots": _slot_rows(declared_slots),
                "regions": regions,
                "body_variant_ids": list(source.get("body_variants") or []),
                "content_shell_policy": str(source.get("content_shell_policy") or ""),
                "body_canvas": _frame(source.get("body_canvas")),
                "legacy_shadow_slots": list(source.get("legacy_shadow_slots") or []),
            }
        )
    return shells


def _variant_rows(
    template_id: str,
    payload: dict[str, Any],
    component_assets: dict[str, dict[str, Any]],
    recipe_map: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    variants = payload.get("variants")
    if not isinstance(variants, list):
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source in enumerate(variants):
        if not isinstance(source, dict):
            continue
        variant_id = str(source.get("variant_id") or "")
        if not variant_id or variant_id in seen:
            raise TemplateCompileError(f"body variant id must be non-empty and unique: {variant_id!r}")
        seen.add(variant_id)
        refs = normalize_component_refs(source, template_id)
        recipe = (recipe_map or {}).get(variant_id, {})
        recipe_asset_ids = recipe_component_asset_ids(recipe, template_id) if recipe else []
        for ref in refs:
            asset_id = str(ref["asset_id"])
            if ref.get("required", True) and asset_id not in component_assets:
                raise TemplateCompileError(
                    f"body variant {variant_id!r} requires unresolved component {asset_id!r}"
                )
        for asset_id in recipe_asset_ids:
            if asset_id not in component_assets:
                raise TemplateCompileError(
                    f"body variant recipe {variant_id!r} requires unresolved component {asset_id!r}"
                )
        rows.append(
            {
                "variant_id": variant_id,
                "shell_id": str(source.get("shell_id") or source.get("page_id") or source.get("layout_id") or "content"),
                "composition_mode": str(
                    source.get("composition_mode")
                    or ("ordered_component_refs" if refs else "open_content_area")
                ),
                "best_for": str(source.get("best_for") or ""),
                "selection": {
                    "content_shapes": list(source.get("content_shapes") or []),
                    "density": source.get("density"),
                    "figure_count": source.get("figure_count"),
                    "min_items": source.get("min_items"),
                    "max_items": source.get("max_items"),
                    "story_roles": list(source.get("story_roles") or ["content"]),
                    "priority": int(source.get("priority") or 0),
                },
                "slots": _slot_rows(source.get("slots")),
                "regions": _normalize_regions(source.get("regions")),
                "clear_region": _frame(source.get("clear_region")),
                "component_refs": refs,
                "component_recipe": recipe,
                "component_dependency_asset_ids": recipe_asset_ids,
                "source_slides": list(source.get("source_slides") or []),
                "composition_scene": str(source.get("composition_scene") or ""),
                "coordinate_space": str(source.get("coordinate_space") or ""),
                "source_guidance": {
                    "section": str(source.get("section") or ""),
                    "narrative_step": source.get("narrative_step"),
                    "source_page_purpose": str(source.get("source_page_purpose") or ""),
                },
            }
        )
    return rows


def _source_map(package: dict[str, Any]) -> dict[str, str]:
    declared = package.get("source_of_truth")
    merged = dict(DEFAULT_SOURCE_OF_TRUTH)
    if isinstance(declared, dict):
        merged.update({str(key): str(value) for key, value in declared.items() if str(value)})
    return merged


def _derived_projections(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    package = template_ir["package"]
    shells = template_ir["shells"]
    variants = template_ir["body_variants"]
    flat_slots = [
        {**slot, "shell_id": shell["shell_id"]}
        for shell in shells
        for slot in shell.get("slots", [])
    ]
    slot_contract_layouts: list[dict[str, Any]] = []
    for shell in shells:
        shell_slots = list(shell.get("slots", []))
        slot_details: list[dict[str, Any]] = []
        for slot in shell_slots:
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
        slot_ids = [slot["slot_id"] for slot in shell_slots]
        slot_contract_layouts.append(
            {
                "layout_id": shell["shell_id"],
                "page_id": Path(shell["svg_path"]).stem,
                "svg_path": shell["svg_path"],
                "slot_model": shell["role"],
                "slots": slot_ids,
                "text_slots": [
                    slot["slot_id"]
                    for slot in shell_slots
                    if slot.get("kind", "text") == "text"
                ],
                "image_slots": [
                    slot["slot_id"]
                    for slot in shell_slots
                    if slot.get("kind") == "image"
                ],
                "replacement": "replace_declared_slots_preserve_template_geometry",
                "slot_details": slot_details,
            }
        )
    geometry_pages = [
        {
            "page_id": shell["shell_id"],
            "svg": shell["svg_path"],
            "regions": shell["regions"],
            "containers": [
                {**slot.get("geometry", {}), "id": slot["slot_id"], "kind": slot.get("kind", "text")}
                for slot in shell.get("slots", [])
                if isinstance(slot.get("geometry"), dict)
            ],
        }
        for shell in shells
    ]
    template_view = {
        "schema_version": "easyslides.template_projection.v1",
        "derived_from": "compiled/template_ir.json",
        "template_id": template_ir["template_id"],
        "display_name": package.get("display_name", template_ir["template_id"]),
        "description": package.get("description", ""),
        "version": package.get("version", ""),
        "status": package.get("status", ""),
        "capability_level": template_ir["capability_level"],
        "roles": [shell["role"] for shell in shells],
        "layout_count": len(shells),
        "variant_count": len(variants),
    }
    return {
        "template.json": template_view,
        "page_catalog.json": {
            "schema_version": "easyslides.page_catalog_projection.v1",
            "derived_from": "compiled/template_ir.json",
            "template_id": template_ir["template_id"],
            "pages": shells,
            "body_variants": variants,
        },
        "slot_contracts.json": {
            "schema_version": "easyslides.template_slot_contracts.v1",
            "derived_from": "compiled/template_ir.json",
            "template_id": template_ir["template_id"],
            "replacement_rule": "replace_declared_slots_preserve_template_geometry",
            "private_clone_required": False,
            "text_fit_policy": dict(
                template_ir.get("design_tokens", {}).get("text_fit_policy") or {}
            ),
            "hard_geometry_invariants": list(
                template_ir.get("qa_policy", {}).get("alignment_invariants") or []
            ),
            "layouts": slot_contract_layouts,
            "slots": flat_slots,
        },
        "geometry_contract.json": {
            "schema_version": "easyslides.template_geometry_projection.v1",
            "derived_from": "compiled/template_ir.json",
            "template_id": template_ir["template_id"],
            "canvas": template_ir["canvas"],
            "hard_invariants": list(
                template_ir.get("qa_policy", {}).get("alignment_invariants") or []
            ),
            "pages": geometry_pages,
        },
        "template_status.json": {
            "schema_version": "easyslides.template_status.v2",
            "derived_from": "template_package.json+qa_policy.json+compiled/template_ir.json",
            "template_id": template_ir["template_id"],
            "status": package.get("status", "candidate"),
            "capability_level": template_ir["capability_level"],
            "production_eligible": bool(package.get("production_eligible", False)),
            "source_digest": template_ir["source_digest"],
        },
    }


def compile_template(
    template_dir: str | Path,
    *,
    write: bool = False,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    directory = Path(template_dir).resolve()
    if not directory.is_dir():
        candidate = LAYOUTS_ROOT / str(template_dir)
        if candidate.is_dir():
            directory = candidate.resolve()
        else:
            raise TemplateCompileError(f"template directory not found: {template_dir}")

    package_path = directory / "template_package.json"
    package = read_json(package_path)
    template_id = str(package.get("template_id") or "")
    if not template_id or template_id != directory.name:
        raise TemplateCompileError(
            f"template_package.json template_id must match directory name {directory.name!r}"
        )

    capability_report = validate_capability_profile(directory)
    if capability_report["status"] != "pass":
        detail = "; ".join(item["message"] for item in capability_report["issues"][:3])
        raise TemplateCompileError(f"template capability profile failed: {detail}")
    capability_profile = capability_report["profile"]
    if capability_profile.get("generation_enabled") is not True:
        raise TemplateCompileError("template capability profile does not permit automatic generation")

    sources = _source_map(package)
    package_source = _safe_source_path(directory, sources["package"], required=True)
    layouts_path = _safe_source_path(directory, sources["shells"], required=True)
    variants_path = _safe_source_path(directory, sources["body_variants"], required=False)
    components_path = _safe_source_path(directory, sources["components"], required=False)
    component_pack_path = _safe_source_path(directory, sources["component_pack"], required=False)
    design_tokens_path = _safe_source_path(directory, sources["design_tokens"], required=False)
    qa_path = _safe_source_path(directory, sources["qa"], required=False)
    provenance_path = _safe_source_path(directory, sources["provenance"], required=False)

    layouts = read_json(layouts_path)
    body_variants = read_json(variants_path, required=False) if variants_path else {}
    component_catalog = read_json(components_path, required=False) if components_path else {}
    component_pack = read_json(component_pack_path, required=False) if component_pack_path else {}
    if component_pack_path:
        component_pack_report = validate_template_component_pack(directory)
        if component_pack_report["status"] != "pass":
            detail = "; ".join(item["message"] for item in component_pack_report["issues"][:3])
            raise TemplateCompileError(f"template component pack contract failed: {detail}")
    else:
        component_pack_report = {"status": "skipped", "dependencies": []}
    component_catalog = {
        **component_catalog,
        "components": expanded_catalog_components(directory, component_catalog),
    }
    component_design_tokens = read_json(design_tokens_path, required=False) if design_tokens_path else {}
    qa_policy = read_json(qa_path, required=False) if qa_path else {}
    level = _infer_capability_level(
        package,
        has_variants=variants_path is not None,
        has_components=components_path is not None,
        has_qa=qa_path is not None,
    )
    _validate_capability_sources(
        level,
        variants_path=variants_path,
        components_path=components_path,
        qa_path=qa_path,
    )

    local_components = _local_component_map(directory, template_id, component_catalog)
    all_components = {**_global_component_map(), **local_components}
    recipe_map = body_variant_recipe_map(directory, component_pack) if component_pack_path else {}
    variants = _variant_rows(template_id, body_variants, all_components, recipe_map)
    referenced_ids = {
        str(ref["asset_id"])
        for variant in variants
        for ref in variant.get("component_refs", [])
    }
    referenced_ids.update(
        asset_id
        for variant in variants
        for asset_id in variant.get("component_dependency_asset_ids", [])
    )
    component_records = [
        _component_runtime_record(directory, asset_id, all_components[asset_id])
        for asset_id in sorted(referenced_ids)
    ]
    shells = _shell_rows(directory, layouts, body_variants)
    canvas = layouts.get("canvas") if isinstance(layouts.get("canvas"), dict) else {}
    source_paths = {
        key: path
        for key, path in {
            "package": package_source,
            "shells": layouts_path,
            "body_variants": variants_path,
            "components": components_path,
            "component_pack": component_pack_path,
            "design_tokens": design_tokens_path,
            "qa": qa_path,
            "provenance": provenance_path,
            "capability_profile": directory / "capability_profile.json",
        }.items()
        if path is not None
    }
    source_hashes = {
        key: {
            "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            "sha256": _sha256(path),
        }
        for key, path in source_paths.items()
    }

    template_ir: dict[str, Any] = OrderedDict(
        schema_version=TEMPLATE_IR_SCHEMA,
        template_id=template_id,
        template_path=directory.relative_to(ROOT).as_posix() if directory.is_relative_to(ROOT) else str(directory),
        package={
            key: package.get(key)
            for key in (
                "package_id",
                "template_id",
                "version",
                "status",
                "display_name",
                "description",
                "production_eligible",
            )
            if package.get(key) not in (None, "")
        },
        capability_level=level,
        capability_profile={
            "schema_version": capability_profile.get("schema_version"),
            "lifecycle": capability_profile.get("lifecycle"),
            "generation_enabled": capability_profile.get("generation_enabled"),
            "composition": capability_profile.get("composition", {}),
            "selection_policy": capability_profile.get("selection_policy", {}),
            "required_gates": capability_profile.get("required_gates", []),
        },
        source_of_truth=sources,
        canvas={
            "width": float(canvas.get("width") or 1280),
            "height": float(canvas.get("height") or 720),
            "format": str(canvas.get("format") or package.get("compatibility", {}).get("canvas_format") or "ppt169"),
        },
        design_tokens={
            "style_system": layouts.get("style_system", ""),
            "colors": layouts.get("colors", {}),
            "text_fit_policy": layouts.get("text_fit_policy", {}),
            "component_tokens": component_design_tokens,
        },
        component_pack={
            "pack_id": component_pack.get("pack_id", ""),
            "version": component_pack.get("version", ""),
            "scope": component_pack.get("scope", ""),
            "dependencies": component_pack_report.get("dependencies", []),
            "design_tokens": component_pack.get("design_tokens", {}),
        },
        shells=shells,
        body_variants=variants,
        components=component_records,
        qa_policy=qa_policy,
        provenance={
            "path": source_hashes.get("provenance", {}).get("path", ""),
            "source_template_id": str(package.get("source_template_id") or ""),
        },
        source_hashes=source_hashes,
    )
    template_ir["source_digest"] = _json_sha256(source_hashes)
    lock = {
        "schema_version": TEMPLATE_LOCK_SCHEMA,
        "template_id": template_id,
        "package_version": str(package.get("version") or ""),
        "source_digest": template_ir["source_digest"],
        "sources": source_hashes,
        "component_dependencies": [
            {
                "asset_id": component["asset_id"],
                "scope": component.get("scope", ""),
                "renderer_id": component.get("renderer_id", ""),
                "asset_path": component.get("asset_path", ""),
                "sha256": component.get("sha256", ""),
            }
            for component in component_records
        ],
        "component_pack": template_ir["component_pack"],
        "capability_profile": template_ir["capability_profile"],
    }
    projections = _derived_projections(template_ir)
    compiled_dir = Path(output_dir).resolve() if output_dir else directory / "compiled"
    if write:
        write_json(compiled_dir / "template_ir.json", template_ir)
        write_json(compiled_dir / "template.lock.json", lock)
        for name, payload in projections.items():
            write_json(compiled_dir / "projections" / name, payload)

    return {
        "schema_version": COMPILE_REPORT_SCHEMA,
        "status": "pass",
        "template_id": template_id,
        "capability_level": level,
        "source_digest": template_ir["source_digest"],
        "shell_count": len(shells),
        "body_variant_count": len(variants),
        "component_dependency_count": len(component_records),
        "output_dir": str(compiled_dir),
        "template_ir": template_ir,
        "lock": lock,
        "projections": projections,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", help="Template id or template directory.")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compile_template(args.template, write=args.write, output_dir=args.out_dir)
    except (OSError, TemplateCompileError) as exc:
        report = {
            "schema_version": COMPILE_REPORT_SCHEMA,
            "status": "fail",
            "issues": [{"code": "TEMPLATE-COMPILE", "message": str(exc)}],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Template compiler: {report['status']}"
            + (f" ({report.get('template_id')}, {report.get('capability_level')})" if report["status"] == "pass" else "")
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
