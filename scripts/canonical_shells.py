"""Generalize source pages into a small, stable EasySlides shell family."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


CANONICAL_SHELLS = (
    {"shell_id": "cover", "page_id": "01_cover", "role": "cover"},
    {"shell_id": "toc", "page_id": "02_toc", "role": "toc"},
    {"shell_id": "chapter", "page_id": "03_chapter", "role": "chapter"},
    {"shell_id": "content", "page_id": "04_content", "role": "content"},
    {"shell_id": "ending", "page_id": "05_ending", "role": "ending"},
)
CANONICAL_SHELL_LIMIT = len(CANONICAL_SHELLS)
CANONICAL_SHELL_MINIMUM = 3
REQUIRED_SHELL_ROLES = ("cover", "content", "ending")
OPTIONAL_SHELL_ROLES = ("toc", "chapter")
SHELL_ROLES = {row["role"] for row in CANONICAL_SHELLS}


def build_shell_profile(shells: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the active public shell surface for a distilled source."""
    active_roles = [str(shell.get("story_role") or shell.get("role")) for shell in shells]
    return {
        "policy": "evidence_driven_three_to_five_stable_shells",
        "minimum_shell_count": CANONICAL_SHELL_MINIMUM,
        "maximum_shell_count": CANONICAL_SHELL_LIMIT,
        "required_shell_roles": list(REQUIRED_SHELL_ROLES),
        "optional_shell_roles": list(OPTIONAL_SHELL_ROLES),
        "active_shell_roles": active_roles,
        "active_shell_count": len(active_roles),
        "toc_present": "toc" in active_roles,
        "chapter_present": "chapter" in active_roles,
    }


def _visual_profile(page: dict[str, Any]) -> str:
    image_count = sum(1 for slot in page.get("slot_candidates", []) if slot.get("kind") == "image")
    if image_count >= 2:
        return "multi_visual"
    if image_count == 1:
        return "figure"
    return "text"


def _density_band(page: dict[str, Any]) -> str:
    score = int(page.get("density_score") or 1)
    if score <= 2:
        return "light"
    if score >= 4:
        return "dense"
    return "balanced"


def body_variant_key(page: dict[str, Any]) -> str | None:
    """Return a stable content-form key; shell pages do not need body variants."""
    if str(page.get("story_role") or "content") != "content":
        return None
    return f"content_{_visual_profile(page)}_{_density_band(page)}"


def _fallback_source(source_pages: list[dict[str, Any]]) -> dict[str, Any]:
    if not source_pages:
        raise ValueError("at least one source page is required to build canonical shells")
    content = [page for page in source_pages if page.get("story_role") == "content"]
    return content[0] if content else source_pages[0]


def build_canonical_shells(source_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose a 3-5 shell public surface from source evidence.

    Cover, content, and ending are the stable minimum. TOC and chapter are
    materialized only when the source pages visibly support those roles.
    """
    by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in SHELL_ROLES}
    for page in source_pages:
        role = str(page.get("story_role") or "content")
        by_role.setdefault(role, []).append(page)

    fallback = _fallback_source(source_pages)
    available_roles = {
        str(page.get("story_role") or "content")
        for page in source_pages
    }
    shells: list[dict[str, Any]] = []
    for shell in CANONICAL_SHELLS:
        if shell["role"] in OPTIONAL_SHELL_ROLES and shell["role"] not in available_roles:
            continue
        exemplar = (by_role.get(shell["role"]) or [fallback])[0]
        row = dict(exemplar)
        row.update(
            {
                "id": shell["page_id"],
                "svg": f"{shell['page_id']}.svg",
                "page_type": shell["role"],
                "story_role": shell["role"],
                "role_fit": [shell["role"]],
                "slot_model": shell["role"],
                "shell_id": shell["shell_id"],
                "canonical_shell": True,
                "source_page_id": exemplar.get("id"),
                "source_role": exemplar.get("story_role"),
                "fallback_source_role": exemplar.get("story_role") != shell["role"],
            }
        )
        shells.append(row)
    content_variants = [variant["variant_id"] for variant in build_body_variants(source_pages)]
    for shell in shells:
        shell["body_variants"] = content_variants if shell["shell_id"] == "content" else []
    return shells


def build_body_variants(source_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group source content pages by reusable visual form, not source order."""
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for page in source_pages:
        variant_id = body_variant_key(page)
        if not variant_id:
            continue
        row = grouped.setdefault(
            variant_id,
            {
                "variant_id": variant_id,
                "shell_id": "content",
                "shell": "04_content.svg",
                "source_slides": [],
                "source_page_ids": [],
                "density_bands": [],
                "components": {"text_slots": 0, "image_slots": 0},
            },
        )
        row["source_slides"].append(page.get("source_slide"))
        row["source_page_ids"].append(page.get("id"))
        row["density_bands"].append(_density_band(page))
        for slot in page.get("slot_candidates", []):
            kind = "image_slots" if slot.get("kind") == "image" else "text_slots"
            row["components"][kind] += 1

    variants: list[dict[str, Any]] = []
    for variant_id, row in grouped.items():
        profile = variant_id.removeprefix("content_")
        variants.append(
            {
                **row,
                "visual_profile": profile.split("_")[0],
                "best_for": {
                    "content_figure": "a claim supported by one primary figure or diagram",
                    "content_multi": "a dense evidence page with multiple visual exhibits",
                    "content_text": "a text-led explanation or argument",
                }.get("content_" + profile.split("_")[0], "content that matches the measured source rhythm"),
                "selection": {
                    "route": "canonical_shell_then_body_variant",
                    "density": sorted(set(row["density_bands"])),
                },
                "composition_mode": "source_measured_open_composition",
                "component_refs": [],
            }
        )
        variants[-1].pop("density_bands", None)
    return variants


def build_source_page_roster(
    source_pages: list[dict[str, Any]],
    variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    variant_by_page = {
        page_id: variant["variant_id"]
        for variant in variants
        for page_id in variant.get("source_page_ids", [])
    }
    roster: list[dict[str, Any]] = []
    for page in source_pages:
        role = str(page.get("story_role") or "content")
        canonical_shell = role if role in SHELL_ROLES else "content"
        roster.append(
            {
                "source_page_id": page.get("id"),
                "source_slide": page.get("source_slide"),
                "source_svg": page.get("source_svg"),
                "source_role": role,
                "canonical_shell": canonical_shell,
                "body_variant": variant_by_page.get(page.get("id")),
                "density_score": page.get("density_score"),
                "slot_count": len(page.get("slot_candidates", [])),
                "preserved_as": "source_page_evidence_and_variant_exemplar",
            }
        )
    return roster


def build_canonical_shell_pack(source_pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    variants = build_body_variants(source_pages)
    shells = build_canonical_shells(source_pages)
    roster = build_source_page_roster(source_pages, variants)
    return shells, variants, roster
