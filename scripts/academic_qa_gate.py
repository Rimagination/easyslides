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
    from scripts.scenario_profiles import (
        duration_page_band,
        get_profile,
        get_scenario_variant,
        load_profiles,
        validate_profiles,
    )
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from deck_plan_contract import validate_deck_plan, validate_deck_plan_file
    from scenario_profiles import (
        duration_page_band,
        get_profile,
        get_scenario_variant,
        load_profiles,
        validate_profiles,
    )


REPORT_SCHEMA_VERSION = "easyslides.academic_qa_report.v1"
RESULT_ROLES = {"key_results", "result", "results", "result_slide"}
RESULT_EVIDENCE_KINDS = {"figure", "table", "data", "dataset", "chart"}
REFERENCE_ROLES = {"references", "reference", "bibliography", "sources", "source_provenance"}
CONCLUSION_ROLES = {"conclusion", "conclusions", "limitations_and_outlook", "takeaways"}
ENDING_ROLES = {"ending", "thank_you", "thanks", "acknowledgements"}
VISIBLE_TEXT_FIELDS = (
    "action_title",
    "claim",
    "visible_text",
    "key_message",
    "central_message",
    "slot_payload",
    "body_payload",
)
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


def _load_variant(
    plan: dict[str, Any],
    profile: dict[str, Any],
    repo_root: Path,
) -> tuple[dict[str, Any], str | None]:
    if str(plan.get("scenario_profile") or "") != "thesis_defense":
        return {}, None
    variant_id = str(
        plan.get("scenario_variant")
        or profile.get("default_scenario_variant")
        or ""
    ).strip()
    if not variant_id:
        return {}, "thesis_defense requires a scenario_variant"
    try:
        catalog = load_profiles(repo_root / "references" / "scenario_profiles.json")
        return get_scenario_variant("thesis_defense", variant_id, catalog), None
    except Exception as exc:
        return {}, str(exc)


def _nested_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_nested_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_nested_text(item) for item in value)
    return ""


def _visible_slide_text(slide: dict[str, Any]) -> str:
    return " ".join(_nested_text(slide.get(field)) for field in VISIBLE_TEXT_FIELDS)


def _defense_section(slide: dict[str, Any]) -> str:
    return str(
        slide.get("defense_section_id")
        or slide.get("defense_section")
        or slide.get("section")
        or ""
    ).strip().lower()


def _toc_section_count(slides: list[dict[str, Any]], plan: dict[str, Any]) -> int:
    defense = plan.get("defense")
    if isinstance(defense, dict) and isinstance(defense.get("toc_sections"), list):
        return len(defense["toc_sections"])
    for slide in slides:
        if str(slide.get("role") or "").lower() != "toc":
            continue
        payload = slide.get("slot_payload")
        if isinstance(payload, dict):
            return len(
                [
                    key
                    for key in payload
                    if re.fullmatch(r"SECTION_\d+", str(key))
                    and str(payload[key]).strip()
                ]
            )
    return 0


def _has_conclusion_before_ending(slides: list[dict[str, Any]]) -> bool:
    if not slides:
        return False
    ending_index = next(
        (
            index
            for index in range(len(slides) - 1, -1, -1)
            if str(slides[index].get("role") or "").lower() in ENDING_ROLES
        ),
        None,
    )
    search_end = ending_index if ending_index is not None else len(slides)
    return any(
        str(slides[index].get("role") or "").lower() in CONCLUSION_ROLES
        for index in range(search_end)
    )


def _layout_run_issues(
    slides: list[dict[str, Any]],
    *,
    max_run: int,
) -> list[tuple[int, str]]:
    issues: list[tuple[int, str]] = []
    previous = ""
    run = 0
    for index, slide in enumerate(slides):
        role = str(slide.get("role") or "").lower()
        if role in {"cover", "toc", "chapter", "ending"}:
            previous = ""
            run = 0
            continue
        quality = slide.get("content_quality")
        if isinstance(quality, dict) and str(quality.get("status") or "").lower() == "placeholder":
            previous = ""
            run = 0
            continue
        layout = str(slide.get("layout_id") or "").rsplit("/", 1)[-1]
        if layout and layout == previous:
            run += 1
        else:
            previous = layout
            run = 1
        if layout and run > max_run:
            issues.append((index, layout))
    return issues


CONTENT_SHELL_ROLES = {"cover", "toc", "chapter", "ending"}


