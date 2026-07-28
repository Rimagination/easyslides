"""Adapter for selecting verified PPT Master body variants."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.body_variant_contract import normalize_component_refs, validate_body_variant_contract
except ModuleNotFoundError:  # pragma: no cover
    from body_variant_contract import normalize_component_refs, validate_body_variant_contract


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
DECK_BODY_VARIANT_REPORT_VERSION = "easyslides.deck_body_variant_report.v1"


@dataclass(frozen=True)
class BodyVariant:
    variant_id: str
    best_for: str
    layout: str
    slots: tuple[str, ...]
    slot_contracts: tuple[dict[str, Any], ...]
    component_refs: tuple[dict[str, Any], ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class BodyVariantRegistry:
    template_id: str
    template_dir: Path
    primary_variant: str
    content_area: dict[str, Any]
    selection_policy: dict[str, Any]
    variants: dict[str, BodyVariant]


@dataclass(frozen=True)
class BodyVariantSelection:
    variant: BodyVariant
    reason: str
    source: str
    registry: BodyVariantRegistry
    tokens: "TemplateTokens"
    required_gates: tuple[str, ...]


@dataclass(frozen=True)
class BodyVariantPayloadContract:
    status: str
    selection: BodyVariantSelection
    payload: dict[str, Any]
    missing_slots: tuple[str, ...]
    extra_slots: tuple[str, ...]
    component_refs: tuple[dict[str, Any], ...]
    issues: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class TemplateTokens:
    palette_id: str
    colors: dict[str, str]
    text_fit_policy: dict[str, Any]
    raw: dict[str, Any]


_SHAPE_KEYWORDS = {
    "table": ("table", "matrix"),
    "matrix": ("table", "matrix"),
    "question_card": ("card", "option", "question", "parallel"),
    "answer_card": ("card", "answer", "parallel"),
    "card": ("card", "parallel"),
    "cards": ("card", "parallel"),
    "figure": ("figure", "image", "exhibit"),
    "image": ("figure", "image", "exhibit"),
    "image_grid": ("image_grid", "image", "panel"),
    "workflow": ("workflow", "process", "timeline", "step", "phase"),
    "process": ("workflow", "process", "timeline", "step", "phase"),
    "timeline": ("timeline", "process", "step"),
    "comparison": ("compare", "comparison", "versus", "before", "after"),
}
REQUIRED_GATES = (
    "body_variant_contract",
    "body_variant_component_contract",
    "template_tokens",
    "text_capacity",
    "svg_quality_checker",
    "preview_render",
    "pptx_roundtrip",
    "validate_pptx_text_layout",
)


def resolve_template_dir(template: str | Path) -> Path:
    path = Path(template)
    if path.is_dir():
        return path
    return LAYOUTS_ROOT / str(template)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _variant_slot_contracts(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    rows: list[dict[str, Any]] = []
    for slot in value:
        if isinstance(slot, str) and slot:
            rows.append({"slot_id": slot, "kind": "text", "required": True})
        elif isinstance(slot, dict):
            slot_id = str(slot.get("slot_id") or slot.get("slot") or slot.get("id") or "")
            if not slot_id:
                continue
            row = dict(slot)
            row["slot_id"] = slot_id
            row.setdefault("kind", "text")
            row.setdefault("required", True)
            rows.append(row)
    return tuple(rows)


def load_body_variant_registry(template: str | Path) -> BodyVariantRegistry:
    """Load verified body variants from a template's body_variants.json."""
    template_dir = resolve_template_dir(template)
    payload = _read_json(template_dir / "body_variants.json")
    template_id = str(payload.get("template_id") or template_dir.name)
    variants: dict[str, BodyVariant] = {}
    for item in payload.get("variants", []):
        if not isinstance(item, dict) or not item.get("variant_id"):
            continue
        variant_id = str(item["variant_id"])
        slot_contracts = _variant_slot_contracts(item.get("slots"))
        variants[variant_id] = BodyVariant(
            variant_id=variant_id,
            best_for=str(item.get("best_for") or ""),
            layout=str(item.get("layout") or item.get("layout_hint") or ""),
            slots=tuple(str(slot["slot_id"]) for slot in slot_contracts),
            slot_contracts=slot_contracts,
            component_refs=tuple(normalize_component_refs(item, template_id)),
            raw=item,
        )
    if not variants:
        raise ValueError(f"{template_dir / 'body_variants.json'} defines no variants")
    primary = str(payload.get("primary_variant") or next(iter(variants)))
    if primary not in variants:
        primary = next(iter(variants))
    policy = payload.get("selection_policy")
    if not isinstance(policy, dict):
        policy = {"default": payload.get("selection_rule", "")}
    content_area = payload.get("content_area") if isinstance(payload.get("content_area"), dict) else {}
    return BodyVariantRegistry(
        template_id=template_id,
        template_dir=template_dir,
        primary_variant=primary,
        content_area=content_area,
        selection_policy=policy,
        variants=variants,
    )


