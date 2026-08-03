#!/usr/bin/env python3
"""Create, validate, and register reusable EasySlides template packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
REGISTRY_PATH = ROOT / "templates" / "template_registry.json"
POLICY_PATH = ROOT / "templates" / "template_policy.json"
PACKAGE_SCHEMA_VERSION = "easyslides.template_package.v1"
REGISTRY_SCHEMA_VERSION = "easyslides.template_registry.v2"
CAPABILITY_LEVELS = ("shell", "semantic", "composable", "production")
DEFAULT_OFFICIAL_TEMPLATE_IDS = frozenset(
    {
        "academic_general",
        "academic_scqa",
        "defense_leftnav",
        "defense_topnav",
        "literature_minimal",
        "nsfc_defense",
        "thu_speech",
    }
)

DEFAULT_SOURCE_OF_TRUTH = {
    "package": "template_package.json",
    "shells": "layouts.json",
    "body_variants": "body_variants.json",
    "components": "component_catalog.json",
    "qa": "qa_policy.json",
    "provenance": "source_page_roster.json",
}


def issue(code: str, message: str, path: str | None = None) -> dict[str, str]:
    row = {"code": code, "message": message}
    if path:
        row["path"] = path
    return row


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _official_template_ids(root: Path) -> frozenset[str]:
    """Load the project policy without allowing a broken policy to widen selection."""
    policy_path = root / "templates" / "template_policy.json"
    try:
        policy = _read_json(policy_path)
        values = policy.get("official_template_ids")
        if isinstance(values, list) and all(isinstance(value, str) and value for value in values):
            return frozenset(values)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return DEFAULT_OFFICIAL_TEMPLATE_IDS


def _safe_relative(value: str) -> bool:
    path = Path(value.replace("\\", "/"))
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _entrypoints(template_dir: Path) -> dict[str, str]:
    candidates = {
        "template": "template.json",
        "layouts": "layouts.json",
        "body_variants": "body_variants.json",
        "slots": "slot_contracts.json",
        "geometry": "geometry_contract.json",
        "components": "component_catalog.json",
        "assets": "assets/asset_manifest.json",
        "qa": "qa_policy.json",
        "provenance": "source_page_roster.json",
        "design_spec": "design_spec.md",
        "rules": "rules.md",
    }
    return {
        key: value
        for key, value in candidates.items()
        if (template_dir / value).is_file()
    }


def _infer_capability_level(template_dir: Path) -> str:
    variants_path = template_dir / "body_variants.json"
    has_variants = variants_path.is_file()
    has_component_refs = False
    if has_variants:
        try:
            variants = _read_json(variants_path).get("variants", [])
            has_component_refs = any(
                isinstance(variant, dict)
                and bool(variant.get("component_refs") or variant.get("components"))
                for variant in variants
            )
        except (OSError, ValueError, json.JSONDecodeError):
            has_component_refs = False
    if (template_dir / "qa_policy.json").is_file() and (template_dir / "component_catalog.json").is_file() and has_component_refs:
        return "production"
    if (template_dir / "component_catalog.json").is_file() and has_component_refs:
        return "composable"
    if has_variants:
        return "semantic"
    return "shell"


def _source_of_truth(template_dir: Path) -> dict[str, str]:
    return {
        key: value
        for key, value in DEFAULT_SOURCE_OF_TRUTH.items()
        if key == "package" or (template_dir / value).is_file()
    }


def build_package_manifest(
    template_dir: str | Path,
    *,
    version: str = "0.1.0",
    status: str = "candidate",
    examples: list[str] | None = None,
) -> dict[str, Any]:
    directory = Path(template_dir).resolve()
    template = _read_json(directory / "template.json")
    layouts = _read_json(directory / "layouts.json")
    template_id = str(template.get("template_id") or directory.name)
    canvas = layouts.get("canvas") if isinstance(layouts.get("canvas"), dict) else {}
    layout_rows = layouts.get("layouts") if isinstance(layouts.get("layouts"), list) else []
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": f"template/{template_id}",
        "template_id": template_id,
        "version": version,
        "status": status,
        "display_name": str(template.get("display_name") or template_id),
        "description": str(template.get("description") or template.get("style_system") or ""),
        "installability": "repo_relative_template_package",
        "entrypoints": _entrypoints(directory),
        "source_of_truth": _source_of_truth(directory),
        "derived_outputs": {
            "template_ir": "compiled/template_ir.json",
            "lock": "compiled/template.lock.json",
            "projections": "compiled/projections",
            "registry": "templates/template_registry.json",
        },
        "capability_level": _infer_capability_level(directory),
        "compatibility": {
            "canvas_format": str(canvas.get("format") or "ppt169"),
            "canvas": {"width": canvas.get("width"), "height": canvas.get("height")},
            "output_contract": str(template.get("output_contract") or "editable-native-pptx"),
            "layout_mode": str(template.get("recommended_template_route") or "semantic_named_slots"),
            "required_renderer": "svg_to_pptx",
        },
        "capabilities": [
            "named_slots",
            "editable_native_pptx",
            "component_asset_catalog",
            "geometry_contract",
            "text_capacity_contract",
        ],
        "scenarios": list(template.get("scenarios") or []),
        "examples": list(examples or []),
        "layout_count": len(layout_rows),
        "source_template_id": str(template.get("source_template_id") or ""),
        "production_eligible": False,
    }


def validate_package(
    template_dir: str | Path,
    *,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    directory = Path(template_dir).resolve()
    issues: list[dict[str, str]] = []
    package_path = directory / "template_package.json"
    manifest_supplied = manifest is not None
    if manifest is None:
        try:
            manifest = _read_json(package_path)
        except FileNotFoundError:
            return {"schema_version": "easyslides.template_package_report.v1", "status": "fail", "issues": [issue("PACKAGE-MISSING", "template_package.json is required", str(package_path))]}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {"schema_version": "easyslides.template_package_report.v1", "status": "fail", "issues": [issue("PACKAGE-JSON", f"invalid package manifest: {exc}", str(package_path))]}

    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        issues.append(issue("PACKAGE-SCHEMA", f"schema_version must be {PACKAGE_SCHEMA_VERSION}", "schema_version"))
    template_id = str(manifest.get("template_id") or "")
    if not template_id:
        issues.append(issue("PACKAGE-TEMPLATE-ID", "template_id is required", "template_id"))
    if not str(manifest.get("version") or "").strip():
        issues.append(issue("PACKAGE-VERSION", "version is required", "version"))
    entrypoints = manifest.get("entrypoints")
    if not isinstance(entrypoints, dict):
        issues.append(issue("PACKAGE-ENTRYPOINTS", "entrypoints must be an object", "entrypoints"))
        entrypoints = {}
    for key, relative in entrypoints.items():
        if not isinstance(relative, str) or not _safe_relative(relative):
            issues.append(issue("PACKAGE-PATH", f"entrypoint {key} must be a safe relative path", f"entrypoints.{key}"))
            continue
        if not (directory / relative).is_file():
            issues.append(issue("PACKAGE-FILE", f"entrypoint {key} is missing: {relative}", f"entrypoints.{key}"))

    source_of_truth = manifest.get("source_of_truth")
    if not isinstance(source_of_truth, dict):
        issues.append(issue("PACKAGE-SOURCES", "source_of_truth must be an object", "source_of_truth"))
        source_of_truth = {}
    capability_level = str(manifest.get("capability_level") or _infer_capability_level(directory))
    if capability_level not in CAPABILITY_LEVELS:
        issues.append(
            issue(
                "PACKAGE-CAPABILITY",
                f"capability_level must be one of {', '.join(CAPABILITY_LEVELS)}",
                "capability_level",
            )
        )
    required_sources = {"package", "shells"}
    if capability_level in {"semantic", "composable", "production"}:
        required_sources.add("body_variants")
    if capability_level in {"composable", "production"}:
        required_sources.add("components")
    if capability_level == "production":
        required_sources.add("qa")
    for key in sorted(required_sources):
        relative = source_of_truth.get(key)
        if not isinstance(relative, str) or not _safe_relative(relative):
            issues.append(issue("PACKAGE-SOURCE", f"canonical source {key} is required", f"source_of_truth.{key}"))
            continue
        if key == "package" and manifest_supplied:
            continue
        if not (directory / relative).is_file():
            issues.append(issue("PACKAGE-SOURCE", f"canonical source {key} is missing: {relative}", f"source_of_truth.{key}"))

    try:
        template = _read_json(directory / "template.json")
        layouts = _read_json(directory / "layouts.json")
        if template_id and str(template.get("template_id") or "") != template_id:
            issues.append(issue("PACKAGE-ID-MISMATCH", "package template_id does not match template.json", "template_id"))
        canvas = layouts.get("canvas") if isinstance(layouts.get("canvas"), dict) else {}
        declared_canvas = manifest.get("compatibility", {}).get("canvas", {}) if isinstance(manifest.get("compatibility"), dict) else {}
        for key in ("width", "height"):
            if declared_canvas.get(key) is not None and canvas.get(key) is not None and declared_canvas.get(key) != canvas.get(key):
                issues.append(issue("PACKAGE-CANVAS", f"compatibility canvas {key} does not match layouts.json", f"compatibility.canvas.{key}"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(issue("PACKAGE-CORE", f"cannot read core template metadata: {exc}", "template.json"))

    return {
        "schema_version": "easyslides.template_package_report.v1",
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "template_id": template_id,
        "package_path": str(package_path),
    }


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": REGISTRY_SCHEMA_VERSION, "packages": [], "templates": []}
    payload = _read_json(path)
    if payload.get("schema_version") not in {REGISTRY_SCHEMA_VERSION, "easyslides.template_registry.v1"}:
        raise ValueError(f"{path} has unsupported schema")
    payload["schema_version"] = REGISTRY_SCHEMA_VERSION
    if not isinstance(payload.get("packages"), list):
        payload["packages"] = []
    if not isinstance(payload.get("templates"), list):
        payload["templates"] = list(payload["packages"])
    return payload


def _registry_row(
    directory: Path,
    root: Path,
    *,
    manifest: dict[str, Any] | None,
    legacy_index: dict[str, Any],
) -> dict[str, Any]:
    template_id = directory.name
    layouts = _read_json(directory / "layouts.json")
    canvas = layouts.get("canvas") if isinstance(layouts.get("canvas"), dict) else {}
    layout_rows = layouts.get("shells") or layouts.get("layouts") or layouts.get("pages") or []
    legacy_meta = legacy_index.get(template_id) if isinstance(legacy_index.get(template_id), dict) else {}
    if manifest:
        compatibility = manifest.get("compatibility") if isinstance(manifest.get("compatibility"), dict) else {}
        return {
            "package_id": str(manifest.get("package_id") or f"template/{template_id}"),
            "template_id": template_id,
            "version": str(manifest.get("version") or ""),
            "status": str(manifest.get("status") or "candidate"),
            "display_name": str(manifest.get("display_name") or template_id),
            "description": str(manifest.get("description") or legacy_meta.get("summary") or ""),
            "path": directory.relative_to(root).as_posix(),
            "canvas_format": str(compatibility.get("canvas_format") or canvas.get("format") or "ppt169"),
            "layout_count": len(layout_rows) if isinstance(layout_rows, list) else 0,
            "capability_level": str(manifest.get("capability_level") or _infer_capability_level(directory)),
            "production_eligible": bool(manifest.get("production_eligible", False)),
            "managed_package": True,
            "keywords": list(legacy_meta.get("keywords") or []),
            "compiled_ir": "compiled/template_ir.json",
        }
    return {
        "package_id": "",
        "template_id": template_id,
        "version": "",
        "status": "legacy",
        "display_name": template_id,
        "description": str(legacy_meta.get("summary") or ""),
        "path": directory.relative_to(root).as_posix(),
        "canvas_format": str(canvas.get("format") or "ppt169"),
        "layout_count": len(layout_rows) if isinstance(layout_rows, list) else 0,
        "capability_level": _infer_capability_level(directory),
        "production_eligible": False,
        "managed_package": False,
        "keywords": list(legacy_meta.get("keywords") or []),
        "compiled_ir": "",
    }


def rebuild_template_registry(
    *,
    repo_root: str | Path = ROOT,
    write: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    layouts_root = root / "templates" / "layouts"
    registry_path = root / "templates" / "template_registry.json"
    legacy_index_path = layouts_root / "layouts_index.json"
    legacy_index = _read_json(legacy_index_path) if legacy_index_path.is_file() else {}
    rows: list[dict[str, Any]] = []
    packages: list[dict[str, Any]] = []
    official_template_ids = _official_template_ids(root)
    skipped = {"assets", "__pycache__"}
    for directory in sorted(path for path in layouts_root.iterdir() if path.is_dir() and path.name not in skipped):
        if not (directory / "layouts.json").is_file():
            continue
        manifest = _read_json(directory / "template_package.json") if (directory / "template_package.json").is_file() else None
        row = _registry_row(directory, root, manifest=manifest, legacy_index=legacy_index)
        row["official"] = directory.name in official_template_ids
        rows.append(row)
        if manifest:
            packages.append(row)
    registry = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "generation_policy": "discover_template_packages_and_legacy_layouts",
        "templates": rows,
        "packages": packages,
        "template_count": len(rows),
        "package_count": len(packages),
    }
    active_rows = [row for row in rows if row.get("official") is True]
    generated_index = {
        row["template_id"]: {
            "summary": row["description"],
            "keywords": row["keywords"],
            "capability_level": row["capability_level"],
            "status": row["status"],
        }
        for row in active_rows
    }
    if write:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        legacy_index_path.write_text(json.dumps(generated_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "pass",
        "registry_path": str(registry_path),
        "template_count": len(rows),
        "package_count": len(packages),
        "templates": rows,
        "packages": packages,
    }


def register_template_package(
    template_dir: str | Path,
    *,
    repo_root: str | Path = ROOT,
    version: str = "0.1.0",
    status: str = "candidate",
    examples: list[str] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    directory = Path(template_dir).resolve()
    root = Path(repo_root).resolve()
    manifest = build_package_manifest(directory, version=version, status=status, examples=examples)
    report = validate_package(directory, manifest=manifest)
    if report["status"] != "pass":
        return {"status": "fail", "manifest": manifest, "validation": report}
    package_path = directory / "template_package.json"
    registry_path = root / "templates" / "template_registry.json"
    if write:
        package_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    registry = rebuild_template_registry(repo_root=root, write=write)
    return {"status": "pass", "manifest": manifest, "validation": report, "registry": registry, "package_path": str(package_path), "registry_path": str(registry_path)}


def list_template_packages(*, repo_root: str | Path = ROOT) -> dict[str, Any]:
    path = Path(repo_root).resolve() / "templates" / "template_registry.json"
    registry = _load_registry(path)
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "pass",
        "registry_path": str(path),
        "template_count": len(registry.get("templates", [])),
        "package_count": len(registry.get("packages", [])),
        "templates": registry.get("templates", []),
        "packages": registry.get("packages", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage EasySlides reusable template packages.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init", help="Create and register a template_package.json.")
    init.add_argument("template_dir", type=Path)
    init.add_argument("--repo-root", type=Path, default=ROOT)
    init.add_argument("--version", default="0.1.0")
    init.add_argument("--status", default="candidate")
    init.add_argument("--example", action="append", default=[])
    init.add_argument("--json", action="store_true")
    validate = subparsers.add_parser("validate", help="Validate a template package.")
    validate.add_argument("template_dir", type=Path)
    validate.add_argument("--json", action="store_true")
    list_parser = subparsers.add_parser("list", help="List registered template packages.")
    list_parser.add_argument("--repo-root", type=Path, default=ROOT)
    list_parser.add_argument("--json", action="store_true")
    rebuild = subparsers.add_parser("rebuild", help="Discover templates and rebuild the unified registry.")
    rebuild.add_argument("--repo-root", type=Path, default=ROOT)
    rebuild.add_argument("--check", action="store_true")
    rebuild.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        result = register_template_package(args.template_dir, repo_root=args.repo_root, version=args.version, status=args.status, examples=args.example)
    elif args.command == "validate":
        result = validate_package(args.template_dir)
    elif args.command == "list":
        result = list_template_packages(repo_root=args.repo_root)
    else:
        result = rebuild_template_registry(repo_root=args.repo_root, write=not args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Template package: {result['status']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
