#!/usr/bin/env python3
"""Build a factual object graph from a PowerPoint OOXML package.

The source graph is the first stage of PPTX distillation. It records what is
present in the package (parts, relationships, objects, geometry, text, and
media references) without deciding whether an object is fixed chrome,
replaceable content, or a reusable component.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from template_import.manifest import (  # noqa: E402
    IMAGE_REL,
    LAYOUT_REL,
    MASTER_REL,
    NS,
    SLIDE_REL,
    THEME_REL,
    emu_to_pixels,
    load_xml_from_zip,
    parse_relationships,
    parse_theme,
    resolve_first_rel,
)


GRAPH_SCHEMA = "easyslides.source_graph.v1"
MANIFEST_SCHEMA = "easyslides.distill_manifest.v1"
SUPPORTED_MODES = ["mirror", "layout", "design-system"]
CLASSIFICATION_STATES = ["fixed", "replaceable", "hybrid", "unknown"]
VISUAL_NODE_TAGS = {"sp", "pic", "graphicFrame", "cxnSp", "grpSp"}
REL_ATTRS = {
    f"{{{NS['r']}}}id": "id",
    f"{{{NS['r']}}}embed": "embed",
    f"{{{NS['r']}}}link": "link",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _tag_name(node: ET.Element | None) -> str:
    if node is None or not isinstance(node.tag, str):
        return ""
    return node.tag.rsplit("}", 1)[-1]


def _int_attr(node: ET.Element | None, name: str, default: int = 0) -> int:
    if node is None:
        return default
    try:
        return int(node.attrib.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _bool_attr(node: ET.Element | None, name: str) -> bool:
    return bool(node is not None and node.attrib.get(name) in {"1", "true", "True"})


def _size_record(width_emu: int, height_emu: int) -> dict[str, int]:
    return {
        "width_emu": width_emu,
        "height_emu": height_emu,
        "width_px": emu_to_pixels(width_emu),
        "height_px": emu_to_pixels(height_emu),
    }


def _geometry(node: ET.Element) -> dict[str, Any] | None:
    xfrm = None
    for path in ("p:spPr/a:xfrm", "p:grpSpPr/a:xfrm", "p:xfrm"):
        xfrm = node.find(path, NS)
        if xfrm is not None:
            break
    if xfrm is None:
        return None

    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    x = _int_attr(off, "x")
    y = _int_attr(off, "y")
    width = _int_attr(ext, "cx")
    height = _int_attr(ext, "cy")
    return {
        "x_emu": x,
        "y_emu": y,
        "width_emu": width,
        "height_emu": height,
        "x": emu_to_pixels(x),
        "y": emu_to_pixels(y),
        "width": emu_to_pixels(width),
        "height": emu_to_pixels(height),
        "center_y_emu": y + height / 2,
        "center_y": emu_to_pixels(y + height // 2),
        "rotation_units": _int_attr(xfrm, "rot"),
        "rotation_degrees": round(_int_attr(xfrm, "rot") / 60000, 4),
        "flip_h": _bool_attr(xfrm, "flipH"),
        "flip_v": _bool_attr(xfrm, "flipV"),
    }


def _color_signature(node: ET.Element | None) -> dict[str, str] | None:
    if node is None:
        return None
    for child in list(node):
        kind = _tag_name(child)
        if kind == "srgbClr" and child.attrib.get("val"):
            return {"kind": "srgb", "value": f"#{child.attrib['val']}"}
        if kind == "schemeClr" and child.attrib.get("val"):
            return {"kind": "scheme", "value": child.attrib["val"]}
        if kind in {"prstClr", "sysClr"}:
            value = child.attrib.get("val") or child.attrib.get("lastClr")
            if value:
                return {"kind": kind, "value": value}
    return None


def _fill_signature(sp_pr: ET.Element | None) -> dict[str, Any] | None:
    if sp_pr is None:
        return None
    for child in list(sp_pr):
        kind = _tag_name(child)
        if kind in {"noFill", "gradFill", "blipFill", "pattFill"}:
            return {"kind": kind}
        if kind == "solidFill":
            return {"kind": kind, "color": _color_signature(child)}
    return None


def _line_signature(sp_pr: ET.Element | None) -> dict[str, Any] | None:
    if sp_pr is None:
        return None
    line = sp_pr.find("a:ln", NS)
    if line is None:
        return None
    return {
        "width_emu": _int_attr(line, "w"),
        "fill": _fill_signature(line),
        "cap": line.attrib.get("cap"),
        "dash": line.find("a:prstDash", NS).attrib.get("val")
        if line.find("a:prstDash", NS) is not None
        else None,
    }


def _text_style(node: ET.Element) -> dict[str, Any]:
    style: dict[str, Any] = {}
    rpr = node.find(".//a:rPr", NS)
    if rpr is None:
        rpr = node.find(".//a:endParaRPr", NS)
    if rpr is None:
        return style
    if rpr.attrib.get("sz"):
        try:
            style["font_size_pt"] = round(int(rpr.attrib["sz"]) / 100, 2)
        except ValueError:
            pass
    for key in ("b", "i", "u"):
        if rpr.attrib.get(key) in {"1", "true", "True"}:
            style[{"b": "bold", "i": "italic", "u": "underline"}[key]] = True
    for tag, output_key in (("latin", "latin_font"), ("ea", "east_asia_font"), ("cs", "complex_script_font")):
        child = rpr.find(f"a:{tag}", NS)
        if child is not None and child.attrib.get("typeface"):
            style[output_key] = child.attrib["typeface"]
    color = _color_signature(rpr.find("a:solidFill", NS))
    if color:
        style["color"] = color
    return style


def _text_content(node: ET.Element) -> dict[str, Any] | None:
    paragraphs: list[str] = []
    for paragraph in node.findall(".//a:p", NS):
        value = "".join(item.text or "" for item in paragraph.findall(".//a:t", NS)).strip()
        if value:
            paragraphs.append(value)
    if not paragraphs:
        return None
    plain = "\n".join(paragraphs)
    return {
        "plain": plain,
        "paragraphs": paragraphs,
        "char_count": len(plain),
        "line_count": len(paragraphs),
    }


def _text_layout(node: ET.Element) -> dict[str, Any] | None:
    body_pr = node.find("p:txBody/a:bodyPr", NS)
    if body_pr is None:
        return None
    layout: dict[str, Any] = {
        "vertical_anchor": body_pr.attrib.get("anchor"),
        "wrap": body_pr.attrib.get("wrap"),
        "rotation": body_pr.attrib.get("vert"),
    }
    for key in ("lIns", "tIns", "rIns", "bIns"):
        if key in body_pr.attrib:
            try:
                layout[f"{key}_emu"] = int(body_pr.attrib[key])
            except ValueError:
                layout[f"{key}_emu"] = body_pr.attrib[key]
    return layout


def _placeholder(node: ET.Element) -> dict[str, Any] | None:
    ph = node.find("p:nvSpPr/p:nvPr/p:ph", NS)
    if ph is None:
        return None
    return {
        "type": ph.attrib.get("type"),
        "idx": ph.attrib.get("idx"),
        "size": ph.attrib.get("sz"),
        "orient": ph.attrib.get("orient"),
    }


def _name_and_shape_id(node: ET.Element) -> tuple[str | None, str | None]:
    c_nv_pr = node.find(".//p:cNvPr", NS)
    if c_nv_pr is None:
        return None, None
    return c_nv_pr.attrib.get("name"), c_nv_pr.attrib.get("id")


def _node_style(node: ET.Element) -> dict[str, Any]:
    sp_pr = node.find("p:spPr", NS)
    if sp_pr is None:
        sp_pr = node.find("p:grpSpPr", NS)
    style: dict[str, Any] = {}
    if sp_pr is not None:
        preset = sp_pr.find("a:prstGeom", NS)
        if preset is not None and preset.attrib.get("prst"):
            style["geometry_preset"] = preset.attrib["prst"]
        fill = _fill_signature(sp_pr)
        if fill:
            style["fill"] = fill
        line = _line_signature(sp_pr)
        if line:
            style["line"] = line
    text_style = _text_style(node)
    if text_style:
        style["text"] = text_style
    return style


def _node_relationships(
    node: ET.Element,
    rels: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    references: list[dict[str, Any]] = []
    assets: list[str] = []
    seen: set[tuple[str, str]] = set()
    for element in node.iter():
        for attr_name, attr_value in element.attrib.items():
            label = REL_ATTRS.get(attr_name)
            if not label or attr_value not in rels:
                continue
            key = (label, attr_value)
            if key in seen:
                continue
            seen.add(key)
            rel = rels[attr_value]
            references.append(
                {
                    "attribute": label,
                    "id": attr_value,
                    "type": rel["type"],
                    "target": rel["target"],
                }
            )
            if rel["type"] == IMAGE_REL:
                assets.append(rel["target"])
    return references, assets


def _node_kind(node: ET.Element) -> str:
    return {
        "sp": "shape",
        "pic": "picture",
        "graphicFrame": "graphic_frame",
        "cxnSp": "connector",
        "grpSp": "group",
    }.get(_tag_name(node), "unknown")


def _visual_children(container: ET.Element) -> list[ET.Element]:
    return [child for child in list(container) if _tag_name(child) in VISUAL_NODE_TAGS]


def _collect_nodes(
    root: ET.Element | None,
    part_path: str,
    rels: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if root is None:
        return [], []
    tree = root.find("p:cSld/p:spTree", NS)
    if tree is None:
        return [], []

    nodes: list[dict[str, Any]] = []
    assets: list[str] = []

    def visit(container: ET.Element, parent_id: str | None, prefix: str) -> None:
        for order, child in enumerate(_visual_children(container)):
            kind = _node_kind(child)
            name, shape_id = _name_and_shape_id(child)
            path = f"{prefix}/{order}" if prefix else str(order)
            object_id = f"{part_path}::{kind}:{shape_id or path}"
            rel_refs, rel_assets = _node_relationships(child, rels)
            assets.extend(rel_assets)
            node: dict[str, Any] = {
                "object_id": object_id,
                "part_path": part_path,
                "kind": kind,
                "shape_id": shape_id,
                "name": name,
                "order": order,
                "tree_path": path,
                "parent_object_id": parent_id,
                "geometry": _geometry(child),
                "placeholder": _placeholder(child),
                "text": _text_content(child),
                "text_layout": _text_layout(child),
                "style": _node_style(child),
                "relationships": rel_refs,
                "classification": "unknown",
                "classification_basis": "phase_1_factual_graph_only",
            }
            nodes.append(node)
            if kind == "group":
                visit(child, object_id, path)

    visit(tree, None, "")
    return nodes, sorted(set(assets))


def _relationship_records(rels: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"id": rel_id, "type": value["type"], "target": value["target"]}
        for rel_id, value in sorted(rels.items())
    ]


def _part_record(
    *,
    zf: zipfile.ZipFile,
    part_path: str,
    part_id: str,
    role: str,
    index: int,
    parent_id: str | None,
    theme_path: str | None,
    used_by_slides: list[int],
) -> tuple[dict[str, Any], set[str]]:
    root = load_xml_from_zip(zf, part_path)
    rels = parse_relationships(zf, part_path)
    nodes, node_assets = _collect_nodes(root, part_path, rels)
    background_target = None
    background = root.find("p:cSld/p:bg", NS) if root is not None else None
    if background is not None:
        blip = background.find(".//a:blip", NS)
        if blip is not None:
            rel_id = blip.attrib.get(f"{{{NS['r']}}}embed")
            if rel_id in rels and rels[rel_id]["type"] == IMAGE_REL:
                background_target = rels[rel_id]["target"]
    references = _relationship_records(rels)
    assets = set(node_assets)
    if background_target:
        assets.add(background_target)
    record = {
        "id": part_id,
        "role": role,
        "index": index,
        "path": part_path,
        "name": PurePosixPath(part_path).name,
        "parent_id": parent_id,
        "theme_path": theme_path,
        "used_by_slides": used_by_slides,
        "evidence_level": "native_ooxml",
        "relationships": references,
        "background": {
            "asset_target": background_target,
            "relationship_type": IMAGE_REL if background_target else None,
        },
        "nodes": nodes,
        "node_count": len(nodes),
        "text_node_count": sum(1 for node in nodes if node.get("text")),
        "image_node_count": sum(1 for node in nodes if node["kind"] == "picture"),
    }
    return record, assets


def _presentation_parts(
    zf: zipfile.ZipFile,
) -> tuple[ET.Element, dict[str, dict[str, str]], list[str], list[str]]:
    root = load_xml_from_zip(zf, "ppt/presentation.xml")
    if root is None:
        raise ValueError("Invalid PPTX: missing ppt/presentation.xml")
    rels = parse_relationships(zf, "ppt/presentation.xml")
    slides: list[str] = []
    masters: list[str] = []
    for item in root.findall("p:sldIdLst/p:sldId", NS):
        rel = rels.get(item.attrib.get(f"{{{NS['r']}}}id", ""))
        if rel and rel["type"] == SLIDE_REL and rel["target"] not in slides:
            slides.append(rel["target"])
    for item in root.findall("p:sldMasterIdLst/p:sldMasterId", NS):
        rel = rels.get(item.attrib.get(f"{{{NS['r']}}}id", ""))
        if rel and rel["type"] == MASTER_REL and rel["target"] not in masters:
            masters.append(rel["target"])
    return root, rels, slides, masters


def _slide_lineage(
    zf: zipfile.ZipFile,
    slide_path: str,
) -> tuple[str | None, str | None]:
    slide_rels = parse_relationships(zf, slide_path)
    layout_path = resolve_first_rel(slide_rels, LAYOUT_REL)
    if not layout_path:
        return None, None
    layout_rels = parse_relationships(zf, layout_path)
    return layout_path, resolve_first_rel(layout_rels, MASTER_REL)


def _canvas(root: ET.Element) -> dict[str, int]:
    size = root.find("p:sldSz", NS)
    return _size_record(_int_attr(size, "cx"), _int_attr(size, "cy"))


def _asset_records(
    zf: zipfile.ZipFile,
    references: dict[str, set[str]],
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for info in sorted(zf.infolist(), key=lambda item: item.filename):
        if not info.filename.startswith("ppt/media/") or info.is_dir():
            continue
        data = zf.read(info.filename)
        assets.append(
            {
                "part_path": info.filename,
                "name": PurePosixPath(info.filename).name,
                "extension": PurePosixPath(info.filename).suffix.lower().lstrip("."),
                "content_type": mimetypes.guess_type(info.filename)[0],
                "compression_method": info.compress_type,
                "size_bytes": len(data),
                "sha256": _sha256_bytes(data),
                "referenced_by": sorted(references.get(info.filename, set())),
            }
        )
    return assets


def build_source_graph(pptx_path: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse a real PPTX package into the Phase 1 factual source graph."""
    pptx_path = Path(pptx_path).resolve()
    if not pptx_path.exists():
        raise FileNotFoundError(pptx_path)

    with zipfile.ZipFile(pptx_path, "r") as zf:
        presentation_root, presentation_rels, slide_paths, master_paths = _presentation_parts(zf)

        layout_paths: list[str] = []
        master_theme_paths: dict[str, str | None] = {}
        for master_path in master_paths:
            master_root = load_xml_from_zip(zf, master_path)
            master_rels = parse_relationships(zf, master_path)
            master_theme_paths[master_path] = resolve_first_rel(master_rels, THEME_REL)
            if master_root is None:
                continue
            for layout_id in master_root.findall("p:sldLayoutIdLst/p:sldLayoutId", NS):
                rel = master_rels.get(layout_id.attrib.get(f"{{{NS['r']}}}id", ""))
                if rel and rel["type"] == LAYOUT_REL and rel["target"] not in layout_paths:
                    layout_paths.append(rel["target"])

        slide_lineage: dict[str, tuple[str | None, str | None]] = {}
        for slide_path in slide_paths:
            layout_path, master_path = _slide_lineage(zf, slide_path)
            slide_lineage[slide_path] = (layout_path, master_path)
            if layout_path and layout_path not in layout_paths:
                layout_paths.append(layout_path)
            if master_path and master_path not in master_paths:
                master_paths.append(master_path)
                master_rels = parse_relationships(zf, master_path)
                master_theme_paths[master_path] = resolve_first_rel(master_rels, THEME_REL)

        master_ids = {path: f"master-{index:02d}" for index, path in enumerate(master_paths, 1)}
        layout_ids = {path: f"layout-{index:02d}" for index, path in enumerate(layout_paths, 1)}
        slide_ids = {path: f"slide-{index:02d}" for index, path in enumerate(slide_paths, 1)}

        used_by_layout: defaultdict[str, list[int]] = defaultdict(list)
        used_by_master: defaultdict[str, list[int]] = defaultdict(list)
        for index, slide_path in enumerate(slide_paths, 1):
            layout_path, master_path = slide_lineage[slide_path]
            if layout_path:
                used_by_layout[layout_path].append(index)
            if master_path:
                used_by_master[master_path].append(index)

        part_assets: dict[str, set[str]] = defaultdict(set)
        masters: list[dict[str, Any]] = []
        for index, part_path in enumerate(master_paths, 1):
            record, assets = _part_record(
                zf=zf,
                part_path=part_path,
                part_id=master_ids[part_path],
                role="master",
                index=index,
                parent_id=None,
                theme_path=master_theme_paths.get(part_path),
                used_by_slides=used_by_master[part_path],
            )
            masters.append(record)
            part_assets[part_path].update(assets)

        layouts: list[dict[str, Any]] = []
        layout_master_path: dict[str, str | None] = {}
        for layout_path in layout_paths:
            layout_master_path[layout_path] = None
            layout_rels = parse_relationships(zf, layout_path)
            parent_path = resolve_first_rel(layout_rels, MASTER_REL)
            layout_master_path[layout_path] = parent_path
        for index, part_path in enumerate(layout_paths, 1):
            record, assets = _part_record(
                zf=zf,
                part_path=part_path,
                part_id=layout_ids[part_path],
                role="layout",
                index=index,
                parent_id=master_ids.get(layout_master_path.get(part_path) or ""),
                theme_path=master_theme_paths.get(layout_master_path.get(part_path) or ""),
                used_by_slides=used_by_layout[part_path],
            )
            layouts.append(record)
            part_assets[part_path].update(assets)

        slides: list[dict[str, Any]] = []
        for index, part_path in enumerate(slide_paths, 1):
            layout_path, master_path = slide_lineage[part_path]
            record, assets = _part_record(
                zf=zf,
                part_path=part_path,
                part_id=slide_ids[part_path],
                role="slide",
                index=index,
                parent_id=layout_ids.get(layout_path or ""),
                theme_path=master_theme_paths.get(master_path or ""),
                used_by_slides=[index],
            )
            record["layout_id"] = layout_ids.get(layout_path or "")
            record["master_id"] = master_ids.get(master_path or "")
            record["layout_path"] = layout_path
            record["master_path"] = master_path
            slides.append(record)
            part_assets[part_path].update(assets)

        asset_references: defaultdict[str, set[str]] = defaultdict(set)
        for part_path, targets in part_assets.items():
            part_id = (
                slide_ids.get(part_path)
                or layout_ids.get(part_path)
                or master_ids.get(part_path)
                or part_path
            )
            for target in targets:
                asset_references[target].add(part_id)
        assets = _asset_records(zf, asset_references)

        theme_records: list[dict[str, Any]] = []
        seen_themes: set[str] = set()
        for theme_path in master_theme_paths.values():
            if not theme_path or theme_path in seen_themes:
                continue
            seen_themes.add(theme_path)
            theme_records.append(
                {
                    "path": theme_path,
                    "theme": parse_theme(load_xml_from_zip(zf, theme_path)),
                }
            )

        canvas = _canvas(presentation_root)
        if manifest and isinstance(manifest.get("slideSize"), dict):
            manifest_size = manifest["slideSize"]
            canvas["width_px"] = int(manifest_size.get("width_px") or canvas["width_px"])
            canvas["height_px"] = int(manifest_size.get("height_px") or canvas["height_px"])
        return {
            "schema_version": GRAPH_SCHEMA,
            "status": "ready",
            "source": {
                "pptx": str(pptx_path),
                "name": pptx_path.name,
                "sha256": _sha256_file(pptx_path),
                "package_part_count": len(zf.namelist()),
                "manifest_available": manifest is not None,
            },
            "canvas": canvas,
            "presentation": {
                "path": "ppt/presentation.xml",
                "relationships": _relationship_records(presentation_rels),
            },
            "themes": theme_records,
            "parts": {"masters": masters, "layouts": layouts, "slides": slides},
            "assets": assets,
            "counts": {
                "masters": len(masters),
                "layouts": len(layouts),
                "slides": len(slides),
                "nodes": sum(item["node_count"] for item in masters + layouts + slides),
                "assets": len(assets),
            },
            "invariants": {
                "graph_is_factual": True,
                "semantic_inference": "deferred_to_phase_2",
                "classification_states": CLASSIFICATION_STATES,
                "supported_modes": SUPPORTED_MODES,
                "vertical_alignment": {
                    "rule": "hard",
                    "eligible_text_center_y_equals_container_center_y": True,
                    "optical_exceptions_require_explicit_flag": True,
                },
            },
        }


