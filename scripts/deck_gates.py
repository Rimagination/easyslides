#!/usr/bin/env python3
"""Run the fail-closed EasySlides deck delivery gate.

This gate is the join point for the six production contracts: source/content
plan, design plan, form-to-component plan, independent review, render evidence,
and hashed handoff artifacts.  It deliberately does not replace the existing
PPTX/template geometry gates; it composes their reports when present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.component_plan_contract import validate_component_plan_file
    from scripts.content_plan_contract import validate_content_plan_file
    from scripts.deck_plan_contract import validate_deck_plan_file
    from scripts.design_plan_contract import validate_design_plan_file
    from scripts.review_contract import validate_review_file
except ModuleNotFoundError:  # pragma: no cover
    from component_plan_contract import validate_component_plan_file
    from content_plan_contract import validate_content_plan_file
    from deck_plan_contract import validate_deck_plan_file
    from design_plan_contract import validate_design_plan_file
    from review_contract import validate_review_file


SCHEMA_VERSION = "easyslides.deck_gates.v1"
REPORT_SCHEMA_VERSION = "easyslides.deck_gates_report.v1"


def issue(code: str, message: str, path: str | None = None, *, severity: str = "blocking") -> dict[str, Any]:
    row = {"code": code, "message": message, "severity": severity}
    if path:
        row["path"] = path
    return row


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _artifact(path: Path, *, kind: str) -> dict[str, Any]:
    if not path.is_file():
        return {"path": path.name, "kind": kind, "status": "missing"}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": path.name, "kind": kind, "status": "present", "sha256": digest, "bytes": path.stat().st_size}


def _gate(gate_id: str, status: str, report: dict[str, Any] | None = None, issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": gate_id, "status": status, "issues": issues or [], "report": report}


def _status_from_report(report: dict[str, Any]) -> str:
    return "pass" if report.get("status") == "pass" else "fail"


def _file_gate(path: Path, gate_id: str, kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = _artifact(path, kind=kind)
    if artifact["status"] != "present":
        return _gate(gate_id, "fail", issues=[issue(f"{gate_id.upper()}-MISSING", f"required artifact is missing: {path.name}", str(path))]), artifact
    return _gate(gate_id, "pass"), artifact


def run_deck_gates(
    deck_dir: str | Path,
    *,
    require_arbiter: bool = True,
    repo_root: str | Path | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(deck_dir).resolve()
    repository = Path(repo_root).resolve() if repo_root else (root.parent.parent if root.parent.name == "projects" else Path(__file__).resolve().parents[1])
    deck_path = root / "deck_plan.json"
    content_path = root / "content_plan.json"
    design_path = root / "design_plan.json"
    component_path = root / "component_plan.json"
    critic_path = root / "critic_report.json"
    arbiter_path = root / "arbiter_report.json"
    artifacts: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []

    deck_report = validate_deck_plan_file(deck_path, repo_root=repository)
    gates.append(_gate("deck_plan", _status_from_report(deck_report), deck_report))
    artifacts.append(_artifact(deck_path, kind="contract"))

    content_report = validate_content_plan_file(content_path, deck_plan_path=deck_path)
    gates.append(_gate("content_plan", _status_from_report(content_report), content_report))
    artifacts.append(_artifact(content_path, kind="contract"))

    design_report = validate_design_plan_file(design_path, content_plan_path=content_path)
    gates.append(_gate("design_plan", _status_from_report(design_report), design_report))
    artifacts.append(_artifact(design_path, kind="contract"))

    component_report = validate_component_plan_file(component_path, deck_plan_path=deck_path, require_form_selection=True)
    gates.append(_gate("component_plan", _status_from_report(component_report), component_report))
    artifacts.append(_artifact(component_path, kind="contract"))

    clarification_path = root / "clarification_request.json"
    clarification = _read_json(clarification_path)
    if clarification is None:
        gates.append(_gate("clarification", "fail", issues=[issue("CLARIFICATION-MISSING", "clarification_request.json is required for production delivery", str(clarification_path))]))
    elif clarification.get("status") != "confirmed":
        gates.append(_gate("clarification", "fail", clarification, [issue("CLARIFICATION-UNCONFIRMED", "clarification request is not confirmed", str(clarification_path))]))
    else:
        gates.append(_gate("clarification", "pass", clarification))
    artifacts.append(_artifact(clarification_path, kind="decision"))

    critic_report = validate_review_file(critic_path, "critic")
    gates.append(_gate("review_critic", _status_from_report(critic_report), critic_report))
    artifacts.append(_artifact(critic_path, kind="independent_review"))

    if require_arbiter:
        arbiter_report = validate_review_file(arbiter_path, "arbiter")
        gates.append(_gate("review_arbiter", _status_from_report(arbiter_report), arbiter_report))
        artifacts.append(_artifact(arbiter_path, kind="independent_review"))
    else:
        policy_path = root / "review_policy.json"
        policy = _read_json(policy_path)
        policy_reason = str((policy or {}).get("arbiter_waiver_reason") or "").strip()
        if not policy_reason:
            gates.append(_gate("review_arbiter", "fail", issues=[issue("ARBITER-WAIVER-MISSING", "arbiter can only be waived with review_policy.json arbiter_waiver_reason", str(policy_path))]))
        else:
            gates.append(_gate("review_arbiter", "pass", policy, [issue("ARBITER-WAIVED", policy_reason, str(policy_path), severity="waived")]))
        artifacts.append(_artifact(policy_path, kind="decision"))

    render_candidates = [root / "render_report.json", root / "visual_review.json"]
    render_path = next((path for path in render_candidates if path.is_file()), None)
    render_payload = _read_json(render_path) if render_path else None
    render_status = "pass" if render_payload and (
        render_payload.get("status") == "pass"
        or (isinstance(render_payload.get("render_report"), dict) and render_payload["render_report"].get("status") == "pass")
    ) else "fail"
    render_issues = [] if render_status == "pass" else [issue("RENDER-EVIDENCE-MISSING", "a passing render_report.json or visual_review.json is required", str(root))]
    gates.append(_gate("render", render_status, render_payload, render_issues))
    artifacts.append(_artifact(render_path or root / "render_report.json", kind="render_evidence"))

    geometry_path = root / "geometry_report.json"
    geometry_payload = _read_json(geometry_path)
    geometry_status = _status_from_report(geometry_payload) if geometry_payload else "fail"
    geometry_issues = [] if geometry_status == "pass" else [issue("GEOMETRY-EVIDENCE-MISSING", "geometry_report.json with status pass is required", str(geometry_path))]
    gates.append(_gate("geometry", geometry_status, geometry_payload, geometry_issues))
    artifacts.append(_artifact(geometry_path, kind="geometry_evidence"))

    source_status = "pass" if content_report.get("status") == "pass" and int(content_report.get("open_claim_count", 0)) == 0 else "fail"
    source_issues = [] if source_status == "pass" else [issue("SOURCE-FIDELITY-OPEN", "all slide-bound claims must be verified before delivery", str(content_path))]
    gates.append(_gate("source_fidelity", source_status, {"open_claim_count": content_report.get("open_claim_count", 0)}, source_issues))

    # The gate itself is the handoff artifact.  Hashes are emitted for every
    # input so a later consumer can detect a review/build mismatch.
    failed = [gate["id"] for gate in gates if gate["status"] != "pass"]
    handoff_status = "pass" if not failed else "fail"
    gates.append(_gate("handoff", handoff_status, {"failed_gates": failed}, [issue("HANDOFF-BLOCKED", "delivery is blocked until every required gate passes", severity="blocking")] if failed else []))
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "deck_dir": str(root),
        "status": "pass" if handoff_status == "pass" else "fail",
        "production_eligible": handoff_status == "pass",
        "failed_gates": failed,
        "gates": gates,
        "artifacts": artifacts,
    }
    if report_path:
        target = Path(report_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the fail-closed EasySlides deck delivery gate.")
    parser.add_argument("deck_dir", type=Path)
    parser.add_argument("--no-arbiter", action="store_true", help="Allow an explicit review_policy.json waiver.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_deck_gates(args.deck_dir, require_arbiter=not args.no_arbiter, repo_root=args.repo_root, report_path=args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Deck gates: {report['status']} ({len(report['failed_gates'])} failed gate(s))")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
