#!/usr/bin/env python3
"""Project facade for slide-image-to-editable PPTX reconstruction.

This script keeps image reconstruction as an upstream EasySlides workflow:
source images and analysis manifests live in a project folder, while final
PPTX output still goes through the existing SVG/shape-IR/DrawingML backend.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from scripts import (
        compare_source_render,
        slide_image_inventory,
        validate_image_reconstruction_pptx,
        validate_pptx_text_layout,
        validate_split_assets,
    )
except ImportError:  # pragma: no cover - direct script execution
    import compare_source_render
    import slide_image_inventory
    import validate_image_reconstruction_pptx
    import validate_pptx_text_layout
    import validate_split_assets


SCHEMA_VERSION = "easyslides.image_reconstruction_pipeline_report.v1"
RUN_SCHEMA_VERSION = "easyslides.image_reconstruction_project.v1"
PROJECT_DIRS = (
    "sources",
    "analysis",
    "pages/page_001/assets/split",
    "pptx",
    "reports",
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _ensure_project_dirs(project: Path) -> None:
    for rel_path in PROJECT_DIRS:
        (project / rel_path).mkdir(parents=True, exist_ok=True)


def _copy_source_images(project: Path, source_images: list[Path]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    source_dir = project / "sources"
    for index, source in enumerate(source_images, start=1):
        if not source.exists():
            raise FileNotFoundError(f"source image not found: {source}")
        suffix = source.suffix.lower() if source.suffix.lower() in IMAGE_SUFFIXES else ".png"
        target = source_dir / f"slide_{index:03d}{suffix}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        with Image.open(target) as image:
            width, height = image.size
        copied.append(
            {
                "slide_id": f"s{index:02d}",
                "source_image": _relative(target, project),
                "width_px": width,
                "height_px": height,
                "elements": [],
                "completeness_check": {
                    "performed": False,
                    "layer_a_count": 0,
                    "notes": "Fill Layer A/B/C inventory before assembly.",
                },
            }
        )
    return copied


def init_project(project: str | Path, source_images: list[str | Path], *, overwrite_analysis: bool = False) -> dict[str, Any]:
    project_path = Path(project)
    project_path.mkdir(parents=True, exist_ok=True)
    _ensure_project_dirs(project_path)
    slides = _copy_source_images(project_path, [Path(path) for path in source_images])

    inventory = {
        "schema_version": slide_image_inventory.INVENTORY_SCHEMA_VERSION,
        "reconstruction_mode": "faithful-practical",
        "slides": slides,
    }
    analysis_path = project_path / "analysis" / "_analysis.json"
    if analysis_path.exists() and not overwrite_analysis:
        raise FileExistsError(f"analysis already exists: {analysis_path}")
    _write_json(analysis_path, inventory)

    run_manifest = {
        "schema_version": RUN_SCHEMA_VERSION,
        "project_kind": "slide_image_reconstruction",
        "analysis": _relative(analysis_path, project_path),
        "sources": [slide["source_image"] for slide in slides],
        "paths": {
            "pages": "pages/",
            "pptx": "pptx/",
            "reports": "reports/",
        },
        "quality_modes": {
            "faithful-practical": "Text, structure, and asset gates are blocking; source-render pixel diff is advisory.",
            "pixel-strict": "Source-render pixel diff is blocking.",
        },
    }
    run_path = project_path / "image_reconstruction_run.json"
    _write_json(run_path, run_manifest)

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "status": "initialized",
        "project": str(project_path),
        "analysis": str(analysis_path),
        "run_manifest": str(run_path),
        "slide_count": len(slides),
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_source_images(project: Path, inventory_path: Path | None) -> list[Path]:
    if inventory_path and inventory_path.exists():
        inventory = _load_json(inventory_path)
        images: list[Path] = []
        for slide in inventory.get("slides", []):
            if not isinstance(slide, dict) or not slide.get("source_image"):
                continue
            raw = Path(str(slide["source_image"]))
            images.append(raw if raw.is_absolute() else project / raw)
        if images:
            return images
    source_dir = project / "sources"
    if not source_dir.exists():
        return []
    return sorted([path for path in source_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES], key=lambda item: item.name)


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _default_pptx(project: Path) -> Path | None:
    direct = _first_existing([project / "pptx" / "output.pptx", project / "exports" / "output.pptx"])
    if direct:
        return direct
    candidates = sorted((project / "pptx").glob("*.pptx")) + sorted((project / "exports").glob("*.pptx"))
    return candidates[0] if candidates else None


def _default_split_manifest(project: Path) -> Path | None:
    candidates = [
        project / "pages" / "page_001" / "assets" / "split_manifest_refined.json",
        project / "pages" / "page_001" / "assets" / "split_manifest.json",
    ]
    return _first_existing(candidates)


def _summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "status",
        "slide_count",
        "element_count",
        "text_box_count",
        "asset_count",
        "avg_mae",
        "avg_changed_pct",
        "contact_sheet",
    )
    return {key: report[key] for key in keys if key in report}


def _count(report: dict[str, Any], severity: str) -> int:
    key = f"{severity}_count"
    if key in report:
        try:
            return int(report[key])
        except (TypeError, ValueError):
            pass
    return sum(1 for issue in report.get("issues", []) if str(issue.get("severity")) == severity)


def _gate(name: str, report: dict[str, Any], report_path: Path, *, advisory: bool = False) -> dict[str, Any]:
    blocking = 0 if advisory else _count(report, "blocking")
    return {
        "name": name,
        "status": str(report.get("status") or "fail"),
        "advisory": advisory,
        "blocking_count": blocking,
        "raw_blocking_count": _count(report, "blocking"),
        "warning_count": _count(report, "warning"),
        "report": str(report_path),
        "summary": _summarize_report(report),
    }


def qa_project(
    project: str | Path,
    *,
    pptx: str | Path | None = None,
    rendered_dir: str | Path | None = None,
    source_images: list[str | Path] | None = None,
    inventory: str | Path | None = None,
    split_assets_manifest: str | Path | None = None,
    mode: str = "faithful-practical",
    fail_source_mae: float = 18.0,
    fail_source_changed_pct: float = 35.0,
    source_fit_mode: str = "contain",
) -> dict[str, Any]:
    if mode not in {"faithful-practical", "pixel-strict"}:
        raise ValueError("mode must be faithful-practical or pixel-strict")
    project_path = Path(project)
    reports_dir = project_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    inventory_path = Path(inventory) if inventory else project_path / "analysis" / "_analysis.json"
    pptx_path = Path(pptx) if pptx else _default_pptx(project_path)
    split_path = Path(split_assets_manifest) if split_assets_manifest else _default_split_manifest(project_path)
    rendered_path = Path(rendered_dir) if rendered_dir else project_path / "reports" / "rendered_png"
    source_paths = [Path(path) for path in source_images] if source_images else _default_source_images(project_path, inventory_path)

    gates: list[dict[str, Any]] = []

    if inventory_path.exists():
        inventory_report = slide_image_inventory.validate_inventory(_load_json(inventory_path))
        inventory_report_path = reports_dir / "slide_image_inventory_report.json"
        _write_json(inventory_report_path, inventory_report)
        gates.append(_gate("slide_image_inventory", inventory_report, inventory_report_path))

    if pptx_path and pptx_path.exists():
        structure_report = validate_image_reconstruction_pptx.validate_image_reconstruction_pptx(pptx_path)
        structure_report_path = reports_dir / "image_reconstruction_pptx_report.json"
        _write_json(structure_report_path, structure_report)
        gates.append(_gate("image_reconstruction_structure", structure_report, structure_report_path))

        text_report = validate_pptx_text_layout.validate_pptx_text_layout(pptx_path)
        text_report_path = reports_dir / "text_layout_report.json"
        _write_json(text_report_path, text_report)
        gates.append(_gate("pptx_text_layout", text_report, text_report_path))

    if split_path and split_path.exists():
        split_report = validate_split_assets.validate_split_assets(split_path)
        split_report_path = reports_dir / "split_assets_report.json"
        _write_json(split_report_path, split_report)
        gates.append(_gate("split_assets", split_report, split_report_path))

    if source_paths and rendered_path.exists():
        diff_dir = reports_dir / "source_render_diff"
        diff_report = compare_source_render.compare_source_images_to_render_dir(
            source_paths,
            rendered_path,
            diff_dir,
            fail_mae=fail_source_mae,
            fail_changed_pct=fail_source_changed_pct,
            fit_mode=source_fit_mode,
        )
        gates.append(
            _gate(
                "source_render_diff",
                diff_report,
                diff_dir / "metrics.json",
                advisory=mode == "faithful-practical",
            )
        )

    if not gates:
        raise ValueError("no QA gates ran; provide an inventory, PPTX, split manifest, or rendered PNG directory")

    blocking_count = sum(gate["blocking_count"] for gate in gates)
    warning_count = sum(gate["warning_count"] for gate in gates)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_count else "pass",
        "mode": mode,
        "project": str(project_path),
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "gates": gates,
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a slide-image reconstruction project scaffold.")
    init_parser.add_argument("project", help="Project directory.")
    init_parser.add_argument("source_images", nargs="+", help="Source slide image(s), in slide order.")
    init_parser.add_argument("--overwrite-analysis", action="store_true", help="Overwrite an existing analysis/_analysis.json.")

    qa_parser = subparsers.add_parser("qa", help="Run image reconstruction QA gates for a project.")
    qa_parser.add_argument("project", help="Project directory.")
    qa_parser.add_argument("--pptx", help="Reconstructed PPTX. Defaults to pptx/output.pptx or the first PPTX in pptx/exports.")
    qa_parser.add_argument("--rendered-dir", help="Directory containing rendered slide PNGs.")
    qa_parser.add_argument("--source-image", action="append", default=[], help="Source image; repeat in slide order.")
    qa_parser.add_argument("--inventory", help="Inventory JSON. Defaults to analysis/_analysis.json.")
    qa_parser.add_argument("--split-assets-manifest", help="Split asset manifest JSON.")
    qa_parser.add_argument("--mode", choices=["faithful-practical", "pixel-strict"], default="faithful-practical")
    qa_parser.add_argument("--fail-source-mae", type=float, default=18.0)
    qa_parser.add_argument("--fail-source-changed-pct", type=float, default=35.0)
    qa_parser.add_argument("--source-fit-mode", choices=["contain", "stretch"], default="contain")
    qa_parser.add_argument("--report", help="Output report path. Defaults to reports/image_reconstruction_pipeline_report.json.")
    qa_parser.add_argument("--quiet", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        report = init_project(args.project, args.source_images, overwrite_analysis=args.overwrite_analysis)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    report = qa_project(
        args.project,
        pptx=args.pptx,
        rendered_dir=args.rendered_dir,
        source_images=args.source_image,
        inventory=args.inventory,
        split_assets_manifest=args.split_assets_manifest,
        mode=args.mode,
        fail_source_mae=args.fail_source_mae,
        fail_source_changed_pct=args.fail_source_changed_pct,
        source_fit_mode=args.source_fit_mode,
    )
    report_path = Path(args.report) if args.report else Path(args.project) / "reports" / "image_reconstruction_pipeline_report.json"
    _write_json(report_path, report)
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
