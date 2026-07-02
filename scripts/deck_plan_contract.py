#!/usr/bin/env python3
"""Validate EasySlides deck_plan.json story contracts.

The deck plan is the source-facing page contract between Strategist and
Executor: it records each slide's action title, claim, evidence references,
layout choice, rhythm, and speaker note before visual execution begins.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.body_variant_adapter import validate_deck_body_variants
    from scripts.deck_execution_lock import build_deck_execution_lock
    from scripts.scenario_profiles import load_profiles, validate_profiles
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from body_variant_adapter import validate_deck_body_variants
    from deck_execution_lock import build_deck_execution_lock
    from scenario_profiles import load_profiles, validate_profiles


SCHEMA_VERSION = "easyslides.deck_plan.v1"
REPORT_SCHEMA_VERSION = "easyslides.deck_plan_report.v1"
PAGE_RE = re.compile(r"^P\d{2,3}$")
RHYTHMS = {"anchor", "dense", "breathing"}
REQUIRED_SLIDE_STRINGS = (
    "page",
    "role",
    "action_title",
    "claim",
    "layout_id",
    "rhythm",
    "speaker_note",
)


def issue(code: str, message: str, path: str | None = None) -> dict[str, str]:
    item = {"code": code, "message": message}
    if path:
        item["path"] = path
    return item


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _profile_ids(repo_root: Path) -> set[str]:
    catalog = load_profiles(repo_root / "references" / "scenario_profiles.json")
    validate_profiles(catalog)
    return set(catalog["profiles"])


def validate_deck_plan(plan: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Any]:
    """Validate a loaded deck plan and return a machine-readable report."""
    repo = (repo_root or Path.cwd()).resolve()
    issues: list[dict[str, str]] = []
    pages: list[str] = []

    if not isinstance(plan, dict):
        issues.append(issue("DECK-PLAN-TYPE", "deck plan must be a JSON object"))
        return _report(issues, pages, 0)

    if plan.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            issue(
                "DECK-PLAN-SCHEMA",
                f"schema_version must be {SCHEMA_VERSION}",
                "schema_version",
            )
        )

    scenario_profile = plan.get("scenario_profile")
    if not _is_nonempty_string(scenario_profile):
        issues.append(issue("DECK-PLAN-PROFILE", "scenario_profile is required", "scenario_profile"))
    else:
        try:
            if scenario_profile not in _profile_ids(repo):
                issues.append(
                    issue(
                        "DECK-PLAN-PROFILE",
                        f"unknown scenario_profile {scenario_profile!r}",
                        "scenario_profile",
                    )
                )
        except Exception as exc:  # pragma: no cover - defensive report for broken catalogs
            issues.append(
                issue(
                    "DECK-PLAN-PROFILE-CATALOG",
                    f"cannot validate scenario profiles: {exc}",
                    "references/scenario_profiles.json",
                )
            )

    source_ids = _validate_source_map(plan.get("source_map"), issues)
    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        issues.append(issue("DECK-PLAN-SLIDES", "slides must be a non-empty list", "slides"))
        return _report(issues, pages, 0)

    seen_pages: set[str] = set()
    for index, slide in enumerate(slides):
        slide_path = f"slides[{index}]"
        if not isinstance(slide, dict):
            issues.append(issue("DECK-PLAN-SLIDE", "slide must be a JSON object", slide_path))
            continue
        page = slide.get("page")
        if _is_nonempty_string(page):
            pages.append(page)
        _validate_slide(slide, slide_path, issues, source_ids, seen_pages)

    body_variant_report = validate_deck_body_variants(plan, repo_root=repo)
    for item in body_variant_report["issues"]:
        issues.append(
            issue(
                "DECK-PLAN-BODY-VARIANT",
                f"{item['code']}: {item['message']}",
                item.get("path"),
            )
        )

    execution_lock = None
    try:
        execution_lock = build_deck_execution_lock(plan, repo_root=repo)
    except Exception as exc:
        issues.append(
            issue(
                "DECK-PLAN-EXECUTION-LOCK",
                f"cannot build deck execution lock: {exc}",
                "deck_execution_lock",
            )
        )

    return _report(issues, pages, len(slides), body_variant_report, execution_lock)


def _validate_source_map(value: Any, issues: list[dict[str, str]]) -> set[str]:
    if not isinstance(value, list) or not value:
        issues.append(issue("DECK-PLAN-SOURCE-MAP", "source_map must be a non-empty list", "source_map"))
        return set()

    ids: set[str] = set()
    parent_refs: list[tuple[str, str]] = []
    for index, source in enumerate(value):
        path = f"source_map[{index}]"
        if not isinstance(source, dict):
            issues.append(issue("DECK-PLAN-SOURCE", "source entry must be a JSON object", path))
            continue
        source_id = source.get("id")
        if not _is_nonempty_string(source_id):
            issues.append(issue("DECK-PLAN-SOURCE-ID", "source id is required", f"{path}.id"))
            continue
        if source_id in ids:
            issues.append(issue("DECK-PLAN-SOURCE-ID", f"duplicate source id {source_id!r}", f"{path}.id"))
        ids.add(source_id)
        for key in ("type", "path", "title"):
            if not _is_nonempty_string(source.get(key)):
                issues.append(issue("DECK-PLAN-SOURCE-FIELD", f"source {source_id!r} missing {key}", f"{path}.{key}"))
        parent = source.get("parent_source")
        if parent is not None:
            parent_refs.append((str(parent), f"{path}.parent_source"))

    for parent, path in parent_refs:
        if parent not in ids:
            issues.append(issue("DECK-PLAN-SOURCE-PARENT", f"unknown parent_source {parent!r}", path))
    return ids


def _validate_slide(
    slide: dict[str, Any],
    slide_path: str,
    issues: list[dict[str, str]],
    source_ids: set[str],
    seen_pages: set[str],
) -> None:
    for key in REQUIRED_SLIDE_STRINGS:
        if not _is_nonempty_string(slide.get(key)):
            code = "DECK-PLAN-ACTION-TITLE" if key == "action_title" else "DECK-PLAN-SLIDE-FIELD"
            issues.append(issue(code, f"slide {key} is required", f"{slide_path}.{key}"))

    page = slide.get("page")
    if _is_nonempty_string(page):
        if not PAGE_RE.match(page):
            issues.append(issue("DECK-PLAN-PAGE", f"invalid page id {page!r}; expected P01", f"{slide_path}.page"))
        if page in seen_pages:
            issues.append(issue("DECK-PLAN-PAGE", f"duplicate page id {page!r}", f"{slide_path}.page"))
        seen_pages.add(page)

    rhythm = slide.get("rhythm")
    if _is_nonempty_string(rhythm) and rhythm not in RHYTHMS:
        issues.append(
            issue(
                "DECK-PLAN-RHYTHM",
                f"rhythm must be one of {sorted(RHYTHMS)}",
                f"{slide_path}.rhythm",
            )
        )

    evidence_sources = slide.get("evidence_sources")
    if not isinstance(evidence_sources, list) or not evidence_sources:
        issues.append(
            issue(
                "DECK-PLAN-EVIDENCE",
                "evidence_sources must be a non-empty list",
                f"{slide_path}.evidence_sources",
            )
        )
        return

    for index, evidence in enumerate(evidence_sources):
        path = f"{slide_path}.evidence_sources[{index}]"
        if not isinstance(evidence, dict):
            issues.append(issue("DECK-PLAN-EVIDENCE", "evidence entry must be a JSON object", path))
            continue
        for key in ("source_id", "locator", "kind"):
            if not _is_nonempty_string(evidence.get(key)):
                issues.append(issue("DECK-PLAN-EVIDENCE", f"evidence {key} is required", f"{path}.{key}"))
        source_id = evidence.get("source_id")
        if _is_nonempty_string(source_id) and source_id not in source_ids:
            issues.append(
                issue(
                    "DECK-PLAN-SOURCE-REF",
                    f"evidence source_id {source_id!r} is not declared in source_map",
                    f"{path}.source_id",
                )
            )


def _empty_body_variant_report(slide_count: int) -> dict[str, Any]:
    return {
        "schema_version": "easyslides.deck_body_variant_report.v1",
        "status": "skipped",
        "issue_count": 0,
        "issues": [],
        "slide_count": slide_count,
        "checked_slide_count": 0,
        "slides": [],
    }


def _report(
    issues: list[dict[str, str]],
    pages: list[str],
    slide_count: int,
    body_variant_report: dict[str, Any] | None = None,
    execution_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body_variant_report = body_variant_report or _empty_body_variant_report(slide_count)
    execution_lock_status = (
        "pass"
        if isinstance(execution_lock, dict) and not issues
        else "fail"
        if isinstance(execution_lock, dict)
        else "skipped"
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "slide_count": slide_count,
        "pages": pages,
        "body_variant_status": body_variant_report["status"],
        "body_variant_reports": body_variant_report["slides"],
        "execution_lock_status": execution_lock_status,
        "execution_lock": execution_lock,
    }


def validate_deck_plan_file(path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _report([issue("DECK-PLAN-FILE", "deck_plan.json not found", str(path))], [], 0)
    except json.JSONDecodeError as exc:
        return _report([issue("DECK-PLAN-JSON", f"invalid JSON: {exc}", str(path))], [], 0)
    return validate_deck_plan(plan, repo_root=repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_plan", type=Path, help="Path to deck_plan.json")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root used to resolve references/scenario_profiles.json",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    report = validate_deck_plan_file(args.deck_plan, repo_root=args.repo_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Deck plan contract: {report['status']} ({report['issue_count']} issue(s))")
        for page in report["pages"]:
            print(f"- {page}")
        for item in report["issues"]:
            loc = f" [{item['path']}]" if "path" in item else ""
            print(f"- {item['code']}: {item['message']}{loc}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
