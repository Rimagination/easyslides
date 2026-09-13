#!/usr/bin/env python3
"""Validate structural editability of a PPTX rebuilt from slide images."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
import zipfile

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

try:
    from scripts import alignment_contract, layout_metrics
except ImportError:  # pragma: no cover - direct script execution
    import alignment_contract
    import layout_metrics


SCHEMA_VERSION = "easyslides.image_reconstruction_pptx_report.v1"
FULL_SLIDE_PICTURE_THRESHOLD = 0.85


def _inches(value: int | float | None) -> float:
    return layout_metrics.emu_to_in(value)


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    slide_number: int,
    shape_name: str | None = None,
    suggestion: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "slide_number": slide_number,
        "message": message,
    }
    if shape_name:
        payload["shape_name"] = shape_name
    if suggestion:
        payload["suggestion"] = suggestion
    return payload


def _iter_shapes(shapes: Iterable[Any]) -> Iterable[Any]:
    for shape in shapes:
        if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.GROUP and hasattr(shape, "shapes"):
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def _shape_area_fraction(shape: Any, slide_area: float) -> float:
    if slide_area <= 0:
        return 0.0
    return max(0.0, _inches(shape.width)) * max(0.0, _inches(shape.height)) / slide_area


def _has_visible_text(shape: Any) -> bool:
    return bool(getattr(shape, "has_text_frame", False) and shape.text_frame and shape.text_frame.text.strip())


def validate_image_reconstruction_pptx(
    pptx_path: str | Path,
    *,
    full_slide_picture_threshold: float = FULL_SLIDE_PICTURE_THRESHOLD,
    production_scheme: str = "image_full_rebuild",
    reconstruction_mode: str = "preserve_complex_images",
    inventory: dict[str, Any] | None = None,
    require_source_text_lines: bool = False,
) -> dict[str, Any]:
    if production_scheme not in {"image_full_rebuild", "image_partial_rebuild"}:
        raise ValueError("expected an image reconstruction production_scheme")
    if reconstruction_mode not in {"full_vector", "preserve_complex_images"}:
        raise ValueError("invalid reconstruction_mode")
    prs = Presentation(str(pptx_path))
    slide_w = _inches(prs.slide_width)
    slide_h = _inches(prs.slide_height)
    slide_area = slide_w * slide_h
    issues: list[dict[str, Any]] = []
    slides: list[dict[str, Any]] = []
    expected_slides = (inventory or {}).get("slides", [])
    if not prs.slides or (inventory is not None and len(expected_slides) != len(prs.slides)):
        issues.append(_issue("PPTX-SLIDE-COUNT", "blocking", "Nonempty PPTX and inventory slide counts must match.", slide_number=0))

    for slide_number, slide in enumerate(prs.slides, start=1):
        text_frame_count = 0
        native_shape_count = 0
        native_table_count = 0
        picture_count = 0
        max_picture_area_fraction = 0.0
        text_boxes = []
        expected = expected_slides[slide_number - 1] if slide_number <= len(expected_slides) else {}
        untouched = production_scheme == "image_partial_rebuild" and expected.get("reconstruction_regions") == []
        exceptions = expected.get("approved_raster_exceptions", [])
        approved = {item["shape_name"] for item in exceptions if isinstance(item, dict) and item.get("shape_name") and item.get("approval")}

        for shape in _iter_shapes(slide.shapes):
            shape_type = getattr(shape, "shape_type", None)
            if getattr(shape, "has_table", False):
                native_table_count += 1
                cells = [cell.text for row in shape.table.rows for cell in row.cells if cell.text.strip()]
                text_boxes.extend(cells)
                text_frame_count += len(cells)
            if _has_visible_text(shape):
                text_frame_count += 1
                text_boxes.append(shape.text_frame.text)
            if shape_type == MSO_SHAPE_TYPE.PICTURE:
                picture_count += 1
                area_fraction = _shape_area_fraction(shape, slide_area)
                max_picture_area_fraction = max(max_picture_area_fraction, area_fraction)
                retained_background = production_scheme == "image_partial_rebuild" and shape.name == "source_background"
                if reconstruction_mode == "full_vector" and not retained_background and shape.name not in approved:
                    issues.append(_issue("PPTX-UNAPPROVED-RASTER", "blocking", "Full-vector reconstruction contains an unapproved picture.", slide_number=slide_number, shape_name=shape.name))
                if area_fraction >= full_slide_picture_threshold and not retained_background:
                    issues.append(
                        _issue(
                            "PPTX-FULL-SLIDE-PICTURE",
                            "blocking",
                            f"Picture covers {area_fraction:.1%} of the slide, which likely means a full-slide screenshot was used.",
                            slide_number=slide_number,
                            shape_name=getattr(shape, "name", None),
                            suggestion="Split the source into visual assets, native structure, and editable text instead of placing one large image.",
                        )
                    )
            elif shape_type in {MSO_SHAPE_TYPE.AUTO_SHAPE, MSO_SHAPE_TYPE.FREEFORM, MSO_SHAPE_TYPE.LINE, MSO_SHAPE_TYPE.CHART, MSO_SHAPE_TYPE.TABLE}:
                native_shape_count += 1

        if text_frame_count == 0:
            issues.append(
                _issue(
                    "PPTX-NO-EDITABLE-TEXT",
                    "warning",
                    "Slide has no editable text frames.",
                    slide_number=slide_number,
                    suggestion="If the source image contains readable text, extract it into native PowerPoint text boxes.",
                )
            )
        if native_shape_count == 0:
            issues.append(
                _issue(
                    "PPTX-NO-NATIVE-STRUCTURE",
                    "warning",
                    "Slide has no native structure shapes, tables, charts, or lines.",
                    slide_number=slide_number,
                    suggestion="Simple panels, arrows, dividers, and badges should be rebuilt as native DrawingML/PPT shapes.",
                )
            )
        if text_frame_count == 0 and native_shape_count == 0 and not untouched:
            issues.append(
                _issue(
                    "PPTX-SINGLE-PICTURE-ONLY" if picture_count == 1 else "PPTX-NO-EDITABLE-OBJECTS",
                    "blocking",
                    "Slide has no editable text or native structure.",
                    slide_number=slide_number,
                )
            )

        if inventory is not None:
            normalize = lambda value: "".join(str(value).split())
            actual_lines = Counter(normalize(line) for box in text_boxes for line in box.splitlines() if line.strip())
            element_lines = [line for element in expected.get("elements", []) if element.get("layer") == "C"
                             for line in str(element.get("text", "")).splitlines() if line.strip()]
            source_lines = expected.get("source_text_lines")
            has_text = any(element.get("layer") == "C" for element in expected.get("elements", []))
            if "source_text_lines" in expected or (require_source_text_lines and has_text):
                valid = isinstance(source_lines, list) and all(
                    isinstance(line, str) and line.strip() and len(line.splitlines()) == 1 for line in source_lines
                ) and (bool(source_lines) or not has_text)
                if not valid:
                    issues.append(_issue("PPTX-SOURCE-TEXT-LINES", "blocking", "Record source_text_lines as complete, source-reviewed text lines before acceptance.", slide_number=slide_number))
                    source_lines = element_lines
                elif Counter(normalize("".join(element_lines))) - Counter(normalize("".join(source_lines))):
                    issues.append(_issue("PPTX-SOURCE-TEXT-LINES", "blocking", "Source-reviewed lines omit text from Layer C; reconcile the inventory against the source.", slide_number=slide_number))
            else:
                source_lines = element_lines
            expected_lines = Counter(normalize(line) for line in source_lines)
            for line, count in expected_lines.items():
                if actual_lines[line] < count:
                    issues.append(_issue("PPTX-TEXT-COVERAGE", "blocking", f"Expected source line missing or split across text boxes: {line}", slide_number=slide_number))

        slides.append(
            {
                "slide_number": slide_number,
                "text_frame_count": text_frame_count,
                "native_shape_count": native_shape_count,
                "native_table_count": native_table_count,
                "picture_count": picture_count,
                "max_picture_area_fraction": round(max_picture_area_fraction, 4),
            }
        )

    alignment_report: dict[str, Any] | None = None
    if inventory is not None and (
        isinstance(inventory.get("alignment_contract"), dict)
        or str(inventory.get("production_scheme") or "").startswith("image_")
    ):
        try:
            alignment_report = alignment_contract.validate_pptx_alignment(pptx_path, inventory)
            issues.extend(alignment_report.get("issues", []))
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            issues.append(
                _issue(
                    "PPTX-ALIGNMENT-READ",
                    "blocking",
                    f"Unable to inspect native text geometry against the alignment contract: {exc}",
                    slide_number=0,
                )
            )

    blocking_count = sum(1 for issue in issues if issue["severity"] == "blocking")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_count else "pass",
        "pptx_path": str(Path(pptx_path).resolve()),
        "slide_count": len(prs.slides),
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "thresholds": {"full_slide_picture_area_fraction": full_slide_picture_threshold},
        "production_scheme": production_scheme,
        "reconstruction_mode": reconstruction_mode,
        "alignment": {
            "checked": alignment_report is not None,
            "status": alignment_report.get("status") if alignment_report else "skipped",
            "checked_text_count": alignment_report.get("checked_text_count", 0) if alignment_report else 0,
        },
        "slides": slides,
        "issues": issues,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate PPTX structural editability after slide-image reconstruction.")
    parser.add_argument("pptx", help="PPTX file to validate.")
    parser.add_argument("--report", help="Optional JSON report path.")
    parser.add_argument("--full-slide-picture-threshold", type=float, default=FULL_SLIDE_PICTURE_THRESHOLD)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--production-scheme", choices=["image_full_rebuild", "image_partial_rebuild"], default="image_full_rebuild")
    parser.add_argument("--reconstruction-mode", choices=["full_vector", "preserve_complex_images"], default="preserve_complex_images")
    parser.add_argument("--inventory", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_image_reconstruction_pptx(
        args.pptx,
        full_slide_picture_threshold=args.full_slide_picture_threshold,
        production_scheme=args.production_scheme,
        reconstruction_mode=args.reconstruction_mode,
        inventory=json.loads(args.inventory.read_text(encoding="utf-8")) if args.inventory else None,
    )
    if args.report:
        _write_json(Path(args.report), report)
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
