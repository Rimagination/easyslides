#!/usr/bin/env python3
"""Validate template-owned feedback contracts that must not regress."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SCHEMA_VERSION = "easyslides.template_feedback_contract_report.v1"
SVG_NS = "http://www.w3.org/2000/svg"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "severity": "blocking", "message": message}
    if details:
        row["details"] = details
    return row


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _same_frame(node: ET.Element, frame: dict[str, Any]) -> bool:
    return all(
        abs(_number(node.get(key)) - _number(frame.get(key))) < 0.01
        for key in ("x", "y", "width", "height")
    )


def _text_frame(node: ET.Element) -> dict[str, float]:
    return {
        "x": _number(node.get("data-pptx-box-x")),
        "y": _number(node.get("data-pptx-box-y")),
        "width": _number(node.get("data-pptx-box-w")),
        "height": _number(node.get("data-pptx-box-h")),
    }


def _frame_contains(node: ET.Element, frame: dict[str, float]) -> bool:
    x, y, width, height = (_number(node.get(key)) for key in ("x", "y", "width", "height"))
    return (
        x <= frame["x"] + 0.01
        and y <= frame["y"] + 0.01
        and x + width >= frame["x"] + frame["width"] - 0.01
        and y + height >= frame["y"] + frame["height"] - 0.01
    )


def _is_decorative_conclusion_container(node: ET.Element) -> bool:
    """Keep structural white table cells distinct from colored conclusion bars."""
    fill = str(node.get("fill") or "").strip().lower()
    return fill not in {"", "none", "#fff", "#ffffff", "white"}


def _slot_contract(template_dir: Path, slot_id: str, shell_id: str) -> dict[str, Any] | None:
    slots = _read_json(template_dir / "slot_contracts.json").get("slots")
    if not isinstance(slots, list):
        return None
    return next(
        (
            slot
            for slot in slots
            if isinstance(slot, dict)
            and slot.get("slot_id") == slot_id
            and slot.get("shell_id") == shell_id
        ),
        None,
    )


def _validate_title(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    slot_id = str(checks["slot_id"])
    shell_id = str(checks["shell_id"])
    contract = _slot_contract(template_dir, slot_id, shell_id)
    if contract is None:
        issues.append(_issue("FEEDBACK-TITLE-CONTRACT", "The required content-title slot is missing."))
        return
    capacity = contract.get("capacity") if isinstance(contract.get("capacity"), dict) else {}
    expected_capacity = checks.get("capacity") if isinstance(checks.get("capacity"), dict) else {}
    for key, expected in expected_capacity.items():
        if capacity.get(key) != expected:
            issues.append(
                _issue(
                    "FEEDBACK-TITLE-CAPACITY",
                    "The content-title single-line capacity contract changed.",
                    key=key,
                    expected=expected,
                    actual=capacity.get(key),
                )
            )
    svg_path = template_dir / str(checks["svg"])
    root = ET.parse(svg_path).getroot()
    title = next((node for node in root.iter() if node.get("data-slot-id") == slot_id), None)
    if title is None:
        issues.append(_issue("FEEDBACK-TITLE-SVG", "The content-title SVG node is missing.", path=str(svg_path)))
        return
    geometry = checks.get("geometry") if isinstance(checks.get("geometry"), dict) else {}
    for key, expected in geometry.items():
        attribute = f"data-pptx-box-{key[0]}" if key in {"x", "y", "width", "height"} else key
        if key == "width":
            attribute = "data-pptx-box-w"
        elif key == "height":
            attribute = "data-pptx-box-h"
        elif key == "x":
            attribute = "data-pptx-box-x"
        elif key == "y":
            attribute = "data-pptx-box-y"
        if _number(title.get(attribute)) < _number(expected):
            issues.append(
                _issue(
                    "FEEDBACK-TITLE-GEOMETRY",
                    "The content-title box no longer reserves the required header width.",
                    attribute=attribute,
                    minimum=expected,
                    actual=title.get(attribute),
                )
            )
    if title.get("data-easyslides-single-line") != "required":
        issues.append(_issue("FEEDBACK-TITLE-SINGLE-LINE", "The content title is no longer marked single-line."))
    if title.get("data-pptx-no-wrap") != "true":
        issues.append(_issue("FEEDBACK-TITLE-NO-WRAP", "The content title may wrap in native PPTX."))


def _validate_content_canvas(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    root = ET.parse(template_dir / str(checks["svg"])).getroot()
    frame = checks.get("forbidden_frame") if isinstance(checks.get("forbidden_frame"), dict) else {}
    for node in root.iter():
        if _local_name(node.tag) == "rect" and _same_frame(node, frame):
            issues.append(
                _issue(
                    "FEEDBACK-CONTENT-CANVAS-VISIBLE",
                    "The content planning canvas must not render as a visible rectangle.",
                    path=str(template_dir / str(checks["svg"])),
                )
            )
            break


def _validate_key_message(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    slot_id = str(checks["slot_id"])
    shell_id = str(checks["shell_id"])
    contract = _slot_contract(template_dir, slot_id, shell_id)
    if contract is None:
        issues.append(_issue("FEEDBACK-KEY-MESSAGE-CONTRACT", "The central-message slot is missing."))
        return
    capacity = contract.get("capacity") if isinstance(contract.get("capacity"), dict) else {}
    expected_capacity = checks.get("capacity") if isinstance(checks.get("capacity"), dict) else {}
    for key, expected in expected_capacity.items():
        if capacity.get(key) != expected:
            issues.append(
                _issue(
                    "FEEDBACK-KEY-MESSAGE-CAPACITY",
                    "The central-message capacity contract changed.",
                    key=key,
                    expected=expected,
                    actual=capacity.get(key),
                )
            )
    if contract.get("role") != "central_message":
        issues.append(
            _issue("FEEDBACK-KEY-MESSAGE-ROLE", "The key-message slot no longer owns the page-level conclusion.")
        )
    root = ET.parse(template_dir / str(checks["svg"])).getroot()
    message = next((node for node in root.iter() if node.get("data-slot-id") == slot_id), None)
    if message is None:
        issues.append(_issue("FEEDBACK-KEY-MESSAGE-SVG", "The central-message SVG node is missing."))
        return
    if message.get("data-easyslides-layout") != checks.get("layout"):
        issues.append(
            _issue("FEEDBACK-KEY-MESSAGE-BULLETS", "The central message must use template-owned square bullets.")
        )
    if message.get("data-pptx-no-wrap") != "true":
        issues.append(
            _issue("FEEDBACK-KEY-MESSAGE-NO-WRAP", "A key-message bullet may not wrap onto a second visual line.")
        )
    geometry = checks.get("geometry") if isinstance(checks.get("geometry"), dict) else {}
    for key, expected in geometry.items():
        attribute = {"x": "data-pptx-box-x", "y": "data-pptx-box-y", "width": "data-pptx-box-w", "height": "data-pptx-box-h"}.get(key, key)
        if abs(_number(message.get(attribute)) - _number(expected)) > 0.01:
            issues.append(
                _issue(
                    "FEEDBACK-KEY-MESSAGE-GEOMETRY",
                    "The central-message frame no longer reserves its fixed information layer.",
                    attribute=attribute,
                    expected=expected,
                    actual=message.get(attribute),
                )
            )


def _validate_page_number(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    slot_id = str(checks["slot_id"])
    shell_id = str(checks["shell_id"])
    contract = _slot_contract(template_dir, slot_id, shell_id)
    if contract is None or contract.get("value_policy") != "automatic_slide_index":
        issues.append(_issue("FEEDBACK-PAGE-NUMBER-CONTRACT", "The automatic page-number slot is missing."))
        return
    root = ET.parse(template_dir / str(checks["svg"])).getroot()
    number = next((node for node in root.iter() if node.get("data-slot-id") == slot_id), None)
    if number is None:
        issues.append(_issue("FEEDBACK-PAGE-NUMBER-SVG", "The page-number SVG node is missing."))
        return
    if number.get("data-pptx-text-anchor") != checks.get("text_anchor"):
        issues.append(_issue("FEEDBACK-PAGE-NUMBER-ANCHOR", "The page number must stay right-aligned."))
    geometry = checks.get("geometry") if isinstance(checks.get("geometry"), dict) else {}
    actual = _text_frame(number)
    if actual["x"] < _number(geometry.get("x")) or actual["y"] < _number(geometry.get("y")):
        issues.append(
            _issue("FEEDBACK-PAGE-NUMBER-POSITION", "The page number must remain in the lower-right corner.")
        )


def _frame_from_element(node: ET.Element) -> dict[str, float]:
    return {
        "x": _number(node.get("x")),
        "y": _number(node.get("y")),
        "width": _number(node.get("width")),
        "height": _number(node.get("height")),
    }


def _frame_contains_frame(container: dict[str, float], frame: dict[str, float]) -> bool:
    return (
        frame["x"] >= container["x"] - 0.01
        and frame["y"] >= container["y"] - 0.01
        and frame["x"] + frame["width"] <= container["x"] + container["width"] + 0.01
        and frame["y"] + frame["height"] <= container["y"] + container["height"] + 0.01
    )


def _validate_toc_control_alignment(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    """Enforce real center matching for every TOC pill label and index."""
    root = ET.parse(template_dir / str(checks["svg"])).getroot()
    tolerance = _number(checks.get("center_tolerance_px") or 1.0)
    pill_containers = {
        str(node.get("data-easyslides-container-id")): _frame_from_element(node)
        for node in root.iter()
        if _local_name(node.tag) == "rect"
        and str(node.get("data-easyslides-container-id") or "").startswith("toc-control-")
    }
    targets = [
        node
        for node in root.iter()
        if node.get("data-slot-id", "").startswith("TOC_ITEM_")
        or node.get("data-easyslides-static-role") == "toc_item_index"
    ]
    if len(pill_containers) != 3 or len(targets) != 6:
        issues.append(
            _issue(
                "FEEDBACK-TOC-CONTROL-STRUCTURE",
                "The three TOC containers and their six labels must remain available for alignment checking.",
                svg=str(checks["svg"]),
            )
        )
        return
    for text in targets:
        frame = _text_frame(text)
        container_id = str(text.get("data-easyslides-center-container") or "")
        container = pill_containers.get(container_id)
        if container is None:
            issues.append(
                _issue(
                    "FEEDBACK-TOC-CONTROL-CONTAINER",
                    "A TOC label or index is no longer inside its pill container.",
                    slot_id=text.get("data-slot-id") or text.get("data-easyslides-static-role", ""),
                )
            )
            continue
        center_delta = abs((frame["y"] + frame["height"] / 2.0) - (container["y"] + container["height"] / 2.0))
        if (
            str(text.get("data-pptx-valign") or "").lower() not in {"middle", "center", "ctr"}
            or text.get("data-center-lock") != "true"
            or center_delta > tolerance
        ):
            issues.append(
                _issue(
                    "FEEDBACK-TOC-CONTROL-VERTICAL-CENTER",
                    "TOC text must be vertically centered in its corresponding pill container.",
                    slot_id=text.get("data-slot-id") or text.get("data-easyslides-static-role", ""),
                    center_delta=round(center_delta, 3),
                    max_center_delta=tolerance,
                )
            )


def _validate_component_chrome(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    component_dir = template_dir / str(checks["component_dir"])
    conclusion_fill = str(checks.get("conclusion_fill") or "")
    conclusion_weight = str(checks.get("conclusion_weight") or "")
    style_policy = str(checks.get("conclusion_style_policy") or "purple_bold")
    # Component assets may be grouped by provenance (for example,
    # ``source_derived/`` and ``imported/``). Scan the complete component
    # tree so a directory reorganization cannot silently bypass feedback QA.
    for path in sorted(component_dir.rglob("*.svg")):
        root = ET.parse(path).getroot()
        rects = [node for node in root.iter() if _local_name(node.tag) == "rect"]
        for image in (node for node in root.iter() if _local_name(node.tag) == "image"):
            if any(_same_frame(rect, image.attrib) for rect in rects):
                issues.append(
                    _issue(
                        "FEEDBACK-IMAGE-FRAME",
                        "A component adds a decorative rectangle around an image asset.",
                        component=path.name,
                    )
                )
        for conclusion in (node for node in root.iter() if node.get("data-slot-id") == "CONCLUSION"):
            if style_policy == "purple_bold" and (
                conclusion.get("fill") != conclusion_fill
                or conclusion.get("font-weight") != conclusion_weight
            ):
                issues.append(
                    _issue(
                        "FEEDBACK-CONCLUSION-STYLE",
                        "A conclusion must render as bold purple text without a container.",
                        component=path.name,
                    )
                )
            if any(
                _frame_contains(rect, _text_frame(conclusion))
                and _is_decorative_conclusion_container(rect)
                for rect in rects
            ):
                issues.append(
                    _issue(
                        "FEEDBACK-CONCLUSION-CONTAINER",
                        "A conclusion must not render inside a decorative rectangle.",
                        component=path.name,
                    )
                )


def _validate_ending(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    root = ET.parse(template_dir / str(checks["svg"])).getroot()
    title = next((node for node in root.iter() if node.get("data-slot-id") == "CLOSING_TITLE"), None)
    expected = str(checks["default_text"])
    if title is None or "".join(title.itertext()).strip() != expected:
        issues.append(_issue("FEEDBACK-ENDING-DEFAULT", "The ending default copy changed.", expected=expected))
    if any(node.get("data-slot-id") == "CLOSING_SUBTITLE" for node in root.iter()):
        issues.append(_issue("FEEDBACK-ENDING-SUBTITLE", "The ending must expose one closing line only."))


def _validate_corners(template_dir: Path, checks: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    for svg_name in checks.get("svgs", []):
        root = ET.parse(template_dir / str(svg_name)).getroot()
        corners = next((node for node in root.iter() if node.get("id") == "chapter-shell-corners"), None)
        if corners is None:
            issues.append(_issue("FEEDBACK-CORNER-GROUP", "The symmetric corner group is missing.", svg=svg_name))
            continue
        top = next((node for node in corners if node.get("id") == "chapter-corner-top-left"), None)
        bottom = next((node for node in corners if node.get("id") == "chapter-corner-bottom-right"), None)
        if top is None or bottom is None:
            issues.append(_issue("FEEDBACK-CORNER-PAIR", "The corner pair is incomplete.", svg=svg_name))
            continue
        if bottom.get("transform") != "rotate(180 640 360)" or bottom.get("data-easyslides-symmetry-source") != top.get("id"):
            issues.append(_issue("FEEDBACK-CORNER-SYMMETRY", "The lower-right corner is not a 180-degree mirror of the upper-left corner.", svg=svg_name))
        top_paths = [node.attrib for node in top]
        bottom_paths = [node.attrib for node in bottom]
        if top_paths != bottom_paths:
            issues.append(_issue("FEEDBACK-CORNER-GEOMETRY", "The mirrored corner pair no longer shares identical source geometry.", svg=svg_name))
        if any("filter" in attributes for attributes in top_paths):
            issues.append(
                _issue(
                    "FEEDBACK-CORNER-DIRECTIONAL-EFFECT",
                    "Symmetric corner artwork must not use a directional visual effect.",
                    svg=svg_name,
                )
            )


def validate_template_feedback_contract(template_dir: str | Path) -> dict[str, Any]:
    """Validate the explicitly declared user-feedback constraints for a template."""
    template = Path(template_dir).resolve()
    contract_path = template / "feedback_contract.json"
    if not contract_path.is_file():
        return {"schema_version": SCHEMA_VERSION, "status": "pass", "applicable": False, "issues": []}
    try:
        contract = _read_json(contract_path)
        checks = contract.get("checks")
        if contract.get("schema_version") != "easyslides.template_feedback_contract.v1" or not isinstance(checks, dict):
            raise ValueError("invalid feedback contract schema")
        issues: list[dict[str, Any]] = []
        _validate_title(template, checks["content_title"], issues)
        _validate_content_canvas(template, checks["content_canvas"], issues)
        _validate_key_message(template, checks["key_message"], issues)
        _validate_page_number(template, checks["page_number"], issues)
        _validate_toc_control_alignment(template, checks["toc_controls"], issues)
        _validate_component_chrome(template, checks["component_chrome"], issues)
        _validate_ending(template, checks["ending"], issues)
        _validate_corners(template, checks["symmetric_corners"], issues)
    except (KeyError, OSError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "fail",
            "applicable": True,
            "issues": [_issue("FEEDBACK-CONTRACT-INVALID", "The template feedback contract cannot be validated.", error=str(exc))],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "applicable": True,
        "contract": str(contract_path),
        "check_count": len(checks),
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template_dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_template_feedback_contract(args.template_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Template feedback contract: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