def load_template_tokens(template: str | Path, palette_id: str | None = None) -> TemplateTokens:
    """Load template-owned visual and text-fit tokens for variant rendering."""
    template_dir = resolve_template_dir(template)
    layouts = _read_json(template_dir / "layouts.json")
    text_fit_policy = layouts.get("text_fit_policy") if isinstance(layouts.get("text_fit_policy"), dict) else {}
    palette_path = template_dir / "theme_palettes.json"
    colors: dict[str, str] = {}
    selected_palette = palette_id or ""
    raw: dict[str, Any] = {
        "style_system": layouts.get("style_system", ""),
        "text_fit_policy": text_fit_policy,
    }
    if palette_path.exists():
        palettes = _read_json(palette_path)
        selected_palette = selected_palette or str(palettes.get("default_palette") or "")
        palette = (palettes.get("palettes") or {}).get(selected_palette)
        if isinstance(palette, dict) and isinstance(palette.get("colors"), dict):
            colors = {str(key): str(value) for key, value in palette["colors"].items()}
        raw["theme_palettes"] = palettes
    elif isinstance(layouts.get("colors"), dict):
        colors = {str(key): str(value) for key, value in layouts["colors"].items()}
    return TemplateTokens(
        palette_id=selected_palette,
        colors=colors,
        text_fit_policy=text_fit_policy,
        raw=raw,
    )


def _variant_id_from_layout_id(layout_id: object, registry: BodyVariantRegistry) -> str | None:
    if not isinstance(layout_id, str) or not layout_id.strip():
        return None
    value = layout_id.strip()
    candidates = [value, value.rsplit("/", 1)[-1], value.rsplit(":", 1)[-1]]
    for candidate in candidates:
        if candidate in registry.variants:
            return candidate
    return None


def _variant_score(variant: BodyVariant, keywords: tuple[str, ...]) -> int:
    haystack = " ".join(
        [
            variant.variant_id,
            variant.best_for,
            variant.layout,
            " ".join(variant.slots),
            json.dumps(variant.raw, ensure_ascii=False),
        ]
    ).lower()
    return sum(1 for keyword in keywords if keyword.lower() in haystack)


def _shape_match(content_shape: object, registry: BodyVariantRegistry) -> str | None:
    if not isinstance(content_shape, str) or not content_shape.strip():
        return None
    shape = content_shape.strip().lower()
    keywords = _SHAPE_KEYWORDS.get(shape, (shape,))
    scored = [
        (_variant_score(variant, keywords), variant.variant_id)
        for variant in registry.variants.values()
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return None


def select_body_variant(template: str | Path, slide: dict[str, Any]) -> BodyVariantSelection:
    """Select a verified body variant for a slide contract."""
    registry = load_body_variant_registry(template)
    tokens = load_template_tokens(template, str(slide.get("palette_id") or "") or None)
    explicit = _variant_id_from_layout_id(slide.get("layout_id"), registry)
    if explicit:
        return BodyVariantSelection(
            variant=registry.variants[explicit],
            reason="explicit_layout_id",
            source="body_variants.json",
            registry=registry,
            tokens=tokens,
            required_gates=REQUIRED_GATES,
        )

    shape = _shape_match(slide.get("content_shape") or slide.get("evidence_shape"), registry)
    if shape:
        return BodyVariantSelection(
            variant=registry.variants[shape],
            reason="content_shape",
            source="body_variants.json",
            registry=registry,
            tokens=tokens,
            required_gates=REQUIRED_GATES,
        )

    return BodyVariantSelection(
        variant=registry.variants[registry.primary_variant],
        reason="primary_fallback",
        source="body_variants.json",
        registry=registry,
        tokens=tokens,
        required_gates=REQUIRED_GATES,
    )


def _slot_payload(slide: dict[str, Any]) -> dict[str, Any]:
    payload = slide.get("slot_payload")
    if payload is None:
        payload = slide.get("body_payload", {})
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items()}
    return {}


