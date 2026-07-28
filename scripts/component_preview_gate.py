#!/usr/bin/env python3
"""Validate component preview SVGs against PPTX layout invariants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREVIEW_ROOT = ROOT / "templates" / "components" / "gallery" / "previews"
SCHEMA_VERSION = "easyslides.component_preview_gate_report.v1"


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _bool_attr(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _float_attr(element: ET.Element, name: str) -> float | None:
    raw = element.attrib.get(name)
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def _center_locked(element: ET.Element) -> bool:
    valign = str(element.attrib.get("data-pptx-valign") or "").strip().lower()
    return _bool_attr(element.attrib.get("data-center-lock")) or valign in {"middle", "center", "ctr"}


def _tspan_ys(element: ET.Element) -> list[float]:
    values: list[float] = []
    for child in element.iter():
        if child is element or _local_name(child.tag) != "tspan":
            continue
        y = _float_attr(child, "y")
        if y is not None:
            values.append(y)
    return values


def _validate_textbox(
    element: ET.Element,
    *,
    path: str,
    tolerance_px: float,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    slot = str(element.attrib.get("data-slot-id") or "text")
    element_path = f"{path}:{slot}"

    if not _bool_attr(element.attrib.get("data-pptx-textbox")):
        issues.append(
            _issue(
                "COMPONENT-PREVIEW-TEXTBOX-DATA",
                "center-locked text must be marked as a PPTX textbox",
                element_path,
            )
        )

    valign = str(element.attrib.get("data-pptx-valign") or "").strip().lower()
    if valign not in {"middle", "center", "ctr"}:
        issues.append(
            _issue(
                "COMPONENT-PREVIEW-VALIGN",
                "center-locked text must declare middle vertical alignment",
                element_path,
            )
        )

    if not _bool_attr(element.attrib.get("data-center-lock")):
        issues.append(
            _issue(
                "COMPONENT-PREVIEW-CENTER-LOCK",
                "PPTX textboxes must opt into center-lock validation",
                element_path,
            )
        )

    box_y = _float_attr(element, "data-pptx-box-y")
    box_h = _float_attr(element, "data-pptx-box-h")
    text_y = _float_attr(element, "y")
    if box_y is None or box_h is None or text_y is None:
        issues.append(
            _issue(
                "COMPONENT-PREVIEW-TEXTBOX-DATA",
                "center-locked text must declare box y/height and text y coordinates",
                element_path,
            )
        )
        return issues

    box_center = box_y + box_h / 2
    if abs(text_y - box_center) > tolerance_px:
        issues.append(
            _issue(
                "COMPONENT-PREVIEW-CENTER",
                f"text center y {text_y:.2f} must match container center y {box_center:.2f}",
                element_path,
            )
        )

    tspan_ys = _tspan_ys(element)
    if tspan_ys:
        line_center = (min(tspan_ys) + max(tspan_ys)) / 2
        if abs(line_center - box_center) > tolerance_px:
            issues.append(
                _issue(
                    "COMPONENT-PREVIEW-TSPAN-CENTER",
                    f"rendered line group center y {line_center:.2f} must match container center y {box_center:.2f}",
                    element_path,
                )
            )

    return issues


def validate_component_preview_svg(path: Path, *, tolerance_px: float = 2.0) -> dict[str, Any]:
    """Return a center-alignment report for one component preview SVG."""
    issues: list[dict[str, str]] = []
    checked_text_count = 0
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ET.ParseError, UnicodeDecodeError) as exc:
        issues.append(_issue("COMPONENT-PREVIEW-SVG-PARSE", f"cannot parse SVG: {exc}", str(path)))
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "fail",
            "issue_count": len(issues),
            "issues": issues,
            "svg": str(path),
            "checked_text_count": checked_text_count,
        }

    for element in root.iter():
        if _local_name(element.tag) != "text":
            continue
        is_pptx_textbox = _bool_attr(element.attrib.get("data-pptx-textbox"))
        if not is_pptx_textbox and not _center_locked(element):
            continue
        checked_text_count += 1
        issues.extend(_validate_textbox(element, path=str(path), tolerance_px=tolerance_px))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "svg": str(path),
        "checked_text_count": checked_text_count,
    }


def validate_component_preview_dir(root: Path = DEFAULT_PREVIEW_ROOT, *, tolerance_px: float = 2.0) -> dict[str, Any]:
    """Validate all SVG previews in a directory."""
    svg_paths = sorted(root.glob("*.svg")) if root.exists() else []
    reports = [validate_component_preview_svg(path, tolerance_px=tolerance_px) for path in svg_paths]
    issues: list[dict[str, str]] = []
    for report in reports:
        issues.extend(report["issues"])
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues and svg_paths else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "preview_root": str(root),
        "svg_count": len(svg_paths),
        "checked_text_count": sum(int(report.get("checked_text_count") or 0) for report in reports),
        "tolerance_px": tolerance_px,
        "svgs": reports,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate component preview SVG center-alignment gates.")
    parser.add_argument("preview_root", nargs="?", type=Path, default=DEFAULT_PREVIEW_ROOT)
    parser.add_argument("--tolerance-px", type=float, default=2.0)
    parser.add_argument("--report", type=Path, help="Write a JSON gate report to this path.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_component_preview_dir(args.preview_root, tolerance_px=args.tolerance_px)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Component preview gate: {report['status']} "
            f"({report['svg_count']} SVG(s), {report['issue_count']} issue(s))"
        )
        for item in report["issues"]:
            print(f"- {item['code']}: {item['message']} [{item['path']}]")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
