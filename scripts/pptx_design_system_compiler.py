#!/usr/bin/env python3
"""Compile Phase 2 PPTX contracts into a declarative design-system pack.

The output is intentionally source-template scoped. It is discoverable by the
global EasySlides component registry, but it is not falsely presented as an
executable ``component_package`` until a reviewed renderer mapping exists.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.pptx_design_system_pack.v1"
FRAGMENT_SCHEMA_VERSION = "easyslides.component_registry_fragment.v1"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _slug(value: Any, fallback: str = "pack") -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return text or fallback


def _source_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _page_role_map(layout_spec: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("slide_id")): str(item.get("page_role") or "content")
        for item in layout_spec.get("slides") or []
        if isinstance(item, dict) and item.get("slide_id")
    }


def _component_selection(
    component: dict[str, Any],
    *,
    page_roles_by_slide: dict[str, str],
) -> dict[str, Any]:
    roles: set[str] = set()
    for instance in component.get("instances") or []:
        if not isinstance(instance, dict):
            continue
        part_id = str(instance.get("part_id") or "")
        if part_id in page_roles_by_slide:
            roles.add(page_roles_by_slide[part_id])
    kind = str(component.get("kind") or "object")
    selection: dict[str, Any] = {
        "content_shapes": [kind],
        "page_roles": sorted(roles),
        "item_count_min": 1,
        "item_count_max": 1,
        "density": "medium",
        "best_for": f"Source-template {kind} component from the distilled {component.get('scope', 'template')} design system.",
        "avoid_when": "The requested page needs geometry or chrome changes outside declared slots.",
    }
    return selection


def _fragment_asset(
    component: dict[str, Any],
    *,
    template_id: str,
    source_workspace: Path,
    page_roles_by_slide: dict[str, str],
    slots_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    component_id = str(component.get("component_id") or "component")
    slot_ids = [str(value) for value in component.get("slot_contract_ids") or []]
    slots = [slots_by_id[slot_id] for slot_id in slot_ids if slot_id in slots_by_id]
    return {
        "asset_id": f"pptx_source/{template_id}/{component_id}",
        "granularity": "pptx_source_component",
        "render_backend": "source_template_projection",
        "source_path": "component_catalog.json",
        "selection": _component_selection(component, page_roles_by_slide=page_roles_by_slide),
        "slots": slots,
        "metadata": {
            "template_id": template_id,
            "source_workspace": str(source_workspace),
            "source_component_id": component_id,
            "classification": component.get("classification"),
            "classification_basis": component.get("classification_basis", []),
            "source_instances": component.get("instances", []),
            "style_contract": component.get("style_contract", {}),
            "promotion_status": "source_template_only",
            "renderer_mapping_required": True,
            "renderer_id": "source_template_projection",
        },
        "allowed_edits": ["replace_declared_slots", "select_declared_projection_mode"],
        "forbidden_edits": ["change_fixed_chrome", "invent_unregistered_layout", "bypass_review_queue"],
        "required_gates": ["source_template_contract", "text_capacity", "visual_measure_gate", "cross_material_smoke_test"],
    }


def compile_design_system_pack(
    *,
    template_id: str,
    source_workspace: Path,
    repository_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Compile Phase 2 JSON files without writing them."""
    source_workspace = Path(source_workspace)
    repository_root = Path(repository_root or source_workspace).resolve()
    identity = _read_json(source_workspace / "identity_spec.json")
    layout = _read_json(source_workspace / "layout_spec.json")
    catalog = _read_json(source_workspace / "component_catalog.json")
    candidates_path = source_workspace / "component_candidates.json"
    candidates = _read_json(candidates_path) if candidates_path.exists() else {"candidates": []}
    slots = _read_json(source_workspace / "slot_contracts.json")
    assets = _read_json(source_workspace / "asset_provenance.json")
    policy = _read_json(source_workspace / "adaptation_policy.json")
    review = _read_json(source_workspace / "review_queue.json")
    graph_path = source_workspace / "source_graph.json"
    graph = _read_json(graph_path) if graph_path.exists() else {}

    page_roles_by_slide = _page_role_map(layout)
    slots_by_id = {
        str(item.get("slot_id")): item
        for item in slots.get("slots") or []
        if isinstance(item, dict) and item.get("slot_id")
    }
    fragment_assets = [
        _fragment_asset(
            component,
            template_id=template_id,
            source_workspace=source_workspace,
            page_roles_by_slide=page_roles_by_slide,
            slots_by_id=slots_by_id,
        )
        for component in catalog.get("components") or []
        if isinstance(component, dict) and component.get("component_id")
    ]
    pack_id = f"pptx_{_slug(template_id)}"
    pack = {
        "schema_version": SCHEMA_VERSION,
        "pack_id": pack_id,
        "version": "0.1.0",
        "display_name": f"{template_id} PPTX design system",
        "description": "Declarative source-template components compiled from EasySlides PPTX distillation contracts.",
        "license": "unknown_requires_review",
        "installability": "source_template_only",
        "promotion_status": "requires_renderer_mapping_and_cross_material_qa",
        "source": {
            "template_id": template_id,
            "workspace": str(source_workspace.resolve()),
            "source_graph": str(graph_path.resolve()),
            "source_graph_sha256": (graph.get("source") or {}).get("sha256"),
        },
        "tokens": identity.get("theme", {}),
        "identity": {
            "identity_must_preserve": identity.get("identity_must_preserve", []),
            "protected_surfaces": identity.get("protected_surfaces", []),
        },
        "layout": {
            "canvas": layout.get("canvas", {}),
            "slides": layout.get("slides", []),
            "layouts": layout.get("layouts", []),
            "inheritance": layout.get("inheritance", {}),
        },
        "components": [
            {
                "component_id": component.get("component_id"),
                "asset_id": f"pptx_source/{template_id}/{component.get('component_id')}",
                "classification": component.get("classification"),
                "slot_contract_ids": component.get("slot_contract_ids", []),
                "instance_count": len(component.get("instances") or []),
                "promotion_status": "source_template_only",
            }
            for component in catalog.get("components") or []
            if isinstance(component, dict)
        ],
        "component_candidates": {
            "path": "component_candidates.json" if candidates_path.exists() else None,
            "candidate_count": len(candidates.get("candidates") or []),
            "promotion_policy": candidates.get("promotion_policy", "legacy_workspace_without_candidates"),
        },
        "slots": slots.get("slots", []),
        "assets": assets.get("assets", []),
        "adaptation_policy": policy,
        "review_queue": {
            "status": review.get("status"),
            "open_count": (review.get("summary") or {}).get("open_count", 0),
            "path": "review_queue.json",
        },
        "qa": {
            "slot_contract_validation": (slots.get("validation") or {}).get("status", "unknown"),
            "review_required_before_promotion": True,
            "required_gates": ["source_template_contract", "visual_measure_gate", "cross_material_smoke_test", "renderer_governance", "cross_renderer_visual_regression"],
        },
    }
    fragment = {
        "schema_version": FRAGMENT_SCHEMA_VERSION,
        "generated_by": "scripts/pptx_design_system_compiler.py",
        "template_id": template_id,
        "source_pack": "design_system_pack.json",
        "source_workspace": _source_relative(source_workspace, repository_root),
        "assets": fragment_assets,
    }
    return {"design_system_pack": pack, "component_registry_fragment": fragment}


def write_design_system_pack(output_dir: Path, compiled: dict[str, dict[str, Any]]) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, payload in compiled.items():
        path = output_dir / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths[name] = path
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile Phase 2 PPTX contracts into a declarative design-system pack.")
    parser.add_argument("source_workspace", help="Reference workspace containing Phase 2 JSON contracts")
    parser.add_argument("--template-id", required=True, help="Template id")
    parser.add_argument("--output-dir", help="Output directory; defaults to source workspace")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_workspace = Path(args.source_workspace).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else source_workspace
    compiled = compile_design_system_pack(template_id=args.template_id, source_workspace=source_workspace)
    paths = write_design_system_pack(output_dir, compiled)
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
