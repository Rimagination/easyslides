#!/usr/bin/env python3
"""Compare source and generated PowerPoint render PNGs.

Use this after rendering the original PPTX and generated/reconstructed PPTX
with the same renderer and dimensions. It reports per-slide image differences
and writes a source/generated/diff contact sheet for visual review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat


PNG_EXTENSIONS = {".png", ".PNG"}


def slide_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10**9


def rendered_pngs(directory: Path) -> list[Path]:
    files = [path for path in directory.iterdir() if path.suffix in PNG_EXTENSIONS and path.is_file()]
    return sorted(files, key=slide_number)


def image_difference(source: Image.Image, generated: Image.Image) -> dict[str, float]:
    source = source.convert("RGB").resize((1280, 720))
    generated = generated.convert("RGB").resize((1280, 720))
    diff = ImageChops.difference(source, generated)
    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / 3
    rms = math.sqrt(sum(value * value for value in stat.rms) / 3)
    histogram = diff.convert("L").histogram()
    changed = sum(histogram[11:])
    return {
        "mae": round(mae, 4),
        "rms": round(rms, 4),
        "changed_pct": round(changed / (1280 * 720) * 100, 4),
    }


def contact_tile(image: Image.Image, label: str, *, size: tuple[int, int] = (260, 146)) -> Image.Image:
    thumb = image.convert("RGB").copy()
    thumb.thumbnail(size)
    canvas = Image.new("RGB", (size[0], size[1] + 20), "white")
    canvas.paste(thumb, ((size[0] - thumb.width) // 2, 0))
    ImageDraw.Draw(canvas).text((8, size[1] + 4), label, fill=(0, 0, 0))
    return canvas


def compare_render_dirs(
    source_dir: Path,
    generated_dir: Path,
    output_dir: Path,
    *,
    fail_avg_mae: float = 1.0,
    fail_max_mae: float = 3.0,
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    generated_dir = generated_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_files = rendered_pngs(source_dir)
    generated_files = rendered_pngs(generated_dir)
    slide_count = min(len(source_files), len(generated_files))
    if slide_count == 0:
        raise ValueError("no comparable PNG slides found")

    slides: list[dict[str, Any]] = []
    tiles: list[Image.Image] = []
    for index, (source_path, generated_path) in enumerate(zip(source_files, generated_files), start=1):
        source = Image.open(source_path).convert("RGB").resize((1280, 720))
        generated = Image.open(generated_path).convert("RGB").resize((1280, 720))
        diff = ImageChops.difference(source, generated)
        metrics = image_difference(source, generated)
        slides.append(
            {
                "slide": index,
                "source": source_path.name,
                "generated": generated_path.name,
                **metrics,
            }
        )
        heat = ImageOps.colorize(ImageOps.autocontrast(diff.convert("L")), black="#111111", white="#ff2b2b")
        tiles.extend(
            [
                contact_tile(source, f"slide {index} source"),
                contact_tile(generated, f"slide {index} generated"),
                contact_tile(heat, f"slide {index} diff"),
            ]
        )

    avg_mae = round(sum(slide["mae"] for slide in slides) / len(slides), 4)
    avg_changed_pct = round(sum(slide["changed_pct"] for slide in slides) / len(slides), 4)
    worst = max(slides, key=lambda item: item["mae"])
    contact_path = output_dir / "visual_diff_contact.png"
    tile_w, tile_h = tiles[0].size
    sheet = Image.new("RGB", (tile_w * 3, tile_h * len(slides)), "#f5f5f5")
    for offset, tile in enumerate(tiles):
        sheet.paste(tile, ((offset % 3) * tile_w, (offset // 3) * tile_h))
    sheet.save(contact_path)

    report = {
        "schema_version": "easyslides.pptx_visual_diff_report.v1",
        "status": "fail" if avg_mae > fail_avg_mae or worst["mae"] > fail_max_mae else "pass",
        "source_dir": str(source_dir),
        "generated_dir": str(generated_dir),
        "slide_count": slide_count,
        "avg_mae": avg_mae,
        "avg_changed_pct": avg_changed_pct,
        "worst_slide": worst,
        "thresholds": {"fail_avg_mae": fail_avg_mae, "fail_max_mae": fail_max_mae},
        "contact_sheet": str(contact_path),
        "slides": slides,
    }
    (output_dir / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two PowerPoint-rendered PNG folders.")
    parser.add_argument("source_dir", help="PNG folder rendered from the source PPTX.")
    parser.add_argument("generated_dir", help="PNG folder rendered from the generated PPTX.")
    parser.add_argument("--out", required=True, help="Output directory for metrics.json and contact sheet.")
    parser.add_argument("--fail-avg-mae", type=float, default=1.0)
    parser.add_argument("--fail-max-mae", type=float, default=3.0)
    args = parser.parse_args(argv)

    report = compare_render_dirs(
        Path(args.source_dir),
        Path(args.generated_dir),
        Path(args.out),
        fail_avg_mae=args.fail_avg_mae,
        fail_max_mae=args.fail_max_mae,
    )
    print(json.dumps({key: report[key] for key in ("status", "slide_count", "avg_mae", "avg_changed_pct", "worst_slide", "contact_sheet")}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