def build_manifest_graph(manifest: dict[str, Any], source_pptx: Path) -> dict[str, Any]:
    """Create a manifest-only graph for legacy/reference workspaces.

    This keeps old fixture workspaces inspectable while making the reduced
    evidence level explicit. A real PPTX always takes the OOXML path above.
    """
    slides: list[dict[str, Any]] = []
    layouts: list[dict[str, Any]] = []
    masters: list[dict[str, Any]] = []
    layout_ids: dict[str, str] = {}
    master_ids: dict[str, str] = {}
    for index, item in enumerate(manifest.get("masters") or [], 1):
        path = str(item.get("path") or f"manifest-master-{index}")
        master_ids[path] = f"master-{index:02d}"
        masters.append({
            "id": master_ids[path], "role": "master", "index": index, "path": path,
            "name": item.get("name") or PurePosixPath(path).name, "parent_id": None,
            "theme_path": item.get("themePath"), "used_by_slides": item.get("usedBySlides") or [],
            "relationships": [], "background": {"asset_target": None, "relationship_type": None},
            "nodes": [], "node_count": int(item.get("shapeCount") or 0),
            "text_node_count": int(item.get("textCount") or 0), "image_node_count": 0,
            "evidence_level": "manifest_only",
        })
    for index, item in enumerate(manifest.get("layouts") or [], 1):
        path = str(item.get("path") or f"manifest-layout-{index}")
        layout_ids[path] = f"layout-{index:02d}"
        parent_path = str(item.get("parentPath") or "")
        layouts.append({
            "id": layout_ids[path], "role": "layout", "index": index, "path": path,
            "name": item.get("name") or PurePosixPath(path).name,
            "parent_id": master_ids.get(parent_path), "theme_path": item.get("themePath"),
            "used_by_slides": item.get("usedBySlides") or [], "relationships": [],
            "background": {"asset_target": None, "relationship_type": None}, "nodes": [],
            "node_count": int(item.get("shapeCount") or 0), "text_node_count": int(item.get("textCount") or 0),
            "image_node_count": len(item.get("imageAssets") or []),
            "placeholders": item.get("placeholders") or [], "evidence_level": "manifest_only",
        })
    size = manifest.get("slideSize") if isinstance(manifest.get("slideSize"), dict) else {}
    canvas = {
        "width_emu": int(size.get("width_emu") or 0), "height_emu": int(size.get("height_emu") or 0),
        "width_px": int(size.get("width_px") or size.get("width") or 1280),
        "height_px": int(size.get("height_px") or size.get("height") or 720),
    }
    for index, item in enumerate(manifest.get("slides") or [], 1):
        slide_path = str(item.get("slidePath") or f"manifest-slide-{index}")
        layout_path = item.get("layoutPath")
        master_path = item.get("masterPath")
        slides.append({
            "id": f"slide-{index:02d}", "role": "slide", "index": int(item.get("index") or index),
            "path": slide_path, "name": item.get("name") or PurePosixPath(slide_path).name,
            "parent_id": layout_ids.get(str(layout_path or "")), "theme_path": None,
            "used_by_slides": [int(item.get("index") or index)], "relationships": [],
            "background": {"asset_target": item.get("backgroundAsset"), "relationship_type": IMAGE_REL if item.get("backgroundAsset") else None},
            "nodes": [], "node_count": int(item.get("shapeCount") or 0),
            "text_node_count": int(item.get("textCount") or len(item.get("textSamples") or [])),
            "image_node_count": len(item.get("imageAssets") or []), "layout_id": layout_ids.get(str(layout_path or "")),
            "master_id": master_ids.get(str(master_path or "")), "layout_path": layout_path,
            "master_path": master_path, "evidence_level": "manifest_only",
        })
    return {
        "schema_version": GRAPH_SCHEMA,
        "status": "manifest_only",
        "source": {
            "pptx": str(Path(source_pptx).resolve()), "name": Path(source_pptx).name,
            "sha256": None, "package_part_count": None, "manifest_available": True,
            "reason": "source_pptx_unavailable_or_legacy_reference_workspace",
        },
        "canvas": canvas,
        "presentation": {"path": None, "relationships": []}, "themes": [{"path": None, "theme": manifest.get("theme") or {}}],
        "parts": {"masters": masters, "layouts": layouts, "slides": slides},
        "assets": [{"part_path": None, "name": name, "extension": PurePosixPath(name).suffix.lower().lstrip("."),
                     "content_type": None, "size_bytes": None, "sha256": None, "referenced_by": []}
                    for name in (manifest.get("assets", {}).get("allAssets") or [])],
        "counts": {"masters": len(masters), "layouts": len(layouts), "slides": len(slides),
                   "nodes": sum(item["node_count"] for item in masters + layouts + slides),
                   "assets": len(manifest.get("assets", {}).get("allAssets") or [])},
        "invariants": {
            "graph_is_factual": False, "semantic_inference": "deferred_to_phase_2",
            "classification_states": CLASSIFICATION_STATES, "supported_modes": SUPPORTED_MODES,
            "vertical_alignment": {"rule": "hard", "eligible_text_center_y_equals_container_center_y": True,
                                    "optical_exceptions_require_explicit_flag": True},
        },
    }


