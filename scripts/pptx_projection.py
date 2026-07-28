#!/usr/bin/env python3
"""Build and execute source-template projection mappings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.pptx_projection_manifest.v1"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _manifest_slides(manifest: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    return {
        int(item.get("index")): item
        for item in (manifest or {}).get("slides", [])
        if isinstance(item, dict) and item.get("index")
    }


def build_projection_manifest(*, template_id: str, source_workspace: Path) -> dict[str, Any]:
    source_workspace = Path(source_workspace).resolve()
    graph = _read_json(source_workspace / "source_graph.json")
    layout = _read_json(source_workspace / "layout_spec.json")
    catalog = _read_json(source_workspace / "component_catalog.json")
    slots_contract = _read_json(source_workspace / "slot_contracts.json")
    manifest_path = source_workspace / "manifest.json"
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    source_slides = _manifest_slides(manifest)
    slots = [item for item in slots_contract.get("slots", []) if isinstance(item, dict)]
    slots_by_slide: dict[str, list[dict[str, Any]]] = {}
    for slot in slots:
        slots_by_slide.setdefault(str(slot.get("source_slide_id") or ""), []).append(slot)

    pages: list[dict[str, Any]] = []
    for slide in layout.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_id = str(slide.get("slide_id") or "")
        index = int(slide.get("index") or 0)
        source_item = source_slides.get(index, {})
        svg_name = str(source_item.get("flatSvgFile") or f"slide_{index:02d}.svg")
        svg_path = source_workspace / "svg-flat" / svg_name
        pages.append(
            {
                "projection_id": f"page_{slide_id}",
                "slide_id": slide_id,
                "index": index,
                "page_role": slide.get("page_role", "content"),
                "renderer_id": "source_template_projection",
                "targets": ["svg", "native_pptx_via_svg_to_pptx"],
                "source_svg": str(svg_path),
                "source_svg_exists": svg_path.exists(),
                "slots": [slot.get("slot_id") for slot in slots_by_slide.get(slide_id, [])],
                "status": "ready" if svg_path.exists() else "review_required",
                "geometry_contract": slide.get("spatial_contract", {}),
            }
        )

    pages_by_slide = {item["slide_id"]: item for item in pages}
    components: list[dict[str, Any]] = []
    for component in catalog.get("components", []):
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("component_id") or "")
        slide_ids = sorted(
            {
                str(instance.get("part_id"))
                for instance in component.get("instances", [])
                if isinstance(instance, dict) and str(instance.get("part_role")) == "slide" and instance.get("part_id")
            }
        )
        mapped_pages = [pages_by_slide[slide_id] for slide_id in slide_ids if slide_id in pages_by_slide]
        classification = str(component.get("classification") or "unknown")
        if classification == "fixed":
            status = "protected"
        elif classification in {"replaceable", "hybrid"} and mapped_pages:
            status = "ready"
        else:
            status = "review_required"
        is_projectable = status == "ready"
        components.append(
            {
                "projection_id": f"component_{component_id}",
                "component_id": component_id,
                "renderer_id": "source_template_projection" if is_projectable else None,
                "targets": ["svg", "native_pptx_via_svg_to_pptx"] if is_projectable else [],
                "classification": classification,
                "source_slide_ids": slide_ids,
                "slot_contract_ids": component.get("slot_contract_ids", []),
                "page_projection_ids": [page["projection_id"] for page in mapped_pages],
                "status": status,
                "promotion_rule": (
                    "fixed_chrome_is_protected_and_not_projected"
                    if status == "protected"
                    else "requires_visual_and_cross_material_qa"
                ),
            }
        )

    ready_pages = sum(item["status"] == "ready" for item in pages)
    ready_components = sum(item["status"] == "ready" for item in components)
    protected_components = sum(item["status"] == "protected" for item in components)
    review_components = sum(item["status"] == "review_required" for item in components)
    return {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_id,
        "source_workspace": str(source_workspace),
        "source_graph_schema": graph.get("schema_version"),
        "renderer_mappings": [
            {
                "renderer_id": "source_template_projection",
                "targets": ["svg"],
                "native_pptx_route": "scripts/svg_to_pptx.py",
                "editable_geometry": True,
                "hard_text_alignment": "text_center_y_matches_container_center_y",
            }
        ],
        "pages": pages,
        "components": components,
        "summary": {
            "page_count": len(pages),
            "ready_page_count": ready_pages,
            "component_count": len(components),
            "ready_component_count": ready_components,
            "protected_component_count": protected_components,
            "review_required_component_count": review_components,
            "review_required_count": len(pages) - ready_pages + review_components,
        },
        "qa": {
            "status": "pass" if ready_pages == len(pages) and (not components or ready_components > 0) else "review_required",
            "required_gates": ["source_template_contract", "template_geometry_qa", "validate_pptx_text_layout", "visual_measure_gate", "cross_material_smoke_test"],
        },
    }


def write_projection_manifest(source_workspace: Path, payload: dict[str, Any]) -> Path:
    path = Path(source_workspace) / "projection_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def project_slide(
    *,
    source_workspace: Path,
    slide_id: str,
    values: dict[str, Any],
    output_svg: Path,
) -> dict[str, Any]:
    workspace = Path(source_workspace).resolve()
    projection = _read_json(workspace / "projection_manifest.json")
    slots_contract = _read_json(workspace / "slot_contracts.json")
    page = next((item for item in projection.get("pages", []) if item.get("slide_id") == slide_id), None)
    if not page:
        raise ValueError(f"unknown slide_id: {slide_id}")
    slot_ids = set(page.get("slots") or [])
    all_slots = [slot for slot in slots_contract.get("slots", []) if isinstance(slot, dict)]
    source_slide_id = str(page.get("source_slide_id") or "")
    scoped_slots = [slot for slot in all_slots if str(slot.get("source_slide_id") or "") == source_slide_id]
    if not scoped_slots:
        scoped_slots = all_slots
    slots = [slot for slot in scoped_slots if slot.get("slot_id") in slot_ids]
    source_svg = Path(str(page.get("source_svg") or ""))
    if not source_svg.is_absolute():
        source_svg = workspace / source_svg
    try:
        from scripts.source_template_renderer import project_source_template_svg
    except ModuleNotFoundError:  # pragma: no cover - direct script execution
        from source_template_renderer import project_source_template_svg

    return project_source_template_svg(
        source_svg,
        output_svg,
        slots=slots,
        values=values,
        asset_root=workspace / "assets",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or execute EasySlides source-template projections.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build projection_manifest.json.")
    build.add_argument("source_workspace")
    build.add_argument("--template-id", required=True)
    project = subparsers.add_parser("project", help="Project declared slots into a source slide SVG.")
    project.add_argument("source_workspace")
    project.add_argument("--slide-id", required=True)
    project.add_argument("--values-json", required=True)
    project.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "build":
        path = write_projection_manifest(
            Path(args.source_workspace),
            build_projection_manifest(template_id=args.template_id, source_workspace=Path(args.source_workspace)),
        )
        print(path)
        return 0
    values = _read_json(Path(args.values_json))
    report = project_slide(
        source_workspace=Path(args.source_workspace),
        slide_id=args.slide_id,
        values=values,
        output_svg=Path(args.output),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
