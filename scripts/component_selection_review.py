#!/usr/bin/env python3
"""Build a human-reviewable explanation of component choices for a deck."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.component_registry import load_component_registry
except ModuleNotFoundError:  # pragma: no cover
    from component_registry import load_component_registry


SCHEMA_VERSION = "easyslides.component_selection_review.v1"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _asset_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(asset.get("asset_id")): asset for asset in registry.get("assets", []) if isinstance(asset, dict) and asset.get("asset_id")}


def _preview_map(gallery_manifest: dict[str, Any] | None) -> dict[str, str]:
    previews: dict[str, str] = {}
    if not isinstance(gallery_manifest, dict):
        return previews
    for package in gallery_manifest.get("packages", []):
        if not isinstance(package, dict):
            continue
        component_id = str(package.get("component_id") or "")
        story = next((row for row in package.get("stories", []) if isinstance(row, dict) and row.get("story_id") == "default"), None)
        if component_id and isinstance(story, dict) and story.get("svg"):
            previews[f"component_package/{component_id}"] = str(story["svg"])
    return previews


def _candidate(asset_id: str, selected: dict[str, Any], asset: dict[str, Any] | None, preview: str | None) -> dict[str, Any]:
    selection = asset.get("selection", {}) if isinstance(asset, dict) and isinstance(asset.get("selection"), dict) else {}
    slots = asset.get("slots", []) if isinstance(asset, dict) and isinstance(asset.get("slots"), list) else []
    return {
        "asset_id": asset_id,
        "rank": selected.get("rank"),
        "score": selected.get("score", 0),
        "recommended": bool(selected.get("recommended", False)),
        "granularity": selected.get("granularity") or (asset or {}).get("granularity", ""),
        "render_backend": selected.get("render_backend") or (asset or {}).get("render_backend", ""),
        "reasons": list(selected.get("selection_reason") or selected.get("reason") or []),
        "best_for": selection.get("best_for", ""),
        "avoid_when": selection.get("avoid_when", ""),
        "capacity": {
            "item_count_min": selection.get("item_count_min"),
            "item_count_max": selection.get("item_count_max"),
            "density": selection.get("density"),
            "slot_count": len(slots),
        },
        "preview": preview,
        "preview_status": "available" if preview else "not_available",
    }


def build_component_selection_review(
    component_plan: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    gallery_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_component_registry()
    assets = _asset_map(registry)
    previews = _preview_map(gallery_manifest)
    slides: list[dict[str, Any]] = []
    for slide in component_plan.get("slides", []):
        if not isinstance(slide, dict):
            continue
        candidates = [row for row in slide.get("selection_candidates", slide.get("selected_assets", [])) if isinstance(row, dict) and row.get("asset_id")]
        rows: list[dict[str, Any]] = []
        for rank, selected in enumerate(candidates, start=1):
            asset_id = str(selected["asset_id"])
            prepared = dict(selected)
            prepared["rank"] = rank
            prepared["recommended"] = rank == 1
            rows.append(_candidate(asset_id, prepared, assets.get(asset_id), previews.get(asset_id)))
        slides.append(
            {
                "page": str(slide.get("page") or ""),
                "role": str(slide.get("role") or ""),
                "content_shape": str(slide.get("content_shape") or ""),
                "selection_status": str(slide.get("selection_status") or ""),
                "narrative_context": slide.get("narrative_context", {}),
                "form_selection": slide.get("form_selection", {}),
                "recommended": rows[0] if rows else None,
                "alternatives": rows[1:],
                "approval_contract": {
                    "deck_plan_field": "component_requirements.selected_asset_id",
                    "rule": "An approved asset must remain compatible with the declared template and input schema.",
                },
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(slide["recommended"] for slide in slides) else "fail",
        "template_id": component_plan.get("template_id", ""),
        "slide_count": len(slides),
        "slides": slides,
    }


def _render_html(review: dict[str, Any]) -> str:
    sections: list[str] = []
    for slide in review["slides"]:
        cards: list[str] = []
        for candidate in [slide.get("recommended"), *slide.get("alternatives", [])]:
            if not isinstance(candidate, dict):
                continue
            label = "Recommended" if candidate.get("recommended") else "Alternative"
            preview = candidate.get("preview")
            image = f'<img src="{html.escape(str(preview))}" alt="{html.escape(candidate["asset_id"])} preview">' if preview else '<div class="no-preview">No preview fixture</div>'
            reasons = "<br>".join(html.escape(str(reason)) for reason in candidate.get("reasons", [])) or "No recorded reason"
            cards.append(
                f'<article class="candidate"><header><b>{label}</b><span>{html.escape(candidate["asset_id"])}</span></header>{image}'
                f'<p class="meta">score {candidate.get("score", 0)} | {html.escape(str(candidate.get("granularity", "")))}</p>'
                f'<p>{reasons}</p><p><b>Best for:</b> {html.escape(str(candidate.get("best_for", "")))}</p>'
                f'<p><b>Avoid when:</b> {html.escape(str(candidate.get("avoid_when", "")))}</p></article>'
            )
        sections.append(f'<section><h2>{html.escape(slide["page"])} <small>{html.escape(slide["content_shape"] or slide["role"])}</small></h2><div class="candidates">{"".join(cards) or "<p>No compatible component.</p>"}</div></section>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>EasySlides Component Choices</title><style>
body{{margin:0;background:#f3f5f7;color:#172033;font-family:Aptos,Segoe UI,sans-serif}}main{{max-width:1440px;margin:auto;padding:30px}}h1,h2{{letter-spacing:0;margin:0}}h1{{font-size:30px}}h2{{font-size:20px;border-bottom:1px solid #d6dde6;padding-bottom:10px}}h2 small{{font-size:13px;color:#657386;font-weight:400}}section{{margin-top:28px}}.candidates{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;padding-top:14px}}.candidate{{background:#fff;border:1px solid #d6dde6;min-width:0}}.candidate header{{padding:12px;border-bottom:1px solid #d6dde6;display:flex;justify-content:space-between;gap:12px;align-items:center}}.candidate header b{{color:#0f7653;font-size:12px;text-transform:uppercase}}.candidate header span{{font-family:Consolas,monospace;font-size:12px;overflow-wrap:anywhere}}img{{width:100%;display:block;aspect-ratio:16/9;background:#e7edf3}}.no-preview{{height:180px;display:grid;place-items:center;background:#e7edf3;color:#657386}}p{{padding:0 14px;margin:10px 0;font-size:13px;line-height:1.45}}.meta{{color:#657386}}</style></head><body><main><h1>Component Choice Review</h1><p>Recommended components and executable alternatives. To lock a choice, use <code>component_requirements.selected_asset_id</code> in the deck plan.</p>{"".join(sections)}</main></body></html>'''


def write_component_selection_review(output_dir: str | Path, review: dict[str, Any]) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "component_choice_review.json"
    html_path = directory / "component_choice_review.html"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(_render_html(review), encoding="utf-8")
    return {"json": str(json_path), "html": str(html_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a component selection review from a component plan.")
    parser.add_argument("component_plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--gallery-manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = _read_json(args.component_plan)
    registry = load_component_registry(args.registry) if args.registry else None
    gallery = _read_json(args.gallery_manifest) if args.gallery_manifest else None
    review = build_component_selection_review(plan, registry=registry, gallery_manifest=gallery)
    paths = write_component_selection_review(args.out, review)
    print(json.dumps({**review, "artifacts": paths}, ensure_ascii=False, indent=2))
    return 0 if review["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
