#!/usr/bin/env python3
"""Build a draft deck_plan.json for single-paper report projects.

This is a lightweight intake layer: it consumes already-imported project
artifacts under `sources/` and `images/`, then emits a traceable deck-plan
draft that Strategist can refine before visual execution.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.deck_plan_contract import validate_deck_plan
    from scripts.scenario_profiles import get_profile, load_profiles, validate_profiles
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from deck_plan_contract import validate_deck_plan
    from scenario_profiles import get_profile, load_profiles, validate_profiles


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
DEFAULT_TEMPLATE_ID = "academic_scqa"
ROLE_BODY_VARIANTS = {
    "paper_identity": ("flexible_canvas", "text"),
    "background_and_gap": ("intro_policy", "context"),
    "research_question": ("key_finding", "key_finding"),
    "method_or_model": ("research_method", "method"),
    "key_results": ("key_finding", "figure"),
    "contributions": ("flexible_canvas", "text"),
    "references": ("flexible_canvas", "text"),
    "limitations_and_outlook": ("flexible_canvas", "text"),
}


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _first_heading(markdown_files: list[Path]) -> str | None:
    for md_path in markdown_files:
        text = md_path.read_text(encoding="utf-8", errors="replace")
        match = HEADING_RE.search(text)
        if match:
            return match.group(1).strip()
    return None


def _discover_paper(project_dir: Path, markdown_files: list[Path]) -> dict[str, str]:
    sources_dir = project_dir / "sources"
    pdfs = sorted(sources_dir.glob("*.pdf"))
    title = _first_heading(markdown_files)
    if pdfs:
        paper_path = pdfs[0]
        return {
            "id": "paper:main",
            "type": "pdf",
            "path": _relative(paper_path, project_dir),
            "title": title or paper_path.stem.replace("_", " "),
        }
    if markdown_files:
        md_path = markdown_files[0]
        return {
            "id": "paper:main",
            "type": "markdown",
            "path": _relative(md_path, project_dir),
            "title": title or md_path.stem.replace("_", " "),
        }
    return {
        "id": "paper:main",
        "type": "unknown",
        "path": "sources/",
        "title": project_dir.name,
    }


def _markdown_image_refs(markdown_files: list[Path], project_dir: Path) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for md_path in markdown_files:
        text = md_path.read_text(encoding="utf-8", errors="replace")
        for match in IMAGE_RE.finditer(text):
            alt = match.group(1).strip()
            raw_path = match.group(2).strip()
            normalized = raw_path.split("#", 1)[0].split("?", 1)[0]
            candidate = (md_path.parent / normalized).resolve()
            if not candidate.exists():
                candidate = (project_dir / normalized).resolve()
            refs.append(
                {
                    "path": _relative(candidate, project_dir),
                    "title": alt or Path(normalized).stem.replace("_", " "),
                }
            )
    return refs


def _manifest_figures(project_dir: Path) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for manifest_path in sorted((project_dir / "sources").glob("*manifest*.json")):
        manifest = _read_json(manifest_path)
        for item in manifest.get("figures", []):
            if isinstance(item, str):
                figure_path = project_dir / "images" / item
                refs.append(
                    {
                        "path": _relative(figure_path, project_dir),
                        "title": Path(item).stem.replace("_", " "),
                    }
                )
            elif isinstance(item, dict):
                raw_path = str(item.get("path") or item.get("file") or item.get("name") or "")
                if not raw_path:
                    continue
                figure_path = Path(raw_path)
                if not figure_path.is_absolute():
                    figure_path = project_dir / raw_path
                    if not figure_path.exists():
                        figure_path = project_dir / "images" / Path(raw_path).name
                refs.append(
                    {
                        "path": _relative(figure_path, project_dir),
                        "title": str(item.get("title") or item.get("caption") or figure_path.stem),
                    }
                )
    return refs


def _image_dir_figures(project_dir: Path) -> list[dict[str, str]]:
    images_dir = project_dir / "images"
    if not images_dir.is_dir():
        return []
    refs = []
    for image_path in sorted(images_dir.iterdir()):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
            refs.append(
                {
                    "path": _relative(image_path, project_dir),
                    "title": image_path.stem.replace("_", " "),
                }
            )
    return refs


def _discover_figures(project_dir: Path, markdown_files: list[Path]) -> list[dict[str, str]]:
    by_path: dict[str, dict[str, str]] = {}
    for ref in (
        _markdown_image_refs(markdown_files, project_dir)
        + _manifest_figures(project_dir)
        + _image_dir_figures(project_dir)
    ):
        path = ref["path"].replace("\\", "/")
        if Path(path).suffix.lower() not in IMAGE_SUFFIXES:
            continue
        by_path.setdefault(path, {"path": path, "title": ref["title"]})
    figures = []
    for index, ref in enumerate(by_path.values(), start=1):
        figures.append(
            {
                "id": f"fig:{index}",
                "type": "figure",
                "path": ref["path"],
                "title": ref["title"],
                "parent_source": "paper:main",
            }
        )
    return figures


def _slide_for_role(index: int, role: str, paper: dict[str, str], figures: list[dict[str, str]]) -> dict[str, Any]:
    page = f"P{index:02d}"
    title = paper["title"]
    evidence_source = "paper:main"
    locator = role.replace("_", " ")
    kind = "paper_section"

    if role == "key_results" and figures:
        evidence_source = figures[0]["id"]
        locator = figures[0]["title"]
        kind = "figure"
    elif role == "references":
        locator = "references"
        kind = "reference"

    action_title_by_role = {
        "paper_identity": f"{title} is ready for a traceable paper report",
        "background_and_gap": "The background and gap need to be stated before details",
        "research_question": "The research question anchors the slide narrative",
        "method_or_model": "The method slide should connect approach to evidence",
        "key_results": "Key results should be shown with source-linked figures",
        "contributions": "Contributions should separate proven claims from interpretation",
        "references": "Source provenance remains visible for review and reuse",
        "limitations_and_outlook": "Limitations and outlook should stay tied to the source",
    }
    claim_by_role = {
        "paper_identity": f"The report is based on {title}.",
        "background_and_gap": "The source paper provides the background and gap for this report.",
        "research_question": "The research question should be extracted and verified from the source.",
        "method_or_model": "The method or model should be summarized from source evidence.",
        "key_results": "The result section should use figure/table evidence rather than unsupported prose.",
        "contributions": "The contribution statement should be checked against the paper's own wording.",
        "references": "References and source provenance are retained for traceability.",
        "limitations_and_outlook": "Limitations and outlook should preserve the paper's caveats.",
    }

    variant_id, content_shape = ROLE_BODY_VARIANTS.get(role, ("flexible_canvas", "text"))
    slide = {
        "page": page,
        "role": role,
        "action_title": action_title_by_role.get(role, role.replace("_", " ").title()),
        "claim": claim_by_role.get(role, f"{role.replace('_', ' ')} is planned from source evidence."),
        "evidence_sources": [
            {
                "source_id": evidence_source,
                "locator": locator,
                "kind": kind,
            }
        ],
        "layout_id": f"{DEFAULT_TEMPLATE_ID}/{variant_id}",
        "content_shape": content_shape,
        "slot_payload": _slot_payload_for_role(role, paper, figures),
        "rhythm": _rhythm_for_role(role),
        "speaker_note": f"Verify and explain the {role.replace('_', ' ')} using the linked source evidence.",
    }
    return slide


def _slot_payload_for_role(
    role: str,
    paper: dict[str, str],
    figures: list[dict[str, str]],
) -> dict[str, str]:
    title = paper["title"]
    first_figure = figures[0] if figures else None
    figure_title = first_figure["title"] if first_figure else "Source figure"
    figure_path = first_figure["path"] if first_figure else ""

    if role == "background_and_gap":
        return {
            "BADGE_1_LABEL": "Situation",
            "BADGE_1_HEADING": "Source context",
            "BADGE_1_BULLETS": f"{title} provides the academic background and problem setting.",
            "BADGE_2_LABEL": "Complication",
            "BADGE_2_HEADING": "Gap to verify",
            "BADGE_2_BULLETS": "Use the paper text to extract the unresolved gap before rendering.",
            "SLOGAN": "Keep the background traceable to the source.",
            "FOOTNOTE": "Draft payload; verify before visual execution.",
        }
    if role == "research_question":
        return {
            "FINDING_LABEL": "Question",
            "FINDING": "The research question anchors the deck narrative.",
            "CONTEXT": "Extract the exact question from the source paper before final rendering.",
            "SOURCE": "paper:main",
            "IMAGE": "",
        }
    if role == "method_or_model":
        return {
            "BLOCK_1_HEADING": "Approach",
            "BLOCK_1_COPY": "Summarize the method from the paper's own terminology.",
            "IMAGE_1": figure_path,
            "BLOCK_2_HEADING": "Evidence link",
            "BLOCK_2_COPY": "Tie each method claim to the declared source map.",
            "IMAGE_2": "",
        }
    if role == "key_results":
        return {
            "FINDING_LABEL": "Result",
            "FINDING": "Key results should be shown with source-linked evidence.",
            "CONTEXT": f"Use {figure_title} as the primary exhibit." if first_figure else "Add figure or table evidence before rendering.",
            "SOURCE": first_figure["id"] if first_figure else "paper:main",
            "IMAGE": figure_path,
        }

    content_by_role = {
        "paper_identity": f"The report is based on {title}; keep title, authors, venue, and source path visible.",
        "contributions": "Separate proven contributions from interpretation, and keep every claim linked to source evidence.",
        "references": "List the main paper and extracted figure/table sources used by the deck.",
        "limitations_and_outlook": "Preserve the paper's caveats, limitations, and outlook without inventing stronger conclusions.",
    }
    return {"CONTENT_BODY": content_by_role.get(role, f"Plan {role.replace('_', ' ')} from source evidence.")}


def _rhythm_for_role(role: str) -> str:
    if role == "paper_identity":
        return "anchor"
    if role in {"contributions", "limitations_and_outlook"}:
        return "breathing"
    return "dense"


def build_paper_report_deck_plan(
    project_dir: Path | str,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    """Return a draft single-paper deck_plan.json from an EasySlides project."""
    project = Path(project_dir).resolve()
    repo = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    sources_dir = project / "sources"
    markdown_files = sorted(sources_dir.glob("*.md")) if sources_dir.is_dir() else []

    paper = _discover_paper(project, markdown_files)
    figures = _discover_figures(project, markdown_files)

    catalog = load_profiles(repo / "references" / "scenario_profiles.json")
    validate_profiles(catalog)
    profile = get_profile("single_paper_report", catalog)
    roles = list(profile["default_story_spine"])
    if "references" not in roles:
        insert_at = roles.index("limitations_and_outlook") if "limitations_and_outlook" in roles else len(roles)
        roles.insert(insert_at, "references")
    slides = [
        _slide_for_role(index, role, paper, figures)
        for index, role in enumerate(roles, start=1)
    ]

    return {
        "schema_version": "easyslides.deck_plan.v1",
        "scenario_profile": "single_paper_report",
        "template_id": DEFAULT_TEMPLATE_ID,
        "paper": {
            "title": paper["title"],
            "source_id": paper["id"],
        },
        "intake": {
            "schema_version": "easyslides.paper_intake.v1",
            "project": str(project),
            "mode": "paper-report intake",
        },
        "source_map": [paper, *figures],
        "slides": slides,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="EasySlides project directory")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root used to resolve references/scenario_profiles.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for deck_plan.json (default: <project_dir>/deck_plan.json)",
    )
    parser.add_argument("--json", action="store_true", help="Print validation report as JSON")
    args = parser.parse_args(argv)

    project = args.project_dir.resolve()
    output = args.output.resolve() if args.output else project / "deck_plan.json"
    plan = build_paper_report_deck_plan(project, repo_root=args.repo_root)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = validate_deck_plan(plan, repo_root=args.repo_root)
    report["output"] = str(output)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Paper intake: {report['status']} ({report['issue_count']} issue(s))")
        print(f"Output: {output}")
        for item in report["issues"]:
            loc = f" [{item['path']}]" if "path" in item else ""
            print(f"- {item['code']}: {item['message']}{loc}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