def build_distill_manifest(
    *,
    template_id: str,
    source_workspace: Path,
    source_pptx: Path,
    source_graph: dict[str, Any],
    stage: str = "phase_2_semantic_registry",
    next_phase: str = "phase_3_design_system_compiler",
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "stage": stage,
        "status": source_graph.get("status", "unknown"),
        "template_id": template_id,
        "source": {
            "pptx": str(Path(source_pptx).resolve()),
            "workspace": str(Path(source_workspace).resolve()),
            "sha256": source_graph.get("source", {}).get("sha256"),
        },
        "artifacts": {
            "source_graph": "source_graph.json",
            "source_manifest": "manifest.json",
            "distilled_spec_compatibility_view": "distilled_spec.json",
            "identity_spec": "identity_spec.json",
            "layout_spec": "layout_spec.json",
            "component_catalog": "component_catalog.json",
            "component_candidates": "component_candidates.json",
            "slot_contracts": "slot_contracts.json",
            "asset_provenance": "asset_provenance.json",
            "adaptation_policy": "adaptation_policy.json",
            "review_queue": "review_queue.json",
            "design_system_pack": "design_system_pack.json",
            "component_registry_fragment": "component_registry_fragment.json",
            "projection_manifest": "projection_manifest.json",
            "promotion_report": "promotion_report.json",
        },
        "supported_modes": SUPPORTED_MODES,
        "classification_states": CLASSIFICATION_STATES,
        "invariants": source_graph.get("invariants", {}),
        "counts": source_graph.get("counts", {}),
        "next_phase": next_phase,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a factual OOXML source graph from a PPTX.")
    parser.add_argument("pptx_file", help="Source .pptx file")
    parser.add_argument("--output", help="Output JSON path; defaults to <stem>_source_graph.json")
    parser.add_argument("--manifest", help="Optional existing manifest.json for cross-check metadata")
    parser.add_argument("--json", action="store_true", help="Print the graph as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pptx_path = Path(args.pptx_file).resolve()
    manifest = None
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    graph = build_source_graph(pptx_path, manifest=manifest)
    output = Path(args.output).resolve() if args.output else pptx_path.with_name(f"{pptx_path.stem}_source_graph.json")
    _write_json(output, graph)
    if args.json:
        print(json.dumps(graph, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote {output}")
        print(json.dumps(graph["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