def validate_body_variant_payload(template: str | Path, slide: dict[str, Any]) -> BodyVariantPayloadContract:
    """Validate payload keys and the selected variant's component composition."""
    selection = select_body_variant(template, slide)
    payload = _slot_payload(slide)
    declared = selection.variant.slots
    required = tuple(
        str(slot["slot_id"])
        for slot in selection.variant.slot_contracts
        if bool(slot.get("required", True))
    )
    provided = tuple(payload)
    missing = tuple(slot for slot in required if slot not in payload)
    extra = tuple(slot for slot in provided if slot not in declared)
    issues: list[dict[str, str]] = []
    if missing:
        issues.append(
            {
                "code": "BODY-VARIANT-MISSING-SLOT",
                "message": f"payload missing declared slot(s): {', '.join(missing)}",
                "path": "slot_payload",
            }
        )
    if extra:
        issues.append(
            {
                "code": "BODY-VARIANT-EXTRA-SLOT",
                "message": f"payload contains undeclared slot(s): {', '.join(extra)}",
                "path": "slot_payload",
            }
        )
    component_report = validate_body_variant_contract(
        selection.registry.template_dir,
        variant_id=selection.variant.variant_id,
    )
    for item in component_report.get("issues", []):
        if not isinstance(item, dict):
            continue
        issues.append(
            {
                "code": str(item.get("code") or "BODY-VARIANT-COMPONENT"),
                "message": str(item.get("message") or "invalid component reference"),
                "path": str(item.get("path") or "component_refs"),
            }
        )
    return BodyVariantPayloadContract(
        status="pass" if not issues else "fail",
        selection=selection,
        payload=payload,
        missing_slots=missing,
        extra_slots=extra,
        component_refs=selection.variant.component_refs,
        issues=tuple(issues),
    )


def _plan_template_id(plan: dict[str, Any]) -> str | None:
    template_id = plan.get("template_id")
    if isinstance(template_id, str) and template_id.strip():
        return template_id.strip()
    template = plan.get("template")
    if isinstance(template, dict):
        template_id = template.get("template_id") or template.get("id")
        if isinstance(template_id, str) and template_id.strip():
            return template_id.strip()
    return None


def _template_from_layout_id(layout_id: object, repo_root: Path) -> str | None:
    if not isinstance(layout_id, str) or "/" not in layout_id:
        return None
    candidate = layout_id.split("/", 1)[0].strip()
    if not candidate:
        return None
    template_dir = repo_root / "templates" / "layouts" / candidate
    if (template_dir / "body_variants.json").exists():
        return candidate
    return None


def _body_variant_issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _template_dir_for_deck(repo_root: Path, template_id: str) -> Path:
    return repo_root / "templates" / "layouts" / template_id


