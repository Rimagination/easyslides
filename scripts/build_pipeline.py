#!/usr/bin/env python3
"""Run the reviewable EasySlides visual-plan, acquisition, and render pipeline.

The pipeline is deliberately a thin orchestrator over the existing contracts:
it never invents source evidence, it records pending image work instead of
silently dropping it, and it leaves the original deck plan untouched unless a
caller explicitly copies the generated build plan back.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

try:
    from scripts.image_acquisition import prepare_acquisition, validate_image_manifest
    from scripts.slide_compiler import SlideCompileError, compile_deck, render_slide_ir_to_pptx, render_slide_ir_to_svg
    from scripts.template_compiler import TemplateCompileError
    from scripts.theme_tokens import parse_theme_overrides
    from scripts.visual_asset_planner import VisualAssetPlanError, plan_visual_assets
    from scripts.clarification_gate import require_production_decisions
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from image_acquisition import prepare_acquisition, validate_image_manifest
    from slide_compiler import SlideCompileError, compile_deck, render_slide_ir_to_pptx, render_slide_ir_to_svg
    from template_compiler import TemplateCompileError
    from theme_tokens import parse_theme_overrides
    from visual_asset_planner import VisualAssetPlanError, plan_visual_assets
    from clarification_gate import require_production_decisions


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "easyslides.build_report.v1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"deck plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid deck plan JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("deck plan must be a JSON object")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _template_dir(template: str | None, deck_plan: Mapping[str, Any]) -> Path | None:
    value = template or deck_plan.get("template_id") or deck_plan.get("template")
    if isinstance(value, Mapping):
        value = value.get("template_id") or value.get("id")
    if not value:
        return None
    path = Path(str(value))
    if path.is_dir():
        return path.resolve()
    candidate = ROOT / "templates" / "layouts" / str(value)
    return candidate.resolve() if candidate.is_dir() else path.resolve()


def _palette_id(args: argparse.Namespace, deck_plan: Mapping[str, Any]) -> str | None:
    if args.palette:
        return str(args.palette)
    for key in ("palette_id", "theme_palette"):
        value = deck_plan.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _bind_visual_plan(
    deck_plan: Mapping[str, Any],
    visual_plan: Mapping[str, Any],
    *,
    visual_plan_path: Path,
    manifest_path: Path | None,
) -> dict[str, Any]:
    """Bind generated-plan metadata to a build-local copy of the deck plan."""
    updated = deepcopy(dict(deck_plan))
    updated["visual_asset_plan"] = str(visual_plan_path)
    if manifest_path is not None:
        updated["image_manifest"] = str(manifest_path)
    by_page: dict[str, list[dict[str, Any]]] = {}
    items = [item for item in visual_plan.get("items", []) if isinstance(item, Mapping)]
    for decision in visual_plan.get("decisions", []):
        if not isinstance(decision, Mapping):
            continue
        page = str(decision.get("page") or "")
        if not page:
            continue
        matches = [
            dict(item)
            for item in items
            if str(item.get("page") or "") == page
            or str(item.get("id") or "").lower().startswith(page.lower() + "_")
        ]
        if matches:
            by_page[page] = matches
    for index, raw in enumerate(updated.get("slides", []), start=1):
        if not isinstance(raw, dict):
            continue
        page = str(raw.get("page") or f"P{index:02d}")
        matches = by_page.get(page) or []
        if matches:
            existing = raw.get("image_bindings") if isinstance(raw.get("image_bindings"), list) else []
            existing_ids = {
                str(binding.get("resource_id") or binding.get("id") or "")
                for binding in existing
                if isinstance(binding, Mapping)
            }
            generated_bindings = [
                {
                    "resource_id": str(item.get("id") or ""),
                    **({"placement": dict(item["placement"])} if isinstance(item.get("placement"), Mapping) else {}),
                }
                for item in matches
                if str(item.get("id") or "") not in existing_ids
            ]
            if existing or generated_bindings:
                raw["image_bindings"] = existing + generated_bindings
            background = next((item for item in matches if item.get("asset_role") == "background"), None)
            raw["image_resource_id"] = str((background or matches[0]).get("id") or "")
    return updated


def _working_deck_plan(
    source_plan: Mapping[str, Any],
    theme_override_values: list[str] | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Create the build-local plan with validated user theme overrides."""
    updated = deepcopy(dict(source_plan))
    overrides = parse_theme_overrides(theme_override_values)
    if overrides:
        base = updated.get("theme_tokens")
        if not isinstance(base, Mapping):
            base = {}
        # The planner and compiler each resolve template defaults.  Storing
        # only the explicit overrides here keeps the source deck plan portable.
        updated["theme_tokens"] = dict(base)
        updated["theme_tokens"].update(overrides)
        updated["theme_overrides"] = overrides
    return updated, overrides


