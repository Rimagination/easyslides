#!/usr/bin/env python3
"""Compare native PowerPoint and LibreOffice renderings of the same PPTX."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.pptx_visual_diff import compare_render_dirs
    from scripts.render_pptx_png import render_pptx_to_png
except ModuleNotFoundError:  # pragma: no cover
    from pptx_visual_diff import compare_render_dirs
    from render_pptx_png import render_pptx_to_png


SCHEMA_VERSION = "easyslides.cross_renderer_visual_regression.v1"
RenderFunction = Callable[..., dict[str, Any]]


def run_cross_renderer_visual_regression(
    pptx_path: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 144,
    fail_avg_mae: float = 8.0,
    fail_max_mae: float = 50.0,
    renderer: RenderFunction = render_pptx_to_png,
) -> dict[str, Any]:
    pptx = Path(pptx_path).resolve()
    root = Path(output_dir).resolve()
    attempts: dict[str, dict[str, Any]] = {}
    for backend in ("powerpoint", "soffice"):
        try:
            report = renderer(pptx, root / backend, dpi=dpi, renderer_backend=backend)
            attempts[backend] = {"status": report.get("status", "fail"), "report": report}
        except FileNotFoundError as exc:
            attempts[backend] = {"status": "unavailable", "reason": str(exc)}
        except Exception as exc:  # A renderer failure is evidence, not a crash.
            attempts[backend] = {"status": "fail", "reason": str(exc)}
    if all(attempts[name]["status"] == "pass" for name in ("powerpoint", "soffice")):
        comparison = compare_render_dirs(
            root / "powerpoint",
            root / "soffice",
            output_dir=root / "comparison",
            fail_avg_mae=fail_avg_mae,
            fail_max_mae=fail_max_mae,
        )
        status = "pass" if comparison.get("status") == "pass" else "fail"
    else:
        comparison = None
        status = "review_required" if any(item["status"] == "unavailable" for item in attempts.values()) else "fail"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "pptx": str(pptx),
        "output_dir": str(root),
        "attempts": attempts,
        "comparison": comparison,
        "policy": {
            "required_backends": ["powerpoint", "soffice"],
            "when_one_backend_is_missing": "review_required",
            "when_both_backends_render": "fail_on_visual_threshold_exceedance",
            "fail_avg_mae": fail_avg_mae,
            "fail_max_mae": fail_max_mae,
        },
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "cross_renderer_visual_regression.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a cross-renderer PPTX visual regression.")
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--fail-avg-mae", type=float, default=8.0)
    parser.add_argument("--fail-max-mae", type=float, default=50.0)
    args = parser.parse_args(argv)
    report = run_cross_renderer_visual_regression(args.pptx, args.out, dpi=args.dpi, fail_avg_mae=args.fail_avg_mae, fail_max_mae=args.fail_max_mae)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
