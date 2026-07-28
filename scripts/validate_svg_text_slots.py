#!/usr/bin/env python3
"""Validate SVG text against declared PPTX text slots.

The PPTX exit gate can detect text-box overflow after export, but it cannot
know that a loose SVG <text> element was intended to stay inside a nearby card.
This checker runs earlier: any text marked with data-pptx-textbox must declare
its fixed box, and every rendered line must fit that box.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sys
from typing import Any
from xml.etree import ElementTree as ET

try:
    from scripts.layout_metrics import estimate_text_width_px
except ImportError:  # pragma: no cover - direct script execution
    from layout_metrics import estimate_text_width_px


SCHEMA_VERSION = "easyslides.svg_text_slot_report.v2"
LINE_HEIGHT_RATIO = 1.25
WIDTH_TOLERANCE = 1.02
HEIGHT_TOLERANCE = 1.02
VALID_VALIGNS = {"top", "t", "middle", "center", "ctr", "bottom", "b"}
CENTER_VALIGNS = {"middle", "center", "ctr"}
CANVAS_WIDTH = 1280.0
CANVAS_HEIGHT = 720.0


@dataclass(frozen=True)
class SvgTextSlot:
    file: str
    element_index: int
    text: str
    lines: list[str]
    x: float
    y: float
    font_size: float
    font_weight: str
    boxed: bool
    box_x: float | None
    box_y: float | None
    box_w: float | None
    box_h: float | None
    valign: str
    center_lock: bool
    slot_id: str
    measure_lines: list[str]
    line_height_ratio: float


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else default


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def _text_content(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if _local_name(child.tag) == "tspan" and child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _tspan_lines(elem: ET.Element) -> list[str]:
    tspans = [child for child in elem if _local_name(child.tag) == "tspan"]
    if not tspans:
        text = _text_content(elem)
        return text.splitlines() if "\n" in text else [text]

    lines: list[str] = []
    current: list[str] = []
    if elem.text and elem.text.strip():
        current.append(elem.text.strip())
    for child in tspans:
        starts_line = child.get("x") is not None or child.get("y") is not None or child.get("dy") is not None
        if starts_line and current:
            lines.append(re.sub(r"\s+", " ", "".join(current)).strip())
            current = []
        if child.text:
            current.append(child.text)
        if child.tail and child.tail.strip():
            current.append(child.tail)
    if current:
        lines.append(re.sub(r"\s+", " ", "".join(current)).strip())
    return [line for line in lines if line]


def estimate_text_width(text: str, font_size: float, font_weight: str = "400") -> float:
    return estimate_text_width_px(text, font_size, font_weight)


def _iter_slots(svg_path: Path) -> list[SvgTextSlot]:
    root = ET.parse(svg_path).getroot()
    slots: list[SvgTextSlot] = []
    for index, elem in enumerate(root.iter(), start=1):
        if _local_name(elem.tag) != "text":
            continue
        text = _text_content(elem)
        if not text:
            continue
        # A placeholder needs a representative contract sample, while a
        # rendered material slide must be measured using its actual text.
        display_lines = _tspan_lines(elem)
        if "{{" in text:
            measure_text = elem.get("data-pptx-measure-text") or text
            measure_lines = measure_text.splitlines() or [measure_text]
        else:
            measure_lines = display_lines
        boxed = _truthy(elem.get("data-pptx-textbox"))
        slots.append(
            SvgTextSlot(
                file=str(svg_path),
                element_index=index,
                text=text,
                lines=_tspan_lines(elem),
                x=_float(elem.get("x")),
                y=_float(elem.get("y")),
                font_size=_float(elem.get("font-size"), 16.0),
                font_weight=elem.get("font-weight") or "400",
                boxed=boxed,
                box_x=_float(elem.get("data-pptx-box-x")) if elem.get("data-pptx-box-x") is not None else None,
                box_y=_float(elem.get("data-pptx-box-y")) if elem.get("data-pptx-box-y") is not None else None,
                box_w=_float(elem.get("data-pptx-box-w")) if elem.get("data-pptx-box-w") is not None else None,
                box_h=_float(elem.get("data-pptx-box-h")) if elem.get("data-pptx-box-h") is not None else None,
                valign=(elem.get("data-pptx-valign") or "").strip().lower(),
                center_lock=_truthy(elem.get("data-center-lock")),
                slot_id=elem.get("data-slot-id") or "",
                measure_lines=measure_lines,
                line_height_ratio=max(0.75, min(1.25, _float(elem.get("data-pptx-line-height-ratio"), LINE_HEIGHT_RATIO))),
            )
        )
    return slots


def _issue(code: str, slot: SvgTextSlot, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "file": slot.file,
        "element_index": slot.element_index,
        "slot_id": slot.slot_id,
        "message": message,
        "details": {
            "text_preview": slot.text[:120],
            "x": round(slot.x, 2),
            "y": round(slot.y, 2),
            "font_size": round(slot.font_size, 2),
            "font_weight": slot.font_weight,
            "valign": slot.valign or None,
            **details,
        },
    }


def validate_svg_text_slots(
    path: str | Path,
    *,
    strict_unboxed: bool = False,
    unboxed_char_threshold: int = 14,
    require_valign: bool = False,
    check_canvas: bool = False,
) -> dict[str, Any]:
    root = Path(path)
    svg_files = sorted(root.glob("*.svg")) if root.is_dir() else [root]
    issues: list[dict[str, Any]] = []
    slot_count = 0

    for svg_path in svg_files:
        for slot in _iter_slots(svg_path):
            slot_count += 1
            if not slot.boxed:
                if strict_unboxed and len(slot.text) >= unboxed_char_threshold:
                    issues.append(
                        _issue(
                            "SVG-TEXT-UNBOXED",
                            slot,
                            "blocking",
                            "Long SVG text has no declared PPTX text slot.",
                            text_length=len(slot.text),
                            threshold=unboxed_char_threshold,
                        )
                    )
                continue

            if slot.box_w is None or slot.box_h is None or slot.box_x is None or slot.box_y is None:
                issues.append(
                    _issue(
                        "SVG-TEXT-MISSING-BOX",
                        slot,
                        "blocking",
                        "data-pptx-textbox text must declare data-pptx-box-x/y/w/h.",
                    )
                )
                continue

            if require_valign and not slot.valign:
                issues.append(
                    _issue(
                        "SVG-TEXT-MISSING-VALIGN",
                        slot,
                        "blocking",
                        "data-pptx-textbox text must declare data-pptx-valign.",
                    )
                )
            elif slot.valign and slot.valign not in VALID_VALIGNS:
                issues.append(
                    _issue(
                        "SVG-TEXT-INVALID-VALIGN",
                        slot,
                        "blocking",
                        "data-pptx-valign must be top, middle/center, or bottom.",
                        allowed=sorted(VALID_VALIGNS),
                    )
                )

            if slot.valign and slot.valign not in VALID_VALIGNS:
                continue

            if slot.center_lock and slot.valign not in CENTER_VALIGNS:
                issues.append(
                    _issue(
                        "SVG-TEXT-CENTER-LOCK-VALIGN",
                        slot,
                        "blocking",
                        "A center-locked text box must use middle/center vertical alignment.",
                    )
                )

            if check_canvas and (
                slot.box_w <= 0
                or slot.box_h <= 0
                or slot.box_x < 0
                or slot.box_y < 0
                or slot.box_x + slot.box_w > CANVAS_WIDTH
                or slot.box_y + slot.box_h > CANVAS_HEIGHT
            ):
                issues.append(
                    _issue(
                        "SVG-TEXT-BOX-OFF-CANVAS",
                        slot,
                        "blocking",
                        "Declared text slot must have positive geometry and stay inside the 1280x720 canvas.",
                        canvas_width=CANVAS_WIDTH,
                        canvas_height=CANVAS_HEIGHT,
                        box_x=round(slot.box_x, 2),
                        box_y=round(slot.box_y, 2),
                        box_w=round(slot.box_w, 2),
                        box_h=round(slot.box_h, 2),
                    )
                )

            max_line_width = max(
                (estimate_text_width(line, slot.font_size, slot.font_weight) for line in slot.measure_lines),
                default=0.0,
            )
            line_height = slot.font_size * slot.line_height_ratio
            needed_h = max(1, len(slot.measure_lines)) * line_height
            if max_line_width > slot.box_w * WIDTH_TOLERANCE:
                issues.append(
                    _issue(
                        "SVG-TEXT-OVERFLOW-X",
                        slot,
                        "blocking",
                        "A declared text slot is too narrow for its longest rendered line.",
                        box_w=round(slot.box_w, 2),
                        estimated_line_w=round(max_line_width, 2),
                        line_count=len(slot.measure_lines),
                    )
                )
            if needed_h > slot.box_h * HEIGHT_TOLERANCE:
                issues.append(
                    _issue(
                        "SVG-TEXT-OVERFLOW-Y",
                        slot,
                        "blocking",
                        "A declared text slot is too short for its rendered line count.",
                        box_h=round(slot.box_h, 2),
                        estimated_text_h=round(needed_h, 2),
                        line_count=len(slot.measure_lines),
                    )
                )

    blocking = [issue for issue in issues if issue["severity"] == "blocking"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    return {
        "schema_version": SCHEMA_VERSION,
        "path": str(root),
        "status": "fail" if blocking else "pass",
        "svg_count": len(svg_files),
        "text_slot_count": slot_count,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "issues": issues,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate SVG text against fixed PPTX text slots.")
    parser.add_argument("path", help="SVG file or directory containing SVG files.")
    parser.add_argument("--strict-unboxed", action="store_true", help="Treat long text without data-pptx-box as blocking.")
    parser.add_argument("--unboxed-char-threshold", type=int, default=14)
    parser.add_argument(
        "--require-valign",
        action="store_true",
        help="Require every declared PPTX text box to state data-pptx-valign.",
    )
    parser.add_argument(
        "--check-canvas",
        action="store_true",
        help="Require declared text boxes to stay inside the 1280x720 canvas.",
    )
    parser.add_argument("--report", help="Optional JSON report path.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_svg_text_slots(
        args.path,
        strict_unboxed=args.strict_unboxed,
        unboxed_char_threshold=args.unboxed_char_threshold,
        require_valign=args.require_valign,
        check_canvas=args.check_canvas,
    )
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status'].upper()}: {report['blocking_count']} blocking, {report['warning_count']} warnings")
        for issue in report["issues"]:
            print(f"{issue['severity']}: {issue['code']} {issue['file']}#{issue['element_index']} {issue['message']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
