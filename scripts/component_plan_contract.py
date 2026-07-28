#!/usr/bin/env python3
"""Validate EasySlides component_plan.json contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.card_library import load_card_library, validate_card_payload
    from scripts.card_recipe import load_visual_recipes, validate_recipe_payload
    from scripts.chart_library import validate_chart_payload
    from scripts.component_package import validate_component_story_payload
    from scripts.component_registry import DEFAULT_OUTPUT, load_component_registry
    from scripts.icon_library import validate_icon_payload
    from scripts.page_recipe import load_page_recipes, validate_page_payload
    from scripts.template_capabilities import asset_allowed_for_template, load_template_capability
except ModuleNotFoundError:  # pragma: no cover
    from card_library import load_card_library, validate_card_payload
    from card_recipe import load_visual_recipes, validate_recipe_payload
    from chart_library import validate_chart_payload
    from component_package import validate_component_story_payload
    from component_registry import DEFAULT_OUTPUT, load_component_registry
    from icon_library import validate_icon_payload
    from page_recipe import load_page_recipes, validate_page_payload
    from template_capabilities import asset_allowed_for_template, load_template_capability


SCHEMA_VERSION = "easyslides.component_plan.v1"
REPORT_SCHEMA_VERSION = "easyslides.component_plan_report.v1"
BASE_REQUIRED_GATES = (
    "component_plan_contract",
    "component_selector",
    "visual_measure_gate",
    "validate_pptx_text_layout",
)


def issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _asset_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(asset["asset_id"]): asset
        for asset in registry.get("assets", [])
        if isinstance(asset, dict) and asset.get("asset_id")
    }


def _payload_for(selected: dict[str, Any]) -> dict[str, Any]:
    payload = selected.get("payload")
    return payload if isinstance(payload, dict) else {}


def _plan_template_id(plan: dict[str, Any]) -> str:
    value = plan.get("template_id")
    return str(value).strip() if _is_nonempty_string(value) else ""


def _slide_template_id(slide: dict[str, Any], plan_template_id: str) -> str:
    value = slide.get("template_id")
    if _is_nonempty_string(value):
        return str(value).strip()
    query = slide.get("selection_query") if isinstance(slide.get("selection_query"), dict) else {}
    value = query.get("template_id")
    if _is_nonempty_string(value):
        return str(value).strip()
    return plan_template_id


def _validate_body_variant_payload(asset: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    declared = [slot["slot_id"] for slot in asset.get("slots", []) if isinstance(slot, dict) and slot.get("slot_id")]
    missing = [slot_id for slot_id in declared if slot_id not in payload]
    extra = [slot_id for slot_id in payload if declared and slot_id not in declared]
    violations = []
    if missing:
        violations.append({"slot_id": ",".join(missing), "missing": True, "overflow_action": "fill_required_slot"})
    if extra:
        violations.append({"slot_id": ",".join(extra), "extra": True, "overflow_action": "remove_undeclared_slot"})
    return {
        "passed": not violations,
        "checked_slots": len(declared),
        "violations": violations,
    }


def _validate_asset_payload(asset_id: str, asset: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"passed": True, "checked_slots": 0, "violations": []}
    if asset_id.startswith("component_package/"):
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        source_asset_id = str(metadata.get("source_asset_id") or "")
        if source_asset_id and not source_asset_id.startswith("component_package/"):
            return validate_component_story_payload(
                source_asset_id,
                payload,
                metadata.get("input_schema") if isinstance(metadata.get("input_schema"), dict) else None,
            )
        return validate_component_story_payload(
            source_asset_id,
            payload,
            metadata.get("input_schema") if isinstance(metadata.get("input_schema"), dict) else None,
        )
    if asset_id.startswith("card/"):
        return validate_card_payload(asset_id.split("/", 1)[1], payload, load_card_library())
    if asset_id.startswith("visual_recipe/"):
        return validate_recipe_payload(asset_id.split("/", 1)[1], payload, load_visual_recipes())
    if asset_id.startswith("page_recipe/"):
        return validate_page_payload(asset_id.split("/", 1)[1], payload, load_page_recipes())
    if asset_id.startswith("chart/"):
        return validate_chart_payload(asset_id.split("/", 1)[1], payload)
    if asset_id.startswith("icon_family/"):
        return validate_icon_payload(asset_id.split("/", 1)[1], payload)
    if asset_id.startswith("body_variant/"):
        return _validate_body_variant_payload(asset, payload)
    return {"passed": True, "checked_slots": 0, "violations": []}


def _validate_component_refs(
    selected: dict[str, Any],
    asset: dict[str, Any],
    assets: dict[str, dict[str, Any]],
    selected_path: str,
) -> tuple[list[dict[str, str]], set[str], list[dict[str, Any]]]:
    def order_value(value: object, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    expected = [
        ref
        for ref in metadata.get("component_refs", [])
        if isinstance(ref, dict) and ref.get("asset_id")
    ]
    actual = selected.get("component_refs")
    if not isinstance(actual, list):
        actual = []
    issues: list[dict[str, str]] = []
    gates: set[str] = set()
    reports: list[dict[str, Any]] = []
    if expected and not actual:
        issues.append(
            issue(
                "COMPONENT-PLAN-COMPOSITION",
                "selected body variant must retain its declared component_refs",
                f"{selected_path}.component_refs",
            )
        )
        return issues, gates, reports

    expected_identity = [
        (str(ref.get("asset_id") or ""), order_value(ref.get("order"), index + 1))
        for index, ref in enumerate(expected)
    ]
    actual_identity = [
        (str(ref.get("asset_id") or ""), order_value(ref.get("order"), index + 1))
        for index, ref in enumerate(actual)
        if isinstance(ref, dict)
    ]
    if expected and actual_identity != expected_identity:
        issues.append(
            issue(
                "COMPONENT-PLAN-COMPOSITION-DRIFT",
                "component_refs must preserve the body variant's declared asset order",
                f"{selected_path}.component_refs",
            )
        )

    instance_ids: set[str] = set()
    for ref_index, ref in enumerate(actual):
        ref_path = f"{selected_path}.component_refs[{ref_index}]"
        if not isinstance(ref, dict):
            issues.append(issue("COMPONENT-PLAN-COMPONENT-REF", "component ref must be an object", ref_path))
            continue
        asset_id = str(ref.get("asset_id") or "")
        instance_id = str(ref.get("instance_id") or "")
        if not asset_id:
            issues.append(issue("COMPONENT-PLAN-COMPONENT-REF", "asset_id is required", f"{ref_path}.asset_id"))
            continue
        if not instance_id:
            issues.append(issue("COMPONENT-PLAN-COMPONENT-REF", "instance_id is required", f"{ref_path}.instance_id"))
        elif instance_id in instance_ids:
            issues.append(issue("COMPONENT-PLAN-COMPONENT-REF", f"duplicate instance_id {instance_id!r}", f"{ref_path}.instance_id"))
        instance_ids.add(instance_id)
        target = assets.get(asset_id)
        if not target and bool(ref.get("required", True)):
            issues.append(issue("COMPONENT-PLAN-COMPONENT-REF", f"unknown required component {asset_id!r}", f"{ref_path}.asset_id"))
            continue
        if target:
            gates.update(str(gate) for gate in target.get("required_gates", []) if str(gate))
        reports.append(
            {
                "asset_id": asset_id,
                "instance_id": instance_id,
                "order": order_value(ref.get("order"), ref_index + 1),
                "status": "resolved" if target else "optional_unresolved",
            }
        )
    if actual:
        gates.add("body_variant_component_contract")
    return issues, gates, reports


def _validate_recipe_dependencies(
    selected: dict[str, Any],
    asset: dict[str, Any],
    assets: dict[str, dict[str, Any]],
    selected_path: str,
) -> tuple[list[dict[str, str]], set[str], list[dict[str, Any]]]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    expected = [str(value) for value in metadata.get("component_dependency_asset_ids", []) if str(value)]
    actual_raw = selected.get("component_dependency_asset_ids")
    actual = [str(value) for value in actual_raw if str(value)] if isinstance(actual_raw, list) else []
    issues: list[dict[str, str]] = []
    gates: set[str] = set()
    reports: list[dict[str, Any]] = []
    if expected != actual:
        issues.append(
            issue(
                "COMPONENT-PLAN-RECIPE-DEPENDENCIES",
                "selected body variant must retain its source-derived component dependency sequence",
                f"{selected_path}.component_dependency_asset_ids",
            )
        )
        return issues, gates, reports
    for index, asset_id in enumerate(actual):
        target = assets.get(asset_id)
        if not target:
            issues.append(
                issue(
                    "COMPONENT-PLAN-RECIPE-DEPENDENCY",
                    f"unknown source-derived component dependency {asset_id!r}",
                    f"{selected_path}.component_dependency_asset_ids[{index}]",
                )
            )
            continue
        gates.update(str(gate) for gate in target.get("required_gates", []) if str(gate))
        reports.append({"asset_id": asset_id, "status": "resolved", "order": index + 1})
    if actual:
        gates.add("template_component_pack_contract")
    return issues, gates, reports


def _deck_pages(deck_plan_path: Path | None) -> list[str]:
    if not deck_plan_path:
        return []
    try:
        plan = json.loads(deck_plan_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    slides = plan.get("slides")
    if not isinstance(slides, list):
        return []
    return [
        str(slide.get("page"))
        for slide in slides
        if isinstance(slide, dict) and _is_nonempty_string(slide.get("page"))
    ]


def validate_component_plan(
    plan: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    deck_plan_path: Path | None = None,
    require_form_selection: bool = False,
) -> dict[str, Any]:
    registry = registry or load_component_registry()
    assets = _asset_map(registry)
    issues: list[dict[str, str]] = []
    slide_reports: list[dict[str, Any]] = []
    required_gates = set(BASE_REQUIRED_GATES)

    if not isinstance(plan, dict):
        issues.append(issue("COMPONENT-PLAN-TYPE", "component plan must be a JSON object", "$"))
        return _report(issues, slide_reports, required_gates)

    if plan.get("schema_version") != SCHEMA_VERSION:
        issues.append(issue("COMPONENT-PLAN-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))

    plan_template_id = _plan_template_id(plan)
    if plan_template_id:
        required_gates.add("template_capability_profile")

    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        issues.append(issue("COMPONENT-PLAN-SLIDES", "slides must be a non-empty list", "slides"))
        return _report(issues, slide_reports, required_gates)

    seen_pages: set[str] = set()
    for slide_index, slide in enumerate(slides):
        slide_path = f"slides[{slide_index}]"
        if not isinstance(slide, dict):
            issues.append(issue("COMPONENT-PLAN-SLIDE", "slide must be an object", slide_path))
            continue
        page = str(slide.get("page") or "")
        if not page:
            issues.append(issue("COMPONENT-PLAN-PAGE", "slide page is required", f"{slide_path}.page"))
        elif page in seen_pages:
            issues.append(issue("COMPONENT-PLAN-PAGE", f"duplicate page {page!r}", f"{slide_path}.page"))
        seen_pages.add(page)

        template_id = _slide_template_id(slide, plan_template_id)
        capability = load_template_capability(template_id)
        if template_id and capability and capability.get("status") == "fail":
            issues.append(
                issue(
                    "COMPONENT-PLAN-TEMPLATE-CAPABILITY",
                    f"template {template_id!r} has an invalid or missing capability profile",
                    f"{slide_path}.selection_query.template_id",
                )
            )
        elif template_id and capability and capability.get("generation_enabled") is not True:
            issues.append(
                issue(
                    "COMPONENT-PLAN-TEMPLATE-CAPABILITY",
                    f"template {template_id!r} is source-scoped or non-template and cannot receive automatic component composition",
                    f"{slide_path}.selection_query.template_id",
                )
            )

        selected_assets = slide.get("selected_assets")
        if not isinstance(selected_assets, list) or not selected_assets:
            issues.append(issue("COMPONENT-PLAN-ASSETS", "each slide must select at least one component asset", f"{slide_path}.selected_assets"))
            continue

        page_report = {"page": page, "asset_reports": []}
        form_selection = slide.get("form_selection")
        if require_form_selection and not isinstance(form_selection, dict):
            issues.append(issue("COMPONENT-PLAN-FORM-SELECTION", "production component plans must include form_selection", f"{slide_path}.form_selection"))
        elif isinstance(form_selection, dict):
            if form_selection.get("schema_version") != "easyslides.form_selection.v1":
                issues.append(issue("COMPONENT-PLAN-FORM-SCHEMA", "form_selection has an unsupported schema", f"{slide_path}.form_selection.schema_version"))
            candidates = form_selection.get("candidates")
            families = {str(row.get("family") or "") for row in candidates or [] if isinstance(row, dict) and row.get("family")}
            if not isinstance(candidates, list) or len(candidates) < 2 or len(families) < 2:
                issues.append(issue("COMPONENT-PLAN-FORM-DIVERGENCE", "form_selection needs at least two candidates from different families", f"{slide_path}.form_selection.candidates"))
        for asset_index, selected in enumerate(selected_assets):
            selected_path = f"{slide_path}.selected_assets[{asset_index}]"
            if not isinstance(selected, dict):
                issues.append(issue("COMPONENT-PLAN-ASSET", "selected asset must be an object", selected_path))
                continue
            asset_id = str(selected.get("asset_id") or "")
            if not asset_id:
                issues.append(issue("COMPONENT-PLAN-ASSET-ID", "asset_id is required", f"{selected_path}.asset_id"))
                continue
            asset = assets.get(asset_id)
            if not asset:
                issues.append(issue("COMPONENT-PLAN-ASSET-ID", f"unknown asset_id {asset_id!r}", f"{selected_path}.asset_id"))
                continue
            allowed, reason = asset_allowed_for_template(asset, capability)
            if not allowed:
                issues.append(
                    issue(
                        "COMPONENT-PLAN-TEMPLATE-ASSET",
                        f"{asset_id!r} is not allowed for template {template_id or 'global'}: {reason}",
                        f"{selected_path}.asset_id",
                    )
                )
            required_gates.update(str(gate) for gate in asset.get("required_gates", []) if str(gate))
            composition_issues, composition_gates, component_reports = _validate_component_refs(
                selected,
                asset,
                assets,
                selected_path,
            )
            issues.extend(composition_issues)
            required_gates.update(composition_gates)
            dependency_issues, dependency_gates, dependency_reports = _validate_recipe_dependencies(
                selected,
                asset,
                assets,
                selected_path,
            )
            issues.extend(dependency_issues)
            required_gates.update(dependency_gates)
            payload = _payload_for(selected)
            payload_report = _validate_asset_payload(asset_id, asset, payload)
            page_report["asset_reports"].append(
                {
                    "asset_id": asset_id,
                    "granularity": asset.get("granularity"),
                    "payload_status": "pass" if payload_report["passed"] else "fail",
                    "checked_slots": payload_report.get("checked_slots", 0),
                    "violations": payload_report.get("violations", []),
                    "composition_status": "pass" if not composition_issues else "fail",
                    "component_refs": component_reports,
                    "component_dependencies": dependency_reports,
                }
            )
            if not payload_report["passed"]:
                issues.append(
                    issue(
                        "COMPONENT-PLAN-PAYLOAD",
                        f"{asset_id} payload violates component capacity or slot contract",
                        f"{selected_path}.payload",
                    )
                )
        slide_reports.append(page_report)

    deck_pages = _deck_pages(deck_plan_path)
    for page in deck_pages:
        if page not in seen_pages:
            issues.append(issue("COMPONENT-PLAN-DECK-COVERAGE", f"deck page {page!r} has no component selection", "slides"))

    return _report(issues, slide_reports, required_gates)


def _report(
    issues: list[dict[str, str]],
    slide_reports: list[dict[str, Any]],
    required_gates: set[str],
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "slide_count": len(slide_reports),
        "required_gates": sorted(required_gates),
        "slides": slide_reports,
    }


def validate_component_plan_file(
    path: Path,
    *,
    registry_path: Path | None = None,
    deck_plan_path: Path | None = None,
    require_form_selection: bool = False,
) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _report([issue("COMPONENT-PLAN-FILE", "component_plan.json not found", str(path))], [], set(BASE_REQUIRED_GATES))
    except json.JSONDecodeError as exc:
        return _report([issue("COMPONENT-PLAN-JSON", f"invalid JSON: {exc}", str(path))], [], set(BASE_REQUIRED_GATES))
    return validate_component_plan(
        plan,
        registry=load_component_registry(registry_path) if registry_path else None,
        deck_plan_path=deck_plan_path,
        require_form_selection=require_form_selection,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate EasySlides component_plan.json contracts.")
    parser.add_argument("component_plan", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--deck-plan", type=Path)
    parser.add_argument("--require-form-selection", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_component_plan_file(args.component_plan, registry_path=args.registry, deck_plan_path=args.deck_plan, require_form_selection=args.require_form_selection)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Component plan: {report['status']} ({report['issue_count']} issue(s))")
        for item in report["issues"]:
            print(f"- {item['code']}: {item['message']} [{item['path']}]")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
