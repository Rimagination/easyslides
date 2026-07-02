#!/usr/bin/env python3
"""Validate split visual assets produced by image-to-editable PPT runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


SCHEMA_VERSION = "easyslides.split_asset_report.v1"
CLOSED_SHAPE_TERMS = {
    "circle",
    "circular",
    "ring",
    "round",
    "badge",
    "loop",
    "圆",
    "圆圈",
    "环形",
}


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    asset_name: str,
    asset_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
        "asset_name": asset_name,
    }
    if asset_path:
        payload["asset_path"] = asset_path
    if details:
        payload["details"] = details
    return payload


def _contains_term(value: str, terms: set[str]) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in terms)


def _looks_closed(asset: dict[str, Any]) -> bool:
    if asset.get("expected_closed_shape") is True or asset.get("closed_shape") is True:
        return True
    text = " ".join(str(asset.get(key, "")) for key in ("name", "description", "shape_role"))
    return _contains_term(text, CLOSED_SHAPE_TERMS)


def _preserves_source_frame(asset: dict[str, Any]) -> bool:
    return str(asset.get("source_type") or "").lower() in {"preserve_source_frame", "preserve_full_frame"}


def _resolve_asset_path(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    candidates = [
        manifest_path.parent / path,
        manifest_path.parent.parent / path,
        manifest_path.parent.parent.parent / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _alpha_bbox(path: Path, threshold: int) -> tuple[tuple[int, int, int, int] | None, tuple[int, int]]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A").point(lambda p: 255 if p > threshold else 0, mode="L")
        return alpha.getbbox(), rgba.size


def _edge_margins(bbox: tuple[int, int, int, int], size: tuple[int, int]) -> dict[str, int]:
    width, height = size
    left, top, right, bottom = bbox
    margins = {
        "left": left,
        "top": top,
        "right": width - right,
        "bottom": height - bottom,
    }
    margins["min"] = min(margins.values())
    return margins


def validate_split_assets(
    manifest_path: str | Path,
    *,
    alpha_threshold: int = 20,
    min_transparent_margin_px: int = 2,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        assets = []

    issues: list[dict[str, Any]] = []
    asset_reports: list[dict[str, Any]] = []
    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or f"asset_{index:02d}")
        raw_path = str(asset.get("path") or "")
        if not raw_path:
            issues.append(_issue("ASSET-PATH-MISSING", "blocking", "Split asset entry is missing path.", asset_name=name))
            continue
        path = _resolve_asset_path(manifest_path, raw_path)
        if not path.exists():
            issues.append(
                _issue(
                    "ASSET-FILE-MISSING",
                    "blocking",
                    "Split asset file does not exist.",
                    asset_name=name,
                    asset_path=str(path),
                )
            )
            continue

        bbox, size = _alpha_bbox(path, alpha_threshold)
        if bbox is None:
            issues.append(
                _issue(
                    "ASSET-EMPTY-ALPHA",
                    "blocking",
                    "Split asset has no opaque foreground pixels.",
                    asset_name=name,
                    asset_path=str(path),
                )
            )
            continue

        margins = _edge_margins(bbox, size)
        closed_shape = _looks_closed(asset)
        asset_reports.append(
            {
                "name": name,
                "path": str(path),
                "size": list(size),
                "alpha_bbox": list(bbox),
                "edge_margins_px": margins,
                "closed_shape": closed_shape,
            }
        )
        if margins["min"] < min_transparent_margin_px:
            if _preserves_source_frame(asset):
                continue
            details = {
                "alpha_bbox": list(bbox),
                "size": list(size),
                "edge_margins_px": margins,
                "min_transparent_margin_px": min_transparent_margin_px,
            }
            severity = "blocking" if closed_shape else "warning"
            code = "ASSET-CLOSED-SHAPE-CLIPPED" if closed_shape else "ASSET-FOREGROUND-TOUCHES-EDGE"
            message = (
                "Closed/circular asset foreground touches the image edge, so the source outline may have been clipped."
                if closed_shape
                else "Asset foreground touches the image edge; add padding or check whether the split crop clipped content."
            )
            issues.append(_issue(code, severity, message, asset_name=name, asset_path=str(path), details=details))

    blocking_count = sum(1 for issue in issues if issue["severity"] == "blocking")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_count else "pass",
        "manifest": str(manifest_path),
        "asset_count": len(assets),
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "thresholds": {
            "alpha_threshold": alpha_threshold,
            "min_transparent_margin_px": min_transparent_margin_px,
        },
        "assets": asset_reports,
        "issues": issues,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate split image assets for clipping and alpha margins.")
    parser.add_argument("manifest", help="split_manifest.json path.")
    parser.add_argument("--report", help="Optional JSON report path.")
    parser.add_argument("--alpha-threshold", type=int, default=20)
    parser.add_argument("--min-transparent-margin-px", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_split_assets(
        args.manifest,
        alpha_threshold=args.alpha_threshold,
        min_transparent_margin_px=args.min_transparent_margin_px,
    )
    if args.report:
        _write_json(Path(args.report), report)
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
