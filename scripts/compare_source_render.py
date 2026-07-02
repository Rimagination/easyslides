#!/usr/bin/env python3
"""Compare source slide images against rendered PPTX slide PNGs.

This gate is for image-to-editable reconstruction: the source of truth is an
image, not another PPTX. It compares each source image with the rendered output
slide after ratio-safe fitting, writes a contact sheet, and reports numeric
differences for CI or manual review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat


SCHEMA_VERSION = "easyslides.source_render_compare_report.v1"
PNG_EXTENSIONS = {".png", ".PNG"}


def _slide_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10**9


def rendered_pngs(directory: Path) -> list[Path]:
    files = [path for path in directory.iterdir() if path.suffix in PNG_EXTENSIONS and path.is_file()]
    return sorted(files, key=_slide_number)


def _fit_contain(image: Image.Image, size: tuple[int, int], *, background: str = "white") -> Image.Image:
    canvas = Image.new("RGB", size, background)
    fitted = ImageOps.contain(image.convert("RGB"), size)
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return canvas


def _normalized_pair(
    source: Image.Image,
    rendered: Image.Image,
    *,
    sample_size: tuple[int, int] = (1280, 720),
    fit_mode: str = "contain",
) -> tuple[Image.Image, Image.Image]:
    rendered_norm = rendered.convert("RGB").resize(sample_size)
    if fit_mode == "stretch":
        source_norm = source.convert("RGB").resize(sample_size)
    else:
        source_norm = _fit_contain(source, sample_size)
    return source_norm, rendered_norm


def _metrics(source: Image.Image, rendered: Image.Image) -> dict[str, float]:
    diff = ImageChops.difference(source, rendered)
    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / 3
    rms = math.sqrt(sum(value * value for value in stat.rms) / 3)
    histogram = diff.convert("L").histogram()
    changed = sum(histogram[11:])
    return {
        "mae": round(mae, 4),
        "rms": round(rms, 4),
        "changed_pct": round(changed / (source.width * source.height) * 100, 4),
    }


def _worst_regions(source: Image.Image, rendered: Image.Image, *, cols: int = 8, rows: int = 4, limit: int = 3) -> list[dict[str, Any]]:
    diff = ImageChops.difference(source, rendered)
    cell_w = source.width // cols
    cell_h = source.height // rows
    regions: list[dict[str, Any]] = []
    for row in range(rows):
        for col in range(cols):
            left = col * cell_w
            top = row * cell_h
            right = source.width if col == cols - 1 else (col + 1) * cell_w
            bottom = source.height if row == rows - 1 else (row + 1) * cell_h
            crop = diff.crop((left, top, right, bottom))
            stat = ImageStat.Stat(crop)
            mae = sum(stat.mean) / 3
            regions.append(
                {
                    "bbox_px": [left, top, right - left, bottom - top],
                    "mae": round(mae, 4),
                }
            )
    return sorted(regions, key=lambda item: item["mae"], reverse=True)[:limit]


def _contact_tile(image: Image.Image, label: str, *, size: tuple[int, int] = (300, 169)) -> Image.Image:
    thumb = image.convert("RGB").copy()
    thumb.thumbnail(size)
    canvas = Image.new("RGB", (size[0], size[1] + 22), "white")
    canvas.paste(thumb, ((size[0] - thumb.width) // 2, 0))
    ImageDraw.Draw(canvas).text((8, size[1] + 5), label, fill=(0, 0, 0))
    return canvas


def compare_source_images_to_render_dir(
    source_images: list[str | Path],
    rendered_dir: str | Path,
    output_dir: str | Path,
    *,
    fail_mae: float = 18.0,
    fail_changed_pct: float = 35.0,
    fit_mode: str = "contain",
) -> dict[str, Any]:
    sources = [Path(path).resolve() for path in source_images]
    rendered_files = rendered_pngs(Path(rendered_dir).resolve())
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not sources:
        raise ValueError("at least one source image is required")
    if not rendered_files:
        raise ValueError("no rendered slide PNGs found")

    slide_count = min(len(sources), len(rendered_files))
    slides: list[dict[str, Any]] = []
    tiles: list[Image.Image] = []
    issues: list[dict[str, Any]] = []

    if len(sources) != len(rendered_files):
        issues.append(
            {
                "code": "SOURCE-RENDER-SLIDE-COUNT-MISMATCH",
                "severity": "warning",
                "message": "Source image count and rendered slide PNG count differ; only comparable pairs were measured.",
                "source_count": len(sources),
                "rendered_count": len(rendered_files),
            }
        )

    for index, (source_path, rendered_path) in enumerate(zip(sources, rendered_files), start=1):
        source = Image.open(source_path)
        rendered = Image.open(rendered_path)
        source_norm, rendered_norm = _normalized_pair(source, rendered, fit_mode=fit_mode)
        diff = ImageChops.difference(source_norm, rendered_norm)
        heat = ImageOps.colorize(ImageOps.autocontrast(diff.convert("L")), black="#111111", white="#ff2b2b")
        metrics = _metrics(source_norm, rendered_norm)
        regions = _worst_regions(source_norm, rendered_norm)
        slide_report = {
            "slide": index,
            "source": str(source_path),
            "rendered": str(rendered_path),
            "source_size_px": list(source.size),
            "rendered_size_px": list(rendered.size),
            "fit_mode": fit_mode,
            **metrics,
            "worst_regions": regions,
        }
        slides.append(slide_report)
        if metrics["mae"] > fail_mae or metrics["changed_pct"] > fail_changed_pct:
            issues.append(
                {
                    "code": "SOURCE-RENDER-DIFF-THRESHOLD",
                    "severity": "blocking",
                    "slide": index,
                    "message": "Rendered slide differs from the source image beyond configured thresholds.",
                    "details": {
                        "mae": metrics["mae"],
                        "changed_pct": metrics["changed_pct"],
                        "worst_regions": regions,
                    },
                }
            )

        tiles.extend(
            [
                _contact_tile(source_norm, f"slide {index} source"),
                _contact_tile(rendered_norm, f"slide {index} rendered"),
                _contact_tile(heat, f"slide {index} diff"),
            ]
        )

    tile_w, tile_h = tiles[0].size
    contact_path = output / "source_render_contact.png"
    sheet = Image.new("RGB", (tile_w * 3, tile_h * slide_count), "#f5f5f5")
    for offset, tile in enumerate(tiles):
        sheet.paste(tile, ((offset % 3) * tile_w, (offset // 3) * tile_h))
    sheet.save(contact_path)

    avg_mae = round(sum(slide["mae"] for slide in slides) / slide_count, 4)
    avg_changed_pct = round(sum(slide["changed_pct"] for slide in slides) / slide_count, 4)
    blocking_count = sum(1 for issue in issues if issue["severity"] == "blocking")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_count else "pass",
        "slide_count": slide_count,
        "source_count": len(sources),
        "rendered_count": len(rendered_files),
        "avg_mae": avg_mae,
        "avg_changed_pct": avg_changed_pct,
        "worst_slide": max(slides, key=lambda item: item["mae"]),
        "thresholds": {"fail_mae": fail_mae, "fail_changed_pct": fail_changed_pct},
        "contact_sheet": str(contact_path),
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "issues": issues,
        "slides": slides,
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_images", nargs="+", help="Source slide image(s), in slide order.")
    parser.add_argument("--rendered-dir", required=True, help="Directory containing rendered slide_###.png files.")
    parser.add_argument("--out", required=True, help="Output directory for metrics.json and contact sheet.")
    parser.add_argument("--fail-mae", type=float, default=18.0)
    parser.add_argument("--fail-changed-pct", type=float, default=35.0)
    parser.add_argument("--fit-mode", choices=["contain", "stretch"], default="contain")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = compare_source_images_to_render_dir(
        args.source_images,
        args.rendered_dir,
        args.out,
        fail_mae=args.fail_mae,
        fail_changed_pct=args.fail_changed_pct,
        fit_mode=args.fit_mode,
    )
    if not args.quiet:
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("status", "slide_count", "avg_mae", "avg_changed_pct", "worst_slide", "contact_sheet")
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
