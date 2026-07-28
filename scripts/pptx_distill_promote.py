#!/usr/bin/env python3
"""Promote a faithful PPTX distillation into reusable EasySlides assets.

The normal distiller intentionally keeps source material for fidelity review.
This promotion step creates the second, user-facing layer: content-free
evidence-driven shell-profile pages plus source-scoped component and symbol asset manifests. It does not
guess unresolved objects; those remain in the source review queue.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def slide_id_from_name(name: str) -> str:
    match = re.match(r"^(\d+)_", name)
    return f"slide-{int(match.group(1)):02d}" if match else ""


def slot_token(slide_id: str, slot: dict[str, Any], index: int) -> str:
    kind = str(slot.get("kind") or "text")
    role = str(slot.get("role") or "").lower()
    if kind == "image":
        return "{{HERO_IMAGE}}" if slide_id == "slide-01" and index == 0 else f"{{{{IMAGE_{index + 1:02d}}}}}"
    if slide_id == "slide-01":
        return ["{{TITLE}}", "{{SUBTITLE}}", "{{PRESENTER}}", "{{DATE}}", "{{DATE_02}}", "{{DATE_03}}"][(min(index, 5))]
    if slide_id.endswith("17"):
        return ["{{CLOSING_TITLE}}", "{{CLOSING_SUBTITLE}}", "{{CONTACT}}", "{{CONTACT_02}}"][(min(index, 3))]
    if "title" in role or index == 0:
        return "{{PAGE_TITLE}}" if index == 0 else f"{{{{PAGE_TITLE_{index + 1:02d}}}}}"
    return f"{{{{BODY_TEXT_{index:02d}}}}}"


def find_text_nodes(element: ET.Element) -> list[ET.Element]:
    return [node for node in element.iter() if local_name(node.tag) == "text"]


def replace_text_element(element: ET.Element, token: str, slot_id: str) -> bool:
    texts = find_text_nodes(element)
    if not texts and local_name(element.tag) == "text":
        texts = [element]
    if not texts:
        return False
    first = texts[0]
    for child in list(first):
        first.remove(child)
    first.text = token
    first.set("data-slot-id", slot_id)
    first.set("data-pptx-valign", "middle")
    first.set("data-center-lock", "true")
    for extra in texts[1:]:
        extra.text = ""
        for child in list(extra):
            extra.remove(child)
    return True


def replace_image_element(element: ET.Element, placeholder_href: str, slot_id: str) -> bool:
    images = [node for node in element.iter() if local_name(node.tag) == "image"]
    if local_name(element.tag) == "image":
        images = [element]
    if not images:
        return False
    for image in images:
        try:
            x = float(image.attrib.get("x", 0))
            y = float(image.attrib.get("y", 0))
            w = float(image.attrib.get("width", 0))
            h = float(image.attrib.get("height", 0))
        except ValueError:
            x = y = w = h = 0
        # Keep full-slide textures and small header ornaments as fixed chrome;
        # medium/large content figures become replaceable image slots.
        if (w >= 1000 and h >= 600) or (y < 120 and x > 900):
            continue
        image.set("href", placeholder_href)
        image.set(f"{{{XLINK_NS}}}href", placeholder_href)
        image.set("data-slot-id", slot_id)
    return True


def is_fixed_chrome_image(image: ET.Element) -> bool:
    """Keep only recurring decorative surfaces, never source material images."""
    try:
        x = float(image.attrib.get("x", 0))
        y = float(image.attrib.get("y", 0))
        w = float(image.attrib.get("width", 0))
        h = float(image.attrib.get("height", 0))
    except ValueError:
        return False
    return (w >= 1000 and h >= 600) or (y < 120 and x > 900) or (y > 500 and w >= 700)


def source_slot_element(root: ET.Element, slot: dict[str, Any]) -> ET.Element | None:
    slot_id = str(slot.get("slot_id") or "")
    geometry = slot.get("geometry") if isinstance(slot.get("geometry"), dict) else {}
    for node in root.iter():
        if node.attrib.get("data-slot-id") == slot_id:
            return node
    x, y, w, h = (float(geometry.get(key) or 0) for key in ("x", "y", "width", "height"))
    for node in root.iter():
        if "data-pptx-box-x" not in node.attrib:
            continue
        try:
            values = tuple(float(node.attrib.get(f"data-pptx-box-{key}", "nan")) for key in ("x", "y", "w", "h"))
        except ValueError:
            continue
        if all(abs(a - b) <= 2.0 for a, b in zip(values, (x, y, w, h))):
            return node
    for node in root.iter():
        if local_name(node.tag) not in {"g", "text", "rect", "svg", "image"}:
            continue
        try:
            nx, ny = float(node.attrib.get("x", "nan")), float(node.attrib.get("y", "nan"))
            nw, nh = float(node.attrib.get("width", "nan")), float(node.attrib.get("height", "nan"))
        except ValueError:
            continue
        if all(abs(a - b) <= 2.0 for a, b in ((nx, x), (ny, y), (nw, w), (nh, h))):
            return node
    return None


def make_placeholder(path: Path) -> None:
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">'
        '<rect width="320" height="180" fill="#F5F7FA" stroke="#B8C1CC" stroke-dasharray="6 4"/>'
        '<path d="M24 142L100 72l50 46 44-58 102 82" fill="none" stroke="#B8C1CC" stroke-width="4"/>'
        '<text x="160" y="30" text-anchor="middle" fill="#7B8794" font-family="Arial" font-size="18">IMAGE SLOT</text>'
        '</svg>\n',
        encoding="utf-8",
    )


def source_svg_for_object(source_workspace: Path, object_id: str) -> tuple[Path | None, str | None]:
    """Map an OOXML object id to the corresponding rendered SVG fragment.

    Slide objects use ``shape-12``/``group-12`` ids, while layout and master
    evidence uses ``layout-shape-12`` and ``master-shape-12``.  Keeping this
    mapping here makes symbol extraction provenance-preserving instead of
    silently dropping the latter two classes.
    """
    match = re.search(r"ppt/(slides|slideLayouts|slideMasters)/(?:slide|slideLayout|slideMaster)(\d+)\.xml::(shape|group|connector|picture):(\d+)", object_id)
    if not match:
        return None, None
    part_kind, part_number, object_kind, object_number = match.groups()
    index = int(part_number)
    if part_kind == "slides":
        filename = f"slide_{index:02d}.svg"
        element_id = f"{object_kind}-{object_number}"
    elif part_kind == "slideLayouts":
        filename = next((path.name for path in (source_workspace / "svg").glob(f"layout_*_slideLayout{index}.svg")), None)
        element_id = f"layout-{object_kind}-{object_number}"
    else:
        filename = next((path.name for path in (source_workspace / "svg").glob(f"master_*_slideMaster{index}.svg")), None)
        element_id = f"master-{object_kind}-{object_number}"
    if not filename:
        return None, None
    path = source_workspace / "svg" / filename
    return (path if path.exists() else None), element_id


def build_reusable_template(template_dir: Path, output_dir: Path, slots_by_slide: dict[str, list[dict[str, Any]]], *, template_id: str) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(template_dir, output_dir)
    placeholder = output_dir / "assets" / "slot-placeholder.svg"
    placeholder.parent.mkdir(parents=True, exist_ok=True)
    make_placeholder(placeholder)
    shell_source_slides: dict[str, str] = {}
    layouts_path = output_dir / "layouts.json"
    if layouts_path.exists():
        try:
            layouts = read_json(layouts_path)
            for page in layouts.get("pages", []):
                if isinstance(page, dict) and page.get("svg") and page.get("source_slide"):
                    shell_source_slides[str(page["svg"])] = f"slide-{int(page['source_slide']):02d}"
        except (OSError, ValueError, TypeError):
            shell_source_slides = {}
    replaced: list[dict[str, Any]] = []
    for svg_path in sorted(output_dir.glob("*.svg")):
        slide_id = shell_source_slides.get(svg_path.name) or slide_id_from_name(svg_path.name)
        slots = sorted(slots_by_slide.get(slide_id, []), key=lambda item: (float(item.get("geometry", {}).get("y", 0)), float(item.get("geometry", {}).get("x", 0))))
        if not slots:
            continue
        tree = ET.parse(svg_path)
        root = tree.getroot()
        text_candidates = [node for node in root.iter() if local_name(node.tag) == "text" and node.attrib.get("data-pptx-textbox") == "true"]
        image_candidates = [node for node in root.iter() if local_name(node.tag) == "image"]
        text_candidates.sort(key=lambda node: (float(node.attrib.get("data-pptx-box-y", node.attrib.get("y", 0))), float(node.attrib.get("data-pptx-box-x", node.attrib.get("x", 0)))))
        image_candidates.sort(key=lambda node: (float(node.attrib.get("y", 0)), float(node.attrib.get("x", 0))))
        text_index = 0
        image_index = 0
        for index, slot in enumerate(slots):
            if slot.get("kind") == "image":
                kind_index = image_index
                element = image_candidates[image_index] if image_index < len(image_candidates) else None
                image_index += 1
            else:
                kind_index = text_index
                element = text_candidates[text_index] if text_index < len(text_candidates) else None
                text_index += 1
            if element is None:
                continue
            slot_id = str(slot.get("slot_id"))
            token = slot_token(slide_id, slot, kind_index)
            changed = replace_image_element(element, "assets/slot-placeholder.svg", slot_id) if slot.get("kind") == "image" else replace_text_element(element, token, slot_id)
            if changed:
                replaced.append({"slide_id": slide_id, "slot_id": slot_id, "kind": slot.get("kind"), "token": token})
        for text_node in [node for node in root.iter() if local_name(node.tag) == "text"]:
            if text_node.attrib.get("data-slot-id"):
                continue
            if text_node.attrib.get("data-pptx-fixed-chrome") == "true":
                continue
            for child in list(text_node):
                text_node.remove(child)
            text_node.text = ""
        auto_image_index = 1
        for image_node in [node for node in root.iter() if local_name(node.tag) == "image"]:
            # The source full-slide raster contains baked-in navigation/source
            # text. It is not reusable chrome; the vector shell already keeps
            # the intended color blocks and ornaments.
            href = image_node.attrib.get("href") or image_node.attrib.get(f"{{{XLINK_NS}}}href") or ""
            if is_fixed_chrome_image(image_node) and "image1_fx" in href:
                image_node.set("opacity", "0")
                image_node.set("data-source-background-hidden", "true")
                continue
            if image_node.attrib.get("data-slot-id") or is_fixed_chrome_image(image_node):
                continue
            auto_slot_id = f"{slide_id}_auto_image_{auto_image_index:02d}"
            image_node.set("href", "assets/slot-placeholder.svg")
            image_node.set(f"{{{XLINK_NS}}}href", "assets/slot-placeholder.svg")
            image_node.set("data-slot-id", auto_slot_id)
            replaced.append({"slide_id": slide_id, "slot_id": auto_slot_id, "kind": "image", "token": f"{{{{IMAGE_AUTO_{auto_image_index:02d}}}}}", "reason": "unresolved_source_image_promoted_to_slot"})
            auto_image_index += 1
        tree.write(svg_path, encoding="utf-8", xml_declaration=False)
    for json_path in output_dir.glob("*.json"):
        try:
            payload = read_json(json_path)
        except (OSError, json.JSONDecodeError):
            continue
        changed = False
        if payload.get("template_id"):
            payload["source_template_id"] = payload["template_id"]
            payload["template_id"] = template_id
            changed = True
        if changed:
            write_json(json_path, payload)
    spec = output_dir / "design_spec.md"
    with spec.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## Promotion status\n\n"
            "This directory is a content-free, source-scoped shell-profile review "
            "candidate. It is not a production template until body variants, "
            "assets, and the fail-closed production gate pass.\n"
        )
    return {"output_dir": str(output_dir), "replaced_slots": replaced, "slot_count": len(replaced)}


def build_asset_manifests(source_workspace: Path, reusable_dir: Path, output_root: Path, template_id: str) -> dict[str, Any]:
    catalog = read_json(source_workspace / "component_catalog.json")
    candidates_path = source_workspace / "component_candidates.json"
    candidate_contract_present = candidates_path.exists()
    candidates_payload = read_json(candidates_path) if candidates_path.exists() else {"candidates": []}
    candidates_by_source_id = {
        str(item.get("source_component_id")): item
        for item in candidates_payload.get("candidates", [])
        if isinstance(item, dict) and item.get("source_component_id")
    }
    output_root.mkdir(parents=True, exist_ok=True)
    components_dir = output_root / "components"
    symbols_dir = output_root / "symbols"
    components_dir.mkdir(parents=True, exist_ok=True)
    symbols_dir.mkdir(parents=True, exist_ok=True)
    page_shell_dir = components_dir / "page_shells"
    page_shell_dir.mkdir(parents=True, exist_ok=True)
    page_shells: list[dict[str, Any]] = []
    for svg_path in sorted(reusable_dir.glob("*.svg")):
        target = page_shell_dir / svg_path.name
        shutil.copy2(svg_path, target)
        page_shells.append(
            {
                "asset_id": f"source_shell/{template_id}/{svg_path.stem}",
                "asset_path": target.relative_to(output_root).as_posix(),
                "asset_status": "renderable_svg",
                "role": next((role for role in ("cover", "toc", "chapter", "content", "ending") if role in svg_path.stem), "content"),
                "editable": True,
            }
        )
    components: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for item in catalog.get("components", []):
        if not isinstance(item, dict):
            continue
        instances = item.get("instances") if isinstance(item.get("instances"), list) else []
        classification = str(item.get("classification") or "unknown")
        if classification not in {"fixed", "hybrid"} or len(instances) < 2:
            if classification in {"fixed", "hybrid"}:
                review_queue.append({"component_id": item.get("component_id"), "reason": "one_off_or_unresolved_repetition", "classification": classification, "source_instances": instances})
            continue
        asset_id = str(item.get("component_id") or "")
        if not asset_id:
            continue
        kind = str(item.get("kind") or "")
        candidate = candidates_by_source_id.get(asset_id, {})
        if candidate_contract_present and candidate.get("status") != "candidate":
            review_queue.append(
                {
                    "component_id": asset_id,
                    "reason": "component_candidate_not_promotable",
                    "candidate_status": candidate.get("status", "missing"),
                }
            )
            continue
        is_symbol = kind in {"shape", "connector"}
        is_component = kind in {"group", "picture"}
        if not (is_symbol or is_component):
            review_queue.append(
                {
                    "component_id": asset_id,
                    "reason": "unsupported_asset_kind",
                    "kind": kind,
                    "source_instances": instances,
                }
            )
            continue
        row = {
            "asset_id": f"{'source_symbol' if is_symbol else 'source_component'}/{template_id}/{asset_id}",
            "component_id": asset_id,
            "classification": classification,
            "kind": kind,
            "style_contract": item.get("style_contract", {}),
            "instance_count": len(instances),
            "source_instances": instances,
            "reuse_policy": "source_scoped_until_visual_promotion",
            "component_candidate": candidate.get("candidate_id") if candidate_contract_present else "legacy_catalog_promotion",
        }
        instance = instances[0] if instances else {}
        object_id = str(instance.get("object_id") or "")
        fragment_path = None
        source_svg, element_id = source_svg_for_object(source_workspace, object_id)
        if source_svg and element_id:
            try:
                source_root = ET.parse(source_svg).getroot()
                source_element = next((node for node in source_root.iter() if node.attrib.get("id") == element_id), None)
                if source_element is not None:
                    fragment_root = ET.Element(f"{{{SVG_NS}}}svg", {"width": "1280", "height": "720", "viewBox": "0 0 1280 720", "data-source-object": object_id})
                    defs = next((node for node in source_root if local_name(node.tag) == "defs"), None)
                    if defs is not None:
                        fragment_root.append(copy.deepcopy(defs))
                    fragment_root.append(copy.deepcopy(source_element))
                    fragment_dir = symbols_dir if is_symbol else components_dir
                    fragment_path = fragment_dir / f"{asset_id}.svg"
                    ET.ElementTree(fragment_root).write(fragment_path, encoding="utf-8", xml_declaration=False)
            except (ET.ParseError, OSError):
                fragment_path = None
        if fragment_path:
            row["asset_path"] = fragment_path.relative_to(output_root).as_posix()
            row["asset_status"] = "extracted_svg_fragment"
            if is_symbol:
                symbols.append(row)
            else:
                components.append(row)
        else:
            review_queue.append(
                {
                    "component_id": asset_id,
                    "reason": "renderable_fragment_not_found",
                    "kind": kind,
                    "source_instances": instances,
                }
            )
    component_manifest = {"schema_version": "easyslides.source_component_assets.v2", "template_id": template_id, "page_shells": page_shells, "components": components, "review_queue": review_queue}
    symbol_manifest = {"schema_version": "easyslides.source_symbol_assets.v2", "template_id": template_id, "symbols": symbols, "review_queue": review_queue}
    write_json(output_root / "component_asset_manifest.json", component_manifest)
    write_json(output_root / "symbol_asset_manifest.json", symbol_manifest)
    write_json(reusable_dir / "asset_promotion.json", {"schema_version": "easyslides.asset_promotion.v1", "template_id": template_id, "component_assets": str(output_root / "component_asset_manifest.json"), "symbol_assets": str(output_root / "symbol_asset_manifest.json"), "promotion_policy": "promotion_gate_verified_source_scoped_candidate"})
    return {"component_asset_manifest": str(output_root / "component_asset_manifest.json"), "symbol_asset_manifest": str(output_root / "symbol_asset_manifest.json"), "component_count": len(components), "symbol_count": len(symbols), "review_queue_count": len(review_queue)}


def require_passed_promotion_report(
    source_workspace: Path,
    promotion_report: dict[str, Any] | None,
) -> dict[str, Any]:
    report = promotion_report
    report_path = source_workspace / "promotion_report.json"
    if report is None and report_path.exists():
        report = read_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("asset promotion requires promotion_report.json")
    if report.get("status") != "pass" or report.get("promotable") is not True:
        raise ValueError(
            "asset promotion blocked: promotion report must have status=pass "
            "and promotable=true"
        )
    return report


def promote(
    source_workspace: Path,
    template_dir: Path,
    *,
    template_id: str,
    reusable_dir: Path | None = None,
    asset_dir: Path | None = None,
    promotion_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verified_report = require_passed_promotion_report(source_workspace, promotion_report)
    slots_payload = read_json(source_workspace / "slot_contracts.json")
    slots_by_slide: dict[str, list[dict[str, Any]]] = {}
    for slot in slots_payload.get("slots", []):
        if isinstance(slot, dict):
            slots_by_slide.setdefault(str(slot.get("source_slide_id") or ""), []).append(slot)
    reusable_dir = reusable_dir or template_dir.parent / f"{template_id}_reusable"
    reusable_template_id = reusable_dir.name
    asset_dir = asset_dir or ROOT / "templates" / "components" / "source_templates" / f"{template_id}_kit"
    reusable = build_reusable_template(template_dir, reusable_dir, slots_by_slide, template_id=reusable_template_id)
    assets = build_asset_manifests(source_workspace, reusable_dir, asset_dir, template_id)
    write_json(
        reusable_dir / "template_status.json",
        {
            "schema_version": "easyslides.template_status.v1",
            "template_id": reusable_template_id,
            "status": "source_scoped_shell_profile_review_candidate",
            "production_eligible": False,
            "promotion_policy": "fail_closed",
            "requires_semantic_rebuild": True,
            "forbidden_production_route": "dom_order_or_source_slide_number",
        },
    )
    result = {
        "status": "source_scoped_shell_profile_review_candidate",
        "production_eligible": False,
        "template_id": template_id,
        "promotion_report_schema": verified_report.get("schema_version"),
        "reusable_template": reusable,
        "assets": assets,
    }
    write_json(source_workspace / "asset_promotion_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a faithful PPTX distillation into reusable template and source-scoped assets.")
    parser.add_argument("source_workspace", type=Path)
    parser.add_argument("template_dir", type=Path)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--reusable-dir", type=Path)
    parser.add_argument("--asset-dir", type=Path)
    parser.add_argument("--promotion-report", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = read_json(args.promotion_report.resolve()) if args.promotion_report else None
    result = promote(args.source_workspace.resolve(), args.template_dir.resolve(), template_id=args.template_id, reusable_dir=args.reusable_dir.resolve() if args.reusable_dir else None, asset_dir=args.asset_dir.resolve() if args.asset_dir else None, promotion_report=report)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Promoted {args.template_id}: {result['reusable_template']['slot_count']} slots, {result['assets']['component_count']} components, {result['assets']['symbol_count']} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
