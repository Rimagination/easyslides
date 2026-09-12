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
    from scripts.scenario_profiles import (
        duration_page_band,
        get_profile,
        get_scenario_variant,
        load_profiles,
        validate_profiles,
    )
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from deck_plan_contract import validate_deck_plan
    from scenario_profiles import (
        duration_page_band,
        get_profile,
        get_scenario_variant,
        load_profiles,
        validate_profiles,
    )


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
CHAPTER_NUMBER_RE = re.compile(r"^(?:第\s*(\d+)\s*[章节篇]|chapter\s+(\d+))", re.IGNORECASE)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
DEFAULT_TEMPLATE_ID = "academic_scqa"
DEFAULT_DEFENSE_TEMPLATE_ID = "defense_topnav"
DEFAULT_DEFENSE_VARIANT = "cn_degree_defense_v4"
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
VARIANT_FORM_IDS = {
    "flexible_canvas": "evidence_split",
    "three_card_summary": "card_grid",
    "four_quadrant_grid": "pillar_diagram",
    "two_column_compare": "split_compare",
    "process_timeline": "timeline",
    "table_matrix": "comparison_table",
    "figure_with_notes": "evidence_split",
    "figure_left_text_right": "evidence_split",
}
VARIANT_CONTENT_SHAPES = {
    "flexible_canvas": "argument",
    "three_card_summary": "parallel_points",
    "four_quadrant_grid": "four_modules",
    "two_column_compare": "comparison",
    "process_timeline": "workflow",
    "table_matrix": "matrix",
    "figure_with_notes": "figure_explanation",
    "figure_left_text_right": "figure_explanation",
}
ROLE_SOURCE_TERMS = {
    "paper_identity": ("摘要", "abstract", "标题", "title"),
    "background_and_gap": ("背景", "引言", "introduction", "研究现状", "现状"),
    "research_question": ("研究问题", "研究目的", "目的", "question", "objective"),
    "method_or_model": ("方法", "研究设计", "样本", "资料", "method", "design"),
    "key_results": ("结果", "发现", "分析", "result", "finding"),
    "contributions": ("贡献", "创新", "意义", "contribution", "significance"),
    "references": ("参考文献", "references", "bibliography"),
    "limitations_and_outlook": ("局限", "不足", "展望", "建议", "limitation", "outlook"),
    "research_background": ("背景", "引言", "introduction", "background"),
    "research_status": ("研究现状", "文献综述", "综述", "literature", "review"),
    "research_gap": ("研究述评", "研究空白", "研究缺口", "gap", "unresolved"),
    "research_question": ("研究问题", "问题", "question"),
    "research_objectives": ("研究目标", "研究目的", "目标", "目的", "objective"),
    "technical_route": ("技术路线", "研究设计", "研究方法", "方法", "route", "method", "design"),
    "materials_and_methods": ("材料", "资料", "样本", "访谈", "方法", "material", "sample", "interview", "method"),
    "discussion_mechanism": ("机制", "讨论", "影响因素", "mechanism", "discussion"),
    "innovation_points": ("创新", "贡献", "innovation", "contribution"),
    "conclusion": ("结论", "讨论", "展望", "conclusion", "outlook"),
    "ending": ("结论", "展望", "conclusion", "outlook"),
}
DEFENSE_SECTIONS = [
    "研究背景与问题",
    "研究设计与方法",
    "核心结果",
    "综合讨论",
    "结论与展望",
    "参考文献",
]
DEFENSE_ROLE_VARIANTS = {
    "research_background": ("flexible_canvas", "argument"),
    "research_status": ("two_column_compare", "comparison"),
    "research_gap": ("three_card_summary", "parallel_points"),
    "research_question": ("flexible_canvas", "question"),
    "research_objectives": ("four_quadrant_grid", "four_modules"),
    "technical_route": ("process_timeline", "process"),
    "materials_and_methods": ("two_column_compare", "comparison"),
    "key_results": ("figure_with_notes", "figure"),
    "discussion_mechanism": ("figure_left_text_right", "figure_explanation"),
    "innovation_points": ("three_card_summary", "parallel_points"),
    "references": ("table_matrix", "comparison"),
    "conclusion": ("flexible_canvas", "argument"),
    "ending": ("ending", "closing"),
}
NON_CHAPTER_HEADINGS = {
    "摘要",
    "abstract",
    "目录",
    "contents",
    "参考文献",
    "references",
    "致谢",
    "acknowledgements",
    "acknowledgments",
    "附录",
    "appendix",
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


def _markdown_headings(markdown_files: list[Path], project_dir: Path) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for md_path in markdown_files:
        text = md_path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if not match:
                continue
            headings.append(
                {
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                    "path": _relative(md_path, project_dir),
                    "line": line_number,
                }
            )
    return headings


def _clean_source_line(line: str) -> str:
    """Keep source wording while removing Markdown-only presentation syntax."""
    value = IMAGE_RE.sub("", line)
    value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[*_~]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _markdown_sections(
    markdown_files: list[Path],
    project_dir: Path,
) -> list[dict[str, Any]]:
    """Extract source paragraphs under headings for page-level evidence."""
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            current["paragraphs"] = [
                value for value in current.get("paragraphs", []) if value
            ]
            current["bullets"] = [
                value for value in current.get("bullets", []) if value
            ]
            sections.append(current)
        current = None

    for md_path in markdown_files:
        lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(lines, start=1):
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading:
                flush()
                current = {
                    "title": heading.group(2).strip(),
                    "level": len(heading.group(1)),
                    "source": {
                        "path": _relative(md_path, project_dir),
                        "line": line_number,
                    },
                    "paragraphs": [],
                    "bullets": [],
                }
                continue
            if current is None or not line.strip() or line.lstrip().startswith("```"):
                continue
            cleaned = _clean_source_line(line)
            if not cleaned:
                continue
            if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", line):
                current["bullets"].append(cleaned)
            else:
                current["paragraphs"].append(cleaned)
        flush()
    return sections


def _source_blocks_for_role(
    role: str,
    sections: list[dict[str, Any]],
    *,
    offset: int = 0,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Select short, source-located evidence blocks for a slide role."""
    terms = tuple(value.casefold() for value in ROLE_SOURCE_TERMS.get(role, ()))
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, section in enumerate(sections):
        title = str(section.get("title") or "")
        body_count = len(section.get("paragraphs") or []) + len(section.get("bullets") or [])
        if body_count == 0:
            continue
        title_folded = title.casefold()
        score = sum(5 if term == title_folded else 2 for term in terms if term in title_folded)
        if score:
            score += 1 if body_count > 1 else 0
        ranked.append((score, index, section))

    ranked.sort(key=lambda row: (-row[0], abs(row[1] - offset), row[1]))
    selected = [row[2] for row in ranked[:2] if row[0] > 0]
    if not selected:
        fallback = [
            section
            for section in sections
            if len(section.get("paragraphs") or []) + len(section.get("bullets") or []) > 0
        ]
        selected = fallback[offset : offset + 2] or fallback[:2]

    blocks: list[dict[str, Any]] = []
    for section in selected:
        texts = list(section.get("bullets") or []) + list(section.get("paragraphs") or [])
        for text in texts[:2]:
            blocks.append(
                {
                    "label": str(section.get("title") or "来源材料"),
                    "text": text[:240].rstrip(),
                    "source_id": "paper:main",
                    "locator": f"{section['source']['path']}:{section['source']['line']}",
                }
            )
            if len(blocks) >= limit:
                return blocks
    return blocks


def _content_quality(
    *,
    conclusion: str,
    explanation: str,
    evidence_blocks: list[dict[str, Any]],
    figure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_count = len(evidence_blocks) + (1 if figure else 0)
    evidence_text = " ".join(str(item.get("text") or "") for item in evidence_blocks)
    source_text_chars = len(evidence_text.strip())
    text_chars = len(" ".join((conclusion, explanation, evidence_text)).strip())
    material_types = ["text"] if evidence_blocks else []
    if figure:
        material_types.append("figure")
    has_rich_source = bool(figure) or source_text_chars >= 80
    score = sum(
        (
            bool(conclusion),
            evidence_count > 0,
            bool(explanation.strip()),
            has_rich_source,
        )
    )
    status = "adequate" if evidence_count > 0 and has_rich_source else "thin" if evidence_count > 0 else "placeholder"
    return {
        "status": status,
        "score": score,
        "text_chars": text_chars,
        "source_text_chars": source_text_chars,
        "evidence_count": evidence_count,
        "material_count": len(material_types),
        "material_types": material_types,
        "reason": (
            "source-backed content with a declared conclusion, evidence, and explanation"
            if status == "adequate"
            else "source material is too short for a content-rich page"
            if status == "thin"
            else "no source paragraph, figure, table, or data is available for this page"
        ),
    }


def _content_contract(
    *,
    conclusion: str,
    explanation: str,
    evidence_blocks: list[dict[str, Any]],
    figure: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = _content_quality(
        conclusion=conclusion,
        explanation=explanation,
        evidence_blocks=evidence_blocks,
        figure=figure,
    )
    evidence = [dict(item) for item in evidence_blocks]
    if figure:
        evidence.append(
            {
                "label": str(figure.get("title") or "原始图件"),
                "text": str(figure.get("caption") or figure.get("title") or ""),
                "source_id": str(figure.get("id") or ""),
                "locator": str(figure.get("title") or figure.get("id") or "figure"),
            }
        )
    return (
        {
            "conclusion": conclusion,
            "evidence": evidence,
            "explanation": explanation,
            "status": quality["status"],
        },
        quality,
    )


def _source_text(blocks: list[dict[str, Any]], fallback: str) -> str:
    text = "；".join(str(item.get("text") or "").strip() for item in blocks if item.get("text"))
    return text or fallback


def _first_heading(markdown_files: list[Path]) -> str | None:
    for md_path in markdown_files:
        text = md_path.read_text(encoding="utf-8", errors="replace")
        match = HEADING_RE.search(text)
        if match:
            return match.group(2).strip()
    return None


def _is_non_chapter_heading(title: str) -> bool:
    normalized = re.sub(r"[\s:：\-—_]+", "", title).strip().lower()
    if normalized in {re.sub(r"[\s:：\-—_]+", "", value).lower() for value in NON_CHAPTER_HEADINGS}:
        return True
    return bool(re.match(r"^(摘要|abstract|目录|contents|参考文献|references|致谢|acknowledg|附录|appendix)", normalized))


def _chapter_id(title: str, index: int) -> str:
    match = CHAPTER_NUMBER_RE.match(title.strip())
    if match:
        number = match.group(1) or match.group(2)
        return f"chapter_{int(number):02d}"
    return f"chapter_{index:02d}"


def _chapter_hierarchy(
    markdown_files: list[Path],
    project_dir: Path,
) -> dict[str, Any]:
    """Infer thesis-level chapters while retaining source heading locations."""
    headings = _markdown_headings(markdown_files, project_dir)
    if len(headings) <= 1:
        return {"heading_level": None, "chapters": []}

    body_headings = headings[1:]
    numbered = [
        heading
        for heading in body_headings
        if CHAPTER_NUMBER_RE.match(str(heading.get("title") or ""))
    ]
    candidates = numbered or [
        heading
        for heading in body_headings
        if not _is_non_chapter_heading(str(heading.get("title") or ""))
    ]
    if not candidates:
        return {"heading_level": None, "chapters": []}

    chapter_level = min(int(heading["level"]) for heading in candidates)
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for heading in body_headings:
        title = str(heading.get("title") or "").strip()
        level = int(heading.get("level") or 0)
        if not title or _is_non_chapter_heading(title):
            if level <= chapter_level:
                current = None
            continue
        if level == chapter_level:
            current = {
                "id": _chapter_id(title, len(chapters) + 1),
                "title": title,
                "level": level,
                "source": {
                    "path": heading["path"],
                    "line": heading["line"],
                },
                "subsections": [],
            }
            chapters.append(current)
        elif current is not None and level > chapter_level:
            current["subsections"].append(
                {
                    "title": title,
                    "level": level,
                    "source": {
                        "path": heading["path"],
                        "line": heading["line"],
                    },
                }
            )
    return {"heading_level": chapter_level, "chapters": chapters}


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


def _markdown_image_refs(markdown_files: list[Path], project_dir: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
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


def _manifest_figures(project_dir: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
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
                        "caption": str(item.get("caption") or ""),
                        "page": item.get("page"),
                    }
                )
    return refs


def _image_dir_figures(project_dir: Path) -> list[dict[str, Any]]:
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


def _figure_class(title: str, index: int) -> str:
    value = title.casefold()
    if any(token in value for token in ("result", "finding", "outcome", "main", "key", "结果", "发现", "结论")):
        return "A"
    if any(token in value for token in ("method", "route", "workflow", "mechan", "model", "方法", "技术路线", "机制", "模型")):
        return "B"
    if any(token in value for token in ("support", "supplement", "control", "character", "table", "补充", "对照", "表")):
        return "C"
    return "A" if index == 1 else "D"


def _image_quality(path: Path, figure_class: str) -> dict[str, Any]:
    if not path.is_file():
        return {
            "status": "missing",
            "width": None,
            "height": None,
            "needs_high_res": figure_class == "A",
            "reason": "source image is missing",
        }
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
    except (ImportError, OSError, ValueError):
        return {
            "status": "needs_review",
            "width": None,
            "height": None,
            "needs_high_res": figure_class == "A",
            "reason": "image dimensions could not be inspected",
        }

    needs_high_res = figure_class == "A" and (width < 1200 or height < 700)
    return {
        "status": "needs_high_res" if needs_high_res else "usable",
        "width": width,
        "height": height,
        "needs_high_res": needs_high_res,
        "reason": "A-class evidence figure is below the intake resolution floor"
        if needs_high_res
        else "",
    }


def _discover_figures(project_dir: Path, markdown_files: list[Path]) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for ref in (
        _markdown_image_refs(markdown_files, project_dir)
        + _manifest_figures(project_dir)
        + _image_dir_figures(project_dir)
    ):
        path = ref["path"].replace("\\", "/")
        if Path(path).suffix.lower() not in IMAGE_SUFFIXES:
            continue
        current = by_path.setdefault(path, {"path": path, "title": ref["title"]})
        if current.get("title") == Path(path).stem.replace("_", " ") and ref.get("title"):
            current["title"] = ref["title"]
        if ref.get("caption") and not current.get("caption"):
            current["caption"] = ref["caption"]
        if ref.get("page") is not None and current.get("page") is None:
            current["page"] = ref["page"]
    figures: list[dict[str, Any]] = []
    for index, ref in enumerate(by_path.values(), start=1):
        figure_class = _figure_class(str(ref["title"]), index)
        figure_path = project_dir / ref["path"]
        figures.append(
            {
                "id": f"fig:{index}",
                "type": "figure",
                "path": ref["path"],
                "title": ref["title"],
                "parent_source": "paper:main",
                "figure_class": figure_class,
                "caption": str(ref.get("caption") or ref["title"]),
                "page": ref.get("page"),
                "quality": _image_quality(figure_path, figure_class),
            }
        )
    return figures


def _slide_for_role(
    index: int,
    role: str,
    paper: dict[str, str],
    figures: list[dict[str, str]],
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
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

    first_figure = figures[0] if role == "key_results" and figures else None
    evidence_blocks = _source_blocks_for_role(role, sections, offset=index - 1)
    content_contract, content_quality = _content_contract(
        conclusion=action_title_by_role.get(role, role.replace("_", " ").title()),
        explanation=claim_by_role.get(role, f"{role.replace('_', ' ')} is planned from source evidence."),
        evidence_blocks=evidence_blocks,
        figure=first_figure,
    )
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
            },
            *[
                {
                    "source_id": str(block["source_id"]),
                    "locator": str(block["locator"]),
                    "kind": "paper_section",
                }
                for block in evidence_blocks
            ],
        ],
        "layout_id": f"{DEFAULT_TEMPLATE_ID}/{variant_id}",
        "content_shape": content_shape,
        "slot_payload": _slot_payload_for_role(
            role,
            paper,
            figures,
            evidence_blocks=evidence_blocks,
            content_contract=content_contract,
        ),
        "content_contract": content_contract,
        "content_quality": content_quality,
        "item_count": max(1, len(evidence_blocks)),
        "preferred_form": VARIANT_FORM_IDS.get(variant_id, "statement"),
        "material_types": content_quality["material_types"],
        "rhythm": _rhythm_for_role(role),
        "speaker_note": f"Verify and explain the {role.replace('_', ' ')} using the linked source evidence.",
    }
    return slide


def _slot_payload_for_role(
    role: str,
    paper: dict[str, str],
    figures: list[dict[str, str]],
    *,
    evidence_blocks: list[dict[str, Any]] | None = None,
    content_contract: dict[str, Any] | None = None,
) -> dict[str, str]:
    title = paper["title"]
    first_figure = figures[0] if figures else None
    figure_title = first_figure["title"] if first_figure else "Source figure"
    figure_path = first_figure["path"] if first_figure else ""

    evidence_blocks = evidence_blocks or []
    contract = content_contract or {}
    explanation = str(contract.get("explanation") or "")
    evidence_text = _source_text(evidence_blocks, "请从来源材料中补入可核对的段落或图表说明。")

    if role == "background_and_gap":
        return {
            "BADGE_1_LABEL": "Situation",
            "BADGE_1_HEADING": "Source context",
            "BADGE_1_BULLETS": evidence_text,
            "BADGE_2_LABEL": "Complication",
            "BADGE_2_HEADING": "Gap to verify",
            "BADGE_2_BULLETS": explanation,
            "SLOGAN": "结论、证据与解释保持同一来源边界。",
            "FOOTNOTE": "来源段落由 intake 提取；最终执行前复核原文。",
        }
    if role == "research_question":
        return {
            "FINDING_LABEL": "Question",
            "FINDING": evidence_blocks[0]["text"] if evidence_blocks else "待从来源中确认研究问题。",
            "CONTEXT": evidence_text,
            "SOURCE": "paper:main",
            "IMAGE": "",
        }
    if role == "method_or_model":
        return {
            "BLOCK_1_HEADING": "Approach",
            "BLOCK_1_COPY": evidence_text,
            "IMAGE_1": figure_path,
            "BLOCK_2_HEADING": "Evidence link",
            "BLOCK_2_COPY": explanation,
            "IMAGE_2": "",
        }
    if role == "key_results":
        return {
            "FINDING_LABEL": "Result",
            "FINDING": evidence_blocks[0]["text"] if evidence_blocks else "待从来源中确认结果表述。",
            "CONTEXT": evidence_text if evidence_blocks else f"使用 {figure_title} 作为主要图件。" if first_figure else "补入图表或数据证据后再执行。",
            "SOURCE": first_figure["id"] if first_figure else "paper:main",
            "IMAGE": figure_path,
        }

    content_by_role = {
        "paper_identity": f"The report is based on {title}; keep title, authors, venue, and source path visible.",
        "contributions": "Separate proven contributions from interpretation, and keep every claim linked to source evidence.",
        "references": "List the main paper and extracted figure/table sources used by the deck.",
        "limitations_and_outlook": "Preserve the paper's caveats, limitations, and outlook without inventing stronger conclusions.",
    }
    return {
        "CONTENT_BODY": evidence_text
        if evidence_blocks
        else content_by_role.get(role, f"Plan {role.replace('_', ' ')} from source evidence.")
    }


def _rhythm_for_role(role: str) -> str:
    if role == "paper_identity":
        return "anchor"
    if role in {"contributions", "limitations_and_outlook"}:
        return "breathing"
    return "dense"


def _defense_slot_payload(
    variant_id: str,
    role: str,
    paper: dict[str, str],
    figure: dict[str, Any] | None = None,
    *,
    evidence_blocks: list[dict[str, Any]] | None = None,
    content_contract: dict[str, Any] | None = None,
) -> dict[str, str]:
    figure_title = str((figure or {}).get("title") or "原始图件")
    figure_path = str((figure or {}).get("path") or "")
    evidence_blocks = evidence_blocks or []
    contract = content_contract or {}
    conclusion = str(contract.get("conclusion") or "")
    explanation = str(contract.get("explanation") or "")
    evidence_text = _source_text(evidence_blocks, "待补入来源段落、图表或数据证据。")
    body_copy = {
        "research_background": "交代研究背景、现实需求与论文要解决的对象。",
        "research_status": "用来源中的研究现状说明已有认识与仍待解决的部分。",
        "research_gap": "将研究空白压缩为可验证的问题与判断标准。",
        "research_question": "明确一个可由后续方法和证据回答的研究问题。",
        "research_objectives": "把研究问题拆解为相互衔接的研究目标。",
        "materials_and_methods": "说明材料、样本和方法如何支撑后续结果判断。",
        "discussion_mechanism": "把结果模式与讨论中的机制解释放在同一证据边界内。",
        "conclusion": "用来源中的结论回答研究问题，并保留结论边界。",
        "references": "列出论文与实际使用的图表来源，便于复核。",
    }.get(role, f"从来源材料中核对{role.replace('_', ' ')}的可见内容。")

    if variant_id == "flexible_canvas":
        return {
            "CONTENT_BODY": "\n".join(
                part
                for part in (
                    f"结论：{conclusion}" if conclusion else "",
                    f"证据：{evidence_text}" if evidence_text else "",
                    f"解释：{explanation}" if explanation else "",
                )
                if part
            )
            or body_copy
        }
    if variant_id == "three_card_summary":
        cards = evidence_blocks[:3]
        return {
            **{
                key: value
                for index, item in enumerate(cards, start=1)
                for key, value in (
                    (f"CARD_{index}_TITLE", str(item.get("label") or f"证据 {index}")),
                    (f"CARD_{index}_BODY", str(item.get("text") or "待补充来源内容。")),
                )
            },
            **{
                key: value
                for index in range(len(cards) + 1, 4)
                for key, value in (
                    (f"CARD_{index}_TITLE", "待确认"),
                    (f"CARD_{index}_BODY", "补入同一研究问题下的来源证据。"),
                )
            },
        }
    if variant_id == "figure_with_notes" and figure_path:
        return {}
    return {}


def _defense_shell_payload(
    index: int,
    role: str,
    paper: dict[str, str],
    *,
    section: str,
    chapter: dict[str, Any] | None = None,
    action_title: str = "",
) -> dict[str, str]:
    title = paper["title"]
    if role == "cover":
        return {
            "TITLE": title,
            "SUBTITLE": "硕博士学位论文答辩",
            "PRESENTER": "汇报人：待补充",
            "ADVISOR": "指导教师：待补充",
            "DATE": "时间：待补充",
        }
    if role == "toc":
        return {
            f"SECTION_{item_index}": label
            for item_index, label in enumerate(DEFENSE_SECTIONS, start=1)
        }
    if role == "chapter":
        chapter = chapter or {}
        return {
            "CHAPTER_NUM": str(chapter.get("number") or "01"),
            "CHAPTER_TITLE": str(chapter.get("title") or "核心结果"),
            "CHAPTER_DESC": "围绕一个科学问题组织原始证据。",
        }
    if role == "ending":
        return {
            "CLOSING_TITLE": "请老师同学们批评指正！谢谢！",
            "CLOSING_SUBTITLE": "汇报结束",
            "PRESENTER": "汇报人：待补充",
            "ADVISOR": "指导教师：待补充",
            "CONTACT": "专业：待补充",
        }
    return {
        "ACTIVE_SECTION_LABEL": section,
        "PAGE_TITLE": action_title or title,
        "KEY_MESSAGE": action_title or "本页结论由来源证据支撑。",
        "PAGE_NUM": f"{index:02d}",
    }


def _defense_variant_for_role(
    role: str,
    evidence_blocks: list[dict[str, Any]],
    *,
    figure: dict[str, Any] | None = None,
    chapter_index: int = 0,
) -> tuple[str, str]:
    """Select a composition from evidence shape, with a safe thin-source fallback."""
    if figure:
        variants = ("figure_with_notes", "figure_left_text_right")
        variant = variants[chapter_index % len(variants)]
        return variant, VARIANT_CONTENT_SHAPES[variant]

    preferred = {
        "research_background": "flexible_canvas",
        "research_status": "two_column_compare",
        "research_gap": "three_card_summary",
        "research_question": "flexible_canvas",
        "research_objectives": "four_quadrant_grid",
        "technical_route": "process_timeline",
        "materials_and_methods": "two_column_compare",
        "discussion_mechanism": "flexible_canvas",
        "innovation_points": "three_card_summary",
        "references": "table_matrix",
        "conclusion": "flexible_canvas",
    }.get(role, "flexible_canvas")

    required_items = {
        "three_card_summary": 3,
        "four_quadrant_grid": 4,
        "two_column_compare": 2,
        "process_timeline": 3,
        "table_matrix": 3,
    }.get(preferred, 1)
    if len(evidence_blocks) < required_items:
        preferred = "flexible_canvas"
    return preferred, VARIANT_CONTENT_SHAPES.get(preferred, "argument")


def _defense_slide(
    index: int,
    role: str,
    paper: dict[str, str],
    *,
    section: str,
    variant_id: str | None = None,
    content_shape: str | None = None,
    chapter: dict[str, Any] | None = None,
    figure: dict[str, Any] | None = None,
    evidence_blocks: list[dict[str, Any]] | None = None,
    chapter_index: int = 0,
    placeholder: bool = False,
) -> dict[str, Any]:
    chapter_title = str((chapter or {}).get("title") or "")
    figure_title = str((figure or {}).get("title") or "")
    if role == "cover":
        action_title = f"{paper['title']} is organized as an evidence-led defense"
        claim = f"The defense is based on {paper['title']}."
    elif role == "toc":
        action_title = "The defense follows the thesis chapters and evidence chain"
        claim = "The page sequence moves from the research problem to the conclusion."
    elif role == "chapter":
        action_title = f"{chapter_title or 'This chapter'} organizes one part of the evidence chain"
        claim = f"{chapter_title or 'The chapter'} is retained from the thesis structure."
    elif role == "key_results" and figure:
        action_title = f"{figure_title} provides evidence for the chapter conclusion"
        claim = f"{figure_title} is retained as source-linked evidence."
    elif role == "results_placeholder":
        action_title = f"{chapter_title or 'The chapter'} result awaits confirmation from original figures"
        claim = "The result page remains a placeholder until source evidence is available."
    else:
        action_titles = {
            "research_background": "The research problem is established before methods and results",
            "research_status": "The literature status narrows the unresolved research space",
            "research_gap": "The research gap is stated as a testable question",
            "research_question": "The thesis question defines the evidence required for the conclusion",
            "research_objectives": "The study objectives translate the question into executable work",
            "technical_route": "The technical route links materials, methods, and result claims",
            "materials_and_methods": "The selected methods make the planned claims auditable",
            "discussion_mechanism": "The discussion connects the result pattern with the proposed mechanism",
            "innovation_points": "The claimed innovation is limited to contributions supported by results",
            "references": "All borrowed figures and claims retain source provenance",
            "conclusion": "The conclusion answers the research question within the evidence boundary",
            "ending": "The defense closes after the conclusion and outlook",
        }
        action_title = action_titles.get(role, f"{role.replace('_', ' ').title()} is tied to source evidence")
        claim = action_title + "."

    evidence_blocks = evidence_blocks or []
    selected_variant, selected_shape = _defense_variant_for_role(
        role,
        evidence_blocks,
        figure=figure,
        chapter_index=chapter_index,
    )
    selected_variant = variant_id or selected_variant
    selected_shape = content_shape or VARIANT_CONTENT_SHAPES.get(selected_variant, selected_shape)
    content_contract, content_quality = _content_contract(
        conclusion=action_title,
        explanation=claim,
        evidence_blocks=evidence_blocks,
        figure=figure,
    )
    page_role = role if role in {"cover", "toc", "chapter", "ending"} else role
    evidence_source = "paper:main"
    evidence_kind = "paper_section"
    locator = role.replace("_", " ")
    if figure:
        evidence_source = str(figure["id"])
        evidence_kind = "figure"
        locator = figure_title
    elif role == "references":
        evidence_kind = "reference"
        locator = "references"

    slide: dict[str, Any] = {
        "page": f"P{index:02d}",
        "role": page_role,
        "action_title": action_title,
        "claim": claim,
        "evidence_sources": [
            {
                "source_id": evidence_source,
                "locator": locator,
                "kind": evidence_kind,
            }
        ],
        "layout_id": (
            f"{DEFAULT_DEFENSE_TEMPLATE_ID}/{selected_variant}"
            if role not in {"cover", "toc", "chapter", "ending"}
            else f"{DEFAULT_DEFENSE_TEMPLATE_ID}/{role}"
        ),
        "content_shape": selected_shape,
        "slot_payload": (
            _defense_slot_payload(
                selected_variant,
                role,
                paper,
                figure,
                evidence_blocks=evidence_blocks,
                content_contract=content_contract,
            )
            if role not in {"cover", "toc", "chapter", "ending"}
            else _defense_shell_payload(
                index,
                role,
                paper,
                section=section,
                chapter=chapter,
                action_title=action_title,
            )
        ),
        "shell_payload": _defense_shell_payload(
            index,
            role,
            paper,
            section=section,
            chapter=chapter,
            action_title=action_title,
        ),
        "rhythm": "anchor" if role in {"cover", "toc", "chapter", "ending"} else _rhythm_for_role(role),
        "speaker_note": f"Use the linked source evidence to explain {role.replace('_', ' ')}.",
        "defense_section": section,
        "placeholder": placeholder,
        "content_contract": content_contract,
        "content_quality": content_quality,
        "item_count": max(1, len(evidence_blocks)),
        "preferred_form": VARIANT_FORM_IDS.get(selected_variant, "statement"),
        "material_types": content_quality["material_types"],
    }
    slide["evidence_sources"].extend(
        {
            "source_id": str(block["source_id"]),
            "locator": str(block["locator"]),
            "kind": "paper_section",
        }
        for block in evidence_blocks
    )
    if chapter:
        slide["chapter_id"] = str(chapter.get("id") or "")
        slide["chapter_title"] = chapter_title
    if figure:
        slide["figure_id"] = str(figure["id"])
    return slide


def _build_thesis_defense_slides(
    paper: dict[str, str],
    figures: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    slides.append(_defense_slide(1, "cover", paper, section=DEFENSE_SECTIONS[0]))
    slides.append(_defense_slide(2, "toc", paper, section=DEFENSE_SECTIONS[0]))

    intro_roles = (
        "research_background",
        "research_status",
        "research_gap",
        "research_question",
        "research_objectives",
    )
    for role_index, role in enumerate(intro_roles):
        slides.append(
            _defense_slide(
                len(slides) + 1,
                role,
                paper,
                section=DEFENSE_SECTIONS[0],
                evidence_blocks=_source_blocks_for_role(role, sections, offset=role_index),
            )
        )

    for role_index, (role, section) in enumerate(
        (
            ("technical_route", DEFENSE_SECTIONS[1]),
            ("materials_and_methods", DEFENSE_SECTIONS[1]),
        )
    ):
        slides.append(
            _defense_slide(
                len(slides) + 1,
                role,
                paper,
                section=section,
                evidence_blocks=_source_blocks_for_role("method_or_model", sections, offset=role_index),
            )
        )

    chapter_rows = chapters or [
        {
            "id": "chapter_main",
            "title": "核心结果（待确认）",
            "number": "01",
            "source_derived": False,
            "subsections": [],
        }
    ]
    for chapter_index, chapter in enumerate(chapter_rows, start=1):
        chapter = dict(chapter)
        chapter.setdefault("number", f"{chapter_index:02d}")
        slides.append(
            _defense_slide(
                len(slides) + 1,
                "chapter",
                paper,
                section=DEFENSE_SECTIONS[2],
                chapter=chapter,
                evidence_blocks=_source_blocks_for_role("key_results", sections, offset=chapter_index - 1),
                chapter_index=chapter_index - 1,
            )
        )
        chapter_figures = figures[chapter_index - 1 : chapter_index] if figures else []
        if chapter_figures:
            slides.append(
                _defense_slide(
                    len(slides) + 1,
                    "key_results",
                    paper,
                    section=DEFENSE_SECTIONS[2],
                    chapter=chapter,
                    figure=chapter_figures[0],
                    evidence_blocks=_source_blocks_for_role("key_results", sections, offset=chapter_index - 1),
                    chapter_index=chapter_index - 1,
                )
            )
        else:
            slides.append(
                _defense_slide(
                    len(slides) + 1,
                    "results_placeholder",
                    paper,
                    section=DEFENSE_SECTIONS[2],
                    chapter=chapter,
                    evidence_blocks=_source_blocks_for_role("key_results", sections, offset=chapter_index - 1),
                    placeholder=True,
                )
            )

    for role_index, (role, section) in enumerate(
        (
            ("discussion_mechanism", DEFENSE_SECTIONS[3]),
            ("innovation_points", DEFENSE_SECTIONS[2]),
            ("references", DEFENSE_SECTIONS[5]),
            ("conclusion", DEFENSE_SECTIONS[4]),
            ("ending", DEFENSE_SECTIONS[4]),
        )
    ):
        slides.append(
            _defense_slide(
                len(slides) + 1,
                role,
                paper,
                section=section,
                evidence_blocks=_source_blocks_for_role(role, sections, offset=role_index),
            )
        )
    return slides


def build_paper_report_deck_plan(
    project_dir: Path | str,
    *,
    repo_root: Path | str | None = None,
    scenario_profile: str = "single_paper_report",
    scenario_variant: str | None = None,
    duration_minutes: int | None = None,
    page_count: int | None = None,
    visual_exploration: bool = False,
) -> dict[str, Any]:
    """Return a draft single-paper deck_plan.json from an EasySlides project."""
    project = Path(project_dir).resolve()
    repo = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    sources_dir = project / "sources"
    markdown_files = sorted(sources_dir.glob("*.md")) if sources_dir.is_dir() else []

    paper = _discover_paper(project, markdown_files)
    figures = _discover_figures(project, markdown_files)
    sections = _markdown_sections(markdown_files, project)

    catalog = load_profiles(repo / "references" / "scenario_profiles.json")
    validate_profiles(catalog)
    profile = get_profile(scenario_profile, catalog)
    if scenario_profile == "thesis_defense":
        selected_variant = str(
            scenario_variant
            or profile.get("default_scenario_variant")
            or DEFAULT_DEFENSE_VARIANT
        )
        variant = get_scenario_variant(scenario_profile, selected_variant, catalog)
        hierarchy = _chapter_hierarchy(markdown_files, project)
        chapters = hierarchy["chapters"]
        slides = _build_thesis_defense_slides(paper, figures, chapters, sections)
        band = duration_page_band(
            scenario_profile,
            duration_minutes,
            variant_id=selected_variant,
            catalog=catalog,
        ) if duration_minutes is not None else None
        page_budget: dict[str, Any] = {
            "mode": "duration_band" if band else "source_adaptive",
            "policy": variant["page_budget_policy"],
            "min": band["min_pages"] if band else profile["typical_slide_count"]["min"],
            "max": band["max_pages"] if band else profile["typical_slide_count"]["max"],
            "draft_page_count": len(slides),
        }
        if band:
            page_budget["duration_band"] = band["label"]
        if duration_minutes is not None:
            page_budget["duration_minutes"] = duration_minutes
        if page_count is not None:
            page_budget["requested_page_count"] = page_count
            page_budget["mode"] = "user_declared_page_count"
            page_budget["min"] = page_count
            page_budget["max"] = page_count
        stages = list(variant["workflow_stages"])
        if visual_exploration:
            stages.insert(1, "visual_exploration")
        return {
            "schema_version": "easyslides.deck_plan.v1",
            "scenario_profile": scenario_profile,
            "scenario_variant": selected_variant,
            "template_id": DEFAULT_DEFENSE_TEMPLATE_ID,
            "palette_id": variant["style_profile"]["palette_id"],
            "typography_profile": variant["style_profile"]["id"],
            "paper": {
                "title": paper["title"],
                "source_id": paper["id"],
            },
            "intake": {
                "schema_version": "easyslides.paper_intake.v2",
                "project": str(project),
                "mode": "thesis-defense intake",
                "workflow_stages": stages,
                "visual_exploration": visual_exploration,
                "visual_exploration_source_of_truth": variant["visual_exploration"]["source_of_truth"],
            },
            "defense": {
                "rules_ref": "references/scenario_profiles.json#profiles.thesis_defense.scenario_variants.cn_degree_defense_v4",
                "chapter_heading_level": hierarchy["heading_level"],
                "chapters": chapters,
                "toc_sections": list(DEFENSE_SECTIONS),
                "intro_min_pages": variant["intro_policy"]["min_pages"],
                "section_weights": variant["section_weights"],
                "figure_index": [figure["id"] for figure in figures],
                "page_budget": page_budget,
                "style_profile": variant["style_profile"],
                "content_quality_policy": variant.get("content_quality_policy", {}),
                "placeholder_pages": [
                    slide["page"]
                    for slide in slides
                    if slide.get("placeholder") is True
                ],
            },
            "source_map": [paper, *figures],
            "slides": slides,
        }

    roles = list(profile["default_story_spine"])
    if "references" not in roles:
        insert_at = roles.index("limitations_and_outlook") if "limitations_and_outlook" in roles else len(roles)
        roles.insert(insert_at, "references")
    slides = [
        _slide_for_role(index, role, paper, figures, sections)
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
    parser.add_argument(
        "--scenario-profile",
        choices=("single_paper_report", "thesis_defense"),
        default="single_paper_report",
        help="Intake profile; thesis_defense enables the Chinese defense v4 contract.",
    )
    parser.add_argument("--scenario-variant", help="Declared scenario variant for the selected profile.")
    parser.add_argument("--duration-minutes", type=int, help="Presentation duration used for the defense page band.")
    parser.add_argument("--page-count", type=int, help="User-declared page target recorded for later planning.")
    parser.add_argument(
        "--visual-exploration",
        action="store_true",
        help="Opt into the v3.9-style visual exploration stage before editable production.",
    )
    parser.add_argument("--json", action="store_true", help="Print validation report as JSON")
    args = parser.parse_args(argv)

    project = args.project_dir.resolve()
    output = args.output.resolve() if args.output else project / "deck_plan.json"
    if args.duration_minutes is not None and args.duration_minutes <= 0:
        parser.error("--duration-minutes must be positive")
    if args.page_count is not None and args.page_count <= 0:
        parser.error("--page-count must be positive")
    plan = build_paper_report_deck_plan(
        project,
        repo_root=args.repo_root,
        scenario_profile=args.scenario_profile,
        scenario_variant=args.scenario_variant,
        duration_minutes=args.duration_minutes,
        page_count=args.page_count,
        visual_exploration=args.visual_exploration,
    )
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
