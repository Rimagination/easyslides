#!/usr/bin/env python3
"""Own and validate per-template component-composition capability profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
PROFILE_FILENAME = "capability_profile.json"
REGISTRY_FILENAME = "capability_registry.json"
SCHEMA_VERSION = "easyslides.template_capability_profile.v1"
REGISTRY_SCHEMA_VERSION = "easyslides.template_capability_registry.v1"

COMPOSITION_MODES = {"shell_only", "body_variant_only", "template_bounded", "template_composable", "disabled", "non_template"}
LIFECYCLES = {"production", "legacy", "source_scoped", "non_template"}
KNOWN_GRANULARITIES = {"page_module", "body_variant", "template_component", "pptx_source_component", "component_package", "card_component", "chart_asset", "icon_family", "page_recipe"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _contracts(directory: Path) -> dict[str, bool]:
    return {
        "layouts": (directory / "layouts.json").is_file(),
        "body_variants": (directory / "body_variants.json").is_file(),
        "component_catalog": (directory / "component_catalog.json").is_file(),
        "component_pack": (directory / "component_pack.json").is_file(),
        "design_tokens": (directory / "design_tokens.json").is_file(),
    }


def derive_capability_profile(template_dir: str | Path) -> dict[str, Any]:
    """Derive a conservative baseline from files that actually exist."""
    directory = Path(template_dir).resolve()
    template_id = directory.name
    contracts = _contracts(directory)
    source_scoped = template_id == "assets" or "distilled" in template_id or "faithful_raster" in template_id
    if template_id == "assets":
        lifecycle, mode, enabled, allowed = "non_template", "non_template", False, []
    elif source_scoped:
        lifecycle, mode, enabled, allowed = "source_scoped", "disabled", False, []
    elif contracts["component_pack"] and contracts["component_catalog"] and contracts["body_variants"]:
        lifecycle, mode, enabled, allowed = "production", "template_composable", True, ["body_variant", "page_module", "template_component"]
    elif contracts["component_catalog"] and contracts["body_variants"]:
        lifecycle, mode, enabled, allowed = "production", "template_bounded", True, ["body_variant", "page_module", "template_component"]
    elif contracts["body_variants"]:
        lifecycle, mode, enabled, allowed = "legacy", "body_variant_only", True, ["body_variant", "page_module"]
    else:
        lifecycle, mode, enabled, allowed = "legacy", "shell_only", True, ["page_module"]
    return {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_id,
        "lifecycle": lifecycle,
        "generation_enabled": enabled,
        "composition": {
            "mode": mode,
            "allowed_granularities": allowed,
            "allow_global_component_fallback": False,
            "allowed_component_packs": [],
            "requires_declared_body_variant": mode in {"body_variant_only", "template_bounded", "template_composable"},
        },
        "contracts": contracts,
        "selection_policy": {
            "template_affinity": "required",
            "undeclared_assets": "reject",
            "manual_selection": "must_be_declared",
            "missing_profile": "block_named_template_component_selection",
        },
        "required_gates": ["template_capability_profile", "component_plan_contract", "visual_measure_gate"],
        "derived_from": "template_directory_contracts",
    }


def validate_capability_profile(template_dir: str | Path) -> dict[str, Any]:
    directory = Path(template_dir).resolve()
    profile_path = directory / PROFILE_FILENAME
    issues: list[dict[str, str]] = []
    profile: dict[str, Any] = {}
    if not profile_path.is_file():
        issues.append(_issue("TEMPLATE-CAPABILITY-MISSING", f"{PROFILE_FILENAME} is required for named templates", PROFILE_FILENAME))
    else:
        try:
            profile = _read_json(profile_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(_issue("TEMPLATE-CAPABILITY-JSON", f"invalid profile: {exc}", PROFILE_FILENAME))
    if profile:
        if profile.get("schema_version") != SCHEMA_VERSION:
            issues.append(_issue("TEMPLATE-CAPABILITY-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))
        if profile.get("template_id") != directory.name:
            issues.append(_issue("TEMPLATE-CAPABILITY-ID", "template_id must match the layout directory name", "template_id"))
        if profile.get("lifecycle") not in LIFECYCLES:
            issues.append(_issue("TEMPLATE-CAPABILITY-LIFECYCLE", "lifecycle is invalid", "lifecycle"))
        if not isinstance(profile.get("generation_enabled"), bool):
            issues.append(_issue("TEMPLATE-CAPABILITY-GENERATION", "generation_enabled must be boolean", "generation_enabled"))
        composition = profile.get("composition") if isinstance(profile.get("composition"), dict) else {}
        mode = composition.get("mode")
        if mode not in COMPOSITION_MODES:
            issues.append(_issue("TEMPLATE-CAPABILITY-MODE", "composition.mode is invalid", "composition.mode"))
        allowed = composition.get("allowed_granularities")
        if not isinstance(allowed, list) or not all(str(value) in KNOWN_GRANULARITIES for value in allowed):
            issues.append(_issue("TEMPLATE-CAPABILITY-GRANULARITY", "allowed_granularities must contain known granularities", "composition.allowed_granularities"))
        if composition.get("allow_global_component_fallback") is not False:
            issues.append(_issue("TEMPLATE-CAPABILITY-GLOBAL-FALLBACK", "global component fallback is disabled for current production templates", "composition.allow_global_component_fallback"))
        if not isinstance(composition.get("allowed_component_packs"), list):
            issues.append(_issue("TEMPLATE-CAPABILITY-PACKS", "allowed_component_packs must be a list", "composition.allowed_component_packs"))
        actual = _contracts(directory)
        declared_contracts = profile.get("contracts") if isinstance(profile.get("contracts"), dict) else {}
        for name, exists in actual.items():
            if declared_contracts.get(name) is not exists:
                issues.append(_issue("TEMPLATE-CAPABILITY-CONTRACT", f"contracts.{name} must reflect the filesystem", f"contracts.{name}"))
        if mode == "body_variant_only" and not actual["body_variants"]:
            issues.append(_issue("TEMPLATE-CAPABILITY-BODY-VARIANTS", "body_variant_only requires body_variants.json", "composition.mode"))
        if mode == "template_bounded" and not (actual["body_variants"] and actual["component_catalog"]):
            issues.append(_issue("TEMPLATE-CAPABILITY-CATALOG", "template_bounded requires body_variants.json and component_catalog.json", "composition.mode"))
        if mode == "template_composable" and not (actual["body_variants"] and actual["component_catalog"] and actual["component_pack"] and actual["design_tokens"]):
            issues.append(_issue("TEMPLATE-CAPABILITY-COMPOSABLE", "template_composable requires variants, catalog, pack, and design tokens", "composition.mode"))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "template_id": directory.name,
        "profile_path": str(profile_path),
        "issue_count": len(issues),
        "issues": issues,
        "profile": profile,
    }


def load_template_capability(template_id: str, *, layouts_root: str | Path = LAYOUTS_ROOT) -> dict[str, Any] | None:
    if not template_id:
        return None
    directory = Path(layouts_root).resolve() / template_id
    report = validate_capability_profile(directory)
    if report["status"] != "pass":
        return {"status": "fail", "template_id": template_id, "issues": report["issues"], "profile": report.get("profile", {})}
    return {"status": "pass", **report["profile"]}


def asset_allowed_for_template(asset: dict[str, Any], capability: dict[str, Any] | None) -> tuple[bool, str]:
    if capability is None:
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        if metadata.get("template_id"):
            return False, "untemplated decks may not borrow template-local assets"
        return True, "untemplated deck may use an unscoped global registry asset"
    if capability.get("status") == "fail":
        return False, "template capability profile is invalid or missing"
    if capability.get("generation_enabled") is not True:
        return False, "template is source-scoped or non-template and cannot receive automatic component composition"
    composition = capability.get("composition") if isinstance(capability.get("composition"), dict) else {}
    granularity = str(asset.get("granularity") or "")
    if granularity not in {str(value) for value in composition.get("allowed_granularities", [])}:
        return False, f"{granularity!r} is not allowed by this template profile"
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    asset_template = str(metadata.get("template_id") or "")
    template_id = str(capability.get("template_id") or "")
    if asset_template:
        if asset_template != template_id:
            return False, "asset belongs to another template"
        return True, "template-local asset is declared by the profile"
    if composition.get("allow_global_component_fallback") is True:
        pack = metadata.get("pack") if isinstance(metadata.get("pack"), dict) else {}
        pack_id = str(pack.get("pack_id") or "")
        if pack_id and pack_id in {str(value) for value in composition.get("allowed_component_packs", [])}:
            return True, "approved global component pack"
    return False, "unscoped global assets are not allowed by this template profile"


def build_capability_registry(*, layouts_root: str | Path = LAYOUTS_ROOT, write_profiles: bool = False) -> dict[str, Any]:
    root = Path(layouts_root).resolve()
    rows: list[dict[str, Any]] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        profile_path = directory / PROFILE_FILENAME
        if write_profiles:
            _write_json(profile_path, derive_capability_profile(directory))
        report = validate_capability_profile(directory)
        profile = report.get("profile") if isinstance(report.get("profile"), dict) else {}
        rows.append(
            {
                "template_id": directory.name,
                "status": report["status"],
                "lifecycle": profile.get("lifecycle", "unknown"),
                "generation_enabled": profile.get("generation_enabled", False),
                "composition_mode": (profile.get("composition") or {}).get("mode", "unknown"),
                "allowed_granularities": (profile.get("composition") or {}).get("allowed_granularities", []),
                "profile": str(profile_path),
                "issue_count": report["issue_count"],
            }
        )
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "template_count": len(rows),
        "templates": rows,
        "policy": "named-template component selection requires a valid local capability profile",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and synchronize EasySlides template capability profiles.")
    parser.add_argument("command", choices=("validate", "sync", "list"))
    parser.add_argument("--template", type=Path)
    parser.add_argument("--layouts-root", type=Path, default=LAYOUTS_ROOT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.template:
        report = validate_capability_profile(args.template)
    else:
        report = build_capability_registry(layouts_root=args.layouts_root, write_profiles=args.command == "sync")
        if args.command == "sync":
            target = args.out or (Path(args.layouts_root) / REGISTRY_FILENAME)
            _write_json(target, report)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Template capabilities: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
