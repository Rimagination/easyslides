#!/usr/bin/env python3
"""Compile deck intent plus Template IR into executable Slide IR.

The Slide IR is the shared input for SVG and native-PPTX rendering.  It is the
first point where a shell, body variant, component instances, placements, and
bound payload are one resolved object rather than parallel planning files.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
from typing import Any
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile

try:
    from scripts.template_compiler import ROOT, TemplateCompileError, compile_template, read_json, write_json
except ModuleNotFoundError:  # pragma: no cover
    from template_compiler import ROOT, TemplateCompileError, compile_template, read_json, write_json


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
PPTX_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PPTX_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PPTX_NS = {"p": PPTX_P_NS, "a": PPTX_A_NS}
EMU_PER_PX = 9525.0
COMPONENT_GROUP_PREFIX = "EasySlides Component: "
SLIDE_IR_SCHEMA = "easyslides.slide_ir.v1"
SLIDE_COMPILE_REPORT_SCHEMA = "easyslides.slide_compile_report.v1"
NSFC_ENDING_DEFAULT = "敬请批评指正"
NSFC_ENDING_FORBIDDEN_TERMS = ("聆听",)
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


class SlideCompileError(ValueError):
    """Raised when slide intent cannot be resolved without guessing."""


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _frame(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        frame = {
            "x": float(value.get("x", 0)),
            "y": float(value.get("y", 0)),
            "width": float(value.get("width", value.get("w", 0))),
            "height": float(value.get("height", value.get("h", 0))),
        }
    except (TypeError, ValueError):
        return None
    if frame["width"] <= 0 or frame["height"] <= 0:
        return None
    return frame


def _role_alias(value: object) -> str:
    role = str(value or "content").strip().lower()
    return {"agenda": "toc", "section": "chapter", "closing": "ending"}.get(role, role)


def _apply_template_text_policy(template_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply template-owned copy rules before generic slot validation."""
    if template_id != "nsfc_defense" or role != "ending":
        return payload

    normalized = dict(payload)
    subtitle = normalized.get("CLOSING_SUBTITLE")
    if subtitle not in (None, "", []):
        raise SlideCompileError(
            "nsfc_defense ending accepts one closing line only; do not use CLOSING_SUBTITLE"
        )
    normalized.pop("CLOSING_SUBTITLE", None)
    title = str(normalized.get("CLOSING_TITLE") or "").strip()
    if not title:
        title = NSFC_ENDING_DEFAULT
    if any(term in title for term in NSFC_ENDING_FORBIDDEN_TERMS):
        raise SlideCompileError(
            "nsfc_defense ending copy may not contain '聆听'; use '敬请批评指正'"
        )
    if "\n" in title or len(title) > 8:
        raise SlideCompileError(
            "nsfc_defense ending copy must be one line with at most 8 Chinese characters"
        )
    normalized["CLOSING_TITLE"] = title
    return normalized


def _scenario_profiles(story_structure: object) -> dict[str, dict[str, Any]]:
    """Return published, named story profiles from a template sidecar."""
    if not isinstance(story_structure, dict):
        return {}
    profiles: dict[str, dict[str, Any]] = {}
    declared = story_structure.get("scenario_profiles")
    if isinstance(declared, dict):
        candidates = declared.values()
    elif isinstance(declared, list):
        candidates = declared
    else:
        candidates = story_structure.values()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        scenario_id = str(candidate.get("scenario_id") or "").strip()
        if scenario_id:
            profiles[scenario_id] = candidate
    return profiles


def _scenario_role(raw: dict[str, Any], role: str) -> str:
    explicit = str(raw.get("grant_role") or raw.get("scenario_role") or "").strip()
    if explicit:
        return explicit
    return role if role in {"cover", "toc", "ending"} else ""


def validate_scenario_contract(deck_plan: dict[str, Any], template_ir: dict[str, Any]) -> dict[str, Any]:
    """Validate a scenario-specific deck grammar before layout compilation.

    Templates own their visual system; a scenario profile owns the reviewer
    narrative. The check stays dormant for legacy plans without ``scenario_id``
    so partial galleries and component fixtures can still compile in isolation.
    """
    scenario_id = str(deck_plan.get("scenario_id") or "").strip()
    if not scenario_id:
        return {"status": "skipped", "reason": "scenario_id_not_declared"}

    profiles = _scenario_profiles(template_ir.get("story_structure"))
    profile = profiles.get(scenario_id)
    if profile is None:
        available = ", ".join(sorted(profiles)) or "none"
        raise SlideCompileError(
            f"template {template_ir.get('template_id')!r} does not publish scenario_id {scenario_id!r}; "
            f"available: {available}"
        )

    mode = str(deck_plan.get("scenario_mode") or "full").strip().lower()
    if mode not in {"full", "short"}:
        raise SlideCompileError("scenario_mode must be 'full' or 'short'")
    slides = deck_plan.get("slides")
    if not isinstance(slides, list):
        raise SlideCompileError("scenario contract requires slides to be a list")

    profile_roles = [str(value) for value in profile.get("full_deck_roles", []) if str(value)]
    allowed_roles = set(profile_roles)
    optional_roles = {
        str(value)
        for value in profile.get("optional_deck_roles", [])
        if str(value)
    }
    bindings = {
        str(row.get("grant_role")): row
        for row in profile.get("variant_bindings", [])
        if isinstance(row, dict) and str(row.get("grant_role") or "")
    }
    seen: dict[str, int] = {}
    declared: list[dict[str, str]] = []

    for index, raw in enumerate(slides, start=1):
        if not isinstance(raw, dict):
            raise SlideCompileError(f"scenario slide {index} must be an object")
        role = _role_alias(raw.get("role"))
        grant_role = _scenario_role(raw, role)
        if not grant_role:
            raise SlideCompileError(
                f"scenario {scenario_id!r} requires grant_role on slide {index}; "
                "declare the page's NSFC narrative responsibility"
            )
        if grant_role not in allowed_roles:
            raise SlideCompileError(
                f"scenario {scenario_id!r} does not recognize grant_role {grant_role!r} on slide {index}"
            )
        if grant_role in seen:
            raise SlideCompileError(
                f"scenario {scenario_id!r} duplicates grant_role {grant_role!r} on slides "
                f"{seen[grant_role]} and {index}"
            )
        seen[grant_role] = index

        expected_shell_role = (
            grant_role
            if grant_role in {"cover", "toc", "ending"}
            else "chapter"
            if grant_role.startswith("chapter_")
            else "content"
        )
        if role != expected_shell_role:
            raise SlideCompileError(
                f"grant_role {grant_role!r} requires shell role {expected_shell_role!r}, got {role!r}"
            )

        binding = bindings.get(grant_role)
        if binding is not None:
            expected_variant = str(binding.get("body_variant_id") or "")
            expected_story_role = str(binding.get("story_role") or "")
            expected_section = str(binding.get("section") or "")
            actual_variant = str(raw.get("body_variant_id") or "")
            actual_story_role = str(raw.get("story_role") or raw.get("narrative_role") or "")
            actual_section = str(raw.get("section") or "")
            if expected_variant and actual_variant != expected_variant:
                raise SlideCompileError(
                    f"grant_role {grant_role!r} requires body_variant_id {expected_variant!r}, "
                    f"got {actual_variant!r}"
                )
            if expected_story_role and actual_story_role != expected_story_role:
                raise SlideCompileError(
                    f"grant_role {grant_role!r} requires story_role {expected_story_role!r}, "
                    f"got {actual_story_role!r}"
                )
            if expected_section and actual_section != expected_section:
                raise SlideCompileError(
                    f"grant_role {grant_role!r} requires section {expected_section!r}, got {actual_section!r}"
                )
        declared.append({"page": str(raw.get("page") or f"P{index:02d}"), "grant_role": grant_role})

    if mode == "full":
        missing = [
            grant_role
            for grant_role in profile_roles
            if grant_role not in optional_roles and grant_role not in seen
        ]
        if missing:
            raise SlideCompileError(
                f"scenario {scenario_id!r} full deck is missing grant_role(s): {', '.join(missing)}"
            )
    elif not {"cover", "ending"}.issubset(seen):
        raise SlideCompileError(
            f"scenario {scenario_id!r} short deck must still declare cover and ending grant_role pages"
        )

    return {
        "status": "pass",
        "scenario_id": scenario_id,
        "scenario_label": str(profile.get("scenario_label") or scenario_id),
        "mode": mode,
        "optional_roles": sorted(optional_roles),
        "declared_roles": declared,
    }


