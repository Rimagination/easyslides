#!/usr/bin/env python3
"""Run academic quality checks against an EasySlides deck_plan.json.

This gate validates academic expression and evidence discipline before SVG/PPTX
execution. It is intentionally deck-plan based: the plan is cheap to revise and
already carries the page-level story contract.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.deck_plan_contract import validate_deck_plan, validate_deck_plan_file
    from scripts.scenario_profiles import get_profile, load_profiles, validate_profiles
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from deck_plan_contract import validate_deck_plan, validate_deck_plan_file
    from scenario_profiles import get_profile, load_profiles, validate_profiles


REPORT_SCHEMA_VERSION = "easyslides.academic_qa_report.v1"
RESULT_ROLES = {"key_results", "result", "results", "result_slide"}
RESULT_EVIDENCE_KINDS = {"figure", "table", "data", "dataset", "chart"}
REFERENCE_ROLES = {"references", "reference", "bibliography", "sources", "source_provenance"}
CONCLUSION_ROLES = {"conclusion", "conclusions", "limitations_and_outlook", "takeaways"}
GENERIC_TOPIC_TITLES = {
    "abstract",
    "agenda",
    "background",
    "conclusion",
    "conclusions",
    "discussion",
    "experiment",
    "experiments",
    "introduction",
    "method",
    "methods",
    "overview",
    "references",
    "related work",
    "results",
    "summary",
    "thank you",
}


def issue(code: str, severity: str, message: str, path: str | None = None) -> dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if path:
        item["path"] = path
    return item


def _normalize_title(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[\s\-_:/|]+", " ", value)
    value = re.sub(r"[^\w\s\u4e00-\u9fff]", "", value)
    return value.strip()


def _is_generic_topic_title(value: str) -> bool:
    normalized = _normalize_title(value)
    return normalized in GENERIC_TOPIC_TITLES or normalized in {
        "背景",
        "方法",
        "结果",
        "讨论",
        "结论",
        "参考文献",
        "致谢",
    }


def _load_profile(plan: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    catalog = load_profiles(repo_root / "references" / "scenario_profiles.json")
    validate_profiles(catalog)
    return get_profile(str(plan.get("scenario_profile", "")), catalog)


def _has_references_slide(slides: list[dict[str, Any]]) -> bool:
    return any(str(slide.get("role", "")).lower() in REFERENCE_ROLES for slide in slides)


def _has_borrowed_or_reference_evidence(plan: dict[str, Any]) -> bool:
    source_types = {"figure", "table", "data", "dataset", "reference"}
    evidence_kinds = {"figure", "table", "data", "dataset", "chart", "reference"}
    for source in plan.get("source_map", []):
        if isinstance(source, dict) and str(source.get("type", "")).lower() in source_types:
            return True
    for slide in plan.get("slides", []):
        if not isinstance(slide, dict):
            continue
        for evidence in slide.get("evidence_sources", []):
            if isinstance(evidence, dict) and str(evidence.get("kind", "")).lower() in evidence_kinds:
                return True
    return False


def _last_slide_is_conclusion(slides: list[dict[str, Any]]) -> bool:
    if not slides:
        return False
    role = str(slides[-1].get("role", "")).lower()
    return role in CONCLUSION_ROLES


def run_academic_qa(plan: dict[str, Any], *, repo_root: Path | str | None = None) -> dict[str, Any]:
    """Return an academic QA report for a loaded deck plan."""
    repo = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    issues: list[dict[str, str]] = []

    contract = validate_deck_plan(plan, repo_root=repo)
    for item in contract["issues"]:
        code = "AQA-BODY-VARIANT" if item["code"] == "DECK-PLAN-BODY-VARIANT" else "AQA-CONTRACT"
        issues.append(
            issue(
                code,
                "error",
                f"{item['code']}: {item['message']}",
                item.get("path"),
            )
        )

    slides = [slide for slide in plan.get("slides", []) if isinstance(slide, dict)]
    try:
        profile = _load_profile(plan, repo)
    except Exception:
        profile = {}

    for index, slide in enumerate(slides):
        path = f"slides[{index}]"
        title = str(slide.get("action_title", ""))
        if _is_generic_topic_title(title):
            issues.append(
                issue(
                    "AQA-ACTION-TITLE",
                    "error",
                    "action_title is a topic label; write a conclusion sentence instead",
                    f"{path}.action_title",
                )
            )

        role = str(slide.get("role", "")).lower()
        if role in RESULT_ROLES:
            kinds = {
                str(evidence.get("kind", "")).lower()
                for evidence in slide.get("evidence_sources", [])
                if isinstance(evidence, dict)
            }
            if not kinds & RESULT_EVIDENCE_KINDS:
                issues.append(
                    issue(
                        "AQA-RESULT-EVIDENCE",
                        "error",
                        "result slides need figure/table/data/chart evidence, not only prose sections",
                        f"{path}.evidence_sources",
                    )
                )

    profile_rules = set(profile.get("required_rules", [])) | set(profile.get("recommended_rules", []))
    if (
        ("citation_retention" in profile_rules or _has_borrowed_or_reference_evidence(plan))
        and not _has_references_slide(slides)
    ):
        issues.append(
            issue(
                "AQA-REFERENCES",
                "warning",
                "borrowed or source-linked evidence is present but no References/source provenance slide is planned",
                "slides",
            )
        )

    if "conclusion_last" in profile_rules and not _last_slide_is_conclusion(slides):
        issues.append(
            issue(
                "AQA-CONCLUSION-LAST",
                "warning",
                "scenario recommends ending on Conclusions rather than Thank You/Q&A",
                "slides[-1].role",
            )
        )

    error_count = sum(1 for item in issues if item["severity"] == "error")
    warning_count = sum(1 for item in issues if item["severity"] == "warning")
    status = "fail" if error_count else "warn" if warning_count else "pass"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": status,
        "issue_count": len(issues),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "slide_count": len(slides),
        "contract_status": contract["status"],
        "body_variant_status": contract.get("body_variant_status", "skipped"),
    }


def _file_error(message: str, path: Path) -> dict[str, Any]:
    item = issue("AQA-FILE", "error", message, str(path))
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "fail",
        "issue_count": 1,
        "error_count": 1,
        "warning_count": 0,
        "issues": [item],
        "slide_count": 0,
        "contract_status": "fail",
        "body_variant_status": "skipped",
    }


def run_academic_qa_file(path: Path, *, repo_root: Path | str | None = None) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _file_error("deck_plan.json not found", path)
    except json.JSONDecodeError as exc:
        return _file_error(f"invalid JSON: {exc}", path)

    report = run_academic_qa(plan, repo_root=repo_root)
    file_contract = validate_deck_plan_file(path, repo_root=Path(repo_root) if repo_root else None)
    if file_contract["status"] == "fail" and report["contract_status"] == "pass":
        report["contract_status"] = "fail"
    return report


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

    report = run_academic_qa_file(args.deck_plan, repo_root=args.repo_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Academic QA Gate: {report['status']} "
            f"({report['error_count']} error(s), {report['warning_count']} warning(s))"
        )
        for item in report["issues"]:
            loc = f" [{item['path']}]" if "path" in item else ""
            print(f"- {item['severity']} {item['code']}: {item['message']}{loc}")
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
