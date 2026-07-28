#!/usr/bin/env python3
"""Normalize and validate body-variant component composition contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.template_component_pack import body_variant_recipe_map, expanded_catalog_components, recipe_component_asset_ids
except ModuleNotFoundError:  # pragma: no cover
    from template_component_pack import body_variant_recipe_map, expanded_catalog_components, recipe_component_asset_ids


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
DEFAULT_COMPONENT_REGISTRY = ROOT / "templates" / "components" / "component_registry.json"
REPORT_SCHEMA_VERSION = "easyslides.body_variant_component_report.v1"

ASSET_PREFIXES = (
    "body_variant/",
    "card/",
    "chart/",
    "component/",
    "component_package/",
    "icon_family/",
    "page_module/",
    "page_recipe/",
    "pptx_component/",
    "visual_recipe/",
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def resolve_template_dir(template: str | Path) -> Path:
    path = Path(template)
    if path.is_dir():
        return path.resolve()
    return (LAYOUTS_ROOT / str(template)).resolve()


def canonical_component_asset_id(template_id: str, value: object) -> str:
    """Return a stable registry asset id for a component reference."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith(ASSET_PREFIXES):
        return raw
    if "/" in raw:
        return raw
    return f"component/{template_id}/{raw}"


def _positive_int(value: object, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _component_name(asset_id: str) -> str:
    return asset_id.rsplit("/", 1)[-1] if asset_id else "component"


def component_ref_source(variant: dict[str, Any]) -> tuple[str, list[Any]]:
    refs = variant.get("component_refs")
    if isinstance(refs, list):
        return "component_refs", refs
    legacy = variant.get("components")
    if isinstance(legacy, list):
        return "components", legacy
    return "", []


def normalize_component_ref(
    value: object,
    *,
    template_id: str,
    default_order: int,
) -> dict[str, Any] | None:
    """Normalize string and object references into one executable shape."""
    if isinstance(value, str):
        asset_id = canonical_component_asset_id(template_id, value)
        raw: dict[str, Any] = {}
    elif isinstance(value, dict):
        raw = value
        asset_id = canonical_component_asset_id(
            template_id,
            raw.get("asset_id") or raw.get("component_id"),
        )
    else:
        return None
    if not asset_id:
        return None

    component_name = _component_name(asset_id)
    order = _positive_int(raw.get("order"), default_order)
    slot_bindings = raw.get("slot_bindings")
    if not isinstance(slot_bindings, dict):
        slot_bindings = {}
    normalized: dict[str, Any] = {
        "asset_id": asset_id,
        "instance_id": str(raw.get("instance_id") or f"{component_name}_{order:02d}"),
        "role": str(raw.get("role") or component_name),
        "order": order,
        "required": bool(raw.get("required", True)),
        "slot_bindings": {
            str(component_slot): str(variant_slot)
            for component_slot, variant_slot in slot_bindings.items()
            if str(component_slot) and str(variant_slot)
        },
    }
    for key in ("region", "placement", "renderer_id"):
        if raw.get(key) not in (None, ""):
            normalized[key] = raw[key]
    return normalized


def normalize_component_refs(variant: dict[str, Any], template_id: str) -> list[dict[str, Any]]:
    """Return ordered canonical refs while accepting the legacy components list."""
    _source, values = component_ref_source(variant)
    refs = [
        ref
        for index, value in enumerate(values, start=1)
        if (ref := normalize_component_ref(value, template_id=template_id, default_order=index))
    ]
    return sorted(refs, key=lambda item: (int(item["order"]), str(item["instance_id"])))


def _asset_map(registry: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(registry, dict):
        return {}
    return {
        str(asset["asset_id"]): asset
        for asset in registry.get("assets", [])
        if isinstance(asset, dict) and asset.get("asset_id")
    }


def load_default_registry() -> dict[str, Any]:
    if not DEFAULT_COMPONENT_REGISTRY.is_file():
        return {"assets": []}
    return read_json(DEFAULT_COMPONENT_REGISTRY)


def load_template_component_assets(template_dir: Path, template_id: str) -> dict[str, dict[str, Any]]:
    path = template_dir / "component_catalog.json"
    if not path.is_file():
        return {}
    payload = read_json(path)
    assets: dict[str, dict[str, Any]] = {}
    for component in expanded_catalog_components(template_dir, payload):
        if not isinstance(component, dict):
            continue
        asset_id = canonical_component_asset_id(
            template_id,
            component.get("asset_id") or component.get("component_id"),
        )
        if asset_id:
            assets[asset_id] = component
    return assets


def _slot_ids(asset: dict[str, Any]) -> set[str]:
    slots = asset.get("slots")
    if not isinstance(slots, list):
        return set()
    result: set[str] = set()
    for slot in slots:
        if isinstance(slot, str) and slot:
            result.add(slot)
        elif isinstance(slot, dict):
            slot_id = str(slot.get("slot_id") or slot.get("slot") or slot.get("id") or "")
            if slot_id:
                result.add(slot_id)
    return result


def _required_slot_ids(asset: dict[str, Any]) -> set[str]:
    slots = asset.get("slots")
    if not isinstance(slots, list):
        return set()
    result: set[str] = set()
    for slot in slots:
        if isinstance(slot, str) and slot:
            result.add(slot)
        elif isinstance(slot, dict):
            slot_id = str(slot.get("slot_id") or slot.get("slot") or slot.get("id") or "")
            if slot_id and bool(slot.get("required", True)):
                result.add(slot_id)
    return result


def _variant_slot_ids(variant: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    slots = variant.get("slots")
    if not isinstance(slots, list):
        return result
    for slot in slots:
        if isinstance(slot, str) and slot:
            result.add(slot)
        elif isinstance(slot, dict):
            slot_id = str(slot.get("slot_id") or slot.get("slot") or slot.get("id") or "")
            if slot_id:
                result.add(slot_id)
    return result


def _region_ids(variant: dict[str, Any]) -> tuple[set[str], list[dict[str, str]]]:
    value = variant.get("regions")
    if isinstance(value, dict):
        rows = [
            {"region_id": str(region_id), **(region if isinstance(region, dict) else {})}
            for region_id, region in value.items()
        ]
    elif isinstance(value, list):
        rows = [region for region in value if isinstance(region, dict)]
    else:
        rows = []
    ids: set[str] = set()
    issues: list[dict[str, str]] = []
    for index, region in enumerate(rows):
        path = f"regions[{index}]"
        region_id = str(region.get("region_id") or region.get("id") or "")
        if not region_id:
            issues.append(_issue("BODY-VARIANT-REGION-ID", "region_id is required", f"{path}.region_id"))
            continue
        if region_id in ids:
            issues.append(_issue("BODY-VARIANT-REGION-ID", f"duplicate region_id {region_id!r}", f"{path}.region_id"))
        ids.add(region_id)
        frame = region.get("frame") if isinstance(region.get("frame"), dict) else region
        try:
            width = float(frame.get("width", frame.get("w", 0)))
            height = float(frame.get("height", frame.get("h", 0)))
        except (TypeError, ValueError):
            width = height = 0
        if width <= 0 or height <= 0:
            issues.append(
                _issue(
                    "BODY-VARIANT-REGION-FRAME",
                    "region frame must declare positive width and height",
                    f"{path}.frame",
                )
            )
    return ids, issues


def _valid_placement(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        return (
            float(value.get("width", value.get("w", 0))) > 0
            and float(value.get("height", value.get("h", 0))) > 0
        )
    except (TypeError, ValueError):
        return False


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
    return frame if frame["width"] > 0 and frame["height"] > 0 else None


def _contains_frame(container: dict[str, float], child: dict[str, float]) -> bool:
    tolerance = 0.01
    return (
        child["x"] >= container["x"] - tolerance
        and child["y"] >= container["y"] - tolerance
        and child["x"] + child["width"] <= container["x"] + container["width"] + tolerance
        and child["y"] + child["height"] <= container["y"] + container["height"] + tolerance
    )


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def validate_body_variant_contract(
    template: str | Path,
    *,
    registry: dict[str, Any] | None = None,
    variant_id: str | None = None,
) -> dict[str, Any]:
    """Validate body variants and their ordered component dependencies."""
    template_dir = resolve_template_dir(template)
    payload = read_json(template_dir / "body_variants.json")
    template_id = str(payload.get("template_id") or template_dir.name)
    composition_space = str(payload.get("coordinate_space") or "")
    body_canvas = _frame(payload.get("content_area"))
    global_assets = _asset_map(registry if registry is not None else load_default_registry())
    local_assets = load_template_component_assets(template_dir, template_id)
    assets = {**global_assets, **local_assets}
    recipe_map = body_variant_recipe_map(template_dir) if (template_dir / "component_pack.json").is_file() else {}

    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    reports: list[dict[str, Any]] = []
    variants = payload.get("variants")
    if not isinstance(variants, list) or not variants:
        issues.append(_issue("BODY-VARIANT-LIST", "variants must be a non-empty list", "variants"))
        variants = []
    if composition_space == "body_canvas" and body_canvas is None:
        issues.append(
            _issue(
                "BODY-VARIANT-BODY-CANVAS",
                "body_canvas composition requires a positive content_area frame",
                "content_area",
            )
        )

    seen_variants: set[str] = set()
    for index, variant in enumerate(variants):
        path = f"variants[{index}]"
        if not isinstance(variant, dict):
            issues.append(_issue("BODY-VARIANT-TYPE", "variant must be an object", path))
            continue
        current_id = str(variant.get("variant_id") or "")
        if variant_id and current_id != variant_id:
            continue
        if not current_id:
            issues.append(_issue("BODY-VARIANT-ID", "variant_id is required", f"{path}.variant_id"))
            continue
        if current_id in seen_variants:
            issues.append(_issue("BODY-VARIANT-ID", f"duplicate variant_id {current_id!r}", f"{path}.variant_id"))
        seen_variants.add(current_id)

        source_field, raw_refs = component_ref_source(variant)
        refs = normalize_component_refs(variant, template_id)
        recipe = recipe_map.get(current_id, {})
        recipe_dependencies = recipe_component_asset_ids(recipe, template_id) if recipe else []
        for asset_id in recipe_dependencies:
            if asset_id not in assets:
                issues.append(
                    _issue(
                        "BODY-VARIANT-RECIPE-DEPENDENCY",
                        f"source-derived recipe references unknown component {asset_id!r}",
                        f"{path}.component_recipe",
                    )
                )
        if source_field == "components":
            warnings.append(
                _issue(
                    "BODY-VARIANT-LEGACY-COMPONENTS",
                    "legacy components[] was normalized; write canonical component_refs[] on the next migration",
                    f"{path}.components",
                )
            )
        if len(refs) != len(raw_refs):
            issues.append(
                _issue(
                    "BODY-VARIANT-COMPONENT-REF",
                    "every component reference must be a string or object with asset_id/component_id",
                    f"{path}.{source_field or 'component_refs'}",
                )
            )

        orders = [int(ref["order"]) for ref in refs]
        if orders and orders != list(range(1, len(refs) + 1)):
            issues.append(
                _issue(
                    "BODY-VARIANT-COMPONENT-ORDER",
                    "component_refs order values must be contiguous and start at 1",
                    f"{path}.component_refs",
                )
            )
        instance_ids = [str(ref["instance_id"]) for ref in refs]
        if len(instance_ids) != len(set(instance_ids)):
            issues.append(
                _issue(
                    "BODY-VARIANT-COMPONENT-INSTANCE",
                    "component_refs instance_id values must be unique within a variant",
                    f"{path}.component_refs",
                )
            )

        variant_slots = _variant_slot_ids(variant)
        region_ids, region_issues = _region_ids(variant)
        for region_issue in region_issues:
            region_issue["path"] = f"{path}.{region_issue['path']}"
            issues.append(region_issue)
        regions_required = bool(region_ids) or str(
            variant.get("composition_contract") or payload.get("composition_contract") or ""
        ) == "regions_required"
        if composition_space == "body_canvas" and body_canvas is not None:
            if str(variant.get("coordinate_space") or "") != "body_canvas":
                issues.append(
                    _issue(
                        "BODY-VARIANT-COORDINATE-SPACE",
                        "body_canvas templates require every variant to declare coordinate_space=body_canvas",
                        f"{path}.coordinate_space",
                    )
                )
            if not str(variant.get("composition_scene") or ""):
                issues.append(
                    _issue(
                        "BODY-VARIANT-COMPOSITION-SCENE",
                        "body_canvas variants require a named composition_scene",
                        f"{path}.composition_scene",
                    )
                )
            clear_region = _frame(variant.get("clear_region"))
            if clear_region is None or not _contains_frame(clear_region, body_canvas):
                issues.append(
                    _issue(
                        "BODY-VARIANT-CLEAR-REGION",
                        "clear_region must fully cover body_canvas before component composition",
                        f"{path}.clear_region",
                    )
                )
            raw_regions = variant.get("regions")
            region_rows = raw_regions if isinstance(raw_regions, list) else []
            for region_index, region in enumerate(region_rows):
                if not isinstance(region, dict):
                    continue
                frame = _frame(region.get("frame") if isinstance(region.get("frame"), dict) else region)
                if frame is not None and not _contains_frame(body_canvas, frame):
                    issues.append(
                        _issue(
                            "BODY-VARIANT-REGION-OUTSIDE-CANVAS",
                            "body_canvas region must remain inside the declared body canvas",
                            f"{path}.regions[{region_index}].frame",
                        )
                    )
        resolved_count = 0
        for ref_index, ref in enumerate(refs):
            ref_path = f"{path}.component_refs[{ref_index}]"
            asset_id = str(ref["asset_id"])
            asset = assets.get(asset_id)
            if not asset:
                target = issues if ref["required"] else warnings
                target.append(
                    _issue(
                        "BODY-VARIANT-COMPONENT-MISSING",
                        f"component asset {asset_id!r} is not registered or template-scoped",
                        f"{ref_path}.asset_id",
                    )
                )
                continue
            resolved_count += 1
            if asset_id in local_assets:
                asset_status = str(asset.get("asset_status") or "")
                if asset_status and asset_status not in {"ready", "renderable", "renderable_svg"}:
                    issues.append(
                        _issue(
                            "BODY-VARIANT-COMPONENT-STATUS",
                            f"required component {asset_id!r} is not renderable: {asset_status}",
                            f"{ref_path}.asset_id",
                        )
                    )
                asset_path = str(asset.get("asset_path") or "")
                if asset_path and not (template_dir / asset_path).is_file():
                    issues.append(
                        _issue(
                            "BODY-VARIANT-COMPONENT-ASSET",
                            f"component asset file does not exist: {asset_path}",
                            f"{ref_path}.asset_id",
                        )
                    )
            component_slots = _slot_ids(asset)
            required_component_slots = _required_slot_ids(asset)
            for component_slot, target_slot in ref["slot_bindings"].items():
                if component_slots and component_slot not in component_slots:
                    issues.append(
                        _issue(
                            "BODY-VARIANT-COMPONENT-SLOT",
                            f"component {asset_id!r} has no slot {component_slot!r}",
                            f"{ref_path}.slot_bindings.{component_slot}",
                        )
                    )
                if target_slot not in variant_slots:
                    issues.append(
                        _issue(
                            "BODY-VARIANT-TARGET-SLOT",
                            f"body variant {current_id!r} has no slot {target_slot!r}",
                            f"{ref_path}.slot_bindings.{component_slot}",
                        )
                    )
            if regions_required:
                region_id = str(ref.get("region") or "")
                if region_id:
                    if region_id not in region_ids:
                        issues.append(
                            _issue(
                                "BODY-VARIANT-COMPONENT-REGION",
                                f"component instance references unknown region {region_id!r}",
                                f"{ref_path}.region",
                            )
                        )
                elif not _valid_placement(ref.get("placement")):
                    issues.append(
                        _issue(
                            "BODY-VARIANT-COMPONENT-PLACEMENT",
                            "composable component refs must declare a valid region or placement",
                            ref_path,
                        )
                    )
                missing_component_bindings = sorted(
                    required_component_slots - set(ref["slot_bindings"])
                )
                if missing_component_bindings:
                    issues.append(
                        _issue(
                            "BODY-VARIANT-COMPONENT-BINDING",
                            "required component slots must be bound by the body variant: "
                            + ", ".join(missing_component_bindings),
                            f"{ref_path}.slot_bindings",
                        )
                    )
        reports.append(
            {
                "variant_id": current_id,
                "composition_mode": (
                    "ordered_component_refs"
                    if refs
                    else str(variant.get("composition_mode") or "open_content_area")
                ),
                "component_ref_count": len(refs),
                "resolved_component_count": resolved_count,
                "component_refs": refs,
                "component_recipe": recipe,
                "component_dependency_asset_ids": recipe_dependencies,
                "component_dependency_count": len(recipe_dependencies),
                "region_count": len(region_ids),
            }
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "template_id": template_id,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
        "variant_count": len(reports),
        "component_ref_count": sum(row["component_ref_count"] for row in reports),
        "component_dependency_count": sum(row["component_dependency_count"] for row in reports),
        "resolved_component_count": sum(row["resolved_component_count"] for row in reports),
        "variants": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", help="Template id or template directory.")
    parser.add_argument("--variant-id", help="Validate one body variant only.")
    parser.add_argument("--json", action="store_true", help="Print the complete report.")
    args = parser.parse_args(argv)
    try:
        report = validate_body_variant_contract(args.template, variant_id=args.variant_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "template_id": report["template_id"],
                    "variant_count": report["variant_count"],
                    "component_ref_count": report["component_ref_count"],
                    "issue_count": report["issue_count"],
                    "warning_count": report["warning_count"],
                },
                ensure_ascii=False,
            )
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