def _source_manifest_path(source_path: Path, source_plan: Mapping[str, Any]) -> Path | None:
    value = source_plan.get("image_manifest")
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (source_path.parent / path).resolve()


def _load_source_manifest(
    source_path: Path,
    source_plan: Mapping[str, Any],
) -> tuple[Path | None, dict[str, Any] | None]:
    source_manifest_path = _source_manifest_path(source_path, source_plan)
    if source_manifest_path is None or not source_manifest_path.is_file():
        return source_manifest_path, None
    try:
        source_manifest = validate_image_manifest(
            json.loads(source_manifest_path.read_text(encoding="utf-8-sig")),
            source=str(source_manifest_path),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"existing image_manifest is invalid: {exc}") from exc
    return source_manifest_path, source_manifest


def _copy_source_manifest_assets(
    source_manifest_path: Path | None,
    source_manifest: Mapping[str, Any] | None,
    output_dir: Path,
) -> int:
    """Stage existing source assets beside the build-local manifest.

    The acquisition reconciler is allowed to update the manifest it receives.
    Copying source-bound files into the build directory therefore both preserves
    the original project and lets the renderer resolve previously acquired
    images instead of silently falling back to the template shell.
    """
    if source_manifest_path is None or source_manifest is None:
        return 0
    copied = 0
    for item in source_manifest.get("items", []):
        if not isinstance(item, Mapping):
            continue
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        source_asset = (source_manifest_path.parent / filename).resolve()
        target_asset = (output_dir / filename).resolve()
        if not source_asset.is_file() or source_asset == target_asset:
            continue
        target_asset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_asset, target_asset)
        copied += 1
    return copied


