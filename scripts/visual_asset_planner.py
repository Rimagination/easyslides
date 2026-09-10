#!/usr/bin/env python3
"""Plan context-aware visual assets before SVG authoring.

The planner is intentionally conservative: source-linked evidence remains
source-linked, while AI generation is offered for atmosphere, hero pages, and
declared visual placeholders.  It writes a reviewable plan and an image
acquisition manifest that the existing image acquisition layer can execute.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.image_acquisition import detect_imagegen_capability, validate_image_manifest
    from scripts.theme_tokens import DEFAULT_TOKENS, apply_theme_overrides, parse_theme_overrides, resolve_template_tokens
except ModuleNotFoundError:  # pragma: no cover
    from image_acquisition import detect_imagegen_capability, validate_image_manifest
    from theme_tokens import DEFAULT_TOKENS, apply_theme_overrides, parse_theme_overrides, resolve_template_tokens


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "easyslides.visual_asset_plan.v1"
POLICIES = {"source_only", "auto_decorative", "ai_rich"}
HERO_ROLES = {"cover", "ending", "chapter", "transition"}
VALID_ROLES = {"cover", "ending", "chapter", "transition", "content", "toc"}
DEFAULT_LOCAL_FRAME = {"x": 860, "y": 145, "width": 330, "height": 380}


class VisualAssetPlanError(ValueError):
    """Raised when a visual plan cannot be made safely."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise VisualAssetPlanError(f"deck plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VisualAssetPlanError(f"invalid deck plan JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VisualAssetPlanError(f"deck plan must be a JSON object: {path}")
    return value


def _role(slide: Mapping[str, Any]) -> str:
    raw = str(slide.get("visual_role") or slide.get("page_role") or slide.get("role") or "content").strip().lower()
    aliases = {"chapter_divider": "chapter", "section": "chapter", "transition_page": "transition", "closing": "ending"}
    raw = aliases.get(raw, raw)
    return raw if raw in VALID_ROLES else "content"


def _title(slide: Mapping[str, Any]) -> str:
    return str(slide.get("action_title") or slide.get("title") or slide.get("claim") or slide.get("question") or "").strip()


def _has_explicit_asset(slide: Mapping[str, Any]) -> bool:
    for key in ("image_bindings", "image_assets", "images", "image_slots", "evidence_images", "source_images"):
        value = slide.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, Mapping) and value:
            return True
    return bool(slide.get("image_resource_id"))


def _has_declared_image_slot(slide: Mapping[str, Any]) -> bool:
    for key in ("image_placeholder", "image_slot", "visual_placeholder", "image_frame", "image_area"):
        if slide.get(key):
            return True
    shape = str(slide.get("content_shape") or "").lower()
    return any(token in shape for token in ("figure", "image", "illustration", "photo", "hero"))


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "allow", "enabled", "decorative"}