def _shell_map(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(shell["shell_id"]): shell
        for shell in template_ir.get("shells", [])
        if isinstance(shell, dict) and shell.get("shell_id")
    }


def _variant_map(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(variant["variant_id"]): variant
        for variant in template_ir.get("body_variants", [])
        if isinstance(variant, dict) and variant.get("variant_id")
    }


def _component_map(template_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(component["asset_id"]): component
        for component in template_ir.get("components", [])
        if isinstance(component, dict) and component.get("asset_id")
    }


def _resolve_shell(template_ir: dict[str, Any], slide: dict[str, Any]) -> dict[str, Any]:
    shells = _shell_map(template_ir)
    explicit = str(slide.get("shell_id") or "")
    if explicit:
        explicit = explicit.rsplit("/", 1)[-1]
        if explicit not in shells:
            raise SlideCompileError(f"unknown shell_id {explicit!r}")
        return shells[explicit]
    role = _role_alias(slide.get("role"))
    matches = [shell for shell in shells.values() if _role_alias(shell.get("role")) == role]
    if len(matches) != 1:
        raise SlideCompileError(f"role {role!r} must resolve to exactly one public shell")
    return matches[0]


def _component_plan_variant(
    slide: dict[str, Any],
    *,
    page: str,
    component_plan: dict[str, Any] | None,
    variants: dict[str, dict[str, Any]],
) -> str:
    if not isinstance(component_plan, dict):
        return ""
    rows = [
        row
        for row in component_plan.get("slides", [])
        if isinstance(row, dict) and str(row.get("page") or "") == page
    ]
    if not rows:
        return ""
    assets = rows[0].get("selected_assets")
    if not isinstance(assets, list):
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("asset_id") or "")
        if asset_id.startswith("body_variant/"):
            candidate = asset_id.rsplit("/", 1)[-1]
            if candidate in variants:
                return candidate
    return ""


def _variant_score(variant: dict[str, Any], slide: dict[str, Any]) -> tuple[int, str]:
    selection = _as_dict(variant.get("selection"))
    shape = str(slide.get("content_shape") or slide.get("evidence_shape") or "").lower()
    story_role = str(slide.get("story_role") or slide.get("narrative_role") or "").strip().lower()
    shapes = {str(value).lower() for value in selection.get("content_shapes", [])}
    story_roles = {str(value).lower() for value in selection.get("story_roles", [])}
    haystack = f"{variant.get('variant_id', '')} {variant.get('best_for', '')}".lower()
    score = 0
    if story_role:
        if story_role in story_roles:
            score += 160
        elif story_roles:
            score -= 1000
    if shape:
        if shape in shapes:
            score += 80
        elif shape in haystack:
            score += 30
    density = slide.get("density")
    if density is not None and selection.get("density") is not None:
        try:
            score += max(0, 20 - abs(int(density) - int(selection["density"])) * 5)
        except (TypeError, ValueError):
            pass
    figure_count = slide.get("figure_count")
    if figure_count is not None and selection.get("figure_count") is not None:
        try:
            score += max(0, 20 - abs(int(figure_count) - int(selection["figure_count"])) * 5)
        except (TypeError, ValueError):
            pass
    score += int(selection.get("priority") or 0)
    return score, str(variant.get("variant_id") or "")