def _merge_source_manifest(
    source_path: Path,
    source_plan: Mapping[str, Any],
    visual_report: dict[str, Any],
) -> dict[str, Any]:
    """Keep explicit/source-bound images while appending newly planned assets."""
    generated = deepcopy(dict(visual_report["image_manifest"]))
    source_manifest_path, source_manifest = _load_source_manifest(source_path, source_plan)
    if source_manifest_path is None or source_manifest is None:
        return generated
    planned_ids = {
        str(item.get("id") or "")
        for item in generated.get("items", [])
        if isinstance(item, Mapping) and str(item.get("id") or "") != "no_visual_assets"
    }
    source_items = [
        dict(item)
        for item in source_manifest.get("items", [])
        if isinstance(item, Mapping)
        and str(item.get("id") or "") != "no_visual_assets"
        and str(item.get("id") or "") not in planned_ids
    ]
    generated_items = [
        item
        for item in generated.get("items", [])
        if not (str(item.get("id") or "") == "no_visual_assets" and source_items)
    ]
    generated["items"] = source_items + generated_items
    if isinstance(generated.get("deck_palette"), Mapping):
        source_manifest["deck_palette"] = generated["deck_palette"]
    generated["acquisition"] = generated.get("acquisition") or source_manifest.get("acquisition") or {"path": "auto"}
    generated.pop("planned_count", None)
    return validate_image_manifest(generated, source="merged visual asset manifest")


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    source_path = Path(args.deck_plan).resolve()
    source_plan = _read_json(source_path)
    require_production_decisions(source_plan.get("decisions", source_plan), expected_scheme="direct_editable")
    build_source_plan, theme_overrides = _working_deck_plan(source_plan, args.theme_token)
    output_dir = Path(args.out_dir).resolve() if args.out_dir else source_path.parent / "build"
    output_dir.mkdir(parents=True, exist_ok=True)
    visual_dir = Path(args.visual_out).resolve() if args.visual_out else output_dir / "visual_assets"
    visual_dir.mkdir(parents=True, exist_ok=True)
    template_dir = _template_dir(args.template, build_source_plan)
    palette_id = _palette_id(args, build_source_plan)

    visual_report: dict[str, Any] = {
        "status": "skipped",
        "reason": "--no-visual-plan",
        "planned_count": 0,
    }
    build_plan = deepcopy(build_source_plan)
    manifest_path: Path | None = None
    source_assets_copied = 0
    if not args.no_visual_plan:
        visual_report = plan_visual_assets(
            build_source_plan,
            template_dir=template_dir,
            policy=args.visual_policy,
            imagegen_available=args.imagegen,
            palette_id=palette_id,
        )
        visual_report["image_manifest"] = _merge_source_manifest(source_path, build_source_plan, visual_report)
        visual_plan_path = visual_dir / "visual_asset_plan.json"
        source_manifest_ref = _source_manifest_path(source_path, build_source_plan)
        manifest_path = visual_dir / "image_prompts.json" if visual_report.get("planned_count", 0) or source_manifest_ref is not None else None
        _write_json(visual_plan_path, visual_report)
        _write_json(visual_dir / "image_prompts.json", visual_report["image_manifest"])
        build_plan = _bind_visual_plan(
            build_source_plan,
            visual_report,
            visual_plan_path=visual_plan_path,
            manifest_path=manifest_path,
        )
    else:
        reference = build_plan.get("image_manifest")
        if reference:
            source_manifest_path, source_manifest = _load_source_manifest(source_path, build_source_plan)
            if source_manifest_path is not None and source_manifest is not None:
                manifest_path = visual_dir / "image_prompts.json"
                _write_json(manifest_path, source_manifest)
            else:
                manifest_path = source_manifest_path
            build_plan["image_manifest"] = str(manifest_path)

    source_manifest_path, source_manifest = _load_source_manifest(source_path, build_source_plan)
    source_assets_copied = _copy_source_manifest_assets(source_manifest_path, source_manifest, visual_dir)

    build_plan_path = output_dir / "deck_plan.build.json"
    _write_json(build_plan_path, build_plan)

    acquisition_report: dict[str, Any] = {"status": "skipped", "reason": "no image manifest"}
    if manifest_path is not None and manifest_path.is_file():
        if args.imagegen is False:
            host_native_available = False
        elif args.host_native:
            host_native_available = True
        else:
            host_native_available = None
        acquisition_report = prepare_acquisition(
            manifest_path,
            explicit_path=args.acquisition_path,
            host_native_available=host_native_available,
            output_dir=visual_dir,
            request_path=visual_dir / "image_acquisition_request.json",
            execute_api=bool(args.execute_api),
        )

    compile_report = compile_deck(
        build_plan_path,
        template=args.template,
        component_plan_path=args.component_plan,
        palette_id=palette_id,
        write=True,
        output_path=output_dir / "slide_ir.json",
    )
    svg_report: dict[str, Any] = {"status": "skipped", "reason": "--no-svg"}
    svg_dir = Path(args.svg_out).resolve() if args.svg_out else output_dir / "svg"
    if not args.no_svg:
        svg_report = render_slide_ir_to_svg(compile_report["slide_ir"], svg_dir)

    pptx_report: dict[str, Any] = {"status": "skipped", "reason": "--pptx-out not supplied"}
    if args.pptx_out:
        pptx_report = render_slide_ir_to_pptx(
            compile_report["slide_ir"],
            Path(args.pptx_out).resolve(),
            svg_output_dir=svg_dir,
        )

    acquisition_status = str(acquisition_report.get("status") or "pass")
    compile_status = str(compile_report.get("status") or "fail")
    render_statuses = [status for status in (svg_report.get("status"), pptx_report.get("status")) if status not in {None, "skipped"}]
    status = "pass" if compile_status == "pass" and all(value == "pass" for value in render_statuses) and acquisition_status in {"pass", "skipped"} else "fail"
    pending_items = [
        row
        for row in acquisition_report.get("reconciliation", {}).get("items", [])
        if isinstance(row, Mapping)
        and str(row.get("id") or "") != "no_visual_assets"
        and str(row.get("status") or "") in {"Pending", "Needs-Manual", "Failed"}
    ]
    if acquisition_status == "pass" and pending_items and acquisition_report.get("resolution", {}).get("path") in {"manual", "host-native"}:
        asset_readiness = "pending_or_manual"
    else:
        asset_readiness = "ready" if not visual_report.get("planned_count") else "generated_or_reconciled"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_deck_plan": str(source_path),
        "build_dir": str(output_dir),
        "build_plan": str(build_plan_path),
        "template_id": compile_report.get("template_id"),
        "palette_id": palette_id or compile_report.get("slide_ir", {}).get("theme", {}).get("palette_id", ""),
        "theme_overrides": theme_overrides,
        "asset_readiness": asset_readiness,
        "source_assets_copied": source_assets_copied,
        "visual_plan": {
            "status": visual_report.get("status"),
            "planned_count": visual_report.get("planned_count", 0),
            "path": str(visual_dir / "visual_asset_plan.json") if visual_report.get("status") == "pass" else "",
        },
        "acquisition": {
            "status": acquisition_report.get("status"),
            "path": acquisition_report.get("resolution", {}).get("path", ""),
            "request": acquisition_report.get("request", ""),
            "capability": acquisition_report.get("capability", {}),
            "fallback": acquisition_report.get("fallback", {"mode": "template_shell"}),
        },
        "compile": {
            "status": compile_report.get("status"),
            "slide_count": compile_report.get("slide_count", 0),
            "slide_ir": str(output_dir / "slide_ir.json"),
        },
        "svg_render": svg_report,
        "pptx_render": pptx_report,
    }
    _write_json(output_dir / "build_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_plan")
    parser.add_argument("--template")
    parser.add_argument("--palette")
    parser.add_argument("--component-plan")
    parser.add_argument("--out-dir")
    parser.add_argument("--visual-out")
    parser.add_argument("--svg-out")
    parser.add_argument("--pptx-out")
    parser.add_argument("--visual-policy", choices=("source_only", "auto_decorative", "ai_rich"), default="auto_decorative")
    imagegen = parser.add_mutually_exclusive_group()
    imagegen.add_argument("--imagegen", dest="imagegen", action="store_true", help="Declare that a host/API image generator is available.")
    imagegen.add_argument("--no-imagegen", dest="imagegen", action="store_false", help="Disable automatic image capability detection for this run.")
    parser.set_defaults(imagegen=None)
    parser.add_argument("--host-native", action="store_true", help="Prefer the host-native image generation handoff when configured.")
    parser.add_argument("--acquisition-path", choices=("auto", "api", "host-native", "manual"), default=None)
    parser.add_argument("--theme-token", action="append", default=[], metavar="ROLE=#RRGGBB", help="Override a semantic theme role; repeat for multiple roles.")
    parser.add_argument("--execute-api", action="store_true")
    parser.add_argument("--no-visual-plan", action="store_true")
    parser.add_argument("--no-svg", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_build(args)
    except (OSError, ValueError, KeyError, SlideCompileError, TemplateCompileError, VisualAssetPlanError) as exc:
        report = {"schema_version": SCHEMA_VERSION, "status": "fail", "issues": [{"code": "BUILD", "message": str(exc)}]}
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"EasySlides build: {report['status']} ({report.get('build_dir', '')})")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