def _image_frame(slide: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a declared local-image frame without inventing evidence geometry."""
    for key in ("image_frame", "image_area", "visual_frame", "visual_placeholder"):
        value = slide.get(key)
        if not isinstance(value, Mapping):
            continue
        frame = value.get("frame") if isinstance(value.get("frame"), Mapping) else value
        if all(name in frame for name in ("x", "y", "width", "height")):
            return {name: frame[name] for name in ("x", "y", "width", "height")}
    return None


def _generation_opt_in(slide: Mapping[str, Any]) -> bool:
    for key in (
        "generate_visual",
        "generate_decorative_visual",
        "allow_ai_visual",
        "ai_visual",
        "visual_opportunity",
        "hero_local_visual",
    ):
        if _truthy(slide.get(key)):
            return True
    return False


def _large_visual_opportunity(slide: Mapping[str, Any]) -> bool:
    """Recognize an intentional visual surface without treating evidence as art."""
    for key in (
        "large_color_block",
        "large_color_area",
        "dominant_color_block",
        "has_large_color_blocks",
        "replaceable_visual_surface",
    ):
        if _truthy(slide.get(key)):
            return True
    return False


def _template_visual_policy(template_dir: str | Path | None) -> dict[str, Any]:
    """Load optional template-specific image opportunities.

    Templates remain usable without this sidecar.  When present, it supplies
    safe frames and explicit opt-ins for decorative hero elements; it never
    authorizes replacing source evidence.
    """
    if not template_dir:
        return {}
    path = Path(template_dir)
    if not path.is_absolute():
        direct = (ROOT / path).resolve()
        path = direct if direct.is_dir() else (ROOT / "templates" / "layouts" / path).resolve()
    policy_path = path / "visual_asset_policy.json"
    if not policy_path.is_file():
        return {}
    try:
        value = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _role_visual_policy(policy: Mapping[str, Any], role: str) -> dict[str, Any]:
    roles = policy.get("roles") if isinstance(policy.get("roles"), Mapping) else {}
    value = roles.get(role) if isinstance(roles, Mapping) else None
    return dict(value) if isinstance(value, Mapping) else {}


def _factual_evidence(slide: Mapping[str, Any]) -> bool:
    raw = json.dumps(slide, ensure_ascii=False).lower()
    return any(token in raw for token in ("figure", "table", "dataset", "experiment", "microscopy", "screenshot", "evidence"))


def _safe_area(slide: Mapping[str, Any], role: str) -> dict[str, Any]:
    declared = slide.get("text_safe_area") or slide.get("safe_area")
    if isinstance(declared, Mapping):
        return deepcopy(dict(declared))
    if isinstance(declared, str) and declared.strip():
        return {"side": declared.strip().lower()}
    if role == "chapter":
        return {"side": "left", "box": {"x": 300, "y": 220, "width": 760, "height": 240}}
    if role == "cover":
        return {"side": "center", "box": {"x": 140, "y": 235, "width": 1000, "height": 300}}
    if role == "ending":
        return {"side": "center", "box": {"x": 180, "y": 220, "width": 920, "height": 250}}
    return {"side": "left", "box": {"x": 80, "y": 170, "width": 600, "height": 300}}


def _theme_tokens(deck_plan: Mapping[str, Any], template_dir: str | Path | None, palette_id: str | None = None) -> dict[str, str]:
    explicit = deck_plan.get("theme_tokens") or deck_plan.get("theme_palette")
    if isinstance(explicit, Mapping):
        return apply_theme_overrides(DEFAULT_TOKENS, explicit)
    if template_dir:
        try:
            selected_palette = palette_id
            if not isinstance(selected_palette, str) or not selected_palette.strip():
                selected_palette = deck_plan.get("palette_id")
            if not isinstance(selected_palette, str) or not selected_palette.strip():
                selected_palette = deck_plan.get("theme_palette") if isinstance(deck_plan.get("theme_palette"), str) else None
            return dict(resolve_template_tokens(template_dir, selected_palette)["tokens"])
        except (OSError, ValueError):
            pass
    return dict(DEFAULT_TOKENS)


def _prompt_for(slide: Mapping[str, Any], role: str, tokens: Mapping[str, str], safe_area: Mapping[str, Any]) -> str:
    title = _title(slide) or "the research topic"
    protagonist = str(slide.get("visual_protagonist") or slide.get("visual_subject") or "a restrained conceptual visual").strip()
    rendering = str(slide.get("image_rendering") or "editorial academic illustration").strip()
    palette = f"primary {tokens.get('primary')}, accent {tokens.get('accent')}, background family {tokens.get('background')}"
    side = str(safe_area.get("side") or "left")
    mood = "spacious and reflective" if role == "ending" else "clear and anticipatory" if role in {"chapter", "transition"} else "calm and authoritative"
    return (
        f"Create a 16:9 {rendering} for a {role} page about {title}. "
        f"The visual subject is {protagonist}. Use {palette} as color guidance and a {mood} mood. "
        f"Keep the {side} side visually quiet for editable slide text. "
        "No visible words, letters, numbers, logos, trademarks, watermarks, charts, or fake citations; "
        "avoid dense detail behind the text area."
    )


def plan_visual_assets(
    deck_plan: Mapping[str, Any],
    *,
    template_dir: str | Path | None = None,
    policy: str = "auto_decorative",
    imagegen_available: bool | None = None,
    palette_id: str | None = None,
) -> dict[str, Any]:
    if policy not in POLICIES:
        raise VisualAssetPlanError(f"policy must be one of {sorted(POLICIES)}")
    if imagegen_available is None:
        capability = detect_imagegen_capability()
    else:
        capability = detect_imagegen_capability(host_native_override=bool(imagegen_available))
        capability["available"] = bool(imagegen_available)
        capability["mode"] = "host-native" if imagegen_available else "manual"
        capability["reason"] = "explicit_imagegen_override"
    imagegen_available = bool(capability["available"])
    tokens = _theme_tokens(deck_plan, template_dir, palette_id)
    template_policy = _template_visual_policy(template_dir)
    slides = deck_plan.get("slides")
    if not isinstance(slides, list):
        raise VisualAssetPlanError("deck_plan.slides must be a list")

    items: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for index, raw in enumerate(slides):
        if not isinstance(raw, Mapping):
            continue
        slide = dict(raw)
        role = _role(slide)
        title = _title(slide)
        explicit_asset = _has_explicit_asset(slide)
        declared_slot = _has_declared_image_slot(slide)
        factual = _factual_evidence(slide)
        locked = bool(slide.get("background_locked") or slide.get("template_background_locked"))
        role_policy = _role_visual_policy(template_policy, role)
        safe_area = _safe_area(slide, role)
        if not (slide.get("text_safe_area") or slide.get("safe_area")):
            policy_background = role_policy.get("background")
            if isinstance(policy_background, Mapping) and isinstance(policy_background.get("safe_area"), Mapping):
                safe_area = deepcopy(dict(policy_background["safe_area"]))
        asset_decisions: list[str] = []
        decision = "none"
        reason = "no eligible visual opportunity"
        if explicit_asset:
            decision = "preserve_source"
            reason = "user or source material already declares an asset"
        elif factual:
            decision = "source_only"
            reason = "page appears evidence-bearing; do not invent a substitute"
        elif locked:
            decision = "preserve_template"
            reason = "template explicitly locks its visual background"
        else:
            background_policy = role_policy.get("background")
            if not isinstance(background_policy, Mapping):
                background_policy = {}
            local_policy = role_policy.get("local_illustration")
            if not isinstance(local_policy, Mapping):
                local_policy = {}
            hero_enabled = (
                role in HERO_ROLES
                and policy != "source_only"
                and background_policy.get("enabled", True) is not False
            )
            local_requested = declared_slot or _generation_opt_in(slide)
            if role in HERO_ROLES and policy == "ai_rich" and local_policy.get("enabled"):
                local_requested = True
            if _large_visual_opportunity(slide) and policy == "ai_rich":
                local_requested = True
            if hero_enabled:
                asset_decisions.append("hero_background")
                reason = f"{role} page benefits from a thematic visual"
            if local_requested and policy != "source_only":
                # Local AI art is decorative by contract. A factual page must
                # have been classified above as source_only before reaching it.
                local_frame = _image_frame(slide) or local_policy.get("frame")
                if local_frame or role in HERO_ROLES:
                    asset_decisions.append("local_illustration")
                    reason = "page declares a decorative visual opportunity"
            if asset_decisions:
                decision = "+".join(asset_decisions)

        decisions.append({
            "page": str(slide.get("page") or f"P{index + 1:02d}"),
            "role": role,
            "decision": decision,
            "reason": reason,
            "imagegen_available": bool(imagegen_available),
            "capability_mode": capability.get("mode"),
            "asset_decisions": asset_decisions,
        })
        if not asset_decisions:
            continue
        page_id = str(slide.get("page") or f"P{index + 1:02d}").lower()
        for asset_decision in asset_decisions:
            is_background = asset_decision == "hero_background"
            suffix = "background" if is_background else "illustration"
            resource_id = f"{page_id}_{suffix}"
            filename = f"{resource_id}.png"
            item: dict[str, Any] = {
                "id": resource_id,
                "page": str(slide.get("page") or f"P{index + 1:02d}"),
                "filename": filename,
                "purpose": f"{role.title()} {'background' if is_background else 'decorative illustration'} for {title or 'the deck'}",
                "slide_role": role if role in {"cover", "ending", "chapter", "transition", "content"} else "chapter",
                "page_role": "hero_page" if is_background else "local",
                "asset_role": "background" if is_background else "illustration",
                "visual_use": "decorative_background" if is_background else "decorative_illustration",
                "source_policy": "generated_decorative_only",
                "text_policy": "none",
                "aspect_ratio": "16:9" if is_background else str(slide.get("image_aspect_ratio") or "4:5"),
                "image_size": "2K",
                "prompt": _prompt_for(slide, role, tokens, safe_area)
                + (" This is decorative atmosphere only, never scientific evidence." if not is_background else ""),
                "alt_text": f"Thematic {role} {'background' if is_background else 'decorative illustration'} for {title or 'the presentation'}",
                "safe_area": safe_area,
                "status": "Pending",
            }
            if is_background:
                item["background"] = {
                    "fit": "slice",
                    "text_tone": "auto",
                    "contrast_target": 4.5,
                    "scrim_fill": tokens.get("scrim_light", "#FFFFFF"),
                    "scrim_opacity": 0.18,
                }
                readability_mode = str(background_policy.get("readability_mode") or "").strip().lower()
                if readability_mode:
                    item["background"]["readability_mode"] = readability_mode
                declared_text_tone = str(background_policy.get("text_tone") or "").strip().lower()
                if declared_text_tone:
                    item["background"]["text_tone"] = declared_text_tone
                text_color_role = str(background_policy.get("text_color_role") or "").strip()
                if text_color_role and tokens.get(text_color_role):
                    item["background"]["text_color"] = tokens[text_color_role]
                elif background_policy.get("text_color"):
                    item["background"]["text_color"] = str(background_policy["text_color"])
            else:
                frame = _image_frame(slide) or local_policy.get("frame")
                if frame is None and role in HERO_ROLES:
                    frame = dict(DEFAULT_LOCAL_FRAME)
                if frame is not None:
                    item["placement"] = {"frame": dict(frame), "fit": "contain", "text_tone": "auto"}
                    layer = str(local_policy.get("layer") or "").strip().lower()
                    if layer:
                        item["placement"]["layer"] = layer
            items.append(item)

    manifest = {
        "schema_version": "easyslides.image_resources.v1",
        "project": str(deck_plan.get("deck_id") or deck_plan.get("title") or "easyslides-deck"),
        "deck_rendering": str(deck_plan.get("image_rendering") or "editorial academic illustration"),
        "deck_palette": tokens,
        "acquisition": {"path": "auto", "imagegen_available": bool(imagegen_available)},
        "items": items or [{
            "id": "no_visual_assets",
            "filename": "no_visual_assets.png",
            "purpose": "No generated visual assets requested",
            "slide_role": "content",
            "page_role": "local",
            "asset_role": "decorative",
            "text_policy": "none",
            "aspect_ratio": "16:9",
            "prompt": "No generation requested.",
            "status": "Needs-Manual",
        }],
    }
    # A plan with no assets should still be inspectable, but the downstream
    # acquisition validator requires at least one row.  Consumers use the
    # explicit `planned_count` to distinguish this sentinel from a request.
    manifest["planned_count"] = len(items)
    manifest = validate_image_manifest(manifest, source="visual asset plan")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "policy": policy,
        "imagegen_available": bool(imagegen_available),
        "capability": capability,
        "theme_tokens": tokens,
        "decisions": decisions,
        "planned_count": len(items),
        "items": items,
        "image_manifest": manifest,
    }


def write_visual_plan(
    deck_plan_path: str | Path,
    output_dir: str | Path,
    *,
    template_dir: str | Path | None = None,
    policy: str = "auto_decorative",
    imagegen_available: bool | None = None,
    palette_id: str | None = None,
    write_deck_plan: bool = False,
    theme_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    deck_path = Path(deck_plan_path).resolve()
    deck_plan = _read_json(deck_path)
    if theme_overrides:
        deck_plan["theme_tokens"] = {
            **(deck_plan.get("theme_tokens") if isinstance(deck_plan.get("theme_tokens"), Mapping) else {}),
            **dict(theme_overrides),
        }
    result = plan_visual_assets(
        deck_plan,
        template_dir=template_dir,
        policy=policy,
        imagegen_available=imagegen_available,
        palette_id=palette_id,
    )
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "visual_asset_plan.json"
    manifest_path = out / "image_prompts.json"
    plan_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(result["image_manifest"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if write_deck_plan:
        updated = deepcopy(deck_plan)
        updated["visual_asset_plan"] = str(plan_path.relative_to(deck_path.parent))
        updated["image_manifest"] = str(manifest_path.relative_to(deck_path.parent))
        for decision, slide in zip(result["decisions"], [row for row in updated.get("slides", []) if isinstance(row, dict)]):
            page = str(decision["page"])
            matching = [
                item for item in result["items"]
                if str(item.get("page") or "") == page
                or str(item.get("id") or "").startswith(page.lower() + "_")
            ]
            if matching:
                existing = slide.get("image_bindings") if isinstance(slide.get("image_bindings"), list) else []
                existing_ids = {
                    str(binding.get("resource_id") or binding.get("id") or "")
                    for binding in existing
                    if isinstance(binding, Mapping)
                }
                generated_bindings = [
                    {
                        "resource_id": str(item["id"]),
                        **({"placement": dict(item["placement"])} if isinstance(item.get("placement"), Mapping) else {}),
                    }
                    for item in matching
                    if str(item["id"]) not in existing_ids
                ]
                if existing or generated_bindings:
                    slide["image_bindings"] = existing + generated_bindings
                background = next((item for item in matching if item.get("asset_role") == "background"), None)
                slide["image_resource_id"] = str((background or matching[0])["id"])
        deck_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["paths"] = {"plan": str(plan_path), "manifest": str(manifest_path), "deck_plan": str(deck_path)}
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan context-aware EasySlides visual assets.")
    parser.add_argument("deck_plan")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--template-dir", default=None)
    parser.add_argument("--palette", default=None, help="Selected palette id from the template catalog.")
    parser.add_argument("--policy", choices=sorted(POLICIES), default="auto_decorative")
    imagegen = parser.add_mutually_exclusive_group()
    imagegen.add_argument("--imagegen", dest="imagegen", action="store_true")
    imagegen.add_argument("--no-imagegen", dest="imagegen", action="store_false")
    parser.set_defaults(imagegen=None)
    parser.add_argument("--write-deck-plan", action="store_true")
    parser.add_argument("--theme-token", action="append", default=[], metavar="ROLE=#RRGGBB", help="Override a semantic theme role; repeat for multiple roles.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = write_visual_plan(
            args.deck_plan,
            args.out_dir,
            template_dir=args.template_dir,
            policy=args.policy,
            imagegen_available=args.imagegen,
            palette_id=args.palette,
            write_deck_plan=args.write_deck_plan,
            theme_overrides=parse_theme_overrides(args.theme_token),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Visual plan: pass ({result['planned_count']} asset(s))")
        return 0
    except (OSError, VisualAssetPlanError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
