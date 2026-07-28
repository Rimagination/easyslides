#!/usr/bin/env python3
"""Validate the design-facing ``design_plan.json`` contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.design_plan.v1"
REPORT_SCHEMA_VERSION = "easyslides.design_plan_report.v1"
PAGE_RE = re.compile(r"^P\d{2,3}$")


def issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _family(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("family") or row.get("form_family") or "").strip()


def validate_design_plan(
    plan: dict[str, Any],
    *,
    content_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(plan, dict):
        return _report([issue("DESIGN-PLAN-TYPE", "design plan must be a JSON object", "$")])
    if plan.get("schema_version") != SCHEMA_VERSION:
        issues.append(issue("DESIGN-PLAN-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))
    if plan.get("plan_status") != "approved":
        issues.append(issue("DESIGN-PLAN-STATUS", "plan_status must be approved before production", "plan_status"))

    language = plan.get("design_language")
    if not isinstance(language, dict):
        issues.append(issue("DESIGN-PLAN-LANGUAGE", "design_language must be an object", "design_language"))
        language = {}
    for key in ("palette", "type_pairing", "signature_motif"):
        if not _text(language.get(key)):
            issues.append(issue("DESIGN-PLAN-LANGUAGE-FIELD", f"{key} is required", f"design_language.{key}"))
    if not _text(language.get("signature_move")):
        issues.append(issue("DESIGN-PLAN-SIGNATURE", "design_language.signature_move is required", "design_language.signature_move"))

    density = plan.get("density")
    if not isinstance(density, dict):
        issues.append(issue("DESIGN-PLAN-DENSITY", "density must be an object", "density"))
    else:
        for key in ("median_words_per_slide", "over_budget_count", "non_text_protagonist_count"):
            if not isinstance(density.get(key), int) or density[key] < 0:
                issues.append(issue("DESIGN-PLAN-DENSITY-FIELD", f"{key} must be a non-negative integer", f"density.{key}"))

    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        issues.append(issue("DESIGN-PLAN-SLIDES", "slides must be a non-empty list", "slides"))
        slides = []
    slide_ids: set[str] = set()
    form_families: list[str] = []
    for index, slide in enumerate(slides):
        path = f"slides[{index}]"
        if not isinstance(slide, dict):
            issues.append(issue("DESIGN-PLAN-SLIDE", "slide row must be an object", path))
            continue
        page = str(slide.get("page") or "")
        if not PAGE_RE.match(page) or page in slide_ids:
            issues.append(issue("DESIGN-PLAN-PAGE", "page must be a unique P01-style id", f"{path}.page"))
        slide_ids.add(page)
        for key in ("visual_protagonist", "chosen_form", "layout_id", "reasoning"):
            if not _text(slide.get(key)):
                issues.append(issue("DESIGN-PLAN-SLIDE-FIELD", f"{key} is required", f"{path}.{key}"))
        candidates = slide.get("candidate_forms")
        if not isinstance(candidates, list) or len(candidates) < 2:
            issues.append(issue("DESIGN-PLAN-CANDIDATES", "candidate_forms must contain at least two alternatives", f"{path}.candidate_forms"))
            candidates = []
        candidate_ids = {str(row.get("form_id") or "") for row in candidates if isinstance(row, dict)}
        candidate_families = {_family(row) for row in candidates if _family(row)}
        if len(candidate_families) < 2:
            issues.append(issue("DESIGN-PLAN-DIVERGENCE", "candidate forms must span at least two form families", f"{path}.candidate_forms"))
        chosen = str(slide.get("chosen_form") or "")
        if chosen and candidate_ids and chosen not in candidate_ids:
            issues.append(issue("DESIGN-PLAN-CHOSEN", "chosen_form must be one of candidate_forms", f"{path}.chosen_form"))
        runner_up = slide.get("runner_up")
        if not isinstance(runner_up, dict) or not _text(runner_up.get("form_id")) or not _text(_family(runner_up)):
            issues.append(issue("DESIGN-PLAN-RUNNER-UP", "runner_up must declare form_id and a different form family", f"{path}.runner_up"))
        elif _family(runner_up) in candidate_families and len(candidate_families) > 1:
            # A runner-up can be a named candidate, but it must not collapse to
            # the chosen form family.  This is the anti-card-monoculture gate.
            chosen_row = next((row for row in candidates if isinstance(row, dict) and row.get("form_id") == chosen), None)
            if chosen_row and _family(chosen_row) == _family(runner_up):
                issues.append(issue("DESIGN-PLAN-RUNNER-UP-FAMILY", "runner_up must come from a different form family", f"{path}.runner_up"))
        family = _family(next((row for row in candidates if isinstance(row, dict) and row.get("form_id") == chosen), runner_up))
        if family:
            form_families.append(family)

    ledger = plan.get("form_ledger")
    if not isinstance(ledger, list) or len(ledger) != len(slides):
        issues.append(issue("DESIGN-PLAN-FORM-LEDGER", "form_ledger must have one row per slide", "form_ledger"))
    else:
        for index, row in enumerate(ledger):
            if not isinstance(row, dict) or not _text(row.get("page")) or not _text(row.get("format_family")):
                issues.append(issue("DESIGN-PLAN-FORM-ROW", "form ledger rows need page and format_family", f"form_ledger[{index}]"))

    if content_plan and isinstance(content_plan.get("slides"), list):
        content_pages = {str(row.get("page")) for row in content_plan["slides"] if isinstance(row, dict) and row.get("page")}
        missing = sorted(content_pages - slide_ids)
        if missing:
            issues.append(issue("DESIGN-PLAN-CONTENT-COVERAGE", f"content pages missing from design plan: {', '.join(missing)}", "slides"))

    return _report(issues, slide_count=len(slides), form_family_count=len(set(form_families)))


def _report(issues: list[dict[str, str]], *, slide_count: int = 0, form_family_count: int = 0) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "slide_count": slide_count,
        "form_family_count": form_family_count,
    }


def validate_design_plan_file(path: Path, *, content_plan_path: Path | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _report([issue("DESIGN-PLAN-FILE", "design_plan.json not found", str(path))])
    except json.JSONDecodeError as exc:
        return _report([issue("DESIGN-PLAN-JSON", f"invalid JSON: {exc}", str(path))])
    content_plan = None
    if content_plan_path:
        try:
            content_plan = json.loads(content_plan_path.read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError):
            content_plan = None
    return validate_design_plan(payload, content_plan=content_plan)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate EasySlides design_plan.json.")
    parser.add_argument("design_plan", type=Path)
    parser.add_argument("--content-plan", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_design_plan_file(args.design_plan, content_plan_path=args.content_plan)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Design plan: {report['status']} ({report['issue_count']} issue(s))")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