def _resolve_variant(
    template_ir: dict[str, Any],
    slide: dict[str, Any],
    *,
    page: str,
    component_plan: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    variants = _variant_map(template_ir)
    if not variants:
        raise SlideCompileError("content shell has no body variants")
    explicit_values = [
        slide.get("body_variant_id"),
        slide.get("variant_id"),
        slide.get("layout_id"),
    ]
    for value in explicit_values:
        if not isinstance(value, str) or not value.strip():
            continue
        candidate = value.strip().rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if candidate in variants:
            return variants[candidate], "explicit"
    planned = _component_plan_variant(
        slide,
        page=page,
        component_plan=component_plan,
        variants=variants,
    )
    if planned:
        return variants[planned], "component_plan"
    scored = sorted((_variant_score(variant, slide) for variant in variants.values()), key=lambda row: (-row[0], row[1]))
    if not scored:
        raise SlideCompileError("no body variant candidates are available")
    best_score, best_id = scored[0]
    if best_score <= 0 and len(scored) > 1:
        raise SlideCompileError(
            "content intent is ambiguous; supply body_variant_id or content_shape"
        )
    return variants[best_id], "semantic_score"


def _slot_contract_map(slots: object) -> dict[str, dict[str, Any]]:
    if not isinstance(slots, list):
        return {}
    return {
        str(slot.get("slot_id")): slot
        for slot in slots
        if isinstance(slot, dict) and slot.get("slot_id")
    }


def _validate_payload(slots: object, payload: dict[str, Any], *, context: str) -> None:
    contracts = _slot_contract_map(slots)
    required = {
        slot_id
        for slot_id, slot in contracts.items()
        if bool(slot.get("required", True))
    }
    missing = sorted(slot_id for slot_id in required if payload.get(slot_id) in (None, "", []))
    extra = sorted(set(payload) - set(contracts))
    if missing:
        raise SlideCompileError(f"{context} is missing required slot payload: {', '.join(missing)}")
    if extra:
        raise SlideCompileError(f"{context} contains undeclared slot payload: {', '.join(extra)}")


def _full_width_equivalent_characters(value: str) -> float:
    """Estimate an unwrapped title's visual width in full-width glyphs."""
    units = 0.0
    for character in value:
        if character.isspace():
            units += 0.25
        elif unicodedata.east_asian_width(character) in {"W", "F"}:
            units += 1.0
        elif character.isalnum():
            units += 0.55
        else:
            units += 0.5
    return units


def _enforce_single_line_slot_contracts(
    slots: object,
    payload: dict[str, Any],
    *,
    context: str,
) -> dict[str, Any]:
    """Apply hard no-wrap contracts declared by a template slot."""
    normalized = dict(payload)
    for slot_id, contract in _slot_contract_map(slots).items():
        capacity = contract.get("capacity")
        if not isinstance(capacity, dict) or not capacity.get("single_line_required"):
            continue
        value = normalized.get(slot_id)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            raise SlideCompileError(
                f"{context} slot {slot_id!r} must be one text value on one visual line"
            )
        text = str(value).strip()
        if "\n" in text or "\r" in text:
            raise SlideCompileError(
                f"{context} slot {slot_id!r} must be one visual line; remove line breaks and shorten the title"
            )
        max_units = float(capacity.get("max_chars_per_line") or 0)
        if max_units and _full_width_equivalent_characters(text) > max_units:
            raise SlideCompileError(
                f"{context} slot {slot_id!r} exceeds its {max_units:g}-character single-line budget; "
                "shorten the title instead of wrapping it"
            )
        normalized[slot_id] = text
    return normalized


def _balanced_cjk_stack_lines(
    value: object,
    *,
    max_chars_per_line: int,
    max_lines: int,
    context: str,
    slot_id: str,
) -> list[str]:
    """Plan narrow CJK labels before Office can apply glyph-level wrapping."""
    if isinstance(value, list):
        raw_lines = [str(item).strip() for item in value if str(item).strip()]
        explicit = True
    else:
        text = str(value or "").strip()
        explicit = "\n" in text or "\r" in text
        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not raw_lines:
        return [""]

    if not explicit:
        # Stack CJK labels in fixed, readable semantic units. These labels are
        # intentionally compact; any whitespace is merely source formatting.
        text = "".join(raw_lines)
        raw_lines = [
            text[start : start + max_chars_per_line]
            for start in range(0, len(text), max_chars_per_line)
        ]

    if len(raw_lines) > max_lines or any(len(line) > max_chars_per_line for line in raw_lines):
        raise SlideCompileError(
            f"{context} slot {slot_id!r} exceeds its {max_lines}-line x "
            f"{max_chars_per_line}-character stacked-label budget; shorten the label"
        )
    return raw_lines


def _enforce_component_text_layout_contracts(
    slots: object,
    payload: dict[str, Any],
    *,
    context: str,
) -> dict[str, Any]:
    """Normalize component-owned text layouts before creating Slide IR."""
    normalized = dict(payload)
    for slot_id, contract in _slot_contract_map(slots).items():
        if str(contract.get("text_layout") or "") != "balanced_cjk_stack":
            continue
        value = normalized.get(slot_id)
        if value in (None, "", []):
            continue
        capacity = contract.get("capacity") if isinstance(contract.get("capacity"), dict) else {}
        max_chars = int(capacity.get("max_chars_per_line") or 1)
        max_lines = int(capacity.get("max_lines") or 1)
        normalized[slot_id] = "\n".join(
            _balanced_cjk_stack_lines(
                value,
                max_chars_per_line=max_chars,
                max_lines=max_lines,
                context=context,
                slot_id=slot_id,
            )
        )
    return normalized


def _normalized_copy(value: object) -> str:
    """Compare visible copy without punctuation or presentation-only spacing."""
    return "".join(
        character.casefold()
        for character in str(value or "")
        if character.isalnum() or unicodedata.east_asian_width(character) in {"W", "F"}
    )


def _enforce_nsfc_content_hierarchy(
    shell_payload: dict[str, Any],
    body_payload: dict[str, Any],
    *,
    slide_index: int,
) -> dict[str, Any]:
    """Keep the central message distinct from evidence-level component copy."""
    normalized = dict(shell_payload)
    value = normalized.get("KEY_MESSAGE")
    lines = _text_lines(value)
    if not 1 <= len(lines) <= 2:
        raise SlideCompileError(
            "nsfc_defense content requires KEY_MESSAGE with one or two square-bullet lines"
        )
    cleaned: list[str] = []
    for line in lines:
        text = line.strip()
        if text.startswith("■"):
            raise SlideCompileError(
                "nsfc_defense KEY_MESSAGE must not include the square bullet; the template renders it"
            )
        if _full_width_equivalent_characters(text) > 38:
            raise SlideCompileError(
                "nsfc_defense KEY_MESSAGE exceeds the 38-character line budget; shorten or split it"
            )
        cleaned.append(text)
    title = _normalized_copy(normalized.get("PAGE_TITLE") or normalized.get("TITLE"))
    for line in cleaned:
        key_copy = _normalized_copy(line)
        if key_copy and key_copy == title:
            raise SlideCompileError(
                "nsfc_defense KEY_MESSAGE repeats PAGE_TITLE; state the page's smallest defensible point instead"
            )
        for slot_id, candidate in body_payload.items():
            if not isinstance(candidate, str) or candidate.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")):
                continue
            if len(key_copy) >= 8 and key_copy == _normalized_copy(candidate):
                raise SlideCompileError(
                    f"nsfc_defense KEY_MESSAGE repeats body slot {slot_id}; make body copy evidence-level instead"
                )
    normalized["KEY_MESSAGE"] = "\n".join(cleaned)
    expected_page_number = f"{slide_index:02d}"
    supplied_page_number = normalized.get("PAGE_NUMBER")
    if supplied_page_number not in (None, "", expected_page_number):
        raise SlideCompileError(
            f"nsfc_defense PAGE_NUMBER is template-owned and must be {expected_page_number}"
        )
    normalized["PAGE_NUMBER"] = expected_page_number
    return normalized


def _enforce_template_owned_slot_policies(
    shell: dict[str, Any],
    shell_payload: dict[str, Any],
    *,
    slide_index: int,
) -> dict[str, Any]:
    """Populate slot values owned by a template instead of the caller."""
    normalized = dict(shell_payload)
    for slot in shell.get("slots", []):
        if not isinstance(slot, dict) or slot.get("value_policy") != "automatic_slide_index":
            continue
        slot_id = str(slot.get("slot_id") or "")
        if not slot_id:
            continue
        expected = f"{slide_index:02d}"
        supplied = normalized.get(slot_id)
        if supplied not in (None, "", expected):
            raise SlideCompileError(
                f"{slot_id} is template-owned and must be {expected}"
            )
        normalized[slot_id] = expected
    return normalized


def _frame_inside_canvas(frame: dict[str, float], canvas: dict[str, Any]) -> bool:
    width = float(canvas.get("width") or 1280)
    height = float(canvas.get("height") or 720)
    tolerance = 0.01
    return (
        frame["x"] >= -tolerance
        and frame["y"] >= -tolerance
        and frame["x"] + frame["width"] <= width + tolerance
        and frame["y"] + frame["height"] <= height + tolerance
    )


def _frame_contains(container: dict[str, float], child: dict[str, float]) -> bool:
    tolerance = 0.01
    return (
        child["x"] >= container["x"] - tolerance
        and child["y"] >= container["y"] - tolerance
        and child["x"] + child["width"] <= container["x"] + container["width"] + tolerance
        and child["y"] + child["height"] <= container["y"] + container["height"] + tolerance
    )


def _content_body_canvas(shell: dict[str, Any]) -> dict[str, float] | None:
    direct = _frame(shell.get("body_canvas"))
    if direct:
        return direct
    for region in shell.get("regions", []):
        if isinstance(region, dict) and str(region.get("region_id") or "") == "body_canvas":
            frame = _frame(region.get("frame"))
            if frame:
                return frame
    return None


def _validate_source_guided_content(
    shell: dict[str, Any],
    variant: dict[str, Any],
    slide: dict[str, Any],
) -> None:
    """Enforce a template's reviewed source narrative instead of free assembly."""
    if str(shell.get("content_shell_policy") or "") != "source_guided_body_variant_required":
        return
    if slide.get("body_components") not in (None, []):
        raise SlideCompileError(
            "source-guided content forbids direct body_components; select a registered source-derived body variant"
        )
    story_role = str(slide.get("story_role") or slide.get("narrative_role") or "").strip()
    if not story_role:
        raise SlideCompileError(
            "source-guided content requires story_role; choose the source narrative step before selecting a body variant"
        )
    allowed_roles = {
        str(value).strip()
        for value in _as_dict(variant.get("selection")).get("story_roles", [])
        if str(value).strip()
    }
    if story_role not in allowed_roles:
        raise SlideCompileError(
            f"body variant {variant.get('variant_id')!r} does not permit story_role {story_role!r}; "
            f"allowed: {', '.join(sorted(allowed_roles))}"
        )
    guidance = _as_dict(variant.get("source_guidance"))
    expected_section = str(guidance.get("section") or "").strip()
    allowed_sections = {
        str(value).strip()
        for value in guidance.get("sections", [])
        if str(value).strip()
    }
    section = str(slide.get("section") or "").strip()
    if allowed_sections and section not in allowed_sections:
        raise SlideCompileError(
            f"body variant {variant.get('variant_id')!r} permits section(s) {', '.join(sorted(allowed_sections))}; "
            f"received {section or '<missing>'!r}"
        )
    if not allowed_sections and expected_section and section != expected_section:
        raise SlideCompileError(
            f"body variant {variant.get('variant_id')!r} belongs to section {expected_section!r}; "
            f"received {section or '<missing>'!r}"
        )


def _explicit_component_asset_id(
    raw: dict[str, Any],
    components: dict[str, dict[str, Any]],
    template_id: str,
) -> str:
    candidate = str(raw.get("asset_id") or raw.get("component_id") or "").strip()
    if candidate in components:
        return candidate
    prefixed = f"component/{template_id}/{candidate}"
    return prefixed if prefixed in components else candidate


def _compile_explicit_content_layers(
    template_ir: dict[str, Any],
    raw_components: object,
    *,
    body_canvas: dict[str, float],
    existing_instance_ids: set[str],
) -> list[dict[str, Any]]:
    """Compile opt-in, registered component instances inside an open content canvas."""
    if raw_components is None:
        return []
    if not isinstance(raw_components, list):
        raise SlideCompileError("body_components must be a list of registered component instances")
    components = _component_map(template_ir)
    layers: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_components, start=1):
        context = f"body_components[{index - 1}]"
        if not isinstance(raw, dict):
            raise SlideCompileError(f"{context} must be an object")
        asset_id = _explicit_component_asset_id(raw, components, str(template_ir.get("template_id") or ""))
        component = components.get(asset_id)
        if component is None:
            raise SlideCompileError(f"{context} references an unregistered component: {asset_id!r}")
        frame = _frame(raw.get("frame") or raw.get("placement"))
        if frame is None:
            raise SlideCompileError(f"{context} must declare a positive frame")
        if not _frame_inside_canvas(frame, template_ir["canvas"]) or not _frame_contains(body_canvas, frame):
            raise SlideCompileError(f"{context} frame must stay inside the content body_canvas")
        instance_id = str(raw.get("instance_id") or f"explicit_{index:02d}").strip()
        if not instance_id or instance_id in existing_instance_ids:
            raise SlideCompileError(f"{context} instance_id must be non-empty and unique")
        existing_instance_ids.add(instance_id)
        payload = _as_dict(raw.get("slot_payload") or raw.get("payload"))
        _validate_payload(component.get("slots"), payload, context=f"component {instance_id}")
        payload = _enforce_component_text_layout_contracts(
            component.get("slots"), payload, context=f"component {instance_id}"
        )
        fit = str(raw.get("fit") or "contain")
        if fit not in {"contain", "stretch"}:
            raise SlideCompileError(f"{context} fit must be 'contain' or 'stretch'")
        if fit == "stretch" and _slot_contract_map(component.get("slots")):
            raise SlideCompileError(
                f"{context} cannot stretch a text-bearing component; use contain to preserve text geometry"
            )
        try:
            z_index = int(raw.get("z_index") or 50 + index * 10)
        except (TypeError, ValueError) as exc:
            raise SlideCompileError(f"{context} z_index must be an integer") from exc
        layers.append(
            {
                "layer_type": "component",
                "asset_id": asset_id,
                "instance_id": instance_id,
                "role": str(raw.get("role") or "explicit_component"),
                "region_id": "explicit",
                "frame": frame,
                "z_index": z_index,
                "fit": fit,
                "component": component,
                "slot_bindings": {},
                "payload": payload,
                "composition_source": "explicit_body_components",
            }
        )
    return sorted(layers, key=lambda row: (int(row["z_index"]), str(row["instance_id"])))


