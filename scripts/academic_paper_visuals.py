"""Select decorative images for the default native academic template.

The classifier is deliberately a small, inspectable keyword matcher. Its
result is a presentation-visual suggestion, not an official degree decision.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class VisualSelectionError(ValueError):
    """The template's image catalogue or an explicit discipline is invalid."""


def _text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return str(value).strip() if value is not None else ""


def _matches(term: str, text: str) -> bool:
    term = term.casefold().strip()
    if not term:
        return False
    if re.search(r"[\u3400-\u9fff]", term):
        return term in text
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


def _scores(text: str, keywords: dict[str, list[str]]) -> tuple[dict[str, int], dict[str, list[str]]]:
    text = text.casefold()
    scores: dict[str, int] = {}
    matches: dict[str, list[str]] = {}
    for code, words in keywords.items():
        hits = [word for word in dict.fromkeys(words) if _matches(word, text)]
        if hits:
            # Distinctive longer phrases outweigh incidental short substrings,
            # such as 农业 in 农业工程 or 医学 in 生物医学工程.
            scores[code] = sum(min(len(word), 8) for word in hits)
            matches[code] = hits
    return scores, matches


def _rank(scores: dict[str, int]) -> str | None:
    ranked = sorted(scores, key=lambda code: (-scores[code], code))
    if not ranked:
        return None
    if len(ranked) > 1 and scores[ranked[0]] - scores[ranked[1]] < 2:
        return None
    return ranked[0]


def _topic_text(plan: dict[str, Any], slides: list[dict[str, Any]]) -> str:
    values: list[str] = []
    for key in ("topic", "title", "deck_title", "paper_title", "research_field", "research_area"):
        values.append(_text(plan.get(key)))
    brief = plan.get("academic_brief")
    if isinstance(brief, dict):
        values.extend(_text(brief.get(key)) for key in ("topic", "academic_goal", "research_field"))
    for slide in slides:
        if str(slide.get("role") or "").lower() != "cover":
            continue
        payload = slide.get("slot_payload") or {}
        if isinstance(payload, dict):
            values.extend(_text(payload.get(key)) for key in ("TITLE", "SUBTITLE", "RESEARCH_FIELD"))
    sources = plan.get("source_map")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and not source.get("parent_source"):
                values.append(_text(source.get("title")))
    return "\n".join(value for value in values if value)


def _body_text(slides: list[dict[str, Any]]) -> str:
    """Use report content as a fallback when the cover is generic."""
    values: list[str] = []
    for slide in slides:
        if str(slide.get("role") or "").lower() == "cover":
            continue
        values.extend(_text(slide.get(key)) for key in ("action_title", "claim"))
        payload = slide.get("slot_payload") or {}
        if isinstance(payload, dict):
            values.extend(_text(payload.get(key)) for key in (
                "PAGE_TITLE", "CHAPTER_TITLE", "KEY_MESSAGE", "TAKEAWAY",
                "BACKGROUND_LINE1", "BACKGROUND_LINE2", "BACKGROUND_LINE3", "CONTENT_BODY",
            ))
    return "\n".join(value for value in values if value)[:50000]


def _catalogue_path(template_root: Path, catalogue: Path, filename: str) -> Path:
    path = (catalogue.parent / filename).resolve()
    try:
        path.relative_to(template_root.resolve())
    except ValueError as exc:
        raise VisualSelectionError(f"catalogue asset escapes template directory: {filename}") from exc
    if not path.is_file():
        raise VisualSelectionError(f"catalogue asset is missing: {filename}")
    return path


def select_discipline_image(template_root: Path, plan: dict[str, Any], slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve one discipline and topic-matched image for cover and contents.

    Explicit category names/codes take precedence. Unsupported or tied topic
    hints return a reviewable unresolved result instead of inventing a match.
    """
    catalogue = template_root / "cover_banners" / "manifest.json"
    data = json.loads(catalogue.read_text(encoding="utf-8-sig"))
    entries = {str(row["discipline_code"]): row for row in data["assets"]}
    keywords = data.get("classification", {}).get("keywords", {})
    context = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    brief = plan.get("academic_brief") if isinstance(plan.get("academic_brief"), dict) else {}

    explicit: list[tuple[str, str]] = []
    for key in ("discipline_code", "discipline_category", "discipline", "subject_category"):
        for source in (plan, context, brief):
            value = _text(source.get(key))
            if value:
                explicit.append((key, value))

    code = None
    matched: list[str] = []
    for key, value in explicit:
        normalized = value.casefold().strip()
        digit_match = re.fullmatch(r"(\d{2})(?:\d{2}(?:\d{2})?)?", normalized)
        explicit_code = digit_match.group(1) if digit_match else next(
            (item for item, row in entries.items() if normalized == row["discipline"].casefold()), None
        )
        if explicit_code and explicit_code not in entries:
            raise VisualSelectionError(f"unknown discipline code: {value}")
        if key == "discipline_code" and not explicit_code:
            raise VisualSelectionError(f"invalid discipline code: {value}")
        if explicit_code:
            if code and code != explicit_code:
                raise VisualSelectionError("conflicting explicit discipline categories")
            code = explicit_code
            matched.append(value)

    topic = _topic_text(plan, slides)
    body = _body_text(slides)
    method = "explicit_category" if code else "topic_keywords"
    if not code:
        # A named major or discipline is stronger evidence than slide wording.
        explicit_text = " ".join(value for _, value in explicit)
        scores, hits = _scores(explicit_text, keywords)
        method = "explicit_field_keywords" if scores else "topic_keywords"
        if explicit_text and not scores:
            return {
                "status": "needs_review",
                "method": "unrecognized_explicit_field",
                "candidates": [],
                "reason": "The supplied discipline is not in the keyword catalogue; supply discipline_code or an image.",
            }
        if not explicit_text:
            scores, hits = _scores(topic, keywords)
            if not _rank(scores) and body:
                scores, hits = _scores(topic + "\n" + body, keywords)
                method = "content_keywords"
        code = _rank(scores)
        if not code:
            return {
                "status": "needs_review",
                "method": "ambiguous" if scores else "no_match",
                "candidates": sorted(scores, key=lambda item: (-scores[item], item)),
                "reason": "No unique discipline could be inferred; supply discipline_code or a suitable image.",
            }
        matched = hits[code]

    entry = entries[code]
    filename = str(entry["file"])
    subject = str(entry.get("subject") or "")
    for override in data.get("classification", {}).get("specialized_assets", []):
        if str(override.get("discipline_code")) != code:
            continue
        if any(_matches(word, (topic + "\n" + body).casefold()) for word in override.get("keywords", [])):
            filename = str(override["file"])
            subject = str(override.get("subject") or subject)
            break
    selected = _catalogue_path(template_root, catalogue, filename)
    return {
        "status": "selected",
        "discipline_code": code,
        "discipline": entry["discipline"],
        "method": method,
        "matched_terms": matched,
        "subject": subject,
        "path": str(selected),
    }
