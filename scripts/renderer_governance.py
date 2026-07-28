#!/usr/bin/env python3
"""Verify that component renderers are declared, available, and reviewable."""

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
    from scripts.component_renderer_registry import REGISTRY, SVG_TARGET, PPTX_TARGET, validate_renderer_id
    from scripts.component_registry import load_component_registry
except ModuleNotFoundError:  # pragma: no cover
    from component_renderer_registry import REGISTRY, SVG_TARGET, PPTX_TARGET, validate_renderer_id
    from component_registry import load_component_registry


SCHEMA_VERSION = "easyslides.renderer_governance.v1"


def _issue(code: str, message: str, asset_id: str) -> dict[str, str]:
    return {"code": code, "message": message, "asset_id": asset_id}


def _load_runtime_handlers() -> None:
    # Import-only registration is deliberate: component packs remain declarative.
    try:
        import scripts.component_gallery  # noqa: F401
        import scripts.component_pptx_renderer  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover
        import component_gallery  # type: ignore # noqa: F401
        import component_pptx_renderer  # type: ignore # noqa: F401


def validate_renderer_governance(registry: dict[str, Any] | None = None, *, require_handlers: bool = True) -> dict[str, Any]:
    registry = registry or load_component_registry()
    if require_handlers:
        _load_runtime_handlers()
    issues: list[dict[str, str]] = []
    checked: list[dict[str, Any]] = []
    for asset in registry.get("assets", []):
        if not isinstance(asset, dict) or asset.get("granularity") != "component_package":
            continue
        asset_id = str(asset.get("asset_id") or "")
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        renderer_id = str(metadata.get("renderer_id") or asset.get("renderer_id") or asset_id.rsplit("/", 1)[-1])
        requested = asset.get("render_targets") if isinstance(asset.get("render_targets"), list) else [SVG_TARGET, PPTX_TARGET]
        targets = [str(target) for target in requested if str(target) in {SVG_TARGET, PPTX_TARGET}]
        target_reports = []
        for target in targets:
            report = validate_renderer_id(renderer_id, target=target)
            handler_registered = (renderer_id, target) in REGISTRY._handlers  # Runtime capability, not pack-controlled state.
            lifecycle = "registered" if handler_registered else ("lazy_preview_registration" if target == PPTX_TARGET else "missing")
            target_reports.append({"target": target, "status": report["status"], "handler_registered": handler_registered, "handler_lifecycle": lifecycle})
            if report["status"] != "pass":
                issues.append(_issue("RENDERER-UNSUPPORTED", "; ".join(report["issues"]), asset_id))
            elif require_handlers and not handler_registered and target != PPTX_TARGET:
                issues.append(_issue("RENDERER-HANDLER-MISSING", f"renderer {renderer_id!r} has no runtime handler for {target!r}", asset_id))
        checked.append({"asset_id": asset_id, "renderer_id": renderer_id, "targets": target_reports})
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "checked_component_count": len(checked),
        "components": checked,
        "policy": {"packs": "declarative_only", "runtime_handlers": "repository_owned", "required_targets": [SVG_TARGET, PPTX_TARGET], "native_pptx_handlers": "may_register_lazily_when_component_pptx_renderer_builds_a_preview"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate EasySlides component renderer governance.")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--no-handlers", action="store_true")
    args = parser.parse_args(argv)
    registry = load_component_registry(args.registry) if args.registry else None
    report = validate_renderer_governance(registry, require_handlers=not args.no_handlers)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