def _compile_content_layers(
    template_ir: dict[str, Any],
    variant: dict[str, Any],
    payload: dict[str, Any],
    *,
    body_canvas: dict[str, float],
) -> list[dict[str, Any]]:
    components = _component_map(template_ir)
    regions = {
        str(region["region_id"]): region
        for region in variant.get("regions", [])
        if isinstance(region, dict) and region.get("region_id")
    }
    layers: list[dict[str, Any]] = []
    for ref in variant.get("component_refs", []):
        if not isinstance(ref, dict):
            continue
        asset_id = str(ref.get("asset_id") or "")
        component = components.get(asset_id)
        if not component:
            if bool(ref.get("required", True)):
                raise SlideCompileError(f"required component is unresolved: {asset_id}")
            continue
        region_id = str(ref.get("region") or "")
        region = regions.get(region_id)
        placement = _frame(ref.get("placement"))
        frame = placement or (_frame(region.get("frame")) if region else None)
        if not frame:
            raise SlideCompileError(
                f"component instance {ref.get('instance_id')!r} has no resolved region or placement"
            )
        if not _frame_inside_canvas(frame, template_ir["canvas"]):
            raise SlideCompileError(
                f"component instance {ref.get('instance_id')!r} falls outside the slide canvas"
            )
        if not _frame_contains(body_canvas, frame):
            raise SlideCompileError(
                f"component instance {ref.get('instance_id')!r} falls outside the content body_canvas"
            )
        bindings = _as_dict(ref.get("slot_bindings"))
        component_payload = {
            str(component_slot): payload.get(str(variant_slot))
            for component_slot, variant_slot in bindings.items()
            if str(variant_slot) in payload
        }
        _validate_payload(
            component.get("slots"),
            component_payload,
            context=f"component {ref.get('instance_id')}",
        )
        component_payload = _enforce_component_text_layout_contracts(
            component.get("slots"),
            component_payload,
            context=f"component {ref.get('instance_id')}",
        )
        layers.append(
            {
                "layer_type": "component",
                "asset_id": asset_id,
                "instance_id": str(ref.get("instance_id") or asset_id.rsplit("/", 1)[-1]),
                "role": str(ref.get("role") or ""),
                "region_id": region_id,
                "frame": frame,
                "z_index": int(
                    ref.get("z_index")
                    or (region.get("z_index") if region else 0)
                    or int(ref.get("order") or 1) * 10
                ),
                "fit": str((region.get("fit") if region else "") or "contain"),
                "component": component,
                "slot_bindings": bindings,
                "payload": component_payload,
            }
        )
    return sorted(layers, key=lambda row: (int(row["z_index"]), str(row["instance_id"])))


