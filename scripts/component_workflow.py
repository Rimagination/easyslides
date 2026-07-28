#!/usr/bin/env python3
"""Run the EasySlides component asset workflow for a deck plan."""

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
    from scripts.component_gallery import DEFAULT_OUTPUT as DEFAULT_GALLERY_OUTPUT
    from scripts.component_gallery import build_component_gallery
    from scripts.component_plan_builder import build_component_plan, build_report as build_plan_builder_report
    from scripts.component_plan_contract import validate_component_plan
    from scripts.component_pptx_renderer import build_component_pptx
    from scripts.component_registry import DEFAULT_OUTPUT as DEFAULT_REGISTRY
    from scripts.component_registry import load_component_registry
    from scripts.component_selection_review import build_component_selection_review, write_component_selection_review
    from scripts.renderer_governance import validate_renderer_governance
except ModuleNotFoundError:  # pragma: no cover
    from component_gallery import DEFAULT_OUTPUT as DEFAULT_GALLERY_OUTPUT
    from component_gallery import build_component_gallery
    from component_plan_builder import build_component_plan, build_report as build_plan_builder_report
    from component_plan_contract import validate_component_plan
    from component_pptx_renderer import build_component_pptx
    from component_registry import DEFAULT_OUTPUT as DEFAULT_REGISTRY
    from component_registry import load_component_registry
    from component_selection_review import build_component_selection_review, write_component_selection_review
    from renderer_governance import validate_renderer_governance


DEFAULT_OUTPUT = ROOT / "build" / "component_workflow"
SCHEMA_VERSION = "easyslides.component_workflow_report.v1"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_component_workflow(
    *,
    deck_plan_path: Path,
    output_dir: Path = DEFAULT_OUTPUT,
    registry_path: Path = DEFAULT_REGISTRY,
    limit: int = 1,
    preferred_granularity: str | None = None,
    build_gallery: bool = True,
    build_pptx_preview: bool = True,
) -> dict[str, Any]:
    """Build component workflow artifacts and return a consolidated report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    deck_plan = _read_json(deck_plan_path)
    registry = load_component_registry(registry_path)

    component_plan = build_component_plan(
        deck_plan,
        registry=registry,
        limit=limit,
        preferred_granularity=preferred_granularity,
    )
    component_plan_path = output_dir / "component_plan.json"
    _write_json(component_plan_path, component_plan)

    validation_report = validate_component_plan(
        component_plan,
        registry=registry,
        deck_plan_path=deck_plan_path,
    )
    component_plan_report = build_plan_builder_report(
        component_plan,
        output=component_plan_path,
        validation_report=validation_report,
    )
    _write_json(output_dir / "component_plan_report.json", component_plan_report)

    gallery_report = None
    gallery_dir = output_dir / "gallery"
    if build_gallery:
        gallery_report = build_component_gallery(output_dir=gallery_dir)

    review_gallery = None
    if isinstance(gallery_report, dict):
        review_gallery = json.loads(json.dumps(gallery_report))
        for package in review_gallery.get("packages", []):
            for story in package.get("stories", []) if isinstance(package, dict) else []:
                if isinstance(story, dict) and story.get("svg"):
                    story["svg"] = (Path("gallery") / str(story["svg"])).as_posix()
    selection_review = build_component_selection_review(
        component_plan,
        registry=registry,
        gallery_manifest=review_gallery,
    )
    selection_review_paths = write_component_selection_review(output_dir, selection_review)
    renderer_governance = validate_renderer_governance(registry)
    _write_json(output_dir / "renderer_governance_report.json", renderer_governance)

    pptx_report = None
    if build_pptx_preview:
        pptx_report = build_component_pptx(
            output_path=output_dir / "component_gallery.pptx",
            validate_text_layout=True,
        )
        _write_json(output_dir / "component_gallery_pptx_report.json", pptx_report)

    statuses = [
        component_plan_report["status"],
        gallery_report["status"] if isinstance(gallery_report, dict) else "skipped",
        pptx_report["status"] if isinstance(pptx_report, dict) else "skipped",
        selection_review["status"],
        renderer_governance["status"],
    ]
    blocking_statuses = [status for status in statuses if status != "skipped"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(status == "pass" for status in blocking_statuses) else "fail",
        "deck_plan": str(deck_plan_path),
        "output_dir": str(output_dir),
        "registry": str(registry_path),
        "component_plan": str(component_plan_path),
        "component_plan_status": component_plan_report["status"],
        "component_plan_report": component_plan_report,
        "gallery_status": gallery_report["status"] if isinstance(gallery_report, dict) else "skipped",
        "gallery": str(gallery_dir / "component_gallery.html") if isinstance(gallery_report, dict) else "",
        "gallery_report": gallery_report,
        "selection_review_status": selection_review["status"],
        "selection_review": selection_review_paths,
        "renderer_governance_status": renderer_governance["status"],
        "renderer_governance": renderer_governance,
        "pptx_status": pptx_report["status"] if isinstance(pptx_report, dict) else "skipped",
        "pptx": pptx_report.get("output") if isinstance(pptx_report, dict) else "",
        "pptx_report": pptx_report,
    }
    _write_json(output_dir / "component_workflow_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the EasySlides component asset workflow for a deck plan.")
    parser.add_argument("deck_plan", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--preferred-granularity")
    parser.add_argument("--skip-gallery", action="store_true")
    parser.add_argument("--skip-pptx", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_component_workflow(
            deck_plan_path=args.deck_plan,
            output_dir=args.out,
            registry_path=args.registry,
            limit=args.limit,
            preferred_granularity=args.preferred_granularity,
            build_gallery=not args.skip_gallery,
            build_pptx_preview=not args.skip_pptx,
        )
    except Exception as exc:
        print(f"component workflow failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Component workflow: {report['status']}")
        print(f"Component plan: {report['component_plan']}")
        if report["gallery"]:
            print(f"Gallery: {report['gallery']}")
        if report["pptx"]:
            print(f"PPTX: {report['pptx']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
