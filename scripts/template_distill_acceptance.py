#!/usr/bin/env python3
"""Run distillation acceptance gates for an EasySlides template.

This CLI turns the PPT distillation review checklist into a repeatable gate:

1. validate the source-faithful template pack
2. export native PPTX and validate text/geometry
3. build a cross-material adaptation smoke test
4. validate the smoke SVG/PPTX output
5. optionally render contact-sheet thumbnails when a renderer is available

It does not replace human visual review. It makes missing or skipped visual
review explicit in a machine-readable report so a template cannot quietly pass
because a renderer or manual step was absent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"
SCHEMA_VERSION = "easyslides.template_distill_acceptance_report.v1"

try:
    from scripts.render_pptx_png import _find_powerpoint_executable
except ImportError:  # pragma: no cover - direct script execution
    from render_pptx_png import _find_powerpoint_executable


@dataclass
class Gate:
    gate_id: str
    description: str
    command: list[str]
    required: bool = True
    report_path: Path | None = None
    artifacts: dict[str, str] = field(default_factory=dict)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def template_id_from_dir(template_dir: Path) -> str:
    layouts = template_dir / "layouts.json"
    if layouts.exists():
        try:
            payload = json.loads(layouts.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict) and payload.get("template_id"):
                return str(payload["template_id"])
        except Exception:
            pass
    return template_dir.name


def is_under_tmp(path: Path) -> bool:
    try:
        path.resolve().relative_to(TMP_ROOT.resolve())
        return True
    except ValueError:
        return False


def short_output(text: str | None, limit: int = 4000) -> str:
    if text is None:
        return ""
    text = text.replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    head = text[: limit // 2].rstrip()
    tail = text[-limit // 2 :].lstrip()
    return f"{head}\n... <truncated> ...\n{tail}"


def child_process_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def run_gate(gate: Gate, *, cwd: Path, dry_run: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    if dry_run:
        return {
            "id": gate.gate_id,
            "description": gate.description,
            "required": gate.required,
            "status": "planned",
            "command": gate.command,
            "artifacts": gate.artifacts,
        }

    completed = subprocess.run(
        gate.command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_process_env(),
    )
    duration = round(time.perf_counter() - started, 3)
    status = "pass" if completed.returncode == 0 else ("fail" if gate.required else "warning")
    result: dict[str, Any] = {
        "id": gate.gate_id,
        "description": gate.description,
        "required": gate.required,
        "status": status,
        "returncode": completed.returncode,
        "duration_seconds": duration,
        "command": gate.command,
        "stdout": short_output(completed.stdout),
        "stderr": short_output(completed.stderr),
        "artifacts": gate.artifacts,
    }
    if gate.report_path is not None and gate.report_path.exists():
        try:
            report = json.loads(gate.report_path.read_text(encoding="utf-8-sig"))
            if isinstance(report, dict):
                result["report_status"] = report.get("status")
                for key in ("blocking_count", "warning_count", "text_box_count", "page_count", "slide_count"):
                    if key in report:
                        result[key] = report[key]
        except Exception as exc:
            result["report_read_error"] = str(exc)
    return result


def renderer_available() -> bool:
    return (
        _find_powerpoint_executable() is not None
        or shutil.which("soffice") is not None
        or shutil.which("libreoffice") is not None
    )


def build_gate_plan(
    *,
    template_dir: Path,
    output_dir: Path,
    forbidden_keywords: list[str],
    run_smoke: bool,
    render_contact: bool,
    require_render: bool,
) -> list[Gate]:
    template_id = template_id_from_dir(template_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    review_pptx = output_dir / f"{template_id}_review.pptx"
    smoke_dir = output_dir / f"{template_id}_material_smoke"
    smoke_pptx = output_dir / f"{template_id}_material_smoke.pptx"

    gates: list[Gate] = [
        Gate(
            "contract_pack",
            "Template contract sidecars can be rebuilt and checked.",
            [sys.executable, "scripts/template_contract_pack.py", str(template_dir), "--check"],
        ),
        Gate(
            "svg_quality",
            "Source-faithful template SVG files have no blocking SVG quality errors.",
            [sys.executable, "scripts/svg_quality_checker.py", str(template_dir), "--template-mode"],
        ),
        Gate(
            "svg_geometry",
            "Source-faithful template SVG geometry has no blocking issues.",
            [
                sys.executable,
                "scripts/template_geometry_qa.py",
                str(template_dir),
                "--report",
                str(output_dir / f"{template_id}_geometry_svg.json"),
                "--json",
            ],
            report_path=output_dir / f"{template_id}_geometry_svg.json",
        ),
        Gate(
            "native_pptx_export",
            "Source-faithful template exports to editable native PPTX.",
            [
                sys.executable,
                "scripts/svg_to_pptx.py",
                str(template_dir),
                "--only",
                "native",
                "-t",
                "none",
                "-a",
                "none",
                "-o",
                str(review_pptx),
            ],
            artifacts={"pptx": display_path(review_pptx)},
        ),
        Gate(
            "pptx_text_layout",
            "Exported native PPTX text layout has no blocking overflow/overlap issues.",
            [
                sys.executable,
                "scripts/validate_pptx_text_layout.py",
                str(review_pptx),
                "--report",
                str(output_dir / f"{template_id}_text_layout.json"),
            ],
            report_path=output_dir / f"{template_id}_text_layout.json",
        ),
        Gate(
            "pptx_geometry",
            "Exported native PPTX geometry matches the template geometry contract.",
            [
                sys.executable,
                "scripts/template_geometry_qa.py",
                str(template_dir),
                "--pptx",
                str(review_pptx),
                "--report",
                str(output_dir / f"{template_id}_geometry_pptx.json"),
                "--json",
            ],
            report_path=output_dir / f"{template_id}_geometry_pptx.json",
        ),
    ]

    if run_smoke:
        smoke_command = [
            sys.executable,
            "scripts/template_material_smoke_test.py",
            str(template_dir),
            "--out",
            str(smoke_dir),
            "--min-text-replacement-ratio",
            "0.45",
            "--json",
        ]
        if is_under_tmp(smoke_dir):
            smoke_command.append("--force")
        for keyword in forbidden_keywords:
            smoke_command.extend(["--forbidden-keyword", keyword])

        gates.extend(
            [
                Gate(
                    "material_smoke_build",
                    "Cross-material adaptation smoke template can be generated without source-specific leakage.",
                    smoke_command,
                    report_path=smoke_dir / "material_smoke_manifest.json",
                    artifacts={"template_dir": display_path(smoke_dir)},
                ),
                Gate(
                    "material_smoke_svg_quality",
                    "Cross-material smoke SVG files have no blocking SVG quality errors.",
                    [sys.executable, "scripts/svg_quality_checker.py", str(smoke_dir)],
                ),
                Gate(
                    "material_smoke_svg_geometry",
                    "Cross-material smoke SVG geometry has no blocking issues.",
                    [
                        sys.executable,
                        "scripts/template_geometry_qa.py",
                        str(smoke_dir),
                        "--report",
                        str(output_dir / f"{template_id}_material_smoke_geometry_svg.json"),
                        "--json",
                    ],
                    report_path=output_dir / f"{template_id}_material_smoke_geometry_svg.json",
                ),
                Gate(
                    "material_smoke_native_pptx_export",
                    "Cross-material smoke template exports to editable native PPTX.",
                    [
                        sys.executable,
                        "scripts/svg_to_pptx.py",
                        str(smoke_dir),
                        "--only",
                        "native",
                        "-t",
                        "none",
                        "-a",
                        "none",
                        "-o",
                        str(smoke_pptx),
                    ],
                    artifacts={"pptx": display_path(smoke_pptx)},
                ),
                Gate(
                    "material_smoke_pptx_text_layout",
                    "Cross-material smoke PPTX text layout has no blocking overflow/overlap issues.",
                    [
                        sys.executable,
                        "scripts/validate_pptx_text_layout.py",
                        str(smoke_pptx),
                        "--report",
                        str(output_dir / f"{template_id}_material_smoke_text_layout.json"),
                    ],
                    report_path=output_dir / f"{template_id}_material_smoke_text_layout.json",
                ),
                Gate(
                    "material_smoke_pptx_geometry",
                    "Cross-material smoke PPTX geometry matches the template geometry contract.",
                    [
                        sys.executable,
                        "scripts/template_geometry_qa.py",
                        str(smoke_dir),
                        "--pptx",
                        str(smoke_pptx),
                        "--report",
                        str(output_dir / f"{template_id}_material_smoke_geometry_pptx.json"),
                        "--json",
                    ],
                    report_path=output_dir / f"{template_id}_material_smoke_geometry_pptx.json",
                ),
            ]
        )

    if render_contact:
        render_required = bool(require_render)
        gates.append(
            Gate(
                "render_contact_sheet",
                "Rendered contact sheet can be generated for human visual review.",
                [
                    sys.executable,
                    "scripts/thumbnail.py",
                    str(review_pptx),
                    str(output_dir / f"{template_id}_render_contact"),
                    "--cols",
                    "4",
                ],
                required=render_required,
                artifacts={"contact_prefix": display_path(output_dir / f"{template_id}_render_contact")},
            )
        )
    return gates


def run_acceptance(
    *,
    template_dir: str | Path,
    output_dir: str | Path | None = None,
    forbidden_keywords: list[str] | None = None,
    run_smoke: bool = True,
    render_contact: bool = True,
    require_render: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    template_dir = Path(template_dir).expanduser().resolve()
    if not template_dir.is_dir():
        raise FileNotFoundError(f"template directory not found: {template_dir}")
    template_id = template_id_from_dir(template_dir)
    output_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else (TMP_ROOT / f"{template_id}_distill_acceptance").resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    render_available = renderer_available()
    effective_render_contact = render_contact and (render_available or require_render)
    gates = build_gate_plan(
        template_dir=template_dir,
        output_dir=output_dir,
        forbidden_keywords=forbidden_keywords or [],
        run_smoke=run_smoke,
        render_contact=effective_render_contact,
        require_render=require_render,
    )

    results = [run_gate(gate, cwd=ROOT, dry_run=dry_run) for gate in gates]
    if render_contact and not render_available and not require_render:
        results.append(
            {
                "id": "render_contact_sheet",
                "description": "Rendered contact sheet skipped because no PPTX renderer is available.",
                "required": False,
                "status": "skipped",
                "renderer_available": False,
            }
        )

    required_failures = [
        result
        for result in results
        if result.get("required") and result.get("status") not in {"pass", "planned"}
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_id,
        "template_dir": str(template_dir),
        "output_dir": str(output_dir),
        "status": "planned" if dry_run else ("fail" if required_failures else "pass"),
        "run_smoke": run_smoke,
        "renderer_available": render_available,
        "render_contact_requested": render_contact,
        "render_contact_required": require_render,
        "required_failure_count": len(required_failures),
        "gate_count": len(results),
        "gates": results,
    }
    write_json(output_dir / "acceptance_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run distillation acceptance gates for an EasySlides template.")
    parser.add_argument("template_dir", help="Template directory to validate.")
    parser.add_argument("--out", help="Output directory for reports and exported PPTX files.")
    parser.add_argument("--forbidden-keyword", action="append", default=[], help="Source-specific term forbidden in smoke output.")
    parser.add_argument("--no-smoke", action="store_true", help="Skip cross-material smoke gates.")
    parser.add_argument("--no-render-contact", action="store_true", help="Do not attempt rendered contact-sheet generation.")
    parser.add_argument("--require-render", action="store_true", help="Fail if rendered contact-sheet generation cannot run.")
    parser.add_argument("--dry-run", action="store_true", help="Write the planned gates without executing commands.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_acceptance(
            template_dir=args.template_dir,
            output_dir=args.out,
            forbidden_keywords=args.forbidden_keyword,
            run_smoke=not args.no_smoke,
            render_contact=not args.no_render_contact,
            require_render=args.require_render,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(
            f"{report['status'].upper()}: {report['template_id']} "
            f"({report['required_failure_count']} required failure(s), {report['gate_count']} gate(s))"
        )
        print(f"Report: {display_path(Path(report['output_dir']) / 'acceptance_report.json')}")
        for gate in report["gates"]:
            if gate["status"] not in {"pass", "planned"}:
                print(f"- {gate['status']}: {gate['id']}")
    return 0 if report["status"] in {"pass", "planned"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
