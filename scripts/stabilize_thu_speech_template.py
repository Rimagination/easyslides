#!/usr/bin/env python3
"""Materialize the reviewed THU Speech design as a self-contained template package.

The source-faithful work lives in ``tmp/thu_speech`` while this command creates
the stable, repo-relative runtime package under ``templates/layouts/thu_speech``.
The package is materialized as a production template and is included in the
official selection set after the repository policy is updated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tmp" / "thu_speech"
TARGET = ROOT / "templates" / "layouts" / "thu_speech"

SVG_NS = "http://www.w3.org/2000/svg"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _svg_open(component_id: str, width: float, height: float) -> str:
    return (
        f'<svg xmlns="{SVG_NS}" version="1.1" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}" overflow="hidden" '
        f'data-component-id="{component_id}" data-easyslides-source-fidelity="thu_speech_stable_component">'
    )


def _text_slot(slot_id: str, x: float, y: float, width: float, height: float, *, size: int = 16, color: str = "#2B2330", weight: str = "normal") -> str:
    safe_id = slot_id.replace("&", "&amp;").replace('"', "&quot;")
    cx = x + width / 2
    cy = y + height / 2
    return (
        f'<text x="{cx:g}" y="{cy + size * 0.35:g}" text-anchor="middle" '
        f'font-family="Microsoft YaHei, Segoe UI, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" data-slot="{safe_id}" data-slot-id="{safe_id}" '
        f'data-slot-kind="text" data-pptx-textbox="true" data-pptx-box-x="{x:g}" '
        f'data-pptx-box-y="{y:g}" data-pptx-box-w="{width:g}" data-pptx-box-h="{height:g}" '
        f'data-pptx-valign="middle" data-center-lock="true">{safe_id}</text>'
    )


def _image_slot(slot_id: str, x: float, y: float, width: float, height: float) -> str:
    safe_id = slot_id.replace("&", "&amp;").replace('"', "&quot;")
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="6" '
        f'fill="#FBF9FC" stroke="#E5DDE8" stroke-width="1" data-easyslides-image-frame-for="{safe_id}"/>'
        f'<image x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" '
        f'preserveAspectRatio="xMidYMid meet" href="" data-slot="{safe_id}" data-slot-id="{safe_id}" '
        f'data-slot-kind="image" data-easyslides-image-fit="contain"/>'
    )


def _component_svg(component_id: str) -> str:
    purple = "#912C8D"
    deep = "#441351"
    blue = "#6A69B6"
    line = "#E5DDE8"
    pale = "#FBF9FC"
    specs: dict[str, tuple[float, float]] = {
        "highlight_image": (278.83, 103.69),
        "keyword_strip": (761.23, 101.28),
        "content_panel_01": (512.55, 358.93),
        "content_panel_02": (512.54, 358.93),
        "cards_group": (590.09, 428.85),
        "callout": (602.60, 65.63),
        "side_image": (460.17, 541.37),
        "metrics_strip": (722.40, 127.94),
        "metric_evidence": (414.14, 340.88),
        "image_caption": (495.43, 83.10),
        "dual_panel_left": (512.0, 465.0),
        "dual_panel_right": (512.0, 465.0),
        "photo_statement": (1058.0, 475.0),
    }
    width, height = specs[component_id]
    out = [_svg_open(component_id, width, height)]
    if component_id == "highlight_image":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="10" fill="{pale}" stroke="{line}"/>')
        out.append(_image_slot("HIGHLIGHT_IMAGE", 8, 8, 112, height - 16))
        out.append(_text_slot("HIGHLIGHT_VALUE", 132, 20, width - 146, 64, size=26, color=purple, weight="bold"))
    elif component_id == "keyword_strip":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="10" fill="#FFFFFF" stroke="{line}"/>')
        pill_width = (width - 56) / 4
        for index in range(4):
            x = 8 + index * (pill_width + 8)
            out.append(f'<rect x="{x:g}" y="18" width="{pill_width:g}" height="65" rx="8" fill="{pale}"/>')
            out.append(_text_slot(f"KEYWORD_{index + 1:02d}", x + 4, 20, pill_width - 8, 60, size=15, color=deep, weight="bold"))
    elif component_id in {"content_panel_01", "content_panel_02"}:
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="12" fill="#FFFFFF" stroke="{line}"/>')
        suffix = "01" if component_id.endswith("01") else "02"
        out.append(_text_slot(f"PANEL_TITLE_{suffix}", 22, 20, width - 44, 36, size=18, color=deep, weight="bold"))
        out.append(f'<line x1="22" y1="72" x2="{width - 22:g}" y2="72" stroke="{line}"/>')
        out.append(_text_slot(f"PANEL_{suffix}_BODY_01", 22, 90, width - 44, 70, size=15))
        out.append(_text_slot(f"PANEL_{suffix}_BODY_02", 22, 170, width - 44, 70, size=15))
        for index, x in enumerate((22, 180, 338), 1):
            out.append(f'<rect x="{x}" y="{height - 62:g}" width="128" height="34" rx="17" fill="{pale}" stroke="{line}"/>')
            out.append(_text_slot(f"PANEL_{suffix}_TAG_{index:02d}", x + 4, height - 59, 120, 28, size=12, color=purple, weight="bold"))
    elif component_id == "cards_group":
        card_height = (height - 24) / 2
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="12" fill="#FFFFFF" stroke="{line}"/>')
        for index in range(2):
            y = 8 + index * (card_height + 8)
            out.append(f'<rect x="10" y="{y:g}" width="{width - 20:g}" height="{card_height:g}" rx="10" fill="{pale}"/>')
            out.append(_text_slot(f"CARD_{index + 1:02d}_TITLE", 28, y + 16, width - 56, 34, size=17, color=deep, weight="bold"))
            out.append(_text_slot(f"CARD_{index + 1:02d}_BODY", 28, y + 58, width - 56, card_height - 72, size=14))
    elif component_id == "callout":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="12" fill="#FBF3FD" stroke="{line}"/>')
        out.append(f'<rect width="8" height="{height:g}" rx="4" fill="{purple}"/>')
        out.append(_text_slot("CALLOUT_TEXT", 28, 8, width - 44, height - 16, size=15, color=deep, weight="bold"))
    elif component_id == "side_image":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="12" fill="#FFFFFF" stroke="{line}"/>')
        out.append(_image_slot("IMAGE_01", 10, 10, width - 20, height - 84))
        out.append(_text_slot("IMAGE_CAPTION", 20, height - 64, width - 40, 42, size=13, color=deep))
    elif component_id == "metrics_strip":
        gap = 8
        card_width = (width - gap * 3) / 4
        for index in range(4):
            x = index * (card_width + gap)
            out.append(f'<rect x="{x:g}" y="1" width="{card_width:g}" height="{height - 2:g}" rx="10" fill="#FFFFFF" stroke="{line}"/>')
            out.append(_text_slot(f"METRIC_{index + 1:02d}_VALUE", x + 6, 12, card_width - 12, 42, size=24, color=purple, weight="bold"))
            out.append(_text_slot(f"METRIC_{index + 1:02d}_LABEL", x + 6, 62, card_width - 12, 42, size=13, color=deep, weight="bold"))
    elif component_id == "metric_evidence":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="12" fill="#FFFFFF" stroke="{line}"/>')
        for index in range(2):
            y = 20 + index * 156
            out.append(f'<circle cx="28" cy="{y + 24:g}" r="16" fill="{blue}"/>')
            out.append(_text_slot(f"EVIDENCE_TITLE_{index + 1:02d}", 56, y, width - 76, 36, size=16, color=deep, weight="bold"))
            out.append(_text_slot(f"EVIDENCE_TEXT_{index + 1:02d}", 20, y + 48, width - 40, 76, size=14))
    elif component_id == "image_caption":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="10" fill="#FBF9FC" stroke="{line}"/>')
        out.append(_text_slot("IMAGE_CAPTION", 16, 10, width - 32, height - 20, size=14, color=deep))
    elif component_id in {"dual_panel_left", "dual_panel_right"}:
        side = "LEFT" if component_id.endswith("left") else "RIGHT"
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="12" fill="#FFFFFF" stroke="{line}"/>')
        out.append(_text_slot(f"PANEL_{side}_TITLE", 20, 18, width - 40, 38, size=18, color=deep, weight="bold"))
        out.append(_image_slot(f"PANEL_{side}_IMAGE", 20, 72, width - 40, 170))
        out.append(_text_slot(f"PANEL_{side}_BODY", 20, 264, width - 40, 150, size=15))
    elif component_id == "photo_statement":
        out.append(f'<rect width="{width:g}" height="{height:g}" rx="14" fill="#FFFFFF" stroke="{line}"/>')
        out.append(_image_slot("IMAGE_01", 20, 20, 390, height - 40))
        out.append(_text_slot("STATEMENT_TITLE", 438, 36, width - 470, 54, size=22, color=deep, weight="bold"))
        out.append(_text_slot("STATEMENT_BODY", 438, 112, width - 470, 190, size=16))
        out.append(_text_slot("STATEMENT_NOTE", 438, height - 82, width - 470, 48, size=13, color=purple, weight="bold"))
    out.append("</svg>\n")
    return "".join(out)


def _slot_row(slot: Any) -> dict[str, Any]:
    if isinstance(slot, dict):
        row = dict(slot)
    else:
        row = {"slot_id": str(slot)}
    slot_id = str(row.get("slot_id") or row.get("id") or row.get("slot") or "")
    row["slot_id"] = slot_id
    row.setdefault("kind", "image" if slot_id in {"IMAGE_01", "IMAGE_02", "IMAGE_03", "IMAGE_04", "HIGHLIGHT_IMAGE", "PANEL_LEFT_IMAGE", "PANEL_RIGHT_IMAGE"} else "text")
    if row["kind"] == "text":
        row.setdefault("max_lines", 2)
        row.setdefault("max_chars_per_line", 24)
    return row


def _materialize_components(target: Path) -> None:
    catalog_path = target / "component_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    component_dir = target / "assets" / "components" / "thu_speech"
    component_dir.mkdir(parents=True, exist_ok=True)
    for component in catalog.get("components", []):
        component_id = str(component.get("component_id") or "")
        if not component_id:
            continue
        (component_dir / f"{component_id}.svg").write_text(_component_svg(component_id), encoding="utf-8")
        component["asset_path"] = f"assets/components/thu_speech/{component_id}.svg"
        component["asset_status"] = "renderable_svg"
        component["renderer_id"] = "source_template_projection"
        component["render_backend"] = "template_svg_component"
        component["slots"] = [_slot_row(slot) for slot in component.get("slots", [])]
    catalog["selection_policy"] = "source_faithful_header_then_stable_template_component"
    catalog["component_asset_root"] = "assets/components/thu_speech"
    _write_json(catalog_path, catalog)


def _prepare_layouts(target: Path) -> None:
    path = target / "layouts.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    slot_models = payload.get("slot_models") if isinstance(payload.get("slot_models"), dict) else {}
    for shell in payload.get("shells", []):
        role = str(shell.get("role") or shell.get("shell_id") or "")
        model = slot_models.get(role)
        if isinstance(model, list):
            shell["slots"] = [_slot_row(slot) for slot in model]
        if role == "content":
            shell["content_shell_policy"] = "source_guided_body_variant_required"
            shell["body_canvas"] = {"x": 0, "y": 120, "width": 1280, "height": 600}
    payload["runtime_contract"] = "compiled/template_ir.json"
    payload["selection_policy"] = "explicit_functional_variant_then_body_variant"
    _write_json(path, payload)


def _prepare_template(target: Path) -> None:
    path = target / "template.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload.update(
        {
            "availability": "explicit_request_only",
            "recommended_template_route": "source_template_projection",
            "runtime_source_of_truth": "templates/layouts/thu_speech",
            "stable_package": True,
            "template_classification": "official",
            "official_template": True,
            "selection_requires_explicit_request": False,
            "archive_policy": "active_official_template",
        }
    )
    _write_json(path, payload)


def _write_supporting_contracts(target: Path) -> None:
    _write_json(
        target / "capability_profile.json",
        {
            "schema_version": "easyslides.template_capability_profile.v1",
            "template_id": "thu_speech",
            "lifecycle": "legacy",
            "classification": "official",
            "selection_requires_explicit_request": False,
            "generation_enabled": True,
            "composition": {
                "mode": "template_bounded",
                "allowed_granularities": ["body_variant", "page_module", "template_component"],
                "allow_global_component_fallback": False,
                "allowed_component_packs": [],
                "requires_declared_body_variant": True,
            },
            "contracts": {
                "layouts": True,
                "body_variants": True,
                "component_catalog": True,
                "component_pack": False,
                "design_tokens": False,
            },
            "selection_policy": {
                "template_affinity": "required",
                "undeclared_assets": "reject",
                "manual_selection": "must_be_declared",
                "missing_profile": "block_named_template_component_selection",
            },
            "required_gates": ["template_capability_profile", "body_variant_contract", "visual_measure_gate", "native_pptx_roundtrip"],
            "derived_from": "stable_thu_speech_package_contract",
        },
    )
    _write_json(
        target / "qa_policy.json",
        {
            "schema_version": "easyslides.template_qa_policy.v1",
            "template_id": "thu_speech",
            "promotion_policy": "fail_closed",
            "alignment_invariants": [
                "text_center_y_matches_container_center_y",
                "declared_slots_stay_inside_canvas",
                "body_variant_regions_stay_inside_body_canvas",
                "image_slots_use_contain_unless_full_canvas_background",
                "image_slots_have_subtle_frame_when_contained",
                "functional_variant_selection_is_explicit",
            ],
            "required_gates": [
                "template_package_validate",
                "template_compile",
                "body_variant_component_contract",
                "functional_page_variant_geometry",
                "svg_quality",
                "native_pptx_roundtrip",
                "placeholder_scan",
                "human_visual_review",
            ],
            "source_faithful_contract": {
                "shell_count": 5,
                "functional_variant_groups": {"cover": 3, "toc": 3, "transition": 4, "ending": 3},
                "transition_series": "transition_series",
                "content_variant_count": 15,
                "excluded_source_slide": 22,
            },
            "image_fit_policy": {
                "scientific_images": "contain",
                "decorative_photos": "cover",
                "full_canvas_backgrounds": "stretch",
                "contained_image_frame": {"stroke": "#E5DDE8", "opacity": 0.78, "width": 1.2, "radius": 3},
            },
            "vertical_center_tolerance_px": 1.0,
        },
    )
    (target / "spec_lock.md").write_text(
        "# thu_speech stable package lock\n\n"
        "This package is the official Tsinghua speech template. It uses five functional shells and a reviewed source-faithful body-variant contract.\n\n"
        "The public contract is five functional shells (`cover`, `toc`, `transition`, `content`, `ending`), one transition series, and fifteen active content variants. Source slide 22 is excluded.\n\n"
        "Content images use `contain` with a subtle `#E5DDE8` frame; full-canvas backgrounds remain `stretch`. Native PPTX generation must pass placeholder and round-trip checks before release.\n",
        encoding="utf-8",
    )
    _write_json(
        target / "template_status.json",
        {
            "schema_version": "easyslides.template_status.v2",
            "template_id": "thu_speech",
            "status": "production",
            "classification": "official",
            "official_template": True,
            "selection_requires_explicit_request": False,
            "production_eligible": True,
            "runtime_contract": "compiled/template_ir.json",
            "source_faithful_content_variants": 15,
            "functional_shells": 5,
            "excluded_source_slides": [22],
        },
    )
    (target / "README.md").write_text(
        "# thu_speech\n\n"
        "Official, source-faithful THU speech template package. It is eligible for default template selection.\n\n"
        "- Functional shells: cover, toc, transition, content, ending\n"
        "- Transition: one shared series with number/photo presets for source slides 07–10\n"
        "- Content: 15 active body variants; source slide 22 is excluded\n"
        "- Runtime: `compiled/template_ir.json` plus source-template projection for source-faithful variants\n"
        "- Default template library: includes `thu_speech` as an official template\n",
        encoding="utf-8",
    )


def materialize(*, force: bool = False) -> dict[str, Any]:
    if not SOURCE.is_dir():
        raise FileNotFoundError(SOURCE)
    if TARGET.exists():
        if not force:
            raise FileExistsError(f"target already exists: {TARGET}; use --force only after an intentional review")
        raise RuntimeError("refusing to overwrite an existing stable package; review and remove it explicitly")
    TARGET.mkdir(parents=True, exist_ok=False)
    files = [
        "01_cover.svg", "02_toc.svg", "03_transition.svg", "04_content.svg", "05_ending.svg",
        "body_variants.json", "component_catalog.json", "design_spec.md", "functional_page_variants.json",
        "geometry_contract.json", "layout_roster.json", "links.json", "layouts.json", "page_catalog.json",
        "rules.md", "slot_contracts.json", "source_page_roster.json", "story_structure.json", "template.json",
    ]
    directories = ["assets", "body_variants", "functional_variants", "page_variants"]
    for name in files:
        shutil.copy2(SOURCE / name, TARGET / name)
    for name in directories:
        shutil.copytree(SOURCE / name, TARGET / name)
    _prepare_layouts(TARGET)
    _prepare_template(TARGET)
    _materialize_components(TARGET)
    _write_supporting_contracts(TARGET)
    return {
        "status": "pass",
        "template_id": "thu_speech",
        "target": str(TARGET),
        "shell_count": 5,
        "content_variant_count": 15,
        "component_count": len(json.loads((TARGET / "component_catalog.json").read_text(encoding="utf-8"))["components"]),
        "excluded_source_slides": [22],
        "excluded_runtime_evidence": ["source_render", "source_thumbnails-*.jpg", "source_render_report.json"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="kept for compatibility; existing packages are never overwritten")
    args = parser.parse_args()
    print(json.dumps(materialize(force=args.force), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
