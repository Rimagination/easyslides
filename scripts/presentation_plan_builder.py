#!/usr/bin/env python3
"""Create reviewable content/design plan scaffolds from an existing deck plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.component_selector import select_form_candidates
except ModuleNotFoundError:  # pragma: no cover
    from component_selector import select_form_candidates


CONTENT_SCHEMA_VERSION = "easyslides.content_plan.v1"
DESIGN_SCHEMA_VERSION = "easyslides.design_plan.v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source_for_slide(slide: dict[str, Any]) -> str:
    evidence = slide.get("evidence_sources")
    if isinstance(evidence, list) and evidence and isinstance(evidence[0], dict):
        return str(evidence[0].get("locator") or evidence[0].get("source_id") or "deck-plan evidence")
    return "deck-plan claim"


def build_content_plan(deck_plan: dict[str, Any]) -> dict[str, Any]:
    slides = [row for row in deck_plan.get("slides", []) if isinstance(row, dict)]
    source_map = [row for row in deck_plan.get("source_map", []) if isinstance(row, dict)]
    content_slides: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    referenced_sources: set[str] = set()
    for slide in slides:
        page = str(slide.get("page") or "")
        claim_id = f"claim-{page.lower()}"
        claim = str(slide.get("claim") or slide.get("action_title") or "").strip()
        evidence = slide.get("evidence_sources") if isinstance(slide.get("evidence_sources"), list) else []
        source = _source_for_slide(slide)
        for row in evidence:
            if isinstance(row, dict) and row.get("source_id"):
                referenced_sources.add(str(row["source_id"]))
        claims.append(
            {
                "claim_id": claim_id,
                "claim": claim,
                "type": "statement",
                "source": source,
                "verbatim": str(slide.get("claim_verbatim") or claim),
                "verified": bool(slide.get("claim_verified", False)),
                "as_of": str(slide.get("as_of") or ""),
            }
        )
        content_slides.append(
            {
                "page": page,
                "role": str(slide.get("role") or "content"),
                "question": str(slide.get("question") or f"这一页要回答什么：{claim}"),
                "takeaway": str(slide.get("action_title") or claim),
                "content_units": [claim or "TODO: add a source-backed content unit"],
                "units_count": 1,
                "claim_ids": [claim_id],
                "evidence_sources": evidence,
            }
        )
    coverage: list[dict[str, Any]] = []
    for source in source_map:
        source_id = str(source.get("id") or "")
        disposition = "built-around" if source_id in referenced_sources else "cut"
        coverage.append(
            {
                "section_id": source_id or f"source-{len(coverage) + 1}",
                "label": str(source.get("title") or source_id or "source"),
                "pages": str(source.get("pages") or ""),
                "disposition": disposition,
                "reason": "referenced by deck plan" if disposition == "built-around" else "not referenced by the current deck plan",
            }
        )
    return {
        "schema_version": CONTENT_SCHEMA_VERSION,
        "plan_status": "draft",
        "deck_id": str(deck_plan.get("deck_id") or deck_plan.get("title") or "easyslides-deck"),
        "deck_message": str(deck_plan.get("deck_message") or (content_slides[0]["takeaway"] if content_slides else "TODO: write the deck message")),
        "audience": str(deck_plan.get("audience") or "TODO: confirm audience"),
        "delivery": str(deck_plan.get("delivery") or "TODO: confirm live or self-read"),
        "source_size": deck_plan.get("source_size") or {},
        "slides": content_slides,
        "claim_ledger": claims,
        "source_coverage": coverage or [{"section_id": "source-1", "label": "TODO: add source coverage", "disposition": "built-around"}],
        "open_questions": ["Confirm the deck message, audience, delivery mode, and every claim's source verification before approval."],
    }


def build_design_plan(deck_plan: dict[str, Any], component_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    component_by_page = {
        str(row.get("page")): row
        for row in (component_plan or {}).get("slides", [])
        if isinstance(row, dict) and row.get("page")
    }
    slides: list[dict[str, Any]] = []
    form_ledger: list[dict[str, Any]] = []
    for index, source_slide in enumerate(row for row in deck_plan.get("slides", []) if isinstance(row, dict)):
        page = str(source_slide.get("page") or f"P{index + 1:02d}")
        component = component_by_page.get(page, {})
        selection = component.get("form_selection") if isinstance(component.get("form_selection"), dict) else select_form_candidates(
            content_shape=str(source_slide.get("content_shape") or ""),
            page_role=str(source_slide.get("role") or "content"),
            item_count=int(source_slide.get("item_count") or 1),
        )
        candidates = selection.get("candidates") if isinstance(selection.get("candidates"), list) else []
        chosen = selection.get("chosen") if isinstance(selection.get("chosen"), dict) else (candidates[0] if candidates else {})
        runner = selection.get("runner_up") if isinstance(selection.get("runner_up"), dict) else (candidates[1] if len(candidates) > 1 else {})
        chosen_form = str(chosen.get("form_id") or "statement")
        chosen_family = str(chosen.get("family") or "statement")
        slides.append(
            {
                "page": page,
                "visual_protagonist": "TODO: name the visual hero for this slide",
                "candidate_forms": [
                    {"form_id": str(row.get("form_id")), "family": str(row.get("family")), "reason": str(row.get("reason") or "")}
                    for row in candidates[:3]
                    if isinstance(row, dict)
                ],
                "chosen_form": chosen_form,
                "runner_up": {"form_id": str(runner.get("form_id") or ""), "family": str(runner.get("family") or "")},
                "reasoning": "TODO: explain why this form beats the runner-up and the card/bullet default",
                "layout_id": str(source_slide.get("layout_id") or "TODO: choose layout"),
                "motion": "static: TODO: decide whether an appear build earns its place",
            }
        )
        form_ledger.append({"page": page, "visual_protagonist": "TODO", "format_family": chosen_family, "build": "TODO"})
    return {
        "schema_version": DESIGN_SCHEMA_VERSION,
        "plan_status": "draft",
        "deck_id": str(deck_plan.get("deck_id") or deck_plan.get("title") or "easyslides-deck"),
        "design_language": {
            "preset": "inherit from selected template",
            "palette": "TODO: define semantic colour roles",
            "type_pairing": "TODO: define display/body fonts",
            "signature_motif": "TODO: define the quiet interior register",
            "signature_move": "TODO: name one content-born signature move",
        },
        "density": {"median_words_per_slide": 0, "over_budget_count": 0, "non_text_protagonist_count": 0},
        "slides": slides,
        "form_ledger": form_ledger,
        "rhythm": [{"page": str(row.get("page") or ""), "beat": str(row.get("rhythm") or "TODO")} for row in deck_plan.get("slides", []) if isinstance(row, dict)],
        "open_questions": ["Choose the design language, approve the form ledger, and replace every TODO before production."],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build draft content_plan.json and design_plan.json scaffolds.")
    parser.add_argument("deck_plan", type=Path)
    parser.add_argument("--component-plan", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    deck_plan = _read(args.deck_plan)
    component_plan = _read(args.component_plan) if args.component_plan else None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    content = build_content_plan(deck_plan)
    design = build_design_plan(deck_plan, component_plan)
    (args.out_dir / "content_plan.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "design_plan.json").write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "plan_status": "draft", "out_dir": str(args.out_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
