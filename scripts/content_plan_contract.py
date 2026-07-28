#!/usr/bin/env python3
"""Validate the source-facing ``content_plan.json`` contract.

The content plan is intentionally separate from ``deck_plan.json``.  The
latter is the existing execution-facing page contract; this file adds the
production evidence layer learned from content-first presentation systems:
deck message, per-slide argument, claim provenance, and explicit source
coverage decisions.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.content_plan.v1"
REPORT_SCHEMA_VERSION = "easyslides.content_plan_report.v1"
PAGE_RE = re.compile(r"^P\d{2,3}$")
DISPOSITIONS = {"built-around", "summarised", "cut"}
CLAIM_TYPES = {
    "number",
    "date",
    "name",
    "citation",
    "superlative",
    "dated-event",
    "statement",
}


def issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unit_text(value: Any) -> bool:
    if _text(value):
        return True
    if isinstance(value, dict):
        return _text(value.get("text") or value.get("label"))
    return False


def validate_content_plan(
    plan: dict[str, Any],
    *,
    deck_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a machine-readable report without mutating the plan."""
    issues: list[dict[str, str]] = []
    if not isinstance(plan, dict):
        return _report([issue("CONTENT-PLAN-TYPE", "content plan must be a JSON object", "$")])

    if plan.get("schema_version") != SCHEMA_VERSION:
        issues.append(issue("CONTENT-PLAN-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))
    if plan.get("plan_status") != "approved":
        issues.append(issue("CONTENT-PLAN-STATUS", "plan_status must be approved before production", "plan_status"))
    if not _text(plan.get("deck_message")):
        issues.append(issue("CONTENT-PLAN-MESSAGE", "deck_message is required", "deck_message"))
    for key in ("audience", "delivery"):
        if key in plan and not _text(plan.get(key)):
            issues.append(issue("CONTENT-PLAN-FIELD", f"{key} must be a non-empty string when present", key))

    claims = _items(plan.get("claim_ledger"))
    if not isinstance(plan.get("claim_ledger"), list):
        issues.append(issue("CONTENT-PLAN-CLAIMS", "claim_ledger must be a list", "claim_ledger"))
    claim_ids: set[str] = set()
    open_claims = 0
    for index, claim in enumerate(claims):
        path = f"claim_ledger[{index}]"
        if not isinstance(claim, dict):
            issues.append(issue("CONTENT-PLAN-CLAIM", "claim row must be an object", path))
            continue
        claim_id = str(claim.get("claim_id") or "")
        if not _text(claim_id) or claim_id in claim_ids:
            issues.append(issue("CONTENT-PLAN-CLAIM-ID", "claim_id must be non-empty and unique", f"{path}.claim_id"))
        claim_ids.add(claim_id)
        for key in ("claim", "source", "verbatim"):
            if not _text(claim.get(key)):
                issues.append(issue("CONTENT-PLAN-CLAIM-FIELD", f"{key} is required", f"{path}.{key}"))
        claim_type = str(claim.get("type") or "statement")
        if claim_type not in CLAIM_TYPES:
            issues.append(issue("CONTENT-PLAN-CLAIM-TYPE", f"unsupported claim type {claim_type!r}", f"{path}.type"))
        verified = claim.get("verified")
        if not isinstance(verified, bool):
            issues.append(issue("CONTENT-PLAN-CLAIM-VERIFIED", "verified must be boolean", f"{path}.verified"))
        if verified is not True:
            open_claims += 1

    slides = _items(plan.get("slides"))
    if not slides:
        issues.append(issue("CONTENT-PLAN-SLIDES", "slides must be a non-empty list", "slides"))
    slide_ids: set[str] = set()
    for index, slide in enumerate(slides):
        path = f"slides[{index}]"
        if not isinstance(slide, dict):
            issues.append(issue("CONTENT-PLAN-SLIDE", "slide row must be an object", path))
            continue
        page = str(slide.get("page") or "")
        if not PAGE_RE.match(page) or page in slide_ids:
            issues.append(issue("CONTENT-PLAN-PAGE", "page must be a unique P01-style id", f"{path}.page"))
        slide_ids.add(page)
        for key in ("role", "question", "takeaway"):
            if not _text(slide.get(key)):
                issues.append(issue("CONTENT-PLAN-SLIDE-FIELD", f"{key} is required", f"{path}.{key}"))
        units = slide.get("content_units")
        if not isinstance(units, list) or not units or not all(_unit_text(unit) for unit in units):
            issues.append(issue("CONTENT-PLAN-UNITS", "content_units must contain at least one text-bearing unit", f"{path}.content_units"))
        if "units_count" in slide and (not isinstance(slide["units_count"], int) or slide["units_count"] < 1):
            issues.append(issue("CONTENT-PLAN-UNIT-COUNT", "units_count must be a positive integer", f"{path}.units_count"))
        referenced = slide.get("claim_ids", [])
        if referenced is not None and not isinstance(referenced, list):
            issues.append(issue("CONTENT-PLAN-CLAIM-REFS", "claim_ids must be a list", f"{path}.claim_ids"))
        for claim_id in referenced or []:
            if str(claim_id) not in claim_ids:
                issues.append(issue("CONTENT-PLAN-CLAIM-REF", f"unknown claim_id {claim_id!r}", f"{path}.claim_ids"))

    coverage = _items(plan.get("source_coverage"))
    if not isinstance(plan.get("source_coverage"), list) or not coverage:
        issues.append(issue("CONTENT-PLAN-COVERAGE", "source_coverage must be a non-empty list", "source_coverage"))
    cut_count = 0
    coverage_ids: set[str] = set()
    for index, row in enumerate(coverage):
        path = f"source_coverage[{index}]"
        if not isinstance(row, dict):
            issues.append(issue("CONTENT-PLAN-COVERAGE-ROW", "coverage row must be an object", path))
            continue
        section_id = str(row.get("section_id") or "")
        if not _text(section_id) or section_id in coverage_ids:
            issues.append(issue("CONTENT-PLAN-COVERAGE-ID", "section_id must be non-empty and unique", f"{path}.section_id"))
        coverage_ids.add(section_id)
        for key in ("label", "disposition"):
            if not _text(row.get(key)):
                issues.append(issue("CONTENT-PLAN-COVERAGE-FIELD", f"{key} is required", f"{path}.{key}"))
        disposition = str(row.get("disposition") or "")
        if disposition not in DISPOSITIONS:
            issues.append(issue("CONTENT-PLAN-COVERAGE-DISPOSITION", f"disposition must be one of {sorted(DISPOSITIONS)}", f"{path}.disposition"))
        if disposition == "cut":
            cut_count += 1
            if not _text(row.get("reason")):
                issues.append(issue("CONTENT-PLAN-CUT-REASON", "cut coverage rows require an explicit reason", f"{path}.reason"))

    if deck_plan and isinstance(deck_plan.get("slides"), list):
        deck_pages = {str(row.get("page")) for row in deck_plan["slides"] if isinstance(row, dict) and row.get("page")}
        missing = sorted(deck_pages - slide_ids)
        if missing:
            issues.append(issue("CONTENT-PLAN-DECK-COVERAGE", f"deck pages missing from content plan: {', '.join(missing)}", "slides"))

    return _report(issues, slide_count=len(slides), claim_count=len(claims), open_claim_count=open_claims, cut_count=cut_count)


def _report(
    issues: list[dict[str, str]],
    *,
    slide_count: int = 0,
    claim_count: int = 0,
    open_claim_count: int = 0,
    cut_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "slide_count": slide_count,
        "claim_count": claim_count,
        "open_claim_count": open_claim_count,
        "cut_count": cut_count,
    }


def validate_content_plan_file(path: Path, *, deck_plan_path: Path | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _report([issue("CONTENT-PLAN-FILE", "content_plan.json not found", str(path))])
    except json.JSONDecodeError as exc:
        return _report([issue("CONTENT-PLAN-JSON", f"invalid JSON: {exc}", str(path))])
    deck_plan = None
    if deck_plan_path:
        try:
            deck_plan = json.loads(deck_plan_path.read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError):
            deck_plan = None
    return validate_content_plan(payload, deck_plan=deck_plan)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate EasySlides content_plan.json.")
    parser.add_argument("content_plan", type=Path)
    parser.add_argument("--deck-plan", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_content_plan_file(args.content_plan, deck_plan_path=args.deck_plan)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Content plan: {report['status']} ({report['issue_count']} issue(s))")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
