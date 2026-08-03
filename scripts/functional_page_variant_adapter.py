"""Select and validate cover/TOC/transition/ending source-page variants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.named_slot_geometry import validate_named_text_slots
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from named_slot_geometry import validate_named_text_slots


def load_registry(template: str | Path) -> dict[str, Any]:
    path = Path(template) / "functional_page_variants.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_functional_variant_geometry(
    template: str | Path,
    variant: dict[str, Any],
) -> dict[str, Any]:
    """Validate the named text-slot geometry before a variant is selected."""
    template_dir = Path(template)
    preview_svg = str(variant.get("preview_svg") or "").strip()
    if not preview_svg:
        return {
            "status": "fail",
            "variant_id": str(variant.get("variant_id") or ""),
            "issues": [{"code": "FUNCTIONAL-VARIANT-SVG", "message": "variant has no preview_svg"}],
        }
    svg_path = template_dir / preview_svg
    if not svg_path.is_file():
        return {
            "status": "fail",
            "variant_id": str(variant.get("variant_id") or ""),
            "preview_svg": preview_svg,
            "issues": [{"code": "FUNCTIONAL-VARIANT-SVG", "message": f"missing preview SVG: {svg_path}"}],
        }
    allowed_overlaps = {
        frozenset(str(slot).strip() for slot in pair)
        for pair in variant.get("allowed_slot_overlaps", [])
        if isinstance(pair, (list, tuple)) and len(pair) == 2 and all(str(slot).strip() for slot in pair)
    }
    report = validate_named_text_slots(svg_path, allowed_overlaps=allowed_overlaps)
    report["variant_id"] = str(variant.get("variant_id") or "")
    report["preview_svg"] = preview_svg
    return report


def validate_functional_variant_registry(template: str | Path) -> dict[str, Any]:
    """Validate every declared functional-page variant in a template."""
    registry = load_registry(template)
    reports: list[dict[str, Any]] = []
    for role, group in (registry.get("groups") or {}).items():
        if not isinstance(group, dict):
            continue
        for variant in group.get("variants", []):
            if not isinstance(variant, dict):
                continue
            report = validate_functional_variant_geometry(template, variant)
            report["role"] = role
            reports.append(report)
    issues = [
        {"role": report.get("role"), "variant_id": report.get("variant_id"), **issue}
        for report in reports
        for issue in report.get("issues", [])
    ]
    return {
        "schema_version": "easyslides.functional_page_variant_qa.v1",
        "status": "pass" if not issues else "fail",
        "template": str(template),
        "variant_count": len(reports),
        "issue_count": len(issues),
        "issues": issues,
        "variants": reports,
    }


def _assert_variant_geometry(template: str | Path, variant: dict[str, Any]) -> None:
    report = validate_functional_variant_geometry(template, variant)
    if report.get("status") == "pass":
        return
    details = "; ".join(
        str(item.get("message") or item.get("code") or "geometry issue")
        for item in report.get("issues", [])[:4]
    )
    raise ValueError(
        f"functional variant {variant.get('variant_id')!r} failed named-slot geometry QA: {details}"
    )


def select_functional_variant(
    template: str | Path,
    role: str,
    variant_id: str | None = None,
) -> dict[str, Any]:
    registry = load_registry(template)
    groups = registry.get("groups", {})
    if role not in groups:
        raise KeyError(f"Unknown functional page role: {role}")
    group = groups[role]
    variants = group.get("variants", [])
    chosen_id = variant_id or group.get("default_variant")
    for variant in variants:
        if variant.get("variant_id") == chosen_id:
            _assert_variant_geometry(template, variant)
            return {"role": role, "variant": variant, "source": "explicit" if variant_id else "group_default"}
    valid = [str(item.get("variant_id")) for item in variants]
    raise KeyError(f"Unknown variant {chosen_id!r} for role {role!r}; choose one of {valid}")


def validate_functional_page_variant_payload(
    template: str | Path,
    slide: dict[str, Any],
) -> dict[str, Any]:
    role = str(slide.get("role") or slide.get("functional_page_group") or "")
    variant_id = slide.get("functional_variant_id") or slide.get("variant_id")
    selection = select_functional_variant(template, role, str(variant_id) if variant_id else None)
    required = set(selection["variant"].get("slots", []))
    payload = dict(slide.get("slot_payload") or {})
    missing = sorted(required - set(payload))
    extra = sorted(set(payload) - required)
    return {
        "status": "pass" if not missing else "fail",
        "role": role,
        "variant_id": selection["variant"].get("variant_id"),
        "preview_svg": selection["variant"].get("preview_svg"),
        "missing_slots": missing,
        "extra_slots": extra,
        "payload": payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template", type=Path)
    parser.add_argument("--role")
    parser.add_argument("--variant")
    parser.add_argument("--check-all", action="store_true", help="Validate every functional-page variant and print JSON.")
    args = parser.parse_args()
    if args.check_all:
        report = validate_functional_variant_registry(args.template)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1
    if not args.role:
        parser.error("--role is required unless --check-all is used")
    print(json.dumps(select_functional_variant(args.template, args.role, args.variant), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