def compile_slides(
    deck_plan: dict[str, Any],
    template_ir: dict[str, Any],
    *,
    component_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slides = deck_plan.get("slides")
    if not isinstance(slides, list) or not slides:
        raise SlideCompileError("deck_plan.json must define a non-empty slides list")
    scenario_audit = validate_scenario_contract(deck_plan, template_ir)
    compiled: list[dict[str, Any]] = []
    for index, raw in enumerate(slides, start=1):
        if not isinstance(raw, dict):
            raise SlideCompileError(f"slides[{index - 1}] must be an object")
        page = str(raw.get("page") or f"P{index:02d}")
        shell = _resolve_shell(template_ir, raw)
        role = _role_alias(raw.get("role") or shell.get("role"))
        shell_payload = _as_dict(raw.get("shell_payload"))
        shell_payload = _apply_template_text_policy(
            str(template_ir.get("template_id") or ""),
            role,
            shell_payload,
        )
        body_payload = _as_dict(raw.get("slot_payload") or raw.get("body_payload"))
        if role == "content" and "KEY_MESSAGE" in body_payload:
            if shell_payload.get("KEY_MESSAGE") not in (None, ""):
                raise SlideCompileError(
                    "KEY_MESSAGE belongs in content shell_payload, not both shell_payload and slot_payload"
                )
            shell_payload["KEY_MESSAGE"] = body_payload.pop("KEY_MESSAGE")
        if role == "content" and shell_payload.get("KEY_MESSAGE") in (None, ""):
            candidate = raw.get("key_message") or raw.get("central_message")
            if candidate not in (None, ""):
                shell_payload["KEY_MESSAGE"] = candidate
        variant: dict[str, Any] | None = None
        variant_reason = ""
        layers: list[dict[str, Any]] = [
            {
                "layer_type": "shell",
                "shell_id": shell["shell_id"],
                "svg_path": shell["svg_path"],
                "z_index": 0,
            }
        ]
        if role == "content":
            variant, variant_reason = _resolve_variant(
                template_ir,
                raw,
                page=page,
                component_plan=component_plan,
            )
            _validate_source_guided_content(shell, variant, raw)
            # Validate template-owned content chrome before checking a large
            # component payload. This keeps title/key-message failures legible
            # instead of burying them under dozens of evidence-slot errors.
            shell_contracts = _slot_contract_map(shell.get("slots"))
            for key in ("PAGE_TITLE", "TITLE", "KEY_MESSAGE"):
                if key in shell_contracts and key not in shell_payload:
                    candidate = body_payload.get(key) if key == "KEY_MESSAGE" else raw.get("title") or body_payload.get(key)
                    if candidate not in (None, ""):
                        shell_payload[key] = candidate
            shell_payload = _enforce_template_owned_slot_policies(
                shell,
                shell_payload,
                slide_index=index,
            )
            if str(template_ir.get("template_id") or "") == "nsfc_defense":
                shell_payload = _enforce_nsfc_content_hierarchy(
                    shell_payload,
                    body_payload,
                    slide_index=index,
                )
            shell_payload = _enforce_single_line_slot_contracts(
                shell.get("slots"),
                shell_payload,
                context=f"content shell {shell['shell_id']}",
            )
            body_canvas = _content_body_canvas(shell)
            if body_canvas is None:
                raise SlideCompileError("content shell must declare a positive body_canvas")
            _validate_payload(variant.get("slots"), body_payload, context=f"body variant {variant['variant_id']}")
            variant_layers = _compile_content_layers(
                template_ir,
                variant,
                body_payload,
                body_canvas=body_canvas,
            )
            layers.extend(variant_layers)
            explicit_layers = _compile_explicit_content_layers(
                template_ir,
                raw.get("body_components"),
                body_canvas=body_canvas,
                existing_instance_ids={
                    str(layer.get("instance_id") or "")
                    for layer in variant_layers
                    if isinstance(layer, dict)
                },
            )
            if (
                str(variant.get("composition_mode") or "") == "open_component_composition"
                and not explicit_layers
            ):
                raise SlideCompileError(
                    "open_component_composition requires at least one body_components entry"
                )
            layers.extend(explicit_layers)
        else:
            if not shell_payload:
                shell_payload = body_payload
            shell_payload = _enforce_single_line_slot_contracts(
                shell.get("slots"),
                shell_payload,
                context=f"shell {shell['shell_id']}",
            )
            _validate_payload(shell.get("slots"), shell_payload, context=f"shell {shell['shell_id']}")

        if role == "content":
            shell_contracts = _slot_contract_map(shell.get("slots"))
            for key in ("PAGE_TITLE", "TITLE", "KEY_MESSAGE"):
                if key in shell_contracts and key not in shell_payload:
                    candidate = body_payload.get(key) if key == "KEY_MESSAGE" else raw.get("title") or body_payload.get(key)
                    if candidate not in (None, ""):
                        shell_payload[key] = candidate
            if str(template_ir.get("template_id") or "") == "nsfc_defense":
                shell_payload = _enforce_nsfc_content_hierarchy(
                    shell_payload,
                    body_payload,
                    slide_index=index,
                )
            missing_shell_required = [
                slot_id
                for slot_id, slot in shell_contracts.items()
                if bool(slot.get("required", True)) and shell_payload.get(slot_id) in (None, "", [])
            ]
            # Content shells may retain optional source-derived slots underneath
            # the clear region; only the page-title contract remains required.
            required_visible = [
                slot_id
                for slot_id in missing_shell_required
                if slot_id in {"PAGE_TITLE", "TITLE", "KEY_MESSAGE", "PAGE_NUMBER"}
            ]
            if required_visible:
                raise SlideCompileError(
                    f"content shell is missing required payload: {', '.join(required_visible)}"
                )
            shell_payload = _enforce_single_line_slot_contracts(
                shell.get("slots"),
                shell_payload,
                context=f"content shell {shell['shell_id']}",
            )

        compiled.append(
            {
                "page": page,
                "slide_index": index,
                "role": role,
                "grant_role": _scenario_role(raw, role),
                "section": str(raw.get("section") or ""),
                "story_role": str(raw.get("story_role") or raw.get("narrative_role") or ""),
                "shell_id": shell["shell_id"],
                "shell": shell,
                "shell_payload": shell_payload,
                "body_variant_id": variant.get("variant_id") if variant else "",
                "body_variant_reason": variant_reason,
                "body_payload": body_payload,
                "clear_region": variant.get("clear_region") if variant else None,
                "layers": layers,
            }
        )
    return {
        "schema_version": SLIDE_IR_SCHEMA,
        "deck_id": str(deck_plan.get("deck_id") or deck_plan.get("title") or "easyslides-deck"),
        "template_id": template_ir["template_id"],
        "template_source_digest": template_ir["source_digest"],
        "canvas": template_ir["canvas"],
        "slide_count": len(compiled),
        "scenario_audit": scenario_audit,
        "slides": compiled,
    }


def compile_deck(
    deck_plan_path: str | Path,
    *,
    template: str | Path | None = None,
    template_ir_path: str | Path | None = None,
    component_plan_path: str | Path | None = None,
    write: bool = False,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    plan_path = Path(deck_plan_path).resolve()
    deck_plan = read_json(plan_path)
    if template_ir_path:
        template_ir = read_json(Path(template_ir_path).resolve())
    else:
        template_value = template or deck_plan.get("template_id")
        if not template_value:
            raise SlideCompileError("template id or template IR is required")
        template_report = compile_template(template_value)
        template_ir = template_report["template_ir"]
    component_plan = read_json(Path(component_plan_path).resolve()) if component_plan_path else None
    slide_ir = compile_slides(deck_plan, template_ir, component_plan=component_plan)
    target = Path(output_path).resolve() if output_path else plan_path.parent / "slide_ir.json"
    if write:
        write_json(target, slide_ir)
    return {
        "schema_version": SLIDE_COMPILE_REPORT_SCHEMA,
        "status": "pass",
        "template_id": template_ir["template_id"],
        "slide_count": slide_ir["slide_count"],
        "output": str(target),
        "slide_ir": slide_ir,
    }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slot_nodes(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for node in root.iter():
        slot_id = str(node.attrib.get("data-slot") or node.attrib.get("data-slot-id") or "")
        if slot_id and slot_id not in result:
            result[slot_id] = node
    return result


def _remove_node(root: ET.Element, node: ET.Element) -> None:
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parent = parents.get(node)
    if parent is not None:
        parent.remove(node)
    else:
        node.clear()


def _text_lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line for line in str(value or "").splitlines() if line.strip()]


def _set_centered_text(node: ET.Element, value: object) -> None:
    lines = _text_lines(value) or [""]
    for child in list(node):
        node.remove(child)
    node.text = None
    font_size = float(node.attrib.get("font-size") or 24)
    line_height = font_size * float(node.attrib.get("data-pptx-line-height-ratio") or 1.15)
    box_y = float(node.attrib.get("data-pptx-box-y") or max(0, float(node.attrib.get("y") or 0) - font_size))
    box_h = float(node.attrib.get("data-pptx-box-h") or max(font_size * 1.3, line_height * len(lines)))
    first_y = box_y + box_h / 2 - (len(lines) - 1) * line_height / 2 + font_size * 0.35
    x = node.attrib.get("x", "0")
    for index, line in enumerate(lines):
        tspan = ET.SubElement(
            node,
            f"{{{SVG_NS}}}tspan",
            {"x": x, "y": f"{first_y + index * line_height:.2f}"},
        )
        tspan.text = line
    node.set("data-pptx-valign", "middle")
    node.set("data-center-lock", "true")


def _set_square_bullets(root: ET.Element, node: ET.Element, value: object) -> None:
    """Render the content-page central message with template-owned square bullets."""
    lines = _text_lines(value)
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parent = parents.get(node)
    if parent is None or not lines:
        _set_centered_text(node, value)
        return

    box_x = float(node.attrib.get("data-pptx-box-x") or 0)
    box_y = float(node.attrib.get("data-pptx-box-y") or 0)
    box_w = float(node.attrib.get("data-pptx-box-w") or 0)
    box_h = float(node.attrib.get("data-pptx-box-h") or 0)
    if box_w <= 0 or box_h <= 0:
        _set_centered_text(node, value)
        return

    font_size = float(node.attrib.get("font-size") or 28)
    line_height = min(40.0, max(34.0, font_size * 1.2))
    line_gap = 8.0 if len(lines) == 2 else 0.0
    block_height = line_height * len(lines) + line_gap * (len(lines) - 1)
    first_y = box_y + (box_h - block_height) / 2
    text_x = box_x + 36.0
    bullet_size = 16.0
    group = ET.Element(
        f"{{{SVG_NS}}}g",
        {"data-easyslides-generated": "square_bullets", "data-easyslides-slot": "KEY_MESSAGE"},
    )
    text_font = node.attrib.get("font-family") or "Arial, sans-serif"
    text_fill = node.attrib.get("fill") or "#060607"
    for index, line in enumerate(lines):
        row_y = first_y + index * (line_height + line_gap)
        group.append(
            ET.Element(
                f"{{{SVG_NS}}}rect",
                {
                    "x": f"{box_x + 4.0:.2f}",
                    "y": f"{row_y + (line_height - bullet_size) / 2:.2f}",
                    "width": f"{bullet_size:.2f}",
                    "height": f"{bullet_size:.2f}",
                    "fill": "#060607",
                },
            )
        )
        text = ET.Element(
            f"{{{SVG_NS}}}text",
            {
                "x": f"{text_x:.2f}",
                "y": f"{row_y + line_height / 2 + font_size * 0.35:.2f}",
                "text-anchor": "start",
                "font-family": text_font,
                "font-size": f"{font_size:.2f}",
                "fill": text_fill,
                "data-pptx-textbox": "true",
                "data-pptx-measure-text": "T",
                "data-pptx-box-x": f"{text_x:.2f}",
                "data-pptx-box-y": f"{row_y:.2f}",
                "data-pptx-box-w": f"{box_w - 42.0:.2f}",
                "data-pptx-box-h": f"{line_height:.2f}",
                "data-pptx-valign": "middle",
                "data-center-lock": "true",
                "data-pptx-line-height-ratio": "1.100",
                "data-pptx-text-anchor": "start",
                "data-pptx-no-wrap": "true",
            },
        )
        text.text = line
        group.append(text)

    position = list(parent).index(node)
    parent.insert(position, group)
    parent.remove(node)


def _set_evidence_rows(root: ET.Element, node: ET.Element, value: object) -> None:
    """Render newline-delimited evidence as individual, centered text rows."""
    lines = _text_lines(value) or [""]
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parent = parents.get(node)
    if parent is None:
        _set_centered_text(node, value)
        return

    box_x = float(node.attrib.get("data-pptx-box-x") or node.attrib.get("x") or 0)
    box_y = float(node.attrib.get("data-pptx-box-y") or 0)
    box_w = float(node.attrib.get("data-pptx-box-w") or 0)
    box_h = float(node.attrib.get("data-pptx-box-h") or 0)
    if box_w <= 0 or box_h <= 0:
        _set_centered_text(node, value)
        return

    row_count = len(lines)
    outer_gap = 12.0
    row_gap = 12.0 if row_count <= 3 else 8.0
    row_h = (box_h - outer_gap * 2 - row_gap * (row_count - 1)) / row_count
    if row_h < 42:
        _set_centered_text(node, value)
        return

    font_size = min(24.0, max(18.0, row_h * 0.28))
    group = ET.Element(f"{{{SVG_NS}}}g", {"data-easyslides-generated": "evidence_rows"})
    text_font = node.attrib.get("font-family") or "Arial, sans-serif"
    text_fill = node.attrib.get("fill") or "#060607"
    for index, line in enumerate(lines):
        row_y = box_y + outer_gap + index * (row_h + row_gap)
        fill = "#FBF5FC" if index % 2 == 0 else "#FFFFFF"
        accent = "#C00000" if index == row_count - 1 and row_count > 1 else "#751497"
        group.append(
            ET.Element(
                f"{{{SVG_NS}}}rect",
                {
                    "x": f"{box_x + 4:.2f}",
                    "y": f"{row_y:.2f}",
                    "width": f"{box_w - 8:.2f}",
                    "height": f"{row_h:.2f}",
                    "fill": fill,
                    "stroke": "#751497",
                    "stroke-opacity": "0.26",
                },
            )
        )
        group.append(
            ET.Element(
                f"{{{SVG_NS}}}rect",
                {
                    "x": f"{box_x + 4:.2f}",
                    "y": f"{row_y:.2f}",
                    "width": "9",
                    "height": f"{row_h:.2f}",
                    "fill": accent,
                },
            )
        )
        number = ET.Element(
            f"{{{SVG_NS}}}text",
            {
                "x": f"{box_x + 28:.2f}",
                "y": f"{row_y + row_h / 2 + 7:.2f}",
                "font-family": text_font,
                "font-size": "18",
                "font-weight": "700",
                "fill": accent,
                "text-anchor": "start",
            },
        )
        number.text = f"{index + 1:02d}"
        group.append(number)
        line_node = ET.Element(
            f"{{{SVG_NS}}}text",
            {
                "x": f"{box_x + 82:.2f}",
                "y": f"{row_y + row_h / 2 + font_size * 0.35:.2f}",
                "text-anchor": "start",
                "font-family": text_font,
                "font-size": f"{font_size:.2f}",
                "fill": text_fill,
                "data-pptx-textbox": "true",
                "data-pptx-measure-text": "T",
                "data-pptx-box-x": f"{box_x + 82:.2f}",
                "data-pptx-box-y": f"{row_y + 4:.2f}",
                "data-pptx-box-w": f"{box_w - 102:.2f}",
                "data-pptx-box-h": f"{row_h - 8:.2f}",
                "data-pptx-valign": "middle",
                "data-center-lock": "true",
                "data-pptx-line-height-ratio": "1.150",
                "data-pptx-text-anchor": "start",
            },
        )
        line_node.text = line
        group.append(line_node)

    position = list(parent).index(node)
    parent.insert(position, group)
    parent.remove(node)


def _copy_asset(source: Path, assets_dir: Path) -> str:
    target = assets_dir / source.name
    if source.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return f"assets/{target.name}"


def _apply_payload(
    root: ET.Element,
    contracts: object,
    payload: dict[str, Any],
    *,
    source_root: Path,
    assets_dir: Path,
    remove_unbound: bool,
) -> None:
    nodes = _slot_nodes(root)
    contract_map = _slot_contract_map(contracts)
    for slot_id, contract in contract_map.items():
        node = nodes.get(slot_id)
        if node is None:
            raise SlideCompileError(f"SVG is missing declared data-slot {slot_id!r}")
        value = payload.get(slot_id)
        if value in (None, "", []):
            if bool(contract.get("required", True)):
                raise SlideCompileError(f"required SVG slot {slot_id!r} has no payload")
            if remove_unbound:
                _remove_node(root, node)
            continue
        kind = str(contract.get("kind") or node.attrib.get("data-slot-kind") or "text")
        if kind in {"text", "list"}:
            if node.attrib.get("data-easyslides-layout") == "square_bullets":
                _set_square_bullets(root, node, value)
            elif node.attrib.get("data-easyslides-layout") == "evidence_rows":
                _set_evidence_rows(root, node, value)
            elif node.attrib.get("data-easyslides-layout") == "balanced_cjk_stack":
                max_chars = int(node.attrib.get("data-easyslides-wrap-max-chars") or 1)
                max_lines = int(node.attrib.get("data-easyslides-wrap-max-lines") or 1)
                lines = _balanced_cjk_stack_lines(
                    value,
                    max_chars_per_line=max_chars,
                    max_lines=max_lines,
                    context="materialized component",
                    slot_id=str(slot_id),
                )
                node.set("data-pptx-no-wrap", "true")
                _set_centered_text(node, lines)
            else:
                _set_centered_text(node, value)
        elif kind == "image":
            source = Path(str(value))
            if not source.is_absolute():
                source = (source_root / source).resolve()
            if not source.is_file():
                raise SlideCompileError(f"image slot {slot_id!r} references missing file: {source}")
            href = _copy_asset(source, assets_dir)
            node.set("href", href)
            node.set(f"{{{XLINK_NS}}}href", href)
        else:
            raise SlideCompileError(f"unsupported slot kind {kind!r}")


def _component_source(component: dict[str, Any]) -> Path:
    raw = str(component.get("asset_path") or "")
    if not raw:
        raise SlideCompileError(f"component {component.get('asset_id')!r} has no executable asset_path")
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.is_file():
        raise SlideCompileError(f"component asset does not exist: {path}")
    return path


_SVG_URL_REFERENCE = re.compile(r"url\(\s*#([A-Za-z_][A-Za-z0-9_.:-]*)\s*\)")


def _namespace_component_svg_ids(component_root: ET.Element, instance_id: str) -> None:
    """Make every embedded component's internal defs private to its instance.

    Source-derived component SVGs legitimately reuse export-time names such as
    ``ggrad2`` and ``fx1``. Once multiple fragments share a slide those names
    live in one SVG document, so an unrelated component can hijack the shell's
    header fill or filter. Namespace both IDs and their ``url(#...)`` / href
    references before embedding; visual geometry and source styling stay intact.
    """
    safe_instance = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(instance_id)).strip("_") or "component"
    id_map: dict[str, str] = {}
    for node in component_root.iter():
        original = node.attrib.get("id")
        if original:
            id_map[original] = f"es_{safe_instance}_{original}"
    if not id_map:
        return

    for node in component_root.iter():
        original = node.attrib.get("id")
        if original in id_map:
            node.set("id", id_map[original])
        for key, raw_value in tuple(node.attrib.items()):
            value = str(raw_value)
            if value in {f"#{source_id}" for source_id in id_map}:
                node.set(key, f"#{id_map[value[1:]]}")
                continue
            rewritten = _SVG_URL_REFERENCE.sub(
                lambda match: f"url(#{id_map.get(match.group(1), match.group(1))})",
                value,
            )
            if rewritten != value:
                node.set(key, rewritten)


def _append_component(
    slide_root: ET.Element,
    layer: dict[str, Any],
    *,
    assets_dir: Path,
) -> None:
    component = layer["component"]
    source = _component_source(component)
    component_root = ET.parse(source).getroot()
    _apply_payload(
        component_root,
        component.get("slots"),
        _as_dict(layer.get("payload")),
        source_root=source.parent,
        assets_dir=assets_dir,
        remove_unbound=True,
    )
    _namespace_component_svg_ids(component_root, str(layer["instance_id"]))
    frame = layer["frame"]
    view_box = component_root.attrib.get(
        "viewBox",
        f"0 0 {component.get('geometry', {}).get('width', frame['width'])} "
        f"{component.get('geometry', {}).get('height', frame['height'])}",
    )
    try:
        _vx, _vy, source_width, source_height = [float(value) for value in view_box.replace(",", " ").split()]
    except (TypeError, ValueError):
        source_width = float(component.get("geometry", {}).get("width") or frame["width"])
        source_height = float(component.get("geometry", {}).get("height") or frame["height"])
    scale_x = frame["width"] / source_width
    scale_y = frame["height"] / source_height
    if str(layer.get("fit")) != "stretch":
        scale_x = scale_y = min(scale_x, scale_y)
    offset_x = frame["x"] + (frame["width"] - source_width * scale_x) / 2
    offset_y = frame["y"] + (frame["height"] - source_height * scale_y) / 2
    group = ET.Element(
        f"{{{SVG_NS}}}g",
        {
            # Source-derived fragments retain their original non-zero viewBox
            # origins. Compensate here so their internal source coordinates
            # land exactly in the declared component frame.
            "transform": f"translate({offset_x - _vx * scale_x:.6f} {offset_y - _vy * scale_y:.6f}) scale({scale_x:.8f} {scale_y:.8f})",
            "data-easyslides-instance": str(layer["instance_id"]),
            "data-easyslides-asset-id": str(layer["asset_id"]),
            "data-easyslides-id-namespace": f"es_{str(layer['instance_id'])}",
        },
    )
    for child in list(component_root):
        group.append(deepcopy(child))
    slide_root.append(group)


def render_slide_ir_to_svg(
    slide_ir: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    assets_dir = target / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    template_path = ROOT / "templates" / "layouts" / str(slide_ir["template_id"])
    template_assets = template_path / "assets"
    if template_assets.is_dir():
        shutil.copytree(template_assets, assets_dir, dirs_exist_ok=True)
    outputs: list[str] = []
    for slide in slide_ir.get("slides", []):
        shell = slide["shell"]
        shell_path = Path(str(shell["svg_path"]))
        if not shell_path.is_absolute():
            shell_path = (ROOT / shell_path).resolve()
        root = ET.parse(shell_path).getroot()
        _apply_payload(
            root,
            shell.get("slots"),
            _as_dict(slide.get("shell_payload")),
            source_root=shell_path.parent,
            assets_dir=assets_dir,
            remove_unbound=True,
        )
        # clear_region is a layout-only constraint. Rendering it as a white
        # rectangle leaves an accidental visible container in the native PPTX.
        for layer in slide.get("layers", []):
            if isinstance(layer, dict) and layer.get("layer_type") == "component":
                _append_component(root, layer, assets_dir=assets_dir)
        output = target / f"{int(slide['slide_index']):02d}_{slide['shell_id']}.svg"
        ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
        outputs.append(str(output))
    return {
        "schema_version": "easyslides.slide_ir_svg_render.v1",
        "status": "pass",
        "output_dir": str(target),
        "slide_count": len(outputs),
        "svg_files": outputs,
    }


def validate_native_component_bounds(
    pptx_path: str | Path,
    slide_ir: dict[str, Any],
    *,
    tolerance_px: float = 1.5,
) -> dict[str, Any]:
    """Fail when a native component group expands beyond its declared frame.

    SVG roots can hide overflow through a viewBox while DrawingML cannot clip a
    group in the same way. Each appended component is named during conversion,
    so the emitted PPTX can be checked against the resolved Slide IR rather
    than trusting the SVG preview.
    """
    path = Path(pptx_path).resolve()
    if not path.is_file():
        return {
            "status": "fail",
            "checked_component_count": 0,
            "issues": [{"code": "PPTX-COMPONENT-BOUNDS-MISSING", "message": "Native PPTX is missing."}],
        }

    expected_by_slide: dict[int, dict[str, dict[str, float]]] = {}
    for slide in slide_ir.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_index = int(slide.get("slide_index") or 0)
        expected: dict[str, dict[str, float]] = {}
        for layer in slide.get("layers", []):
            if not isinstance(layer, dict) or layer.get("layer_type") != "component":
                continue
            instance_id = str(layer.get("instance_id") or "").strip()
            frame = _frame(layer.get("frame"))
            if instance_id and frame:
                expected[instance_id] = frame
        if expected:
            expected_by_slide[slide_index] = expected

    issues: list[dict[str, Any]] = []
    checked = 0
    tolerance_emu = int(round(tolerance_px * EMU_PER_PX))
    try:
        with ZipFile(path) as archive:
            for slide_index, expected in expected_by_slide.items():
                member = f"ppt/slides/slide{slide_index}.xml"
                if member not in archive.namelist():
                    issues.append(
                        {
                            "code": "PPTX-COMPONENT-BOUNDS-SLIDE-MISSING",
                            "message": "Native PPTX is missing a compiled component slide.",
                            "slide_index": slide_index,
                        }
                    )
                    continue
                root = ET.fromstring(archive.read(member))
                actual: dict[str, tuple[int, int, int, int]] = {}
                for group in root.findall(".//p:grpSp", PPTX_NS):
                    name = group.find("p:nvGrpSpPr/p:cNvPr", PPTX_NS)
                    group_name = str(name.attrib.get("name") or "") if name is not None else ""
                    if not group_name.startswith(COMPONENT_GROUP_PREFIX):
                        continue
                    instance_id = group_name[len(COMPONENT_GROUP_PREFIX):]
                    xfrm = group.find("p:grpSpPr/a:xfrm", PPTX_NS)
                    off = xfrm.find("a:off", PPTX_NS) if xfrm is not None else None
                    ext = xfrm.find("a:ext", PPTX_NS) if xfrm is not None else None
                    if off is None or ext is None:
                        issues.append(
                            {
                                "code": "PPTX-COMPONENT-BOUNDS-GEOMETRY",
                                "message": "Native component group has no drawable bounds.",
                                "slide_index": slide_index,
                                "instance_id": instance_id,
                            }
                        )
                        continue
                    try:
                        actual[instance_id] = (
                            int(off.attrib["x"]),
                            int(off.attrib["y"]),
                            int(ext.attrib["cx"]),
                            int(ext.attrib["cy"]),
                        )
                    except (KeyError, TypeError, ValueError):
                        issues.append(
                            {
                                "code": "PPTX-COMPONENT-BOUNDS-GEOMETRY",
                                "message": "Native component group contains invalid bounds.",
                                "slide_index": slide_index,
                                "instance_id": instance_id,
                            }
                        )

                for instance_id, frame in expected.items():
                    bounds = actual.get(instance_id)
                    if bounds is None:
                        issues.append(
                            {
                                "code": "PPTX-COMPONENT-BOUNDS-MISSING",
                                "message": "Native PPTX did not preserve a component boundary group.",
                                "slide_index": slide_index,
                                "instance_id": instance_id,
                            }
                        )
                        continue
                    checked += 1
                    x, y, width, height = bounds
                    left = int(round(frame["x"] * EMU_PER_PX))
                    top = int(round(frame["y"] * EMU_PER_PX))
                    right = int(round((frame["x"] + frame["width"]) * EMU_PER_PX))
                    bottom = int(round((frame["y"] + frame["height"]) * EMU_PER_PX))
                    if x < left - tolerance_emu or y < top - tolerance_emu or x + width > right + tolerance_emu or y + height > bottom + tolerance_emu:
                        issues.append(
                            {
                                "code": "PPTX-COMPONENT-BOUNDS-OVERFLOW",
                                "message": "Native component geometry exceeds its declared Slide IR frame.",
                                "slide_index": slide_index,
                                "instance_id": instance_id,
                                "frame": frame,
                                "native_bounds_emu": {"x": x, "y": y, "width": width, "height": height},
                            }
                        )
    except (OSError, ET.ParseError) as exc:
        return {
            "status": "fail",
            "checked_component_count": checked,
            "issues": [{"code": "PPTX-COMPONENT-BOUNDS-READ", "message": str(exc)}],
        }

    return {
        "status": "fail" if issues else "pass",
        "checked_component_count": checked,
        "issues": issues,
    }


def render_slide_ir_to_pptx(
    slide_ir: dict[str, Any],
    output_path: str | Path,
    *,
    svg_output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path).resolve()
    svg_dir = Path(svg_output_dir).resolve() if svg_output_dir else output.parent / f"{output.stem}_svg"
    svg_report = render_slide_ir_to_svg(slide_ir, svg_dir)
    try:
        from scripts.svg_to_pptx.pptx_builder import create_pptx_with_native_svg
    except ModuleNotFoundError:  # pragma: no cover
        from svg_to_pptx.pptx_builder import create_pptx_with_native_svg
    ok = create_pptx_with_native_svg(
        [Path(path) for path in svg_report["svg_files"]],
        output,
        canvas_format=str(slide_ir.get("canvas", {}).get("format") or "ppt169"),
        verbose=False,
        transition=None,
        use_compat_mode=False,
        use_native_shapes=True,
        enable_notes=False,
    )
    native_component_bounds = validate_native_component_bounds(output, slide_ir)
    return {
        "schema_version": "easyslides.slide_ir_pptx_render.v1",
        "status": "pass" if ok and output.is_file() and native_component_bounds["status"] == "pass" else "fail",
        "output": str(output),
        "slide_count": slide_ir.get("slide_count", 0),
        "svg_render": svg_report,
        "native_component_bounds": native_component_bounds,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_plan", type=Path)
    parser.add_argument("--template")
    parser.add_argument("--template-ir", type=Path)
    parser.add_argument("--component-plan", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--svg-out", type=Path)
    parser.add_argument("--pptx-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compile_deck(
            args.deck_plan,
            template=args.template,
            template_ir_path=args.template_ir,
            component_plan_path=args.component_plan,
            write=bool(args.out),
            output_path=args.out,
        )
        if args.svg_out:
            report["svg_render"] = render_slide_ir_to_svg(report["slide_ir"], args.svg_out)
        if args.pptx_out:
            report["pptx_render"] = render_slide_ir_to_pptx(
                report["slide_ir"],
                args.pptx_out,
                svg_output_dir=args.svg_out,
            )
            if report["pptx_render"]["status"] != "pass":
                report["status"] = "fail"
    except (OSError, TemplateCompileError, SlideCompileError, ET.ParseError) as exc:
        report = {
            "schema_version": SLIDE_COMPILE_REPORT_SCHEMA,
            "status": "fail",
            "issues": [{"code": "SLIDE-COMPILE", "message": str(exc)}],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Slide compiler: {report['status']} ({report.get('slide_count', 0)} slide(s))")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
