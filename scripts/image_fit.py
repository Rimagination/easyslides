#!/usr/bin/env python3
"""Normalize image-slot fitting for SVG and native-PPTX rendering.

Scientific figures must keep their intrinsic aspect ratio.  The source PPTX
importer represents cropped pictures as a nested ``<svg>`` wrapper containing
an image with ``preserveAspectRatio=none``; that is faithful to the imported
source geometry but is not safe for an abstracted, replaceable image slot.

This module converts declared image slots to an explicit fit policy:

* ``contain`` -> ``xMidYMid meet``
* ``cover``   -> ``xMidYMid slice``
* ``stretch`` -> ``none`` (reserved for backgrounds/decorative assets)

For ``contain`` slots, the importer wrapper is flattened to a direct image so
both SVG preview and the native DrawingML converter can apply the same policy.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

IMAGE_FIT_PRESERVE_ASPECT = {
    "contain": "xMidYMid meet",
    "cover": "xMidYMid slice",
    "stretch": "none",
}

IMAGE_FRAME_STROKE = "#E5DDE8"
IMAGE_FRAME_STROKE_OPACITY = "0.78"
IMAGE_FRAME_STROKE_WIDTH = "1.2"
IMAGE_FRAME_RADIUS = "3"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_image_fit(value: object, *, default: str = "contain") -> str:
    fit = str(value or default).strip().lower()
    aliases = {"fit": "contain", "meet": "contain", "crop": "cover", "slice": "cover"}
    fit = aliases.get(fit, fit)
    if fit not in IMAGE_FIT_PRESERVE_ASPECT:
        raise ValueError(f"unsupported image fit {value!r}; expected contain, cover, or stretch")
    return fit


def _contract_map(contracts: object) -> dict[str, dict[str, Any]]:
    if isinstance(contracts, dict):
        return {
            str(key): value
            for key, value in contracts.items()
            if isinstance(value, dict)
        }
    if not isinstance(contracts, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in contracts:
        if not isinstance(item, dict):
            continue
        slot_id = str(item.get("slot_id") or item.get("id") or "").strip()
        if slot_id:
            result[slot_id] = item
    return result


def _slot_id(node: ET.Element) -> str:
    return str(node.get("data-slot") or node.get("data-slot-id") or "").strip()


def _parents(root: ET.Element) -> dict[int, ET.Element]:
    return {id(child): parent for parent in root.iter() for child in list(parent)}


def _number(value: object) -> float | None:
    try:
        return float(str(value).strip().replace("px", ""))
    except (TypeError, ValueError):
        return None


def _view_box(root: ET.Element) -> tuple[float, float, float, float] | None:
    raw = str(root.get("viewBox") or "").replace(",", " ").split()
    if len(raw) != 4:
        return None
    values = [_number(value) for value in raw]
    if any(value is None for value in values):
        return None
    return tuple(value for value in values if value is not None)  # type: ignore[return-value]


def _is_full_canvas_image(root: ET.Element, node: ET.Element) -> bool:
    view_box = _view_box(root)
    if view_box is None:
        return False
    vx, vy, vw, vh = view_box
    values = [_number(node.get(key)) for key in ("x", "y", "width", "height")]
    if any(value is None for value in values):
        return False
    x, y, width, height = values  # type: ignore[misc]
    return (
        abs(x - vx) < 0.5
        and abs(y - vy) < 0.5
        and abs(width - vw) < 0.5
        and abs(height - vh) < 0.5
    )


def _has_matching_visual_rect(parent: ET.Element, node: ET.Element) -> bool:
    values = [_number(node.get(key)) for key in ("x", "y", "width", "height")]
    if any(value is None for value in values):
        return False
    for sibling in list(parent):
        if local_name(sibling.tag) != "rect" or sibling is node:
            continue
        if sibling.get("data-easyslides-image-frame-for"):
            return True
        sibling_values = [_number(sibling.get(key)) for key in ("x", "y", "width", "height")]
        if any(value is None for value in sibling_values):
            continue
        if all(abs(left - right) < 0.5 for left, right in zip(values, sibling_values)):
            fill = str(sibling.get("fill") or "").strip().lower()
            stroke = str(sibling.get("stroke") or "").strip().lower()
            if fill not in {"", "none"} or stroke not in {"", "none"}:
                return True
    return False


def _image_frame_enabled(contract: dict[str, Any], fit: str) -> bool:
    # Cover is intended for decorative photography/backgrounds.  Contain is
    # the academic figure/table/equation path and receives the subtle frame.
    if fit != "contain":
        return False
    value = contract.get("image_frame", "subtle")
    return str(value).strip().lower() not in {"", "none", "false", "0", "off"}


def _add_image_frame(root: ET.Element, node: ET.Element, slot_id: str, contract: dict[str, Any], fit: str) -> bool:
    if not _image_frame_enabled(contract, fit) or _is_full_canvas_image(root, node):
        return False
    parents = _parents(root)
    parent = parents.get(id(node))
    if parent is None or _has_matching_visual_rect(parent, node):
        return False
    frame = ET.Element(
        f"{{{SVG_NS}}}rect",
        {
            "x": str(node.get("x") or "0"),
            "y": str(node.get("y") or "0"),
            "width": str(node.get("width") or "0"),
            "height": str(node.get("height") or "0"),
            "rx": IMAGE_FRAME_RADIUS,
            "ry": IMAGE_FRAME_RADIUS,
            "fill": "none",
            "stroke": IMAGE_FRAME_STROKE,
            "stroke-opacity": IMAGE_FRAME_STROKE_OPACITY,
            "stroke-width": IMAGE_FRAME_STROKE_WIDTH,
            "data-easyslides-image-frame-for": slot_id or "<unnamed>",
            "data-easyslides-generated": "true",
        },
    )
    position = list(parent).index(node)
    parent.insert(position, frame)
    return True


def _is_simple_image_wrapper(wrapper: ET.Element, image: ET.Element) -> bool:
    """Return whether ``wrapper`` is the importer crop wrapper we can flatten."""
    if local_name(wrapper.tag) != "svg" or local_name(image.tag) != "image":
        return False
    children = list(wrapper)
    if len(children) != 1 or children[0] is not image:
        return False
    for attr in ("x", "y", "width", "height"):
        if not wrapper.get(attr):
            return False
    # Do not flatten a wrapper that carries visual effects or clipping.  The
    # source-derived body variants use only geometry/viewBox on these wrappers.
    allowed = {"x", "y", "width", "height", "viewBox", "preserveAspectRatio"}
    return set(wrapper.attrib).issubset(allowed)


def _flatten_image_wrapper(
    root: ET.Element,
    wrapper: ET.Element,
    image: ET.Element,
    *,
    preserve_aspect_ratio: str,
) -> ET.Element | None:
    parents = _parents(root)
    parent = parents.get(id(wrapper))
    if parent is None or not _is_simple_image_wrapper(wrapper, image):
        return None

    direct = ET.Element(image.tag)
    # Preserve the source image reference and slot metadata, but use the
    # wrapper's declared frame as the direct picture frame.  This intentionally
    # drops the importer crop viewBox: contain must show the complete figure.
    for key, value in image.attrib.items():
        if key not in {"x", "y", "width", "height", "preserveAspectRatio"}:
            direct.set(key, value)
    for key in ("x", "y", "width", "height"):
        direct.set(key, wrapper.get(key) or "0")
    direct.set("preserveAspectRatio", preserve_aspect_ratio)
    direct.set("data-easyslides-image-fit", "contain" if preserve_aspect_ratio.endswith("meet") else "cover")

    position = list(parent).index(wrapper)
    parent.remove(wrapper)
    parent.insert(position, direct)
    return direct


def apply_image_fit_policy(
    root: ET.Element,
    contracts: object = None,
    *,
    default: str = "contain",
    flatten_wrappers: bool = True,
) -> dict[str, Any]:
    """Apply declared image fit policy to every image slot in ``root``.

    The return value is a small QA report.  It is intentionally independent of
    the renderer so source-faithful template builders can use the same helper.
    """
    contract_map = _contract_map(contracts)
    changed: list[str] = []
    flattened: list[str] = []
    framed: list[str] = []
    issues: list[str] = []

    for node in list(root.iter()):
        if local_name(node.tag) != "image" or node.get("data-slot-kind") != "image":
            continue
        slot_id = _slot_id(node)
        contract = contract_map.get(slot_id, {})
        try:
            fit = normalize_image_fit(contract.get("image_fit") or node.get("data-easyslides-image-fit"), default=default)
        except ValueError as exc:
            issues.append(f"{slot_id or '<unnamed>'}: {exc}")
            continue
        par = IMAGE_FIT_PRESERVE_ASPECT[fit]
        wrapper = _parents(root).get(id(node))
        if flatten_wrappers and fit == "contain" and wrapper is not None:
            flattened_node = _flatten_image_wrapper(
                root,
                wrapper,
                node,
                preserve_aspect_ratio=par,
            )
            if flattened_node is not None:
                node = flattened_node
                flattened.append(slot_id or "<unnamed>")
        if node.get("preserveAspectRatio") != par:
            node.set("preserveAspectRatio", par)
            changed.append(slot_id or "<unnamed>")
        node.set("data-easyslides-image-fit", fit)
        if _add_image_frame(root, node, slot_id, contract, fit):
            framed.append(slot_id or "<unnamed>")

    return {
        "status": "pass" if not issues else "fail",
        "changed": changed,
        "flattened": flattened,
        "framed": framed,
        "issues": issues,
    }


def find_image_fit_violations(root: ET.Element, contracts: object = None) -> list[str]:
    """Find declared image slots whose SVG semantics still allow distortion."""
    contract_map = _contract_map(contracts)
    violations: list[str] = []
    for node in root.iter():
        if local_name(node.tag) != "image" or node.get("data-slot-kind") != "image":
            continue
        slot_id = _slot_id(node) or "<unnamed>"
        contract = contract_map.get(slot_id, {})
        try:
            fit = normalize_image_fit(contract.get("image_fit") or node.get("data-easyslides-image-fit"), default="contain")
        except ValueError as exc:
            violations.append(f"{slot_id}: {exc}")
            continue
        expected = IMAGE_FIT_PRESERVE_ASPECT[fit]
        actual = (node.get("preserveAspectRatio") or "").strip()
        if actual != expected:
            violations.append(f"{slot_id}: expected preserveAspectRatio={expected!r}, got {actual or '<missing>'!r}")
    return violations