def _content_quality_policy(
    plan: dict[str, Any],
    variant: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    defense = plan.get("defense") if isinstance(plan.get("defense"), dict) else {}
    candidates = (
        plan.get("content_quality_policy"),
        defense.get("content_quality_policy"),
        variant.get("content_quality_policy"),
    )
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate, True
    explicit = any(
        isinstance(slide, dict)
        and ("content_quality" in slide or "content_contract" in slide)
        for slide in plan.get("slides", [])
    )
    return {}, explicit


def _quality_metrics(slide: dict[str, Any]) -> dict[str, Any]:
    quality = slide.get("content_quality") if isinstance(slide.get("content_quality"), dict) else {}
    contract = slide.get("content_contract") if isinstance(slide.get("content_contract"), dict) else {}
    evidence = contract.get("evidence") if isinstance(contract.get("evidence"), list) else []
    source_text_chars = quality.get("source_text_chars")
    if not isinstance(source_text_chars, int):
        source_text_chars = sum(
            len(str(item.get("text") or ""))
            for item in evidence
            if isinstance(item, dict)
        )
    evidence_count = quality.get("evidence_count")
    if not isinstance(evidence_count, int):
        evidence_count = len(evidence)
    material_types = quality.get("material_types")
    if not isinstance(material_types, list):
        material_types = []
    return {
        "status": str(quality.get("status") or contract.get("status") or "").strip().lower(),
        "evidence_count": evidence_count,
        "source_text_chars": source_text_chars,
        "material_types": [str(item).strip().lower() for item in material_types if str(item).strip()],
        "contract": contract,
    }


def _run_content_quality_qa(
    plan: dict[str, Any],
    slides: list[dict[str, Any]],
    variant: dict[str, Any],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    policy, explicit = _content_quality_policy(plan, variant)
    if not explicit:
        return {
            "status": "skipped",
            "checked_pages": 0,
            "adequate_pages": 0,
            "thin_pages": [],
            "placeholder_pages": [],
            "distinct_layouts": 0,
            "layout_diversity_ratio": 0.0,
        }

    required_structure = policy.get("required_structure")
    if not isinstance(required_structure, list) or not required_structure:
        required_structure = ["conclusion", "evidence", "explanation"]
    min_evidence = int(policy.get("min_evidence_blocks") or 1)
    min_source_chars = int(policy.get("min_source_text_chars") or 80)
    thin_severity = str(policy.get("thin_severity") or "warning").lower()
    placeholder_severity = str(policy.get("placeholder_severity") or "warning").lower()
    if thin_severity not in {"warning", "error"}:
        thin_severity = "warning"
    if placeholder_severity not in {"warning", "error"}:
        placeholder_severity = "warning"

    body_slides = [
        slide
        for slide in slides
        if str(slide.get("role") or "").lower() not in CONTENT_SHELL_ROLES
    ]
    thin_pages: list[str] = []
    placeholder_pages: list[str] = []
    adequate_pages = 0
    for index, slide in enumerate(body_slides):
        page = str(slide.get("page") or f"P{index + 1:02d}")
        metrics = _quality_metrics(slide)
        contract = metrics["contract"]
        missing = [
            key
            for key in required_structure
            if key not in contract
        ]
        if missing:
            issues.append(
                issue(
                    "AQA-CONTENT-STRUCTURE",
                    "error",
                    f"content contract is missing required field(s): {', '.join(str(item) for item in missing)}",
                    f"slides[{index}].content_contract",
                )
            )
            continue

        status = metrics["status"]
        has_non_text_material = any(
            item in {"figure", "table", "data", "dataset", "chart", "image"}
            for item in metrics["material_types"]
        )
        too_few_blocks = metrics["evidence_count"] < min_evidence
        too_little_source = metrics["source_text_chars"] < min_source_chars and not has_non_text_material
        if status == "placeholder" or metrics["evidence_count"] == 0:
            placeholder_pages.append(page)
            issues.append(
                issue(
                    "AQA-CONTENT-PLACEHOLDER",
                    placeholder_severity,
                    "content page has no source evidence; keep it as a declared placeholder until the source is supplied",
                    f"slides[{index}].content_contract.evidence",
                )
            )
        elif status == "thin" or too_few_blocks or too_little_source:
            thin_pages.append(page)
            issues.append(
                issue(
                    "AQA-CONTENT-THIN",
                    thin_severity,
                    f"content page needs at least {min_evidence} evidence block(s) and {min_source_chars} source-text characters, unless a figure/table/data material is present",
                    f"slides[{index}].content_quality",
                )
            )
        else:
            adequate_pages += 1

    diversity_policy = variant.get("layout_policy") if isinstance(variant.get("layout_policy"), dict) else {}
    if isinstance(plan.get("defense"), dict) and isinstance(plan["defense"].get("layout_policy"), dict):
        diversity_policy = {**diversity_policy, **plan["defense"]["layout_policy"]}
    min_distinct = int(
        policy.get("min_distinct_content_layouts")
        or diversity_policy.get("min_distinct_content_layouts")
        or 3
    )
    min_ratio = float(
        policy.get("min_layout_diversity_ratio")
        or diversity_policy.get("min_layout_diversity_ratio")
        or 0.3
    )
    min_pages = int(
        policy.get("layout_diversity_min_pages")
        or diversity_policy.get("layout_diversity_min_pages")
        or 6
    )
    layouts = [
        str(slide.get("layout_id") or "").rsplit("/", 1)[-1]
        for slide in body_slides
        if str(slide.get("layout_id") or "")
    ]
    distinct_layouts = len(set(layouts))
    diversity_ratio = distinct_layouts / len(layouts) if layouts else 0.0
    diversity_issue = len(layouts) >= min_pages and (
        distinct_layouts < min_distinct or diversity_ratio < min_ratio
    )
    if diversity_issue:
        issues.append(
            issue(
                "AQA-LAYOUT-DIVERSITY",
                "warning",
                f"content pages use {distinct_layouts} distinct layout(s) across {len(layouts)} pages; target is at least {min_distinct} layouts and a {min_ratio:.0%} diversity ratio",
                "slides.layout_id",
            )
        )

    quality_issues = len(thin_pages) + len(placeholder_pages)
    return {
        "status": "warn" if quality_issues or diversity_issue else "pass",
        "checked_pages": len(body_slides),
        "adequate_pages": adequate_pages,
        "thin_pages": thin_pages,
        "placeholder_pages": placeholder_pages,
        "distinct_layouts": distinct_layouts,
        "layout_diversity_ratio": round(diversity_ratio, 3),
    }


def _run_thesis_defense_qa(
    plan: dict[str, Any],
    slides: list[dict[str, Any]],
    profile: dict[str, Any],
    variant: dict[str, Any],
    issues: list[dict[str, str]],
    repo_root: Path,
) -> None:
    policy = variant.get("layout_policy") if isinstance(variant.get("layout_policy"), dict) else {}
    toc_range = policy.get("toc_top_level_sections") if isinstance(policy.get("toc_top_level_sections"), dict) else {}
    toc_count = _toc_section_count(slides, plan)
    if toc_count and (
        toc_count < int(toc_range.get("min", 0))
        or toc_count > int(toc_range.get("max", 10**6))
    ):
        issues.append(
            issue(
                "AQA-TOC-RANGE",
                "error",
                f"TOC must contain {toc_range.get('min')}-{toc_range.get('max')} top-level sections",
                "defense.toc_sections",
            )
        )
    elif not toc_count and bool(policy.get("toc_required")):
        issues.append(
            issue(
                "AQA-TOC-MISSING",
                "warning",
                "thesis defense variant recommends a 4-7 item top-level TOC",
                "slides",
            )
        )

    intro_policy = variant.get("intro_policy") if isinstance(variant.get("intro_policy"), dict) else {}
    intro_min = int(intro_policy.get("min_pages") or 0)
    intro_slides = [
        slide
        for slide in slides
        if _defense_section(slide) in {"introduction", "intro", "研究背景与问题"}
    ]
    tagged_sections = any(_defense_section(slide) for slide in slides)
    if intro_min and intro_slides and len(intro_slides) < intro_min:
        issues.append(
            issue(
                "AQA-INTRO-MINIMUM",
                "error",
                f"introduction needs at least {intro_min} pages when source material supports it",
                "defense.intro_min_pages",
            )
        )
    elif not tagged_sections:
        issues.append(
            issue(
                "AQA-DEFENSE-METADATA",
                "warning",
                "thesis defense slides should declare defense_section or defense_section_id for structural QA",
                "slides",
            )
        )

    chapters = plan.get("defense", {}).get("chapters") if isinstance(plan.get("defense"), dict) else None
    if isinstance(chapters, list) and chapters:
        declared_ids = {
            str(chapter.get("id") or "")
            for chapter in chapters
            if isinstance(chapter, dict) and str(chapter.get("id") or "")
        }
        covered_ids = {
            str(slide.get("chapter_id") or "")
            for slide in slides
            if str(slide.get("chapter_id") or "")
        }
        missing = sorted(declared_ids - covered_ids)
        if missing:
            issues.append(
                issue(
                    "AQA-CHAPTER-COVERAGE",
                    "error",
                    f"declared thesis chapter(s) have no planned slide coverage: {', '.join(missing)}",
                    "defense.chapters",
                )
            )

        min_layouts = int(policy.get("min_distinct_content_layouts_per_chapter") or 0)
        if min_layouts > 1:
            for chapter_id in sorted(covered_ids & declared_ids):
                chapter_slides = [
                    slide
                    for slide in slides
                    if str(slide.get("chapter_id") or "") == chapter_id
                    and str(slide.get("role") or "").lower() not in {"chapter"}
                ]
                layouts = {
                    str(slide.get("layout_id") or "").rsplit("/", 1)[-1]
                    for slide in chapter_slides
                    if str(slide.get("layout_id") or "")
                }
                if len(chapter_slides) >= 2 and len(layouts) < min_layouts:
                    issues.append(
                        issue(
                            "AQA-CHAPTER-LAYOUT-RHYTHM",
                            "error",
                            f"{chapter_id} needs at least {min_layouts} distinct content layouts",
                            f"defense.chapters[{chapter_id}]",
                        )
                    )

    max_run = int(policy.get("max_consecutive_identical_content_layouts") or 0)
    if max_run:
        for index, layout in _layout_run_issues(slides, max_run=max_run):
            issues.append(
                issue(
                    "AQA-LAYOUT-RHYTHM",
                    "error",
                    f"content layout {layout!r} appears in more than {max_run} consecutive pages",
                    f"slides[{index}].layout_id",
                )
            )

    banned = (
        variant.get("visible_text_policy", {}).get("banned_phrases")
        if isinstance(variant.get("visible_text_policy"), dict)
        else []
    )
    for index, slide in enumerate(slides):
        visible = _visible_slide_text(slide).casefold()
        for phrase in banned if isinstance(banned, list) else []:
            phrase_text = str(phrase).strip()
            if phrase_text and phrase_text.casefold() in visible:
                issues.append(
                    issue(
                        "AQA-BANNED-VISIBLE-PHRASE",
                        "error",
                        f"visible slide text contains banned planning phrase {phrase_text!r}",
                        f"slides[{index}]",
                    )
                )

    defense = plan.get("defense") if isinstance(plan.get("defense"), dict) else {}
    page_budget = defense.get("page_budget") if isinstance(defense.get("page_budget"), dict) else {}
    duration = page_budget.get("duration_minutes") or defense.get("duration_minutes")
    if duration is not None:
        band = duration_page_band(
            "thesis_defense",
            duration,
            variant_id=str(plan.get("scenario_variant") or profile.get("default_scenario_variant") or ""),
            catalog=load_profiles(repo_root / "references" / "scenario_profiles.json"),
        )
        if band and not (int(band["min_pages"]) <= len(slides) <= int(band["max_pages"])):
            severity = "error" if page_budget.get("enforce") is True else "warning"
            issues.append(
                issue(
                    "AQA-PAGE-BUDGET",
                    severity,
                    f"{band['label']} recommends {band['min_pages']}-{band['max_pages']} pages; draft has {len(slides)}",
                    "defense.page_budget",
                )
            )

    for index, source in enumerate(plan.get("source_map", [])):
        if not isinstance(source, dict) or source.get("type") != "figure":
            continue
        quality = source.get("quality")
        if isinstance(quality, dict) and quality.get("needs_high_res") is True:
            issues.append(
                issue(
                    "AQA-FIGURE-HIGH-RES",
                    "warning",
                    "A-class evidence figure should be replaced with a high-resolution original before final export",
                    f"source_map[{index}]",
                )
            )


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
    variant, variant_error = _load_variant(plan, profile, repo)
    if str(plan.get("scenario_profile") or "") == "thesis_defense":
        if variant_error:
            issues.append(
                issue(
                    "AQA-SCENARIO-VARIANT",
                    "error",
                    variant_error,
                    "scenario_variant",
                )
            )
        elif variant:
            _run_thesis_defense_qa(plan, slides, profile, variant, issues, repo)

    content_quality_summary = _run_content_quality_qa(plan, slides, variant, issues)

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

    if "conclusion_before_ending" in profile_rules and not _has_conclusion_before_ending(slides):
        issues.append(
            issue(
                "AQA-CONCLUSION-BEFORE-END",
                "warning",
                "scenario recommends placing Conclusions/Outlook before the fixed ending page",
                "slides",
            )
        )
    elif "conclusion_last" in profile_rules and not _last_slide_is_conclusion(slides):
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
        "content_quality_status": content_quality_summary["status"],
        "content_quality_summary": content_quality_summary,
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