def validate_deck_body_variants(
    plan: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    """Validate every template-scoped deck-plan slide against body variants."""
    repo = Path(repo_root).resolve() if repo_root else ROOT
    issues: list[dict[str, str]] = []
    slide_reports: list[dict[str, Any]] = []
    slides = plan.get("slides") if isinstance(plan, dict) else None
    if not isinstance(slides, list):
        return {
            "schema_version": DECK_BODY_VARIANT_REPORT_VERSION,
            "status": "skipped",
            "issue_count": 0,
            "issues": [],
            "slide_count": 0,
            "checked_slide_count": 0,
            "slides": [],
        }

    plan_template = _plan_template_id(plan)
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        path = f"slides[{index}]"
        slide_template = slide.get("template_id")
        if not isinstance(slide_template, str) or not slide_template.strip():
            slide_template = _template_from_layout_id(slide.get("layout_id"), repo) or plan_template
        if not isinstance(slide_template, str) or not slide_template.strip():
            continue

        template_dir = _template_dir_for_deck(repo, slide_template.strip())
        if not (template_dir / "body_variants.json").exists():
            issues.append(
                _body_variant_issue(
                    "BODY-VARIANT-TEMPLATE",
                    f"template {slide_template!r} has no body_variants.json",
                    f"{path}.template_id",
                )
            )
            continue

        try:
            contract = validate_body_variant_payload(template_dir, slide)
        except Exception as exc:
            issues.append(
                _body_variant_issue(
                    "BODY-VARIANT-CONTRACT",
                    f"cannot validate body variant payload: {exc}",
                    path,
                )
            )
            continue

        slide_report = {
            "path": path,
            "page": str(slide.get("page") or ""),
            "template_id": contract.selection.registry.template_id,
            "variant_id": contract.selection.variant.variant_id,
            "reason": contract.selection.reason,
            "status": contract.status,
            "declared_slots": list(contract.selection.variant.slots),
            "provided_slots": list(contract.payload),
            "component_refs": list(contract.component_refs),
            "palette_id": contract.selection.tokens.palette_id,
            "required_gates": list(contract.selection.required_gates),
            "issues": list(contract.issues),
        }
        slide_reports.append(slide_report)
        for item in contract.issues:
            issues.append(
                _body_variant_issue(
                    item["code"],
                    item["message"],
                    f"{path}.{item.get('path', 'slot_payload')}",
                )
            )

    status = "fail" if issues else "pass" if slide_reports else "skipped"
    return {
        "schema_version": DECK_BODY_VARIANT_REPORT_VERSION,
        "status": status,
        "issue_count": len(issues),
        "issues": issues,
        "slide_count": len(slides),
        "checked_slide_count": len(slide_reports),
        "slides": slide_reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", help="Template id or template directory.")
    parser.add_argument("--layout-id", help="Explicit layout id from deck_plan.json.")
    parser.add_argument("--content-shape", help="Semantic content shape, such as table or figure.")
    parser.add_argument("--slot-payload-json", help="JSON object keyed by declared body variant slot ids.")
    args = parser.parse_args(argv)

    slide: dict[str, Any] = {"layout_id": args.layout_id, "content_shape": args.content_shape}
    if args.slot_payload_json:
        try:
            slot_payload = json.loads(args.slot_payload_json)
        except json.JSONDecodeError as exc:
            parser.error(f"--slot-payload-json must be valid JSON: {exc}")
        if not isinstance(slot_payload, dict):
            parser.error("--slot-payload-json must decode to a JSON object")
        slide["slot_payload"] = slot_payload

    selection = select_body_variant(args.template, slide)
    contract = validate_body_variant_payload(args.template, slide) if args.slot_payload_json else None
    print(
        json.dumps(
            {
                "template_id": selection.registry.template_id,
                "variant_id": selection.variant.variant_id,
                "reason": selection.reason,
                "source": selection.source,
                "slots": list(selection.variant.slots),
                "component_refs": list(selection.variant.component_refs),
                "content_area": selection.registry.content_area,
                "palette_id": selection.tokens.palette_id,
                "colors": selection.tokens.colors,
                "required_gates": list(selection.required_gates),
                **(
                    {
                        "payload_contract": {
                            "status": contract.status,
                            "missing_slots": list(contract.missing_slots),
                            "extra_slots": list(contract.extra_slots),
                            "component_refs": list(contract.component_refs),
                            "issues": list(contract.issues),
                        }
                    }
                    if contract
                    else {}
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if contract is None or contract.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
