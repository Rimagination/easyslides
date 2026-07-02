#!/usr/bin/env python3
"""Build and validate EasySlides deck execution locks.

The execution lock is the compact handoff from Strategist to Executor. It
freezes per-page layout, rhythm, body variant selection, template tokens, and
required gates so SVG generation can re-read facts instead of relying on memory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.body_variant_adapter import validate_deck_body_variants
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from body_variant_adapter import validate_deck_body_variants


SCHEMA_VERSION = "easyslides.deck_execution_lock.v1"
REPORT_SCHEMA_VERSION = "easyslides.deck_execution_lock_report.v1"
BASE_REQUIRED_GATES = (
    "deck_plan_contract",
    "deck_execution_lock",
    "svg_quality_checker",
    "preview_render",
    "pptx_roundtrip",
)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _plan_template_id(plan: dict[str, Any]) -> str:
    template_id = plan.get("template_id")
    if _is_nonempty_string(template_id):
        return str(template_id)
    template = plan.get("template")
    if isinstance(template, dict):
        for key in ("template_id", "id"):
            if _is_nonempty_string(template.get(key)):
                return str(template[key])
    return ""


def _body_report_by_page(body_variant_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for item in body_variant_report.get("slides", []):
        if isinstance(item, dict) and _is_nonempty_string(item.get("page")):
            reports[str(item["page"])] = item
    return reports


def _gate_list(body_variant_report: dict[str, Any]) -> list[str]:
    gates = set(BASE_REQUIRED_GATES)
    for item in body_variant_report.get("slides", []):
        if isinstance(item, dict):
            gates.update(str(gate) for gate in item.get("required_gates", []) if str(gate))
    return sorted(gates)


def _body_variant_lock(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "template_id": item.get("template_id", ""),
        "variant_id": item.get("variant_id", ""),
        "reason": item.get("reason", ""),
        "status": item.get("status", ""),
        "declared_slots": list(item.get("declared_slots", [])),
        "provided_slots": list(item.get("provided_slots", [])),
        "palette_id": item.get("palette_id", ""),
        "required_gates": list(item.get("required_gates", [])),
    }


def build_deck_execution_lock(
    plan: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    """Build a machine-readable execution lock from a validated deck plan."""
    repo = Path(repo_root).resolve() if repo_root else Path.cwd()
    body_variant_report = validate_deck_body_variants(plan, repo_root=repo)
    body_by_page = _body_report_by_page(body_variant_report)
    pages: dict[str, dict[str, Any]] = {}
    slides = plan.get("slides") if isinstance(plan, dict) else []
    if not isinstance(slides, list):
        slides = []

    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        page = str(slide.get("page") or f"P{index + 1:02d}")
        body_item = body_by_page.get(page)
        pages[page] = {
            "index": index,
            "role": str(slide.get("role") or ""),
            "action_title": str(slide.get("action_title") or ""),
            "claim": str(slide.get("claim") or ""),
            "layout_id": str(slide.get("layout_id") or ""),
            "rhythm": str(slide.get("rhythm") or ""),
            "content_shape": str(slide.get("content_shape") or slide.get("evidence_shape") or ""),
            "chart_id": str(slide.get("chart_id") or ""),
            "evidence_sources": list(slide.get("evidence_sources", []))
            if isinstance(slide.get("evidence_sources"), list)
            else [],
            "body_variant": _body_variant_lock(body_item),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(plan.get("schema_version") or ""),
        "scenario_profile": str(plan.get("scenario_profile") or ""),
        "template_id": _plan_template_id(plan),
        "slide_count": len(slides),
        "required_gates": _gate_list(body_variant_report),
        "body_variant_status": body_variant_report.get("status", "skipped"),
        "pages": pages,
    }


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def validate_deck_execution_lock(
    plan: dict[str, Any],
    lock: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    """Validate that an execution lock still matches the current deck plan."""
    issues: list[dict[str, str]] = []
    if not isinstance(lock, dict):
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("EXEC-LOCK-TYPE", "execution lock must be a JSON object", "$")],
        }

    if lock.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "EXEC-LOCK-SCHEMA",
                f"schema_version must be {SCHEMA_VERSION}",
                "schema_version",
            )
        )

    expected = build_deck_execution_lock(plan, repo_root=repo_root)
    if lock.get("slide_count") != expected["slide_count"]:
        issues.append(
            _issue(
                "EXEC-LOCK-SLIDE-COUNT",
                f"slide_count drifted from {expected['slide_count']} to {lock.get('slide_count')}",
                "slide_count",
            )
        )

    locked_pages = lock.get("pages")
    if not isinstance(locked_pages, dict):
        issues.append(_issue("EXEC-LOCK-PAGES", "pages must be a JSON object", "pages"))
        locked_pages = {}

    for page, expected_page in expected["pages"].items():
        actual_page = locked_pages.get(page)
        if not isinstance(actual_page, dict):
            issues.append(_issue("EXEC-LOCK-PAGE", f"missing page {page}", f"pages.{page}"))
            continue
        for key, code in (("layout_id", "EXEC-LOCK-LAYOUT"), ("rhythm", "EXEC-LOCK-RHYTHM")):
            if actual_page.get(key) != expected_page.get(key):
                issues.append(
                    _issue(
                        code,
                        f"{page} {key} drifted from {expected_page.get(key)!r} to {actual_page.get(key)!r}",
                        f"pages.{page}.{key}",
                    )
                )
        expected_body = expected_page.get("body_variant") or {}
        actual_body = actual_page.get("body_variant") or {}
        if expected_body.get("variant_id") != actual_body.get("variant_id"):
            issues.append(
                _issue(
                    "EXEC-LOCK-BODY-VARIANT",
                    f"{page} body variant drifted from {expected_body.get('variant_id')!r} to {actual_body.get('variant_id')!r}",
                    f"pages.{page}.body_variant.variant_id",
                )
            )

    missing_gates = sorted(set(expected["required_gates"]) - set(lock.get("required_gates", [])))
    if missing_gates:
        issues.append(
            _issue(
                "EXEC-LOCK-GATES",
                f"required_gates missing: {', '.join(missing_gates)}",
                "required_gates",
            )
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
    }


def validate_deck_execution_lock_file(
    plan_path: Path,
    lock_path: Path,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("EXEC-LOCK-FILE", f"file not found: {exc.filename}", str(exc.filename))],
        }
    except json.JSONDecodeError as exc:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("EXEC-LOCK-JSON", f"invalid JSON: {exc}", str(exc.doc))],
        }
    return validate_deck_execution_lock(plan, lock, repo_root=repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_plan", type=Path, help="Path to deck_plan.json")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--write", type=Path, help="Write deck_execution_lock.json to this path")
    parser.add_argument("--validate", type=Path, help="Validate an existing deck_execution_lock.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    if args.validate:
        report = validate_deck_execution_lock_file(args.deck_plan, args.validate, repo_root=args.repo_root)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Deck execution lock: {report['status']} ({report['issue_count']} issue(s))")
        return 0 if report["status"] == "pass" else 1

    try:
        plan = json.loads(args.deck_plan.read_text(encoding="utf-8"))
        lock = build_deck_execution_lock(plan, repo_root=args.repo_root)
    except Exception as exc:
        print(f"failed to build deck execution lock: {exc}", file=sys.stderr)
        return 1

    if args.write:
        args.write.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(lock, ensure_ascii=False, indent=2) if args.json else "Deck execution lock: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
