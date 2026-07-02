#!/usr/bin/env python3
"""Run and aggregate EasySlides visual measurement gates.

The individual validators stay focused:

- ``template_geometry_qa.py`` checks template SVG/PPTX geometry contracts.
- ``validate_pptx_text_layout.py`` checks exported PPTX text fit.
- ``pptx_visual_diff.py`` compares renderer-produced PNGs.

This script is the exit-gate facade that turns those reports into one
machine-readable verdict for project pipelines.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts import compare_source_render, pptx_visual_diff, template_geometry_qa, validate_pptx_text_layout, validate_split_assets
except ImportError:  # pragma: no cover - direct script execution
    import compare_source_render
    import pptx_visual_diff
    import template_geometry_qa
    import validate_pptx_text_layout
    import validate_split_assets


SCHEMA_VERSION = "easyslides.visual_measure_report.v1"
SLOT_CONTRACT_REPORT_VERSION = "easyslides.template_slot_contract_report.v1"
SLOT_CONTRACT_VERSION = "easyslides.template_slot_contracts.v1"
PRESERVE_GEOMETRY_REPLACEMENT = "replace_declared_slots_preserve_template_geometry"


@dataclass(frozen=True)
class GateReport:
    name: str
    report: dict[str, Any]
    report_path: Path | None = None


def _status(report: dict[str, Any]) -> str:
    status = str(report.get("status") or "").lower()
    if status in {"pass", "fail", "skipped"}:
        return status
    return "fail" if _count(report, "blocking") else "pass"


def _count(report: dict[str, Any], severity: str) -> int:
    explicit_key = f"{severity}_count"
    if explicit_key in report:
        try:
            return int(report[explicit_key])
        except (TypeError, ValueError):
            pass
    return sum(1 for issue in report.get("issues", []) if str(issue.get("severity")) == severity)


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "status",
        "page_count",
        "slide_count",
        "text_box_count",
        "avg_mae",
        "avg_changed_pct",
        "worst_slide",
        "contact_sheet",
        "asset_count",
    )
    return {key: report[key] for key in keys if key in report}


def _location(issue: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "svg",
        "page",
        "slide",
        "slide_number",
        "shape_index",
        "shape_name",
        "asset_name",
        "asset_path",
        "element_index",
        "text",
    )
    return {key: issue[key] for key in keys if key in issue}


def _suggestion(code: str, gate: str) -> str:
    if code.startswith("SLOT-CONTRACT"):
        return "Declare only editable text/image slots and use replace_declared_slots_preserve_template_geometry."
    if code.startswith("TEXT-OVERFLOW") or code.endswith("CONTAINER-OVERFLOW"):
        return "Shorten the copy, split the slide, or choose a lower-density slot before export."
    if code.startswith("TEXT-OVERLAP") or code.endswith("PROTECTED-OVERLAP"):
        return "Move editable content back into its declared slot and keep locked template chrome unchanged."
    if code.startswith("TEXT-OFF") or code.endswith("OFF-CANVAS"):
        return "Clamp the text box to the slide canvas or revise the source geometry contract."
    if "FONT-TOO-SMALL" in code:
        return "Use a larger slot, split the content, or reduce copy instead of shrinking below the readable floor."
    if gate == "source_render_diff":
        return "Inspect the source-render contact sheet, then fix missing assets, text positions, or layer decisions in the reconstruction manifest."
    if gate == "split_assets":
        return "Inspect the split asset PNG, then add transparent padding, re-split merged fragments, or preserve the closed source shape with a safer mask."
    if "DIFF" in code or gate == "render_diff":
        return "Inspect the contact sheet, then preserve source geometry or rasterize complex styling before export."
    if gate.startswith("template_geometry"):
        return "Repair the template geometry contract or mark the element as locked/editable correctly."
    return "Inspect the source gate report and repair the measured visual contract before delivery."


def _normalized_issue(gate: GateReport, issue: dict[str, Any]) -> dict[str, Any]:
    code = str(issue.get("code") or f"{gate.name.upper()}-ISSUE")
    payload = {
        "gate": gate.name,
        "code": code,
        "severity": str(issue.get("severity") or "blocking"),
        "message": str(issue.get("message") or "Visual measurement gate reported an issue."),
        "suggestion": _suggestion(code, gate.name),
    }
    if gate.report_path is not None:
        payload["source_report"] = str(gate.report_path)
    location = _location(issue)
    if location:
        payload["location"] = location
    details = issue.get("details")
    if isinstance(details, dict) and details:
        payload["details"] = details
    return payload


def _synthetic_failure_issue(gate: GateReport) -> dict[str, Any]:
    if gate.name == "render_diff":
        worst = gate.report.get("worst_slide")
        message = "Rendered deck differs from the reference beyond configured thresholds."
        details = {"worst_slide": worst} if worst is not None else {}
        return {
            "gate": gate.name,
            "code": "VISUAL-DIFF-THRESHOLD",
            "severity": "blocking",
            "message": message,
            "suggestion": _suggestion("VISUAL-DIFF-THRESHOLD", gate.name),
            "source_report": str(gate.report_path) if gate.report_path is not None else "",
            "details": details,
        }
    return {
        "gate": gate.name,
        "code": f"{gate.name.upper()}-FAILED",
        "severity": "blocking",
        "message": "Visual measurement gate failed without itemized issues.",
        "suggestion": _suggestion("", gate.name),
        "source_report": str(gate.report_path) if gate.report_path is not None else "",
    }


def build_visual_measure_report(gates: Iterable[GateReport]) -> dict[str, Any]:
    gate_items = list(gates)
    summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    blocking_count = 0
    warning_count = 0

    for gate in gate_items:
        status = _status(gate.report)
        gate_blocking = _count(gate.report, "blocking")
        gate_warning = _count(gate.report, "warning")
        if status == "fail" and gate_blocking == 0:
            gate_blocking = 1
        blocking_count += gate_blocking
        warning_count += gate_warning
        summaries.append(
            {
                "name": gate.name,
                "status": status,
                "blocking_count": gate_blocking,
                "warning_count": gate_warning,
                "report_path": str(gate.report_path) if gate.report_path is not None else "",
                "summary": _summary(gate.report),
            }
        )

        raw_issues = [item for item in gate.report.get("issues", []) if isinstance(item, dict)]
        issues.extend(_normalized_issue(gate, issue) for issue in raw_issues)
        if status == "fail" and not raw_issues:
            issues.append(_synthetic_failure_issue(gate))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_count else "pass",
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "gate_count": len(gate_items),
        "gates": summaries,
        "issues": issues,
    }


def _contract_issue(code: str, message: str, severity: str = "blocking", **details: Any) -> dict[str, Any]:
    payload = {"code": code, "severity": severity, "message": message}
    if details:
        payload["details"] = details
    return payload


def validate_template_slot_contract(template_dir: str | Path) -> dict[str, Any]:
    """Validate that a template declares editable slots without freeform rebuilds."""
    template_dir = Path(template_dir)
    path = template_dir / "slot_contracts.json"
    issues: list[dict[str, Any]] = []
    if not path.exists():
        issues.append(
            _contract_issue(
                "SLOT-CONTRACT-MISSING",
                "slot_contracts.json is missing, so editable slots cannot be separated from locked chrome.",
            )
        )
        payload: dict[str, Any] = {}
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            payload = {}
            issues.append(
                _contract_issue(
                    "SLOT-CONTRACT-INVALID-JSON",
                    "slot_contracts.json is not valid JSON.",
                    error=str(exc),
                )
            )

    if payload:
        if payload.get("schema_version") != SLOT_CONTRACT_VERSION:
            issues.append(
                _contract_issue(
                    "SLOT-CONTRACT-SCHEMA",
                    "slot_contracts.json must use the EasySlides template slot contract schema.",
                    actual_schema=payload.get("schema_version"),
                    expected_schema=SLOT_CONTRACT_VERSION,
                )
            )
        if payload.get("replacement_rule") != PRESERVE_GEOMETRY_REPLACEMENT:
            issues.append(
                _contract_issue(
                    "SLOT-CONTRACT-REPLACEMENT-RULE",
                    "Template replacement must preserve source geometry and replace only declared slots.",
                    actual_replacement=payload.get("replacement_rule"),
                    expected_replacement=PRESERVE_GEOMETRY_REPLACEMENT,
                )
            )

        layouts = payload.get("layouts")
        if not isinstance(layouts, list):
            issues.append(_contract_issue("SLOT-CONTRACT-LAYOUTS", "slot_contracts.json layouts must be a list."))
            layouts = []
        for index, layout in enumerate(layouts):
            if not isinstance(layout, dict):
                issues.append(
                    _contract_issue(
                        "SLOT-CONTRACT-LAYOUT",
                        "Each slot contract layout must be an object.",
                        layout_index=index,
                    )
                )
                continue
            layout_id = str(layout.get("layout_id") or f"layout_{index + 1}")
            replacement = layout.get("replacement", payload.get("replacement_rule"))
            if replacement != PRESERVE_GEOMETRY_REPLACEMENT:
                issues.append(
                    _contract_issue(
                        "SLOT-CONTRACT-LAYOUT-REPLACEMENT",
                        "Layout replacement must preserve template geometry.",
                        layout_id=layout_id,
                        actual_replacement=replacement,
                        expected_replacement=PRESERVE_GEOMETRY_REPLACEMENT,
                    )
                )

            slots = {str(slot) for slot in layout.get("slots", []) if str(slot)}
            for key in ("text_slots", "image_slots"):
                for slot in layout.get(key, []):
                    slot_id = str(slot)
                    if slot_id not in slots:
                        issues.append(
                            _contract_issue(
                                "SLOT-CONTRACT-UNDECLARED-SLOT",
                                f"{key} contains a slot not listed in slots.",
                                layout_id=layout_id,
                                slot_id=slot_id,
                            )
                        )
            for detail in layout.get("slot_details", []):
                if not isinstance(detail, dict):
                    continue
                slot_id = str(detail.get("slot_id") or "")
                if slot_id and slot_id not in slots:
                    issues.append(
                        _contract_issue(
                            "SLOT-CONTRACT-DETAIL-UNDECLARED",
                            "slot_details contains a slot not listed in slots.",
                            layout_id=layout_id,
                            slot_id=slot_id,
                        )
                    )

    blocking_count = sum(1 for issue in issues if issue["severity"] == "blocking")
    return {
        "schema_version": SLOT_CONTRACT_REPORT_VERSION,
        "contract_schema_version": payload.get("schema_version") if payload else "",
        "template_dir": str(template_dir),
        "status": "fail" if blocking_count else "pass",
        "layout_count": len(payload.get("layouts", [])) if isinstance(payload.get("layouts"), list) else 0,
        "blocking_count": blocking_count,
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_existing_report(raw: str) -> GateReport:
    if "=" not in raw:
        raise ValueError("--existing-report must use NAME=PATH")
    name, path_text = raw.split("=", 1)
    path = Path(path_text)
    return GateReport(name=name, report=json.loads(path.read_text(encoding="utf-8")), report_path=path)


def _report_dir(args: argparse.Namespace) -> Path:
    if args.report:
        return Path(args.report).parent
    if args.pptx:
        return Path(args.pptx).resolve().parent
    return Path.cwd()


def collect_gate_reports(args: argparse.Namespace) -> list[GateReport]:
    reports: list[GateReport] = [_load_existing_report(item) for item in args.existing_report]
    report_dir = _report_dir(args)

    template_dir = Path(args.template_dir) if args.template_dir else None
    pptx_path = Path(args.pptx) if args.pptx else None

    if template_dir and not args.skip_slot_contract:
        report = validate_template_slot_contract(template_dir)
        path = report_dir / "template_slot_contract_report.json"
        _write_json(path, report)
        reports.append(GateReport("template_slot_contract", report, path))

    if template_dir and not args.skip_template_svg:
        report = template_geometry_qa.validate_template_geometry(template_dir)
        path = report_dir / "template_geometry_svg_report.json"
        _write_json(path, report)
        reports.append(GateReport("template_geometry_svg", report, path))

    if template_dir and pptx_path and not args.skip_template_pptx:
        report = template_geometry_qa.validate_pptx_against_contract(pptx_path, template_dir)
        path = report_dir / "template_geometry_pptx_report.json"
        _write_json(path, report)
        reports.append(GateReport("template_geometry_pptx", report, path))

    if pptx_path and not args.skip_pptx_text:
        report = validate_pptx_text_layout.validate_pptx_text_layout(pptx_path)
        path = report_dir / "text_layout_report.json"
        _write_json(path, report)
        reports.append(GateReport("pptx_text_layout", report, path))

    if args.source_render_dir or args.generated_render_dir:
        if not args.source_render_dir or not args.generated_render_dir:
            raise ValueError("--source-render-dir and --generated-render-dir must be provided together")
        diff_out = Path(args.visual_diff_out) if args.visual_diff_out else report_dir / "visual_diff"
        report = pptx_visual_diff.compare_render_dirs(
            Path(args.source_render_dir),
            Path(args.generated_render_dir),
            diff_out,
            fail_avg_mae=args.fail_avg_mae,
            fail_max_mae=args.fail_max_mae,
        )
        reports.append(GateReport("render_diff", report, diff_out / "metrics.json"))

    if args.source_image or args.rendered_slide_dir:
        if not args.source_image or not args.rendered_slide_dir:
            raise ValueError("--source-image and --rendered-slide-dir must be provided together")
        diff_out = Path(args.source_render_diff_out) if args.source_render_diff_out else report_dir / "source_render_diff"
        report = compare_source_render.compare_source_images_to_render_dir(
            [Path(path) for path in args.source_image],
            Path(args.rendered_slide_dir),
            diff_out,
            fail_mae=args.fail_source_mae,
            fail_changed_pct=args.fail_source_changed_pct,
            fit_mode=args.source_fit_mode,
        )
        reports.append(GateReport("source_render_diff", report, diff_out / "metrics.json"))

    if args.split_assets_manifest:
        path = Path(args.split_assets_report) if args.split_assets_report else report_dir / "split_assets_report.json"
        report = validate_split_assets.validate_split_assets(
            Path(args.split_assets_manifest),
            alpha_threshold=args.split_assets_alpha_threshold,
            min_transparent_margin_px=args.split_assets_min_margin_px,
        )
        _write_json(path, report)
        reports.append(GateReport("split_assets", report, path))

    if not reports:
        raise ValueError("no visual measurement gates were requested")
    return reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-dir", help="Template directory containing geometry_contract.json.")
    parser.add_argument("--pptx", help="Exported PPTX to validate.")
    parser.add_argument("--source-render-dir", help="PNG directory rendered from the source/reference PPTX.")
    parser.add_argument("--generated-render-dir", help="PNG directory rendered from the generated PPTX.")
    parser.add_argument("--visual-diff-out", help="Output directory for visual diff metrics and contact sheet.")
    parser.add_argument("--fail-avg-mae", type=float, default=1.0)
    parser.add_argument("--fail-max-mae", type=float, default=3.0)
    parser.add_argument("--source-image", action="append", default=[], help="Source slide image for image-to-editable visual comparison. Repeat in slide order.")
    parser.add_argument("--rendered-slide-dir", help="PNG directory rendered from the reconstructed PPTX.")
    parser.add_argument("--source-render-diff-out", help="Output directory for source-vs-render metrics and contact sheet.")
    parser.add_argument("--fail-source-mae", type=float, default=18.0)
    parser.add_argument("--fail-source-changed-pct", type=float, default=35.0)
    parser.add_argument("--source-fit-mode", choices=["contain", "stretch"], default="contain")
    parser.add_argument("--split-assets-manifest", help="split_manifest.json from an image-to-editable asset sheet.")
    parser.add_argument("--split-assets-report", help="Output JSON path for split asset clipping checks.")
    parser.add_argument("--split-assets-alpha-threshold", type=int, default=20)
    parser.add_argument("--split-assets-min-margin-px", type=int, default=2)
    parser.add_argument("--existing-report", action="append", default=[], help="Include an existing gate report as NAME=PATH.")
    parser.add_argument("--skip-template-svg", action="store_true")
    parser.add_argument("--skip-template-pptx", action="store_true")
    parser.add_argument("--skip-slot-contract", action="store_true")
    parser.add_argument("--skip-pptx-text", action="store_true")
    parser.add_argument("--report", help="Output JSON path for the unified visual measurement report.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the full report to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_visual_measure_report(collect_gate_reports(args))
    except Exception as exc:
        if not args.quiet:
            print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.report:
        _write_json(Path(args.report), report)
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
