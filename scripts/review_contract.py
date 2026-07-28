#!/usr/bin/env python3
"""Validate independent EasySlides critic and arbiter report artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CRITIC_SCHEMA_VERSION = "easyslides.critic_report.v1"
ARBITER_SCHEMA_VERSION = "easyslides.arbiter_report.v1"
REPORT_SCHEMA_VERSION = "easyslides.review_contract_report.v1"
EFFORTS = {"fast", "standard", "thorough"}
SEVERITIES = {"blocker", "major", "minor"}


def issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _report(kind: str, issues: list[dict[str, str]], **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_type": kind,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        **extra,
    }


def validate_critic_report(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return _report("critic", [issue("CRITIC-TYPE", "critic report must be an object", "$")])
    if payload.get("schema_version") != CRITIC_SCHEMA_VERSION:
        issues.append(issue("CRITIC-SCHEMA", f"schema_version must be {CRITIC_SCHEMA_VERSION}", "schema_version"))
    if not _text(payload.get("deck_id")):
        issues.append(issue("CRITIC-DECK", "deck_id is required", "deck_id"))
    if payload.get("review_effort") not in EFFORTS:
        issues.append(issue("CRITIC-EFFORT", f"review_effort must be one of {sorted(EFFORTS)}", "review_effort"))
    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        issues.append(issue("CRITIC-COVERAGE", "coverage is required", "coverage"))
    else:
        opened = coverage.get("slides_opened")
        if not isinstance(opened, list) or not opened:
            issues.append(issue("CRITIC-SLIDES", "coverage.slides_opened must list reviewed slides", "coverage.slides_opened"))
        declared = coverage.get("slide_count")
        if isinstance(declared, int) and isinstance(opened, list) and len(opened) != declared:
            issues.append(issue("CRITIC-COVERAGE-GAP", "slides_opened must cover the declared slide_count", "coverage.slides_opened"))
    findings = payload.get("findings")
    if not isinstance(findings, list):
        issues.append(issue("CRITIC-FINDINGS", "findings must be a list", "findings"))
        findings = []
    finding_ids: set[str] = set()
    blocking_findings = 0
    for index, finding in enumerate(findings):
        path = f"findings[{index}]"
        if not isinstance(finding, dict):
            issues.append(issue("CRITIC-FINDING", "finding must be an object", path))
            continue
        finding_id = str(finding.get("id") or "")
        if not _text(finding_id) or finding_id in finding_ids:
            issues.append(issue("CRITIC-FINDING-ID", "finding id must be non-empty and unique", f"{path}.id"))
        finding_ids.add(finding_id)
        if finding.get("severity") not in SEVERITIES:
            issues.append(issue("CRITIC-SEVERITY", f"severity must be one of {sorted(SEVERITIES)}", f"{path}.severity"))
        if finding.get("severity") in {"blocker", "major"}:
            blocking_findings += 1
        for key in ("slide", "dimension", "issue", "fix"):
            if not _text(str(finding.get(key) or "")):
                issues.append(issue("CRITIC-FINDING-FIELD", f"{key} is required", f"{path}.{key}"))
    verdict = str(payload.get("verdict") or "")
    if verdict not in {"pass", "revise"}:
        issues.append(issue("CRITIC-VERDICT", "verdict must be pass or revise", "verdict"))
    if verdict == "pass" and blocking_findings:
        issues.append(issue("CRITIC-BLOCKING-PASS", "a critic cannot pass with blocker or major findings", "verdict"))
    return _report("critic", issues, finding_count=len(findings), blocking_finding_count=blocking_findings)


def validate_arbiter_report(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return _report("arbiter", [issue("ARBITER-TYPE", "arbiter report must be an object", "$")])
    if payload.get("schema_version") != ARBITER_SCHEMA_VERSION:
        issues.append(issue("ARBITER-SCHEMA", f"schema_version must be {ARBITER_SCHEMA_VERSION}", "schema_version"))
    if not _text(payload.get("deck_id")):
        issues.append(issue("ARBITER-DECK", "deck_id is required", "deck_id"))
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list):
        issues.append(issue("ARBITER-VERDICTS", "verdicts must be a list", "verdicts"))
        verdicts = []
    refs: set[str] = set()
    unresolved = 0
    for index, row in enumerate(verdicts):
        path = f"verdicts[{index}]"
        if not isinstance(row, dict):
            issues.append(issue("ARBITER-VERDICT", "verdict row must be an object", path))
            continue
        ref = str(row.get("finding_ref") or "")
        if not _text(ref) or ref in refs:
            issues.append(issue("ARBITER-FINDING-REF", "finding_ref must be non-empty and unique", f"{path}.finding_ref"))
        refs.add(ref)
        if row.get("real_verdict") not in {"real", "false_positive", "unsure"}:
            issues.append(issue("ARBITER-REAL", "real_verdict must be real, false_positive, or unsure", f"{path}.real_verdict"))
        if row.get("fix_verdict") not in {"helps", "hurts", "neutral"}:
            issues.append(issue("ARBITER-FIX", "fix_verdict must be helps, hurts, or neutral", f"{path}.fix_verdict"))
        if row.get("real_verdict") in {"real", "unsure"}:
            unresolved += 1
    escalated = payload.get("escalated_unreviewed", [])
    if not isinstance(escalated, list):
        issues.append(issue("ARBITER-ESCALATION", "escalated_unreviewed must be a list", "escalated_unreviewed"))
    elif escalated:
        unresolved += len(escalated)
    verdict = str(payload.get("verdict") or "")
    if verdict not in {"pass", "revise"}:
        issues.append(issue("ARBITER-VERDICT", "verdict must be pass or revise", "verdict"))
    if verdict == "pass" and unresolved:
        issues.append(issue("ARBITER-OPEN-PASS", "an arbiter cannot pass while real or unsure findings remain", "verdict"))
    return _report("arbiter", issues, verdict_count=len(verdicts), unresolved_count=unresolved)


def validate_review_file(path: Path, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        schema = CRITIC_SCHEMA_VERSION if kind == "critic" else ARBITER_SCHEMA_VERSION
        return _report(kind, [issue(f"{kind.upper()}-FILE", f"{kind}_report.json not found", str(path))], expected_schema=schema)
    except json.JSONDecodeError as exc:
        return _report(kind, [issue(f"{kind.upper()}-JSON", f"invalid JSON: {exc}", str(path))])
    return validate_critic_report(payload) if kind == "critic" else validate_arbiter_report(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate EasySlides critic or arbiter review JSON.")
    parser.add_argument("kind", choices=("critic", "arbiter"))
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_review_file(args.report, args.kind)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"{args.kind.title()} report: {report['status']} ({report['issue_count']} issue(s))")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
