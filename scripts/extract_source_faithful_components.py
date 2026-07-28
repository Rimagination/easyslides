#!/usr/bin/env python3
"""Extract review-only SVG component fragments directly from a distilled PPTX.

The extractor copies selected source SVG nodes verbatim. It intentionally does
not restyle, simplify, normalize, or replace source text. Original image bytes
are embedded without altering their crop, transform, or layer order so each
review asset remains self-contained.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import mimetypes
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KIT_ROOT = ROOT / "templates" / "components" / "source_templates" / "nsfc_defense_distilled_kit"
DEFAULT_PLAN = KIT_ROOT / "source_faithful_component_plan.json"
DEFAULT_OUTPUT = ROOT / "projects" / "nsfc_source_component_extraction_20260728"
DEFAULT_SOURCE_WORKSPACE = ROOT / "templates" / "reference" / "template_asset_sources" / "nsfc_defense_distilled"
COMPONENT_DIR = KIT_ROOT / "components" / "source_faithful"
CATALOG_PATH = KIT_ROOT / "source_faithful_component_catalog.json"

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)
SCHEMA_VERSION = "easyslides.source_faithful_component_catalog.v1"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _svg_nodes(root: ET.Element, requested_ids: list[str]) -> list[ET.Element]:
    by_id = {str(element.attrib.get("id")): element for element in root.iter() if element.attrib.get("id")}
    missing = [node_id for node_id in requested_ids if node_id not in by_id]
    if missing:
        raise ValueError(f"source SVG is missing selected node(s): {', '.join(missing)}")

    requested = {by_id[node_id] for node_id in requested_ids}
    parent_map = {child: parent for parent in root.iter() for child in parent}
    selected: list[ET.Element] = []
    for element in root.iter():
        if element not in requested:
            continue
        parent = parent_map.get(element)
        has_selected_ancestor = False
        while parent is not None:
            if parent in requested:
                has_selected_ancestor = True
                break
            parent = parent_map.get(parent)
        if not has_selected_ancestor:
            selected.append(element)
    return selected


def _embed_media_assets(root: ET.Element, *, source_dir: Path) -> list[dict[str, Any]]:
    """Embed original image bytes; no crop, color, or image transform is changed."""
    embedded: list[dict[str, Any]] = []
    href_names = ("href", f"{{{XLINK_NS}}}href")
    for element in root.iter():
        for attribute in href_names:
            href = element.attrib.get(attribute)
            if not href or href.startswith(("#", "data:", "http:", "https:")):
                continue
            source_asset = (source_dir / href).resolve()
            if not source_asset.exists():
                raise ValueError(f"missing source asset referenced by SVG: {href} from {source_dir}")
            content = source_asset.read_bytes()
            mime_type = mimetypes.guess_type(source_asset.name)[0] or "application/octet-stream"
            element.attrib[attribute] = f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"
            embedded.append(
                {
                    "source_href": href,
                    "source_file": source_asset.name,
                    "byte_count": len(content),
                    "sha256": _sha256_bytes(content),
                }
            )
    return embedded


def _text_nodes(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == "text"]


def _fragment_svg(
    *,
    source_svg: Path,
    node_ids: list[str],
    bounds: dict[str, Any],
    component_id: str,
    destination: Path,
) -> dict[str, Any]:
    source_root = ET.fromstring(source_svg.read_text(encoding="utf-8"))
    selected = _svg_nodes(source_root, node_ids)
    source_node_xml = [ET.tostring(node, encoding="utf-8") for node in selected]
    source_text_xml = [ET.tostring(node, encoding="utf-8") for node in selected for node in _text_nodes(node)]

    x = float(bounds["x"])
    y = float(bounds["y"])
    width = float(bounds["width"])
    height = float(bounds["height"])
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "version": "1.1",
            "width": f"{width:g}",
            "height": f"{height:g}",
            "viewBox": f"{x:g} {y:g} {width:g} {height:g}",
            "overflow": "hidden",
            "data-component-id": component_id,
            "data-easyslides-source-fidelity": "verbatim_source_svg_nodes",
        },
    )
    source_defs = next((element for element in source_root if _local_name(element.tag) == "defs"), None)
    if source_defs is not None:
        root.append(copy.deepcopy(source_defs))
    for node in selected:
        root.append(copy.deepcopy(node))

    embedded_media = _embed_media_assets(root, source_dir=source_svg.parent)
    expected_visual_node_xml = [
        ET.tostring(node, encoding="utf-8")
        for node in root
        if _local_name(node.tag) != "defs"
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")

    fragment_root = ET.fromstring(destination.read_text(encoding="utf-8"))
    fragment_visual_node_xml = [
        ET.tostring(node, encoding="utf-8")
        for node in fragment_root
        if _local_name(node.tag) != "defs"
    ]
    if expected_visual_node_xml != fragment_visual_node_xml:
        raise ValueError(f"visual node mutation detected while extracting {component_id}")
    fragment_text_xml = [ET.tostring(node, encoding="utf-8") for node in _text_nodes(fragment_root)]
    if source_text_xml != fragment_text_xml:
        raise ValueError(f"text mutation detected while extracting {component_id}")

    return {
        "source_node_count": len(selected),
        "source_node_sha256": _sha256_bytes(b"\n".join(source_node_xml)),
        "source_visual_node_sha256": _sha256_bytes(b"\n".join(expected_visual_node_xml)),
        "fragment_visual_node_sha256": _sha256_bytes(b"\n".join(fragment_visual_node_xml)),
        "source_text_count": len(source_text_xml),
        "source_text_sha256": _sha256_bytes(b"\n".join(source_text_xml)),
        "fragment_text_sha256": _sha256_bytes(b"\n".join(fragment_text_xml)),
        "embedded_media": embedded_media,
        "style_mutation_count": 0,
        "text_mutation_count": 0,
    }


def _render_preview(source: Path, destination: Path) -> None:
    import cairosvg

    destination.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(url=str(source), write_to=str(destination), output_width=1280)


def _build_contact_sheet(records: list[dict[str, Any]], output_dir: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    columns = 3
    card_width = 420
    card_height = 298
    rows = (len(records) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * card_width, rows * card_height), "#F7F7F9")
    draw = ImageDraw.Draw(canvas)
    try:
        title_font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 17)
        detail_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 11)
    except OSError:  # pragma: no cover
        title_font = ImageFont.load_default()
        detail_font = ImageFont.load_default()

    for index, record in enumerate(records):
        row, column = divmod(index, columns)
        x = column * card_width
        y = row * card_height
        draw.rectangle((x + 8, y + 8, x + card_width - 8, y + card_height - 8), fill="#FFFFFF", outline="#D8D2DF", width=1)
        draw.text((x + 20, y + 19), record["display_name"], fill="#1D1A21", font=title_font)
        draw.text((x + 20, y + 46), f"{record['category']} | {record['source_slide']}", fill="#726A78", font=detail_font)
        preview = output_dir / record["preview_path"]
        with Image.open(preview) as image:
            image = image.convert("RGB")
            image.thumbnail((card_width - 36, card_height - 82), Image.Resampling.LANCZOS)
            canvas.paste(image, (x + (card_width - image.width) // 2, y + 68 + (card_height - 76 - image.height) // 2))

    contact_path = output_dir / "source_faithful_component_contact_sheet.png"
    canvas.save(contact_path)
    return contact_path


def _render_html(records: list[dict[str, Any]]) -> str:
    return _render_html_clean(records)


def _render_html_legacy(records: list[dict[str, Any]]) -> str:
    cards = []
    for record in records:
        cards.append(
            f'''<article class="component" data-category="{html.escape(record["category"], quote=True)}">
  <div class="head"><div><span>{html.escape(record["category"])}</span><h2>{html.escape(record["display_name"])}</h2></div><small>{html.escape(record["source_slide"])}</small></div>
  <img src="{html.escape(record["preview_path"], quote=True)}" alt="{html.escape(record["display_name"], quote=True)}">
  <dl><div><dt>源节点</dt><dd>{html.escape(', '.join(record["source_node_ids"]))}</dd></div><div><dt>边界</dt><dd>{record["bounds"]["width"]} × {record["bounds"]["height"]}</dd></div><div><dt>说明</dt><dd>{html.escape(record["description"])}</dd></div></dl>
</article>'''
        )
    categories = sorted({record["category"] for record in records})
    filters = "".join(f'<button data-category="{html.escape(category, quote=True)}">{html.escape(category)}</button>' for category in categories)
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>国自然答辩·原样组件提取</title>
<style>
:root{{--ink:#1d1a21;--muted:#706a76;--line:#ded7e5;--purple:#751497;--paper:#f8f7fa}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei","Aptos","Segoe UI",sans-serif}}header{{position:sticky;top:0;z-index:2;padding:18px 4vw;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}}h1{{margin:0;font-size:23px}}header p{{margin:6px 0 0;color:var(--muted);font-size:13px}}main{{max-width:1500px;margin:auto;padding:20px 4vw 56px}}.filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}}button{{padding:5px 10px;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--muted);font:inherit;font-size:12px;cursor:pointer}}button.active{{background:var(--purple);border-color:var(--purple);color:#fff}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.component{{background:#fff;border:1px solid var(--line);border-radius:6px;overflow:hidden}}.head{{display:flex;justify-content:space-between;gap:10px;min-height:65px;padding:12px 14px;border-bottom:1px solid var(--line)}}.head span{{color:var(--purple);font-size:11px;font-weight:800}}h2{{margin:3px 0 0;font-size:16px}}small{{color:var(--muted);font-size:11px}}img{{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#fff;border-bottom:1px solid var(--line)}}dl{{display:grid;gap:7px;margin:0;padding:12px 14px;font-size:11px}}dl div{{display:grid;grid-template-columns:43px 1fr;gap:7px}}dt{{color:var(--muted)}}dd{{margin:0;line-height:1.5}}.hidden{{display:none}}@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{header{{position:static}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>国自然答辩·原样组件提取</h1><p>直接裁切源 SVG 节点；不改颜色、字体、字号、边框、阴影、裁剪或图层顺序。</p></header><main><div class="filters"><button class="active" data-category="all">全部</button>{filters}</div><section class="grid">{"".join(cards)}</section></main><script>const buttons=[...document.querySelectorAll('button')],cards=[...document.querySelectorAll('.component')];buttons.forEach(button=>button.addEventListener('click',()=>{{const category=button.dataset.category;buttons.forEach(item=>item.classList.toggle('active',item===button));cards.forEach(card=>card.classList.toggle('hidden',category!=='all'&&card.dataset.category!==category));}}));</script></body></html>\n'''


def _render_html_clean(records: list[dict[str, Any]]) -> str:
    cards = []
    for record in records:
        cards.append(
            f'''<article class="component" data-category="{html.escape(record["category"], quote=True)}">
  <div class="head"><div><span>{html.escape(record["category"])}</span><h2>{html.escape(record["display_name"])}</h2></div><small>{html.escape(record["source_slide"])}</small></div>
  <img src="{html.escape(record["preview_path"], quote=True)}" alt="{html.escape(record["display_name"], quote=True)}">
  <dl><div><dt>源节点</dt><dd>{html.escape(', '.join(record["source_node_ids"]))}</dd></div><div><dt>边界</dt><dd>{record["bounds"]["width"]} x {record["bounds"]["height"]}</dd></div><div><dt>说明</dt><dd>{html.escape(record["description"])}</dd></div></dl>
</article>'''
        )
    categories = sorted({record["category"] for record in records})
    filters = "".join(
        f'<button data-category="{html.escape(category, quote=True)}">{html.escape(category)}</button>'
        for category in categories
    )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>国自然答辩：原样组件提取</title>
<style>
:root{{--ink:#1d1a21;--muted:#706a76;--line:#ded7e5;--purple:#751497;--paper:#f8f7fa}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei","Aptos","Segoe UI",sans-serif}}header{{position:sticky;top:0;z-index:2;padding:18px 4vw;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}}h1{{margin:0;font-size:23px}}header p{{margin:6px 0 0;color:var(--muted);font-size:13px}}main{{max-width:1500px;margin:auto;padding:20px 4vw 56px}}.filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}}button{{padding:5px 10px;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--muted);font:inherit;font-size:12px;cursor:pointer}}button.active{{background:var(--purple);border-color:var(--purple);color:#fff}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.component{{background:#fff;border:1px solid var(--line);border-radius:6px;overflow:hidden}}.head{{display:flex;justify-content:space-between;gap:10px;min-height:65px;padding:12px 14px;border-bottom:1px solid var(--line)}}.head span{{color:var(--purple);font-size:11px;font-weight:800}}h2{{margin:3px 0 0;font-size:16px}}small{{color:var(--muted);font-size:11px}}img{{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#fff;border-bottom:1px solid var(--line)}}dl{{display:grid;gap:7px;margin:0;padding:12px 14px;font-size:11px}}dl div{{display:grid;grid-template-columns:43px 1fr;gap:7px}}dt{{color:var(--muted)}}dd{{margin:0;line-height:1.5}}.hidden{{display:none}}@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{header{{position:static}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>国自然答辩：原样组件提取</h1><p>直接裁切源 SVG 节点；不改颜色、字体、字号、边框、阴影、裁剪或图层顺序。</p></header><main><div class="filters"><button class="active" data-category="all">全部</button>{filters}</div><section class="grid">{"".join(cards)}</section></main><script>const buttons=[...document.querySelectorAll('button')],cards=[...document.querySelectorAll('.component')];buttons.forEach(button=>button.addEventListener('click',()=>{{const category=button.dataset.category;buttons.forEach(item=>item.classList.toggle('active',item===button));cards.forEach(card=>card.classList.toggle('hidden',category!=='all'&&card.dataset.category!==category));}}));</script></body></html>\n'''


def extract_source_faithful_components(
    *,
    plan_path: Path = DEFAULT_PLAN,
    source_workspace: Path = DEFAULT_SOURCE_WORKSPACE,
    component_dir: Path = COMPONENT_DIR,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    plan = _read_json(plan_path)
    source_dir = source_workspace / str((plan.get("source") or {}).get("svg_dir") or "svg-flat")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source SVG directory not found: {source_dir}")
    components = plan.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("source faithful component plan must contain components")

    if component_dir.exists():
        shutil.rmtree(component_dir)
    if output_dir.exists():
        for child in (output_dir / "faithful_previews", output_dir / "source_faithful_component_contact_sheet.png"):
            if child.is_dir():
                shutil.rmtree(child)
            elif child.exists():
                child.unlink()
    component_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for entry in components:
        if not isinstance(entry, dict):
            continue
        component_id = str(entry["component_id"])
        source_slide = str(entry["source_slide"])
        source_svg = source_dir / f"{source_slide}.svg"
        if not source_svg.is_file():
            raise FileNotFoundError(f"source slide SVG not found: {source_svg}")
        destination = component_dir / f"{component_id}.svg"
        extraction = _fragment_svg(
            source_svg=source_svg,
            node_ids=[str(value) for value in entry["source_node_ids"]],
            bounds=dict(entry["bounds"]),
            component_id=component_id,
            destination=destination,
        )
        preview_path = output_dir / "faithful_previews" / f"{component_id}.png"
        _render_preview(destination, preview_path)
        records.append(
            {
                "asset_id": f"source_faithful/nsfc_defense_distilled/{component_id}",
                "component_id": component_id,
                "display_name": str(entry["display_name"]),
                "category": str(entry["category"]),
                "description": str(entry["description"]),
                "source_slide": source_slide,
                "source_svg": source_svg.relative_to(ROOT).as_posix(),
                "source_node_ids": [str(value) for value in entry["source_node_ids"]],
                "bounds": dict(entry["bounds"]),
                "asset_path": destination.relative_to(ROOT).as_posix(),
                "preview_path": preview_path.relative_to(output_dir).as_posix(),
                "asset_status": "source_faithful_review_only",
                "editable_slots": [],
                "fidelity": extraction,
            }
        )

    source_manifest = _read_json(source_workspace / "manifest.json")
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "template_id": str(plan.get("template_id") or ""),
        "extraction_mode": str(plan.get("extraction_mode") or ""),
        "status": "pass",
        "component_count": len(records),
        "source": {
            "pptx": (source_manifest.get("source") or {}).get("pptx"),
            "source_workspace": source_workspace.relative_to(ROOT).as_posix(),
            "source_svg_dir": source_dir.relative_to(ROOT).as_posix(),
        },
        "fidelity_constraints": list(plan.get("fidelity_constraints") or []),
        "components": records,
    }
    _write_json(CATALOG_PATH, catalog)
    _write_json(output_dir / "source_faithful_component_manifest.json", catalog)
    (output_dir / "source_faithful_component_gallery.html").write_text(_render_html(records), encoding="utf-8")
    contact_path = _build_contact_sheet(records, output_dir)
    _write_json(
        output_dir / "source_faithful_component_fidelity_report.json",
        {
            "schema_version": "easyslides.source_faithful_component_fidelity_report.v1",
            "status": "pass",
            "component_count": len(records),
            "style_mutation_count": sum(int(record["fidelity"]["style_mutation_count"]) for record in records),
            "text_mutation_count": sum(int(record["fidelity"]["text_mutation_count"]) for record in records),
            "embedded_media_count": sum(len(record["fidelity"]["embedded_media"]) for record in records),
            "contact_sheet": contact_path.name,
            "components": [
                {
                    "component_id": record["component_id"],
                    "source_node_sha256": record["fidelity"]["source_node_sha256"],
                    "source_visual_node_sha256": record["fidelity"]["source_visual_node_sha256"],
                    "fragment_visual_node_sha256": record["fidelity"]["fragment_visual_node_sha256"],
                    "source_text_sha256": record["fidelity"]["source_text_sha256"],
                    "fragment_text_sha256": record["fidelity"]["fragment_text_sha256"],
                }
                for record in records
            ],
        },
    )
    return catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract source-faithful components from the distilled NSFC defense source.")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--source-workspace", type=Path, default=DEFAULT_SOURCE_WORKSPACE)
    parser.add_argument("--component-dir", type=Path, default=COMPONENT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = extract_source_faithful_components(
        plan_path=args.plan,
        source_workspace=args.source_workspace,
        component_dir=args.component_dir,
        output_dir=args.out,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Source-faithful components: {result['status']} ({result['component_count']} component(s))")
        print(args.out / "source_faithful_component_gallery.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
