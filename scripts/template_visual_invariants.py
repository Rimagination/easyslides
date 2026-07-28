#!/usr/bin/env python3
"""Validate explicit visual invariants owned by an EasySlides template.

Unlike heuristic geometry checks, this module only enforces relationships a
template has deliberately declared.  That keeps source-faithful artwork intact
while making two production promises fail closed:

* ``data-center-lock=true`` text is emitted as a real vertically centred PPTX
  text box; an optional named visual container must share its centre line.
* a group mirrored through ``data-easyslides-symmetry-source`` is a literal
  180-degree geometry pair without effects that could render directionally.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SCHEMA_VERSION = "easyslides.template_visual_invariants_report.v1"
CENTER_ALIGN_TOLERANCE_PX = 1.0
_TRUTHY = {"1", "true", "yes"}
_ROTATE_RE = re.compile(r"rotate\s*\(\s*([-+]?\d*\.?\d+)\s*(?:[,\s]+([-+]?\d*\.?\d+)\s*[,\s]+([-+]?\d*\.?\d+))?\s*\)", re.IGNORECASE)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _issue(code: str, message: str, *, path: Path, **details: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "code": code,
        "severity": "blocking",
        "message": message,
        "path": str(path),
    }
    if details:
        row["details"] = details
    return row


def _svg_paths(template_dir: Path) -> list[Path]:
    """Return authored shell/component SVGs, excluding compiled report output."""
    return sorted(
        path
        for path in template_dir.rglob("*.svg")
        if "compiled" not in path.relative_to(template_dir).parts
        and "promotion_gate" not in path.relative_to(template_dir).parts
    )


def _text_frame(node: ET.Element) -> tuple[float, float, float, float] | None:
    values = (
        _number(node.get("data-pptx-box-x")),
        _number(node.get("data-pptx-box-y")),
        _number(node.get("data-pptx-box-w")),
        _number(node.get("data-pptx-box-h")),
    )
    if any(value is None for value in values):
        return None
    x, y, width, height = values
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return float(x), float(y), float(width), float(height)


def _rect_frame(node: ET.Element) -> tuple[float, float, float, float] | None:
    if _local_name(node.tag) != "rect":
        return None
    values = (
        _number(node.get("x")),
        _number(node.get("y")),
        _number(node.get("width")),
        _number(node.get("height")),
    )
    if any(value is None for value in values):
        return None
    x, y, width, height = values
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return float(x), float(y), float(width), float(height)


def _load_center_tolerance(template_dir: Path) -> float:
    policy_path = template_dir / "qa_policy.json"
    if not policy_path.is_file():
        return CENTER_ALIGN_TOLERANCE_PX
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError):
        return CENTER_ALIGN_TOLERANCE_PX
    value = _number(policy.get("vertical_center_tolerance_px") if isinstance(policy, dict) else None)
    return value if value is not None and value >= 0 else CENTER_ALIGN_TOLERANCE_PX


def _container_nodes(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for node in root.iter():
        for key in ("id", "data-easyslides-container-id"):
            identifier = str(node.get(key) or "").strip()
            if identifier and identifier not in result:
                result[identifier] = node
    return result


def _validate_center_locked_text(
    root: ET.Element,
    path: Path,
    *,
    tolerance_px: float,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    containers = _container_nodes(root)
    for index, node in enumerate(root.iter(), start=1):
        if _local_name(node.tag) != "text" or not _truthy(node.get("data-center-lock")):
            continue
        slot = node.get("data-slot-id") or node.get("data-easyslides-static-role") or f"text#{index}"
        if not _truthy(node.get("data-pptx-textbox")):
            issues.append(
                _issue(
                    "VISUAL-CENTER-LOCK-TEXTBOX",
                    "Center-locked text must be emitted as an explicit PPTX text box.",
                    path=path,
                    slot=slot,
                )
            )
        if str(node.get("data-pptx-valign") or "").strip().lower() not in {"middle", "center", "ctr"}:
            issues.append(
                _issue(
                    "VISUAL-CENTER-LOCK-VALIGN",
                    "Center-locked text must declare middle vertical alignment.",
                    path=path,
                    slot=slot,
                )
            )
        frame = _text_frame(node)
        if frame is None:
            issues.append(
                _issue(
                    "VISUAL-CENTER-LOCK-FRAME",
                    "Center-locked text must declare a positive PPTX text frame.",
                    path=path,
                    slot=slot,
                )
            )
            continue

        container_id = str(node.get("data-easyslides-center-container") or "").strip()
        if not container_id:
            continue
        container = containers.get(container_id)
        container_frame = _rect_frame(container) if container is not None else None
        if container_frame is None:
            issues.append(
                _issue(
                    "VISUAL-CENTER-CONTAINER-MISSING",
                    "The declared centre container must resolve to a rectangle in the same SVG.",
                    path=path,
                    slot=slot,
                    container_id=container_id,
                )
            )
            continue
        _x, text_y, _width, text_height = frame
        _cx, container_y, _cw, container_height = container_frame
        center_delta = abs((text_y + text_height / 2.0) - (container_y + container_height / 2.0))
        if center_delta > tolerance_px:
            issues.append(
                _issue(
                    "VISUAL-CENTER-CONTAINER-ALIGNMENT",
                    "Text frame centre must match its declared container centre.",
                    path=path,
                    slot=slot,
                    container_id=container_id,
                    center_delta=round(center_delta, 3),
                    max_center_delta=tolerance_px,
                )
            )
    return issues


def _viewbox_center(root: ET.Element) -> tuple[float, float] | None:
    raw = str(root.get("viewBox") or "").replace(",", " ")
    values = [_number(value) for value in raw.split()]
    if len(values) != 4 or any(value is None for value in values):
        return None
    x, y, width, height = (float(value) for value in values)
    return x + width / 2.0, y + height / 2.0


def _subtree_signature(node: ET.Element, *, root: bool = False) -> tuple[Any, ...]:
    ignored = {"id", "transform", "data-easyslides-symmetry-source"} if root else set()
    attrs = tuple(sorted((key, value) for key, value in node.attrib.items() if key not in ignored))
    return (
        _local_name(node.tag),
        attrs,
        tuple(_subtree_signature(child) for child in list(node)),
    )


def _has_filter(node: ET.Element) -> bool:
    return any("filter" in child.attrib for child in node.iter())


def _validate_mirror_pairs(root: ET.Element, path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    nodes_by_id = {
        str(node.get("id")): node
        for node in root.iter()
        if str(node.get("id") or "").strip()
    }
    expected_center = _viewbox_center(root)
    for node in root.iter():
        source_id = str(node.get("data-easyslides-symmetry-source") or "").strip()
        if not source_id:
            continue
        source = nodes_by_id.get(source_id)
        mirror_id = str(node.get("id") or "").strip() or "unnamed-mirror"
        if source is None:
            issues.append(
                _issue(
                    "VISUAL-SYMMETRY-SOURCE-MISSING",
                    "A mirrored decoration must point to an existing source group.",
                    path=path,
                    mirror_id=mirror_id,
                    source_id=source_id,
                )
            )
            continue
        match = _ROTATE_RE.search(str(node.get("transform") or ""))
        if match is None or abs(float(match.group(1)) - 180.0) > 0.01:
            issues.append(
                _issue(
                    "VISUAL-SYMMETRY-ROTATION",
                    "A mirrored decoration must use a 180-degree rotation.",
                    path=path,
                    mirror_id=mirror_id,
                    transform=node.get("transform"),
                )
            )
        elif expected_center is not None:
            cx, cy = (_number(match.group(2)), _number(match.group(3)))
            if cx is None or cy is None or abs(cx - expected_center[0]) > 0.01 or abs(cy - expected_center[1]) > 0.01:
                issues.append(
                    _issue(
                        "VISUAL-SYMMETRY-CENTER",
                        "The 180-degree mirror must rotate around the SVG canvas centre.",
                        path=path,
                        mirror_id=mirror_id,
                        expected_center=[round(expected_center[0], 3), round(expected_center[1], 3)],
                    )
                )
        if _subtree_signature(source, root=True) != _subtree_signature(node, root=True):
            issues.append(
                _issue(
                    "VISUAL-SYMMETRY-GEOMETRY",
                    "Mirrored decorations must preserve identical source geometry and styling.",
                    path=path,
                    mirror_id=mirror_id,
                    source_id=source_id,
                )
            )
        if _has_filter(source) or _has_filter(node):
            issues.append(
                _issue(
                    "VISUAL-SYMMETRY-DIRECTIONAL-EFFECT",
                    "Mirrored decoration groups may not contain SVG filters because their rendered direction is not mirror-safe.",
                    path=path,
                    mirror_id=mirror_id,
                    source_id=source_id,
                )
            )
    return issues


def validate_template_visual_invariants(template_dir: str | Path) -> dict[str, Any]:
    """Check declared centring and symmetry relations for all template SVGs."""
    template = Path(template_dir).resolve()
    tolerance_px = _load_center_tolerance(template)
    issues: list[dict[str, Any]] = []
    checked_center_locks = 0
    checked_mirrors = 0
    for path in _svg_paths(template):
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError, UnicodeDecodeError) as exc:
            issues.append(
                _issue(
                    "VISUAL-INVARIANT-SVG-PARSE",
                    "Template SVG cannot be parsed for visual invariant validation.",
                    path=path,
                    error=str(exc),
                )
            )
            continue
        checked_center_locks += sum(
            1
            for node in root.iter()
            if _local_name(node.tag) == "text" and _truthy(node.get("data-center-lock"))
        )
        checked_mirrors += sum(1 for node in root.iter() if node.get("data-easyslides-symmetry-source"))
        issues.extend(_validate_center_locked_text(root, path, tolerance_px=tolerance_px))
        issues.extend(_validate_mirror_pairs(root, path))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "template_dir": str(template),
        "svg_count": len(_svg_paths(template)),
        "checked_center_lock_count": checked_center_locks,
        "checked_mirror_pair_count": checked_mirrors,
        "center_tolerance_px": tolerance_px,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate explicit EasySlides template visual invariants.")
    parser.add_argument("template_dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_template_visual_invariants(args.template_dir)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Template visual invariants: {report['status']} "
            f"({report['checked_center_lock_count']} centre locks, "
            f"{report['checked_mirror_pair_count']} mirror pairs)"
        )
        for item in report["issues"]:
            print(f"- {item['code']}: {item['message']} [{item['path']}]")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
