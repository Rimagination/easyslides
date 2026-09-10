#!/usr/bin/env python3
"""Measure text/background contrast for generated and template-backed visuals."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "easyslides.readability_report.v1"
DEFAULT_LIGHT = "#FFFFFF"
DEFAULT_DARK = "#18212B"


class ReadabilityError(ValueError):
    """Raised when readability input is invalid or cannot be inspected."""


def hex_rgb(value: str) -> tuple[int, int, int]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6:
        raise ReadabilityError(f"expected a six-digit hex color, got {value!r}")
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError as exc:
        raise ReadabilityError(f"invalid hex color: {value!r}") from exc


def _linear(channel: int) -> float:
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_linear(channel) for channel in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str | tuple[int, int, int], background: str | tuple[int, int, int] | float) -> float:
    fg = relative_luminance(hex_rgb(foreground) if isinstance(foreground, str) else foreground)
    if isinstance(background, (int, float)):
        bg = float(background)
    else:
        bg = relative_luminance(hex_rgb(background) if isinstance(background, str) else background)
    lighter, darker = max(fg, bg), min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def choose_text_tone(
    background_luminance: float,
    *,
    light: str = DEFAULT_LIGHT,
    dark: str = DEFAULT_DARK,
    target: float = 4.5,
) -> dict[str, Any]:
    light_ratio = contrast_ratio(light, background_luminance)
    dark_ratio = contrast_ratio(dark, background_luminance)
    tone = "light" if light_ratio >= dark_ratio else "dark"
    ratio = max(light_ratio, dark_ratio)
    return {
        "tone": tone,
        "text_color": light if tone == "light" else dark,
        "contrast_ratio": round(ratio, 3),
        "light_contrast": round(light_ratio, 3),
        "dark_contrast": round(dark_ratio, 3),
        "passes": ratio >= float(target),
        "needs_scrim": ratio < float(target),
    }


def _load_image(path: Path):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency is optional at import time
        raise ReadabilityError("Pillow is required for image readability analysis") from exc
    if not path.is_file():
        raise ReadabilityError(f"image not found: {path}")
    try:
        return Image.open(path).convert("RGB")
    except OSError as exc:
        raise ReadabilityError(f"cannot decode image: {path}: {exc}") from exc


def _box(region: Mapping[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    raw = region.get("box") if isinstance(region.get("box"), Mapping) else region
    try:
        x = max(0, int(float(raw.get("x", 0))))
        y = max(0, int(float(raw.get("y", 0))))
        w = max(1, int(float(raw.get("width", raw.get("w", width)))))
        h = max(1, int(float(raw.get("height", raw.get("h", height)))))
    except (TypeError, ValueError) as exc:
        raise ReadabilityError(f"invalid readability region: {region!r}") from exc
    return min(x, width - 1), min(y, height - 1), min(width, x + w), min(height, y + h)


def _sample_luminances(image, region: Mapping[str, Any], grid: int = 24) -> list[float]:
    x0, y0, x1, y1 = _box(region, image.width, image.height)
    crop = image.crop((x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)))
    sample = crop.resize((min(grid, max(1, crop.width)), min(grid, max(1, crop.height))))
    flattened = getattr(sample, "get_flattened_data", None)
    pixels = flattened() if callable(flattened) else sample.getdata()
    return [relative_luminance(pixel) for pixel in pixels]


def _percentile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _coverage_after_scrim(values: Iterable[float], text_color: str, scrim_luminance: float, opacity: float, target: float) -> float:
    effective = [((1.0 - opacity) * value) + (opacity * scrim_luminance) for value in values]
    return sum(contrast_ratio(text_color, value) >= target for value in effective) / max(1, len(effective))


def _scrim_opacity_for_target(values: list[float], text_color: str, scrim_color: str, target: float, *, minimum: float) -> tuple[float, float]:
    scrim_luminance = relative_luminance(hex_rgb(scrim_color))
    required = 1.0
    for step in range(0, 96):
        opacity = step / 100.0
        if _coverage_after_scrim(values, text_color, scrim_luminance, opacity, target) >= 0.9:
            required = opacity
            break
    opacity = max(float(minimum), required)
    return opacity, _coverage_after_scrim(values, text_color, scrim_luminance, opacity, target)


def analyze_region(
    image,
    region: Mapping[str, Any],
    *,
    light: str = DEFAULT_LIGHT,
    dark: str = DEFAULT_DARK,
    target: float = 4.5,
) -> dict[str, Any]:
    values = _sample_luminances(image, region)
    median = _percentile(values, 0.5)
    p10 = _percentile(values, 0.1)
    p90 = _percentile(values, 0.9)
    chosen = choose_text_tone(median, light=light, dark=dark, target=target)
    coverage = sum(contrast_ratio(chosen["text_color"], value) >= target for value in values) / max(1, len(values))
    # A mixed/texture-heavy region should receive a scrim even when the median
    # happens to pass, because text strokes cross both the bright and dark tail.
    mixed = (p90 - p10) >= 0.34
    scrim_fill = dark if chosen["tone"] == "light" else light
    scrim_opacity, coverage_after_scrim = _scrim_opacity_for_target(
        values,
        chosen["text_color"],
        scrim_fill,
        target,
        minimum=0.28 if mixed else 0.18,
    )
    passes_before_scrim = bool(chosen["passes"] and coverage >= 0.9 and not mixed)
    passes_after_scrim = bool(coverage_after_scrim >= 0.9)
    return {
        "box": _box(region, image.width, image.height),
        "median_luminance": round(median, 4),
        "p10_luminance": round(p10, 4),
        "p90_luminance": round(p90, 4),
        "texture_range": round(p90 - p10, 4),
        "mixed_background": mixed,
        "coverage_at_target": round(coverage, 3),
        "coverage_after_scrim": round(coverage_after_scrim, 3),
        "tone": chosen["tone"],
        "text_color": chosen["text_color"],
        "contrast_ratio": chosen["contrast_ratio"],
        "passes_before_scrim": passes_before_scrim,
        "passes_after_scrim": passes_after_scrim,
        "passes": bool(passes_before_scrim or passes_after_scrim),
        "needs_scrim": bool(not passes_before_scrim),
        "scrim_fill": scrim_fill,
        "scrim_opacity": round(scrim_opacity, 3),
    }


def analyze_image(
    image_path: str | Path,
    regions: Iterable[Mapping[str, Any]],
    *,
    light: str = DEFAULT_LIGHT,
    dark: str = DEFAULT_DARK,
    target: float = 4.5,
) -> dict[str, Any]:
    path = Path(image_path).resolve()
    image = _load_image(path)
    results = [
        {"id": str(region.get("id") or f"region-{index + 1}"), **analyze_region(image, region, light=light, dark=dark, target=target)}
        for index, region in enumerate(regions)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(row["passes"] for row in results) else "fail",
        "image": str(path),
        "width": image.width,
        "height": image.height,
        "target_contrast": target,
        "regions": results,
        "blocking_count": sum(not row["passes"] for row in results),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure image/text contrast for EasySlides.")
    parser.add_argument("image")
    parser.add_argument("--regions", required=True, help="JSON file containing an array of regions.")
    parser.add_argument("--light", default=DEFAULT_LIGHT)
    parser.add_argument("--dark", default=DEFAULT_DARK)
    parser.add_argument("--target", type=float, default=4.5)
    parser.add_argument("--report", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        regions = json.loads(Path(args.regions).read_text(encoding="utf-8-sig"))
        if not isinstance(regions, list):
            raise ReadabilityError("--regions must contain a JSON array")
        report = analyze_image(args.image, regions, light=args.light, dark=args.dark, target=args.target)
        output = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            Path(args.report).resolve().write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0 if report["status"] == "pass" else 1
    except (OSError, ReadabilityError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
