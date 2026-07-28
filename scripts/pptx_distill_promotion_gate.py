#!/usr/bin/env python3
"""Run the promotion gate for a distilled PPTX template.

This is the orchestration layer for distillation. The focused validators keep
their own rules; this module decides whether the complete evidence set is
promotable, still needs review, or has a blocking failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts import pptx_visual_diff, template_geometry_qa, template_material_smoke_test
    from scripts import validate_pptx_text_layout, validate_svg_text_slots, visual_measure_gate
    from scripts import cross_renderer_visual_regression, renderer_governance
except (ModuleNotFoundError, ImportError):  # pragma: no cover - direct script execution
    import pptx_visual_diff
    import template_geometry_qa
    import template_material_smoke_test
    import validate_pptx_text_layout
    import validate_svg_text_slots
    import visual_measure_gate
    import cross_renderer_visual_regression
    import renderer_governance


SCHEMA_VERSION = "easyslides.pptx_distill_promotion_report.v1"
PROJECTION_SCHEMA_VERSION = "easyslides.pptx_projection_manifest.v1"
DISTILL_SCHEMA_VERSION = "easyslides.distill_manifest.v1"
ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DISTILL_ARTIFACTS = (
    "source_graph",
    "source_manifest",
    "identity_spec",
    "layout_spec",
    "component_catalog",
    "component_candidates",
    "slot_contracts",
    "asset_provenance",
    "adaptation_policy",
    "review_queue",
    "design_system_pack",
    "component_registry_fragment",
    "projection_manifest",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _issue(code: str, message: str, *, severity: str = "blocking", **details: Any) -> dict[str, Any]:
    payload = {"code": code, "severity": severity, "message": message}
    if details:
        payload["details"] = details
    return payload


def _gate(
    gate_id: str,
    status: str,
    *,
    description: str,
    report_path: Path | None = None,
    issues: Iterable[dict[str, Any]] = (),
    **details: Any,
) -> dict[str, Any]:
    items = [item for item in issues if isinstance(item, dict)]
    payload: dict[str, Any] = {
        "id": gate_id,
        "description": description,
        "status": status,
        "blocking_count": sum(item.get("severity") == "blocking" for item in items),
        "warning_count": sum(item.get("severity") == "warning" for item in items),
        "review_count": sum(item.get("severity") == "review" for item in items),
        "issues": items,
    }
    if report_path is not None:
        payload["report_path"] = str(report_path)
    payload.update(details)
    return payload


def _path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def validate_distill_artifacts(source_workspace: str | Path) -> dict[str, Any]:
    """Check that the phase outputs needed for promotion are present."""
    workspace = Path(source_workspace).expanduser().resolve()
    issues: list[dict[str, Any]] = []
    manifest_path = workspace / "distill_manifest.json"
    if not manifest_path.exists():
        issues.append(_issue("DISTILL-MANIFEST-MISSING", "distill_manifest.json is missing."))
        return _gate(
            "distill_artifacts",
            "fail",
            description="Distillation artifacts required by the promotion gate exist and are internally declared.",
            report_path=manifest_path,
            issues=issues,
            source_workspace=str(workspace),
        )

    try:
        manifest = _read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(_issue("DISTILL-MANIFEST-INVALID", "distill_manifest.json cannot be read as an object.", error=str(exc)))
        return _gate(
            "distill_artifacts",
            "fail",
            description="Distillation artifacts required by the promotion gate exist and are internally declared.",
            report_path=manifest_path,
            issues=issues,
            source_workspace=str(workspace),
        )

    if manifest.get("schema_version") != DISTILL_SCHEMA_VERSION:
        issues.append(
            _issue(
                "DISTILL-MANIFEST-SCHEMA",
                "distill_manifest.json uses an unsupported schema version.",
                actual=manifest.get("schema_version"),
                expected=DISTILL_SCHEMA_VERSION,
            )
        )
    if manifest.get("stage") not in {
        "phase_1_source_graph",
        "phase_2_semantic_registry",
        "phase_3_design_system_compiler",
        "phase_4_projection_and_renderer_mapping",
        "phase_5_qa_and_promotion",
    }:
        issues.append(_issue("DISTILL-MANIFEST-STAGE", "distill_manifest.json has an unsupported pipeline stage."))

    declared = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    missing: list[str] = []
    for artifact_id in REQUIRED_DISTILL_ARTIFACTS:
        filename = str(declared.get(artifact_id) or "")
        if not filename or not (workspace / filename).exists():
            missing.append(artifact_id)
    if missing:
        issues.append(
            _issue(
                "DISTILL-ARTIFACT-MISSING",
                "One or more phase outputs required for promotion are missing.",
                artifacts=missing,
            )
        )

    return _gate(
        "distill_artifacts",
        "fail" if any(item["severity"] == "blocking" for item in issues) else "pass",
        description="Distillation artifacts required by the promotion gate exist and are internally declared.",
        report_path=manifest_path,
        issues=issues,
        stage=manifest.get("stage"),
        artifact_count=len(declared),
    )


def validate_projection(source_workspace: str | Path) -> dict[str, Any]:
    """Validate projection mappings and distinguish review from hard failure."""
    workspace = Path(source_workspace).expanduser().resolve()
    path = workspace / "projection_manifest.json"
    issues: list[dict[str, Any]] = []
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(_issue("PROJECTION-MANIFEST-INVALID", "projection_manifest.json cannot be read.", error=str(exc)))
        return _gate(
            "projection",
            "fail",
            description="Declared source-template slots have a renderer mapping and usable source geometry.",
            report_path=path,
            issues=issues,
        )

    if payload.get("schema_version") != PROJECTION_SCHEMA_VERSION:
        issues.append(
            _issue(
                "PROJECTION-SCHEMA",
                "projection_manifest.json uses an unsupported schema version.",
                actual=payload.get("schema_version"),
                expected=PROJECTION_SCHEMA_VERSION,
            )
        )
    mappings = [item for item in payload.get("renderer_mappings", []) if isinstance(item, dict)]
    if not any(item.get("renderer_id") == "source_template_projection" for item in mappings):
        issues.append(_issue("PROJECTION-RENDERER-MISSING", "source_template_projection renderer mapping is missing."))

    pages = [item for item in payload.get("pages", []) if isinstance(item, dict)]
    components = [item for item in payload.get("components", []) if isinstance(item, dict)]
    if not pages:
        issues.append(_issue("PROJECTION-PAGES-MISSING", "Projection manifest contains no page mappings."))

    review_items: list[dict[str, Any]] = []
    for page in pages:
        source_svg = Path(str(page.get("source_svg") or ""))
        exists = bool(page.get("source_svg_exists")) and source_svg.exists()
        if not exists:
            issues.append(
                _issue(
                    "PROJECTION-SOURCE-SVG-MISSING",
                    "A page projection has no usable source SVG.",
                    slide_id=page.get("slide_id"),
                    source_svg=str(source_svg),
                )
            )
        if page.get("status") != "ready":
            review_items.append(
                _issue(
                    "PROJECTION-PAGE-REVIEW",
                    "A page projection is not marked ready.",
                    severity="review",
                    slide_id=page.get("slide_id"),
                    status=page.get("status"),
                )
            )
    for component in components:
        if component.get("status") == "review_required":
            review_items.append(
                _issue(
                    "PROJECTION-COMPONENT-REVIEW",
                    "A component mapping still needs semantic or visual review before global promotion.",
                    severity="review",
                    component_id=component.get("component_id"),
                    classification=component.get("classification"),
                    status=component.get("status"),
                )
            )
    issues.extend(review_items)
    blocking = any(item["severity"] == "blocking" for item in issues)
    status = "fail" if blocking else ("review_required" if review_items else "pass")
    return _gate(
        "projection",
        status,
        description="Declared source-template slots have a renderer mapping and usable source geometry.",
        report_path=path,
        issues=issues,
        page_count=len(pages),
        component_count=len(components),
        ready_page_count=sum(item.get("status") == "ready" for item in pages),
        ready_component_count=sum(item.get("status") == "ready" for item in components),
    )


def _write_child_report(report_dir: Path, filename: str, payload: dict[str, Any]) -> Path:
    return _write_json(report_dir / filename, payload)


def _is_semantic_template(template_dir: Path) -> bool:
    try:
        payload = _read_json(template_dir / "layouts.json")
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return payload.get("mode") == "semantic"


def _visual_gate_reports(
    *,
    template_dir: Path,
    report_dir: Path,
    pptx_path: Path | None,
    source_render_dir: Path | None,
    generated_render_dir: Path | None,
    fail_avg_mae: float,
    fail_max_mae: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slot = visual_measure_gate.validate_template_slot_contract(template_dir)
    slot_path = _write_child_report(report_dir, "template_slot_contract_report.json", slot)
    semantic_template = _is_semantic_template(template_dir)
    svg_text = None
    svg_text_path = None
    if semantic_template:
        svg_text = validate_svg_text_slots.validate_svg_text_slots(
            template_dir,
            strict_unboxed=True,
            require_valign=True,
            check_canvas=True,
        )
        svg_text_path = _write_child_report(report_dir, "svg_text_slot_report.json", svg_text)
    geometry_svg = template_geometry_qa.validate_template_geometry(template_dir)
    geometry_svg_path = _write_child_report(report_dir, "template_geometry_svg_report.json", geometry_svg)

    gate_reports = [
        visual_measure_gate.GateReport("template_slot_contract", slot, slot_path),
        visual_measure_gate.GateReport("template_geometry_svg", geometry_svg, geometry_svg_path),
    ]
    top_level: list[dict[str, Any]] = [
        _gate(
            "template_slot_contract",
            slot.get("status", "fail"),
            description="Template sidecars declare editable slots and preserve source geometry.",
            report_path=slot_path,
            issues=slot.get("issues", []),
            layout_count=slot.get("layout_count", 0),
        ),
        _gate(
            "template_geometry_svg",
            geometry_svg.get("status", "fail"),
            description="Source-faithful template SVG geometry satisfies its contract.",
            report_path=geometry_svg_path,
            issues=geometry_svg.get("issues", []),
            page_count=geometry_svg.get("page_count", 0),
        ),
    ]
    if semantic_template and svg_text is not None:
        top_level.insert(
            1,
            _gate(
                "svg_text_slots",
                svg_text.get("status", "fail"),
                description="Declared SVG text boxes satisfy hard capacity, canvas, and vertical-alignment rules.",
                report_path=svg_text_path,
                issues=svg_text.get("issues", []),
                text_slot_count=svg_text.get("text_slot_count", 0),
            ),
        )

    if pptx_path is not None:
        geometry_pptx = template_geometry_qa.validate_pptx_against_contract(pptx_path, template_dir)
        geometry_pptx_path = _write_child_report(report_dir, "template_geometry_pptx_report.json", geometry_pptx)
        text_layout = validate_pptx_text_layout.validate_pptx_text_layout(pptx_path)
        text_layout_path = _write_child_report(report_dir, "text_layout_report.json", text_layout)
        gate_reports.extend(
            [
                visual_measure_gate.GateReport("template_geometry_pptx", geometry_pptx, geometry_pptx_path),
                visual_measure_gate.GateReport("pptx_text_layout", text_layout, text_layout_path),
            ]
        )
        top_level.extend(
            [
                _gate(
                    "template_geometry_pptx",
                    geometry_pptx.get("status", "fail"),
                    description="Exported native PPTX geometry matches the source template contract.",
                    report_path=geometry_pptx_path,
                    issues=geometry_pptx.get("issues", []),
                    page_count=geometry_pptx.get("page_count", 0),
                ),
                _gate(
                    "pptx_text_layout",
                    text_layout.get("status", "fail"),
                    description="Exported native PPTX text fits and keeps hard vertical alignment rules.",
                    report_path=text_layout_path,
                    issues=text_layout.get("issues", []),
                    text_box_count=text_layout.get("text_box_count", 0),
                ),
            ]
        )
    else:
        missing = [_issue("PPTX-REVIEW-REQUIRED", "No exported PPTX was supplied for native geometry and text-layout validation.", severity="review")]
        top_level.extend(
            [
                _gate("template_geometry_pptx", "review_required", description="Exported native PPTX geometry matches the source template contract.", issues=missing),
                _gate("pptx_text_layout", "review_required", description="Exported native PPTX text fits and keeps hard vertical alignment rules.", issues=missing),
            ]
        )

    if source_render_dir is not None or generated_render_dir is not None:
        if source_render_dir is None or generated_render_dir is None:
            diff = {
                "status": "fail",
                "blocking_count": 1,
                "warning_count": 0,
                "issues": [_issue("VISUAL-DIFF-INPUTS-INCOMPLETE", "Both source and generated render directories are required.")],
            }
        else:
            diff = pptx_visual_diff.compare_render_dirs(
                source_render_dir,
                generated_render_dir,
                report_dir / "visual_diff",
                fail_avg_mae=fail_avg_mae,
                fail_max_mae=fail_max_mae,
            )
        diff_path = report_dir / "visual_diff" / "metrics.json"
        if not diff_path.exists():
            diff_path = _write_child_report(report_dir, "visual_diff_report.json", diff)
        gate_reports.append(visual_measure_gate.GateReport("render_diff", diff, diff_path))
        top_level.append(
            _gate(
                "render_diff",
                diff.get("status", "fail"),
                description="Rendered source and generated slides stay within configured visual-diff thresholds.",
                report_path=diff_path,
                issues=diff.get("issues", []),
                slide_count=diff.get("slide_count", 0),
                avg_mae=diff.get("avg_mae"),
                avg_changed_pct=diff.get("avg_changed_pct"),
            )
        )
    else:
        top_level.append(
            _gate(
                "render_diff",
                "review_required",
                description="Rendered source and generated slides stay within configured visual-diff thresholds.",
                issues=[_issue("VISUAL-DIFF-REVIEW-REQUIRED", "Source and generated render directories were not supplied.", severity="review")],
            )
        )

    visual_report = visual_measure_gate.build_visual_measure_report(gate_reports)
    _write_child_report(report_dir, "visual_measure_report.json", visual_report)
    return visual_report, top_level


def run_cross_material_gate(
    *,
    template_dir: Path,
    report_dir: Path,
    forbidden_keywords: list[str],
    max_pages: int,
) -> dict[str, Any]:
    # Keep disposable material-smoke files under tmp/ so their forced
    # recreation is confined by the smoke-test safety guard. Promotion
    # reports themselves remain in the caller-provided report directory.
    smoke_dir = ROOT / "tmp" / f"{template_dir.name}_promotion_material_smoke"
    try:
        smoke = template_material_smoke_test.run_material_smoke_test(
            template_dir,
            smoke_dir,
            max_pages=max_pages,
            forbidden_keywords=forbidden_keywords,
            # This directory is a gate-owned, reproducible test artifact.
            # Rebuild it on every run so promotion remains idempotent.
            force=True,
        )
    except Exception as exc:
        failure = _issue("CROSS-MATERIAL-EXECUTION", "Cross-material smoke test could not be executed.", error=str(exc))
        return _gate(
            "cross_material_smoke",
            "fail",
            description="A second material set replaces declared slots without source-specific leakage or ellipsis.",
            report_path=report_dir / "material_smoke" / "material_smoke_manifest.json",
            issues=[failure],
        )

    smoke_path = smoke_dir / "material_smoke_manifest.json"
    geometry = template_geometry_qa.validate_template_geometry(smoke_dir)
    geometry_path = _write_child_report(report_dir, "material_smoke_geometry_svg_report.json", geometry)
    svg_text = None
    svg_text_path = None
    if _is_semantic_template(template_dir):
        svg_text = validate_svg_text_slots.validate_svg_text_slots(
            smoke_dir,
            strict_unboxed=True,
            require_valign=True,
            check_canvas=True,
        )
        svg_text_path = _write_child_report(report_dir, "material_smoke_svg_text_slot_report.json", svg_text)
    issues: list[dict[str, Any]] = []
    for item in smoke.get("failures", []):
        issues.append(_issue("CROSS-MATERIAL-" + str(item).upper(), f"Cross-material smoke test reported failure: {item}."))
    issues.extend(geometry.get("issues", []))
    if svg_text is not None:
        issues.extend(svg_text.get("issues", []))

    smoke_pptx = report_dir / "material_smoke.pptx"
    export = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "svg_to_pptx.py"),
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
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


    native_text_path = report_dir / "material_smoke_text_layout_report.json"
    native_geometry_path = report_dir / "material_smoke_geometry_pptx_report.json"
    if export.returncode != 0 or not smoke_pptx.exists():
        issues.append(
            _issue(
                "CROSS-MATERIAL-NATIVE-PPTX-EXPORT",
                "Cross-material smoke SVG could not be exported to native PPTX.",
                stdout=export.stdout[-2000:],
                stderr=export.stderr[-2000:],
            )
        )
    else:
        native_text = validate_pptx_text_layout.validate_pptx_text_layout(smoke_pptx)
        native_geometry = template_geometry_qa.validate_pptx_against_contract(smoke_pptx, smoke_dir)
        _write_child_report(report_dir, native_text_path.name, native_text)
        _write_child_report(report_dir, native_geometry_path.name, native_geometry)
        issues.extend(native_text.get("issues", []))
        issues.extend(native_geometry.get("issues", []))

    blocking = any(item.get("severity") == "blocking" for item in issues)
    status = "fail" if blocking else "pass"
    report_path = smoke_path if smoke_path.exists() else geometry_path
    return _gate(
        "cross_material_smoke",
        status,
        description="A second material set replaces declared slots without source-specific leakage or ellipsis.",
        report_path=report_path,
        issues=issues,
        smoke_report=str(smoke_path),
        geometry_report=str(geometry_path),
        svg_text_report=str(svg_text_path) if svg_text_path else None,
        native_pptx=str(smoke_pptx),
        native_text_report=str(native_text_path) if native_text_path.exists() else None,
        native_geometry_report=str(native_geometry_path) if native_geometry_path.exists() else None,
        page_count=smoke.get("page_count", 0),
        text_replacement_ratio=smoke.get("text_replacement_ratio"),
        image_replaced_count=smoke.get("image_replaced_count", 0),
    )


def run_renderer_governance_gate(*, report_dir: Path) -> dict[str, Any]:
    report = renderer_governance.validate_renderer_governance()
    report_path = _write_child_report(report_dir, "renderer_governance_report.json", report)
    issues = [
        _issue(str(item.get("code") or "RENDERER-GOVERNANCE"), str(item.get("message") or "Renderer governance failed."), asset_id=item.get("asset_id"))
        for item in report.get("issues", [])
        if isinstance(item, dict)
    ]
    return _gate(
        "renderer_governance",
        "pass" if report.get("status") == "pass" else "fail",
        description="Every declared component renderer is repository-owned and supports its declared SVG and native-PPTX targets.",
        report_path=report_path,
        issues=issues,
        checked_component_count=report.get("checked_component_count", 0),
    )


def run_cross_renderer_visual_gate(*, pptx_path: Path | None, report_dir: Path) -> dict[str, Any]:
    if pptx_path is None or not pptx_path.is_file():
        return _gate(
            "cross_renderer_visual_regression",
            "review_required",
            description="Native PowerPoint and LibreOffice must render the same native PPTX within visual-difference thresholds.",
            issues=[_issue("CROSS-RENDERER-PPTX-MISSING", "No native PPTX was supplied for cross-renderer visual regression.", severity="review")],
        )
    report = cross_renderer_visual_regression.run_cross_renderer_visual_regression(
        pptx_path,
        report_dir / "cross_renderer_visual_regression",
    )
    status = str(report.get("status") or "fail")
    severity = "review" if status == "review_required" else "blocking"
    issues: list[dict[str, Any]] = []
    if status != "pass":
        for backend, attempt in report.get("attempts", {}).items():
            if isinstance(attempt, dict) and attempt.get("status") != "pass":
                issues.append(
                    _issue(
                        "CROSS-RENDERER-" + str(backend).upper(),
                        str(attempt.get("reason") or f"{backend} rendering did not pass."),
                        severity=severity,
                    )
                )
        comparison = report.get("comparison")
        if isinstance(comparison, dict) and comparison.get("status") == "fail":
            issues.append(_issue("CROSS-RENDERER-VISUAL-DIFF", "Cross-renderer visual difference exceeded the configured threshold."))
    return _gate(
        "cross_renderer_visual_regression",
        status,
        description="Native PowerPoint and LibreOffice must render the same native PPTX within visual-difference thresholds.",
        report_path=report_dir / "cross_renderer_visual_regression" / "cross_renderer_visual_regression.json",
        issues=issues,
        attempts=report.get("attempts", {}),
    )


def resolve_promotion_status(gates: Iterable[dict[str, Any]]) -> str:
    statuses = {str(gate.get("status")) for gate in gates}
    if "fail" in statuses:
        return "fail"
    if statuses & {"review_required", "not_run", "skipped"}:
        return "review_required"
    return "pass"


def build_promotion_report(
    *,
    source_workspace: str | Path,
    template_dir: str | Path,
    output_dir: str | Path,
    pptx_path: str | Path | None = None,
    source_render_dir: str | Path | None = None,
    generated_render_dir: str | Path | None = None,
    forbidden_keywords: list[str] | None = None,
    run_cross_material: bool = True,
    max_smoke_pages: int = 8,
    fail_avg_mae: float = 1.0,
    fail_max_mae: float = 3.0,
) -> dict[str, Any]:
    workspace = Path(source_workspace).expanduser().resolve()
    template = Path(template_dir).expanduser().resolve()
    report_dir = Path(output_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    pptx = Path(pptx_path).expanduser().resolve() if pptx_path else None
    source_render = Path(source_render_dir).expanduser().resolve() if source_render_dir else None
    generated_render = Path(generated_render_dir).expanduser().resolve() if generated_render_dir else None

    gates = [validate_distill_artifacts(workspace), validate_projection(workspace)]
    visual_report, visual_gates = _visual_gate_reports(
        template_dir=template,
        report_dir=report_dir,
        pptx_path=pptx,
        source_render_dir=source_render,
        generated_render_dir=generated_render,
        fail_avg_mae=fail_avg_mae,
        fail_max_mae=fail_max_mae,
    )
    gates.extend(visual_gates)
    gates.append(run_renderer_governance_gate(report_dir=report_dir))
    gates.append(run_cross_renderer_visual_gate(pptx_path=pptx, report_dir=report_dir))
    if run_cross_material:
        gates.append(
            run_cross_material_gate(
                template_dir=template,
                report_dir=report_dir,
                forbidden_keywords=forbidden_keywords or [],
                max_pages=max_smoke_pages,
            )
        )
    else:
        gates.append(
            _gate(
                "cross_material_smoke",
                "not_run",
                description="A second material set replaces declared slots without source-specific leakage or ellipsis.",
                issues=[_issue("CROSS-MATERIAL-NOT-RUN", "Cross-material smoke test was disabled.", severity="review")],
            )
        )

    status = resolve_promotion_status(gates)
    blocking = sum(int(gate.get("blocking_count", 0) or 0) for gate in gates)
    warnings = sum(int(gate.get("warning_count", 0) or 0) for gate in gates)
    reviews = sum(int(gate.get("review_count", 0) or 0) for gate in gates)
    if status == "fail":
        next_actions = ["Resolve every blocking gate, then rerun this promotion gate."]
    elif status == "review_required":
        next_actions = ["Complete the review-required projection, native PPTX, visual-diff, or cross-material evidence, then rerun."]
    else:
        next_actions = ["Promotion evidence is complete; register the template or component package after human visual sign-off."]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "promotable": status == "pass",
        "source_workspace": str(workspace),
        "template_dir": str(template),
        "output_dir": str(report_dir),
        "inputs": {
            "pptx": str(pptx) if pptx else None,
            "source_render_dir": str(source_render) if source_render else None,
            "generated_render_dir": str(generated_render) if generated_render else None,
            "cross_material_enabled": run_cross_material,
        },
        "blocking_count": blocking,
        "warning_count": warnings,
        "review_count": reviews,
        "gate_count": len(gates),
        "gates": gates,
        "visual_measure": {
            "status": visual_report.get("status"),
            "blocking_count": visual_report.get("blocking_count", 0),
            "warning_count": visual_report.get("warning_count", 0),
            "gate_count": visual_report.get("gate_count", 0),
            "report_path": str(report_dir / "visual_measure_report.json"),
        },
        "decision": {
            "promotable": status == "pass",
            "rule": "fail_on_blocking; review_required_on_missing_or_unresolved_evidence; pass_only_when_all_gates_pass",
            "next_actions": next_actions,
        },
    }
    _write_json(report_dir / "promotion_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the unified PPTX distillation promotion gate.")
    parser.add_argument("source_workspace", help="Reference workspace containing distill_manifest.json and projection_manifest.json.")
    parser.add_argument("template_dir", help="EasySlides template directory containing SVGs and contract sidecars.")
    parser.add_argument("--out", help="Report directory. Defaults to tmp/<template>_promotion_gate.")
    parser.add_argument("--pptx", help="Exported native PPTX for geometry and text-layout validation.")
    parser.add_argument("--source-render-dir", help="Rendered source/reference slide PNG directory.")
    parser.add_argument("--generated-render-dir", help="Rendered generated slide PNG directory.")
    parser.add_argument("--forbidden-keyword", action="append", default=[], help="Source-specific term forbidden in smoke output.")
    parser.add_argument("--max-smoke-pages", type=int, default=8)
    parser.add_argument("--fail-avg-mae", type=float, default=1.0)
    parser.add_argument("--fail-max-mae", type=float, default=3.0)
    parser.add_argument("--no-cross-material", action="store_true", help="Record cross-material evidence as review-required without running it.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    source_workspace = Path(args.source_workspace).expanduser().resolve()
    template_dir = Path(args.template_dir).expanduser().resolve()
    out_dir = (
        Path(args.out).expanduser().resolve()
        if args.out
        else (Path(__file__).resolve().parents[1] / "tmp" / f"{template_dir.name}_promotion_gate").resolve()
    )
    try:
        report = build_promotion_report(
            source_workspace=source_workspace,
            template_dir=template_dir,
            output_dir=out_dir,
            pptx_path=args.pptx,
            source_render_dir=args.source_render_dir,
            generated_render_dir=args.generated_render_dir,
            forbidden_keywords=args.forbidden_keyword,
            run_cross_material=not args.no_cross_material,
            max_smoke_pages=args.max_smoke_pages,
            fail_avg_mae=args.fail_avg_mae,
            fail_max_mae=args.fail_max_mae,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"{report['status'].upper()}: {report['gate_count']} gates, "
            f"{report['blocking_count']} blocking, {report['review_count']} review-required"
        )
        print(f"Report: {out_dir / 'promotion_report.json'}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
