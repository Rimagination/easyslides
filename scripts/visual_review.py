#!/usr/bin/env python3
"""Create a visual review package for a rendered or renderable PPTX deck."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

try:
    from scripts.render_pptx_png import render_pptx_to_png
except ImportError:  # pragma: no cover - direct script execution
    from render_pptx_png import render_pptx_to_png


SCHEMA_VERSION = "easyslides.visual_review.v1"
PNG_EXTENSIONS = {".png", ".PNG"}


def _slide_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10**9


def rendered_pngs(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix in PNG_EXTENSIONS],
        key=_slide_number,
    )


def _contact_tile(image_path: Path, label: str, *, size: tuple[int, int]) -> Image.Image:
    thumb = Image.open(image_path).convert("RGB")
    thumb.thumbnail(size)
    label_h = 26
    canvas = Image.new("RGB", (size[0], size[1] + label_h), "#f7f7f5")
    canvas.paste(thumb, ((size[0] - thumb.width) // 2, (size[1] - thumb.height) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, size[1] + 7), label, fill="#1f2328")
    return canvas


def create_contact_sheet(
    image_files: list[Path],
    output_path: str | Path,
    *,
    columns: int = 4,
    tile_size: tuple[int, int] = (280, 158),
) -> Path:
    if not image_files:
        raise ValueError("no rendered slide PNGs found")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = max(1, columns)
    tiles = [
        _contact_tile(path, f"slide {index:03d}", size=tile_size)
        for index, path in enumerate(image_files, start=1)
    ]
    tile_w, tile_h = tiles[0].size
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (tile_w * columns, tile_h * rows), "#e8e8e3")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * tile_w, (index // columns) * tile_h))
    sheet.save(output)
    return output


def _stage_slide_images(image_files: list[Path], output: Path) -> list[Path]:
    slides_dir = output / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for source in image_files:
        # Keep the source page number so a filtered review (e.g. --slides 8)
        # still refers to the deck's real slide numbers, not a re-numbered 1..N.
        target = slides_dir / f"slide_{_slide_number(source):03d}.png"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        staged.append(target)
    return staged


def _html_review(manifest: dict[str, Any]) -> str:
    title = html.escape(str(manifest["title"]))
    slides = manifest.get("slides", [])
    rows = []
    for slide in slides:
        image = html.escape(str(slide["image"]))
        alt = html.escape(f"slide {slide['slide']:03d}")
        rows.append(
            f"""<section class="slide">
  <img src="{image}" alt="{alt}">
  <div class="checks">
    <label><input type="checkbox"> readable</label>
    <label><input type="checkbox"> aligned</label>
    <label><input type="checkbox"> complete</label>
  </div>
</section>"""
        )
    body = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; }}
    body {{ margin: 0; background: #f4f4f1; color: #171717; }}
    header {{ padding: 20px 28px 12px; border-bottom: 1px solid #d9d9d2; }}
    h1 {{ font-size: 22px; line-height: 1.25; margin: 0; letter-spacing: 0; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; padding: 22px 28px 30px; }}
    .slide {{ background: #ffffff; border: 1px solid #dadad2; border-radius: 8px; overflow: hidden; }}
    img {{ display: block; width: 100%; height: auto; background: #fff; }}
    .checks {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 10px 12px 12px; font-size: 13px; }}
    label {{ display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }}
  </style>
</head>
<body>
  <header><h1>{title}</h1></header>
  <main>
{body}
  </main>
</body>
</html>
"""


def build_review_package(
    pptx_path: str | Path,
    output_dir: str | Path,
    *,
    rendered_dir: str | Path | None = None,
    skip_render: bool = False,
    dpi: int = 144,
    title: str | None = None,
    only_pages: set[int] | None = None,
) -> dict[str, Any]:
    pptx = Path(pptx_path).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    slides_dir = Path(rendered_dir).resolve() if rendered_dir else output / "slides"

    if not skip_render:
        render_report = render_pptx_to_png(pptx, slides_dir, dpi=dpi)
    else:
        render_report = {
            "schema_version": "easyslides.pptx_render_png_report.v1",
            "status": "pass" if rendered_pngs(slides_dir) else "fail",
            "pptx_path": str(pptx),
            "output_dir": str(slides_dir),
            "renderer": "pre-rendered",
            "dpi": dpi,
        }

    image_files = rendered_pngs(slides_dir)
    if only_pages:
        image_files = [
            path for path in image_files
            if _slide_number(path) in only_pages
        ]
    if not image_files:
        raise ValueError(f"no rendered slide PNGs found: {slides_dir}")
    image_files = _stage_slide_images(image_files, output)

    contact_sheet = create_contact_sheet(image_files, output / "contact_sheet.png")
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_review",
        "title": title or f"Visual review: {pptx.name}",
        "pptx_path": str(pptx),
        "output_dir": str(output),
        "render_report": render_report,
        "rendered_dir": str(slides_dir),
        "slide_count": len(image_files),
        "contact_sheet": contact_sheet.name,
        "html": "index.html",
        "slides": [
            {
                "slide": _slide_number(path),
                "image": path.relative_to(output).as_posix(),
                "checks": ["readable", "aligned", "complete"],
            }
            for path in image_files
        ],
    }
    (output / "visual_review.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "index.html").write_text(_html_review(manifest), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a deck visual review package.")
    parser.add_argument("pptx", help="PPTX file to review.")
    parser.add_argument("--out", required=True, help="Output directory for review artifacts.")
    parser.add_argument("--rendered-dir", help="Use an existing rendered PNG directory.")
    parser.add_argument("--skip-render", action="store_true", help="Do not render; require --rendered-dir or existing --out/slides PNGs.")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--slides", help=(
        "Comma-separated 1-based slide numbers to keep in the review package, "
        "e.g. --slides 1,8,14. Rendering still processes the whole deck "
        "(the backend converts the file as a whole); the filter limits which "
        "slides enter the manifest, contact sheet, and HTML — useful for "
        "re-reviewing just the pages you fixed against --rendered-dir."
    ))
    parser.add_argument("--title")
    parser.add_argument("--quiet", action="store_true")
    return parser


def parse_slide_filter(spec: str | None) -> set[int] | None:
    """'1,8-10' -> {1, 8, 9, 10}; None when no filter given."""
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            lo, _, hi = part.partition('-')
            pages.update(range(int(lo), int(hi) + 1))
        else:
            pages.add(int(part))
    return pages or None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = build_review_package(
            args.pptx,
            args.out,
            rendered_dir=args.rendered_dir,
            skip_render=args.skip_render,
            dpi=args.dpi,
            title=args.title,
            only_pages=parse_slide_filter(args.slides),
        )
    except Exception as exc:
        if not args.quiet:
            print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if not args.quiet:
        print(json.dumps({
            "status": manifest["status"],
            "slide_count": manifest["slide_count"],
            "review": str(Path(manifest["output_dir"]) / manifest["html"]),
            "contact_sheet": str(Path(manifest["output_dir"]) / manifest["contact_sheet"]),
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
