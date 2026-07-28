"""PPT Master-compatible workflow gates for EasySlides projects.

This module does not generate slide SVGs. It codifies the PPT Master style
pipeline around the existing EasySlides tools: validate phase artifacts, report
the next action, and run the export commands in the required order.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

try:
    from scripts.clarification_gate import ClarificationError, require_confirmed
except ImportError:  # pragma: no cover - direct script execution
    from clarification_gate import ClarificationError, require_confirmed


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    required: list[str]
    missing: list[str]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
            "missing": self.missing,
            "warnings": self.warnings,
        }


def _rel(path: Path, project_path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return path.as_posix()


def _existing(project_path: Path, rel_paths: list[str]) -> tuple[list[str], list[str]]:
    required: list[str] = []
    missing: list[str] = []
    for rel_path in rel_paths:
        required.append(rel_path)
        if not (project_path / rel_path).exists():
            missing.append(rel_path)
    return required, missing


def _svg_files(project_path: Path) -> list[Path]:
    svg_dir = project_path / "svg_output"
    return sorted(svg_dir.glob("*.svg")) if svg_dir.exists() else []


def _notes_files(project_path: Path) -> list[Path]:
    notes_dir = project_path / "notes"
    return sorted(notes_dir.glob("*.md")) if notes_dir.exists() else []


def _clarification_issue(project_path: Path) -> str | None:
    """Return a blocking issue only when the project opted into clarification."""
    request_path = project_path / "clarification_request.json"
    if not request_path.exists():
        return None
    try:
        require_confirmed(request_path)
    except ClarificationError as exc:
        return f"clarification_request.json (confirmed): {exc}"
    return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _template_id_from_payload(payload: dict[str, Any]) -> str:
    template_id = payload.get("template_id")
    if isinstance(template_id, str) and template_id.strip():
        return template_id.strip()
    template = payload.get("template")
    if isinstance(template, dict):
        for key in ("template_id", "id"):
            value = template.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def resolve_template_dir(project_path: str | Path) -> Path | None:
    """Resolve the active template directory from project lock/plan files."""
    project = Path(project_path)
    direct_project_template = project / "templates"
    if (direct_project_template / "geometry_contract.json").exists():
        return direct_project_template

    template_id = ""
    for rel_path in ("deck_execution_lock.json", "deck_plan.json"):
        template_id = _template_id_from_payload(_load_json(project / rel_path))
        if template_id:
            break
    if not template_id:
        return None

    candidates = [
        project / "templates" / template_id,
        REPO_ROOT / "templates" / "layouts" / template_id,
    ]
    for candidate in candidates:
        if (candidate / "geometry_contract.json").exists():
            return candidate
    return None


def validate_phase_a(project_path: str | Path) -> GateResult:
    """Validate Strategist-phase artifacts needed before Executor starts."""
    project = Path(project_path)
    required, missing = _existing(
        project,
        [
            "design_spec.md",
            "spec_lock.md",
            "sources",
            "images",
            "templates",
            "svg_output",
            "notes",
            "exports",
        ],
    )
    warnings: list[str] = []
    clarification_issue = _clarification_issue(project)
    if clarification_issue:
        missing.append(clarification_issue)
    if not (project / "deck_execution_lock.json").exists():
        warnings.append(
            "deck_execution_lock.json is absent; PPT Master compatibility can continue, "
            "but EasySlides strict deck execution gates are not locked."
        )
    return GateResult("phase_a", not missing, required, missing, warnings)


def validate_executor_phase(project_path: str | Path) -> GateResult:
    """Validate Executor-phase artifacts needed before post-processing/export."""
    project = Path(project_path)
    required, missing = _existing(project, ["design_spec.md", "spec_lock.md", "svg_output", "notes/total.md"])
    warnings: list[str] = []
    svg_files = _svg_files(project)
    if not svg_files:
        missing.append("svg_output/*.svg")
    else:
        warnings.append(f"{len(svg_files)} SVG page(s) found in svg_output/.")
    return GateResult("executor_phase", not missing, required + ["svg_output/*.svg"], missing, warnings)


def validate_export_inputs(project_path: str | Path) -> GateResult:
    """Validate inputs for the canonical export command sequence."""
    project = Path(project_path)
    required, missing = _existing(project, ["svg_output", "notes/total.md"])
    if not _svg_files(project):
        missing.append("svg_output/*.svg")
    clarification_issue = _clarification_issue(project)
    if clarification_issue:
        missing.append(clarification_issue)
    warnings: list[str] = []
    final_dir = project / "svg_final"
    if final_dir.exists() and list(final_dir.glob("*.svg")):
        warnings.append("svg_final/ already contains SVGs and will be refreshed by finalize_svg.py.")
    return GateResult("export_inputs", not missing, required + ["svg_output/*.svg"], missing, warnings)


def project_status(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path)
    phase_a = validate_phase_a(project)
    executor = validate_executor_phase(project)
    export_gate = validate_export_inputs(project)
    exports = sorted((project / "exports").glob("*.pptx")) if (project / "exports").exists() else []

    if not phase_a.passed:
        next_action = "complete_phase_a"
    elif not executor.passed:
        next_action = "run_executor_svg_generation"
    elif not export_gate.passed:
        next_action = "repair_export_inputs"
    elif not exports:
        next_action = "run_export"
    else:
        next_action = "review_latest_export"

    return {
        "project_path": str(project),
        "phase_a": phase_a.as_dict(),
        "executor_phase": executor.as_dict(),
        "export_inputs": export_gate.as_dict(),
        "svg_count": len(_svg_files(project)),
        "notes_count": len(_notes_files(project)),
        "exports": [_rel(path, project) for path in exports],
        "next_action": next_action,
    }


def export_command_plan(
    project_path: str | Path,
    validate_pptx: bool = True,
    validate_svg_slots: bool = True,
    validate_template_geometry: bool = True,
    render_png: bool = False,
) -> list[list[str]]:
    project_path_obj = Path(project_path)
    project = str(project_path_obj)
    template_dir = resolve_template_dir(project_path_obj)
    commands = [
    ]
    if validate_svg_slots:
        commands.append(
            [
                sys.executable,
                str(SCRIPTS_DIR / "validate_svg_text_slots.py"),
                str(project_path_obj / "svg_output"),
                "--strict-unboxed",
                "--require-valign",
                "--check-canvas",
                "--report",
                str(project_path_obj / "reports" / "svg_text_slot_report.json"),
            ]
        )
    if validate_template_geometry and template_dir is not None:
        commands.append(
            [
                sys.executable,
                str(SCRIPTS_DIR / "visual_measure_gate.py"),
                "--template-dir",
                str(template_dir),
                "--report",
                str(project_path_obj / "reports" / "visual_measure_pre_export_report.json"),
                "--quiet",
            ]
        )
    commands.extend(
        [
            [sys.executable, str(SCRIPTS_DIR / "total_md_split.py"), project],
            [sys.executable, str(SCRIPTS_DIR / "finalize_svg.py"), project],
            [sys.executable, str(SCRIPTS_DIR / "svg_to_pptx.py"), project],
        ]
    )
    if render_png:
        commands.append([sys.executable, str(SCRIPTS_DIR / "ppt_master_pipeline.py"), "render-latest-pptx", project])
    if validate_pptx:
        commands.append([sys.executable, str(SCRIPTS_DIR / "ppt_master_pipeline.py"), "validate-latest-visual-measure", project])
    return commands


def run_export(
    project_path: str | Path,
    dry_run: bool = False,
    validate_pptx: bool = True,
    validate_svg_slots: bool = True,
    validate_template_geometry: bool = True,
    render_png: bool = False,
) -> dict[str, Any]:
    gate = validate_export_inputs(project_path)
    if not gate.passed:
        return {
            "passed": False,
            "gate": gate.as_dict(),
            "commands": [],
            "returncodes": [],
        }

    commands = export_command_plan(
        project_path,
        validate_pptx=validate_pptx,
        validate_svg_slots=validate_svg_slots,
        validate_template_geometry=validate_template_geometry,
        render_png=render_png,
    )
    if dry_run:
        return {
            "passed": True,
            "dry_run": True,
            "gate": gate.as_dict(),
            "commands": commands,
            "returncodes": [],
        }

    returncodes: list[int] = []
    for command in commands:
        result = subprocess.run(command, cwd=REPO_ROOT, text=True)
        returncodes.append(result.returncode)
        if result.returncode != 0:
            return {
                "passed": False,
                "dry_run": False,
                "gate": gate.as_dict(),
                "commands": commands,
                "returncodes": returncodes,
            }
    return {
        "passed": True,
        "dry_run": False,
        "gate": gate.as_dict(),
        "commands": commands,
        "returncodes": returncodes,
    }


def validate_latest_pptx(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path)
    exports = sorted((project / "exports").glob("*.pptx"), key=lambda path: path.stat().st_mtime)
    if not exports:
        return {"passed": False, "error": "no pptx exports found"}
    latest = exports[-1]
    report = project / "reports" / "text_layout_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "validate_pptx_text_layout.py"),
        str(latest),
        "--report",
        str(report),
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, text=True)
    return {
        "passed": result.returncode == 0,
        "pptx": _rel(latest, project),
        "report": _rel(report, project),
        "returncode": result.returncode,
    }


def validate_latest_visual_measure(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path)
    exports = sorted((project / "exports").glob("*.pptx"), key=lambda path: path.stat().st_mtime)
    if not exports:
        return {"passed": False, "error": "no pptx exports found"}
    latest = exports[-1]
    report = project / "reports" / "visual_measure_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "visual_measure_gate.py"),
        "--pptx",
        str(latest),
        "--report",
        str(report),
        "--quiet",
    ]
    template_dir = resolve_template_dir(project)
    if template_dir is not None:
        command[2:2] = ["--template-dir", str(template_dir)]
    result = subprocess.run(command, cwd=REPO_ROOT, text=True)
    return {
        "passed": result.returncode == 0,
        "pptx": _rel(latest, project),
        "report": _rel(report, project),
        "template_dir": str(template_dir) if template_dir is not None else "",
        "returncode": result.returncode,
    }


def render_latest_pptx(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path)
    exports = sorted((project / "exports").glob("*.pptx"), key=lambda path: path.stat().st_mtime)
    if not exports:
        return {"passed": False, "error": "no pptx exports found"}
    latest = exports[-1]
    output_dir = project / "reports" / "rendered_png"
    report = project / "reports" / "rendered_png_report.json"
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "render_pptx_png.py"),
        str(latest),
        "--out",
        str(output_dir),
        "--report",
        str(report),
        "--quiet",
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, text=True)
    return {
        "passed": result.returncode == 0,
        "pptx": _rel(latest, project),
        "output_dir": _rel(output_dir, project),
        "report": _rel(report, project),
        "returncode": result.returncode,
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _print_gate(gate: GateResult) -> None:
    status = "PASS" if gate.passed else "FAIL"
    print(f"{gate.name}: {status}")
    if gate.missing:
        print("missing:")
        for item in gate.missing:
            print(f"  - {item}")
    if gate.warnings:
        print("warnings:")
        for item in gate.warnings:
            print(f"  - {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PPT Master-compatible workflow gates for EasySlides.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "validate-phase-a", "validate-executor", "validate-export-inputs"):
        sub = subparsers.add_parser(name)
        sub.add_argument("project_path")
        sub.add_argument("--json", action="store_true")

    export = subparsers.add_parser("export")
    export.add_argument("project_path")
    export.add_argument("--dry-run", action="store_true")
    export.add_argument("--no-svg-text-slot-check", action="store_true")
    export.add_argument("--no-pptx-text-check", action="store_true")
    export.add_argument("--no-visual-measure", action="store_true")
    export.add_argument("--no-template-geometry-check", action="store_true")
    export.add_argument("--render-png-preview", action="store_true")
    export.add_argument("--json", action="store_true")

    latest = subparsers.add_parser("validate-latest-pptx")
    latest.add_argument("project_path")
    latest.add_argument("--json", action="store_true")

    latest_visual = subparsers.add_parser("validate-latest-visual-measure")
    latest_visual.add_argument("project_path")
    latest_visual.add_argument("--json", action="store_true")

    render_latest = subparsers.add_parser("render-latest-pptx")
    render_latest.add_argument("project_path")
    render_latest.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "status":
        result = project_status(args.project_path)
        if args.json:
            _print_json(result)
        else:
            print(f"next_action: {result['next_action']}")
            _print_gate(validate_phase_a(args.project_path))
            _print_gate(validate_executor_phase(args.project_path))
            _print_gate(validate_export_inputs(args.project_path))
        return 0

    if args.command == "validate-phase-a":
        gate = validate_phase_a(args.project_path)
    elif args.command == "validate-executor":
        gate = validate_executor_phase(args.project_path)
    elif args.command == "validate-export-inputs":
        gate = validate_export_inputs(args.project_path)
    elif args.command == "export":
        result = run_export(
            args.project_path,
            dry_run=args.dry_run,
            validate_pptx=not args.no_pptx_text_check and not args.no_visual_measure,
            validate_svg_slots=not args.no_svg_text_slot_check,
            validate_template_geometry=not args.no_template_geometry_check,
            render_png=args.render_png_preview,
        )
        if args.json:
            _print_json(result)
        else:
            for command in result["commands"]:
                print(" ".join(command))
            print("PASS" if result["passed"] else "FAIL")
        return 0 if result["passed"] else 1
    elif args.command == "validate-latest-pptx":
        result = validate_latest_pptx(args.project_path)
        if args.json:
            _print_json(result)
        else:
            print("PASS" if result["passed"] else "FAIL")
            if "pptx" in result:
                print(result["pptx"])
            if "error" in result:
                print(result["error"])
        return 0 if result["passed"] else 1
    elif args.command == "validate-latest-visual-measure":
        result = validate_latest_visual_measure(args.project_path)
        if args.json:
            _print_json(result)
        else:
            print("PASS" if result["passed"] else "FAIL")
            if "pptx" in result:
                print(result["pptx"])
            if "report" in result:
                print(result["report"])
            if "error" in result:
                print(result["error"])
        return 0 if result["passed"] else 1
    elif args.command == "render-latest-pptx":
        result = render_latest_pptx(args.project_path)
        if args.json:
            _print_json(result)
        else:
            print("PASS" if result["passed"] else "FAIL")
            if "pptx" in result:
                print(result["pptx"])
            if "output_dir" in result:
                print(result["output_dir"])
            if "error" in result:
                print(result["error"])
        return 0 if result["passed"] else 1
    else:
        raise AssertionError(f"unhandled command {args.command!r}")

    if args.json:
        _print_json(gate.as_dict())
    else:
        _print_gate(gate)
    return 0 if gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
