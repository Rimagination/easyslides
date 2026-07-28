#!/usr/bin/env python3
"""Validate EasySlides component package workspaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGES_ROOT = ROOT / "templates" / "components" / "packages"
INSTALLED_PACKAGES_ROOT = ROOT / "templates" / "components" / "installed"
SCHEMA_VERSION = "easyslides.component_package.v1"
STORY_SCHEMA_VERSION = "easyslides.component_story.v1"
REPORT_SCHEMA_VERSION = "easyslides.component_package_report.v1"
INPUT_SCHEMA_VERSION = "easyslides.component_input_schema.v1"
VERTICAL_CENTER_RULE = "text_center_y_matches_container_center_y"

try:
    from scripts.card_library import load_card_library, validate_card_payload
    from scripts.card_recipe import load_visual_recipes, validate_recipe_payload
    from scripts.page_recipe import load_page_recipes, validate_page_payload
    from scripts.component_renderer_registry import resolve_renderer_id, validate_renderer_id
except ModuleNotFoundError:  # pragma: no cover
    from card_library import load_card_library, validate_card_payload
    from card_recipe import load_visual_recipes, validate_recipe_payload
    from page_recipe import load_page_recipes, validate_page_payload
    from component_renderer_registry import resolve_renderer_id, validate_renderer_id


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _schema_issues(schema: object, *, path: str = "input_schema", nested: bool = False) -> list[dict[str, str]]:
    """Validate the intentionally small declarative input-schema dialect."""
    issues: list[dict[str, str]] = []
    if not isinstance(schema, dict):
        return [_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "input schema nodes must be objects", path)]
    if not nested and schema.get("schema_version") != INPUT_SCHEMA_VERSION:
        issues.append(
            _issue(
                "COMPONENT-PACKAGE-INPUT-SCHEMA",
                f"input_schema.schema_version must be {INPUT_SCHEMA_VERSION}",
                f"{path}.schema_version",
            )
        )
    schema_type = str(schema.get("type") or "")
    if schema_type not in {"object", "array", "string", "number", "integer", "boolean"}:
        issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "schema type is unsupported", f"{path}.type"))
        return issues
    if schema_type == "object":
        properties = schema.get("properties")
        required = schema.get("required", [])
        if not isinstance(properties, dict):
            issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "object schema requires properties", f"{path}.properties"))
            properties = {}
        if not isinstance(required, list) or not all(_is_nonempty_string(key) for key in required):
            issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "required must be a list of property names", f"{path}.required"))
            required = []
        for key in required:
            if key not in properties:
                issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "required property must be declared", f"{path}.required"))
        for key, child in properties.items():
            if not _is_nonempty_string(key):
                issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "property names must be non-empty", f"{path}.properties"))
                continue
            issues.extend(_schema_issues(child, path=f"{path}.properties.{key}", nested=True))
    elif schema_type == "array":
        if not isinstance(schema.get("items"), dict):
            issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "array schema requires an items schema", f"{path}.items"))
        else:
            issues.extend(_schema_issues(schema["items"], path=f"{path}.items", nested=True))
    for key in ("min_items", "max_items", "min_length", "max_length"):
        if key in schema and (not isinstance(schema[key], int) or schema[key] < 0):
            issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", f"{key} must be a non-negative integer", f"{path}.{key}"))
    if isinstance(schema.get("min_items"), int) and isinstance(schema.get("max_items"), int):
        if schema["min_items"] > schema["max_items"]:
            issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "min_items cannot exceed max_items", path))
    if isinstance(schema.get("min_length"), int) and isinstance(schema.get("max_length"), int):
        if schema["min_length"] > schema["max_length"]:
            issues.append(_issue("COMPONENT-PACKAGE-INPUT-SCHEMA", "min_length cannot exceed max_length", path))
    return issues


def _validate_input_value(value: Any, schema: dict[str, Any], *, path: str) -> list[str]:
    """Validate a story payload without allowing executable JSON-schema features."""
    violations: list[str] = []
    schema_type = str(schema.get("type") or "")
    if schema_type == "object":
        if not isinstance(value, dict):
            return [f"{path} must be an object"]
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for key in required:
            if key not in value or value[key] in (None, "", []):
                violations.append(f"{path}.{key} is required")
        if schema.get("additional_properties") is False:
            for key in value:
                if key not in properties:
                    violations.append(f"{path}.{key} is not declared")
        for key, child in properties.items():
            if key in value and value[key] is not None:
                violations.extend(_validate_input_value(value[key], child, path=f"{path}.{key}"))
        return violations
    if schema_type == "array":
        if not isinstance(value, list):
            return [f"{path} must be an array"]
        if isinstance(schema.get("min_items"), int) and len(value) < schema["min_items"]:
            violations.append(f"{path} requires at least {schema['min_items']} item(s)")
        if isinstance(schema.get("max_items"), int) and len(value) > schema["max_items"]:
            violations.append(f"{path} allows at most {schema['max_items']} item(s)")
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else None
        if item_schema:
            for index, item in enumerate(value):
                violations.extend(_validate_input_value(item, item_schema, path=f"{path}[{index}]"))
        return violations
    if schema_type == "string":
        if not isinstance(value, str):
            return [f"{path} must be a string"]
        if isinstance(schema.get("min_length"), int) and len(value) < schema["min_length"]:
            violations.append(f"{path} is shorter than {schema['min_length']} character(s)")
        if isinstance(schema.get("max_length"), int) and len(value) > schema["max_length"]:
            violations.append(f"{path} exceeds {schema['max_length']} character(s)")
        return violations
    if schema_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return [f"{path} must be a number"]
    if schema_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return [f"{path} must be an integer"]
    if schema_type == "boolean" and not isinstance(value, bool):
        return [f"{path} must be a boolean"]
    return violations


def validate_component_input_payload(input_schema: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    violations = _validate_input_value(payload, input_schema, path="payload")
    return {"passed": not violations, "checked_slots": len(payload), "violations": violations}


def _package_dirs(root: Path = PACKAGES_ROOT) -> list[Path]:
    if not root.exists():
        return []
    skipped_parts = {".git", ".archive", ".staging", "__pycache__"}
    return sorted(
        path.parent
        for path in root.rglob("component.json")
        if path.is_file() and not any(part in skipped_parts for part in path.relative_to(root).parts)
    )


def load_component_packages(root: Path = PACKAGES_ROOT) -> list[tuple[Path, dict[str, Any]]]:
    return [(path, _read_json(path / "component.json")) for path in _package_dirs(root)]


def load_component_packages_from_roots(roots: list[Path] | tuple[Path, ...]) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    seen: set[Path] = set()
    for root in roots:
        for package_dir, package in load_component_packages(Path(root)):
            resolved = package_dir.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            rows.append((package_dir, package))
    return sorted(rows, key=lambda row: str(row[0]).lower())


def _text_slots(package: dict[str, Any]) -> list[dict[str, Any]]:
    slots = package.get("slots")
    if not isinstance(slots, list):
        return []
    rows = []
    for slot in slots:
        if isinstance(slot, dict) and str(slot.get("kind") or "text") == "text":
            rows.append(slot)
    return rows


def _has_vertical_center_invariant(package: dict[str, Any]) -> bool:
    qa = package.get("qa") if isinstance(package.get("qa"), dict) else {}
    invariants = qa.get("alignment_invariants")
    if not isinstance(invariants, list):
        return False
    for invariant in invariants:
        if not isinstance(invariant, dict):
            continue
        if (
            invariant.get("rule") == VERTICAL_CENTER_RULE
            and invariant.get("scope") in {"text_in_container", "all_text_slots"}
            and invariant.get("severity") == "error"
        ):
            return True
    return False


def _story_payload(path: Path) -> dict[str, Any] | None:
    try:
        story = _read_json(path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None
    if story.get("schema_version") != STORY_SCHEMA_VERSION:
        return None
    payload = story.get("payload")
    return payload if isinstance(payload, dict) else None


def validate_component_story_payload(
    source_asset_id: str,
    payload: dict[str, Any],
    input_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generic_report = (
        validate_component_input_payload(input_schema, payload)
        if isinstance(input_schema, dict)
        else {"passed": True, "checked_slots": 0, "violations": []}
    )
    if source_asset_id.startswith("card/"):
        source_report = validate_card_payload(source_asset_id.split("/", 1)[1], payload, load_card_library())
    elif source_asset_id.startswith("visual_recipe/"):
        source_report = validate_recipe_payload(source_asset_id.split("/", 1)[1], payload, load_visual_recipes())
    elif source_asset_id.startswith("page_recipe/"):
        source_report = validate_page_payload(source_asset_id.split("/", 1)[1], payload, load_page_recipes())
    else:
        source_report = {"passed": True, "checked_slots": 0, "violations": []}
    return {
        "passed": bool(generic_report["passed"] and source_report["passed"]),
        "checked_slots": int(generic_report.get("checked_slots", 0)) + int(source_report.get("checked_slots", 0)),
        "violations": [*generic_report.get("violations", []), *source_report.get("violations", [])],
    }


def validate_component_package(package_dir: Path, package: dict[str, Any] | None = None) -> dict[str, Any]:
    package = package if package is not None else _read_json(package_dir / "component.json")
    issues: list[dict[str, str]] = []

    if package.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("COMPONENT-PACKAGE-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))

    for key in ("component_id", "asset_id", "granularity", "render_backend", "source_asset_id"):
        if not _is_nonempty_string(package.get(key)):
            issues.append(_issue("COMPONENT-PACKAGE-FIELD", f"{key} is required", key))

    renderer_report = validate_renderer_id(resolve_renderer_id(package))
    if renderer_report["status"] != "pass":
        issues.append(_issue("COMPONENT-PACKAGE-RENDERER", renderer_report["issues"][0], "renderer_id"))

    if package.get("granularity") != "component_package":
        issues.append(_issue("COMPONENT-PACKAGE-GRANULARITY", "granularity must be component_package", "granularity"))

    selection = package.get("selection")
    if not isinstance(selection, dict):
        issues.append(_issue("COMPONENT-PACKAGE-SELECTION", "selection must be an object", "selection"))
    else:
        if not isinstance(selection.get("content_shapes"), list) or not selection.get("content_shapes"):
            issues.append(_issue("COMPONENT-PACKAGE-SELECTION", "selection.content_shapes must be a non-empty list", "selection.content_shapes"))
        for key in ("item_count_min", "item_count_max"):
            if key in selection and not isinstance(selection.get(key), int):
                issues.append(_issue("COMPONENT-PACKAGE-SELECTION", f"selection.{key} must be an integer", f"selection.{key}"))

    slots = package.get("slots")
    if not isinstance(slots, list) or not slots:
        issues.append(_issue("COMPONENT-PACKAGE-SLOTS", "slots must be a non-empty list", "slots"))
    else:
        for index, slot in enumerate(slots):
            path = f"slots[{index}]"
            if not isinstance(slot, dict):
                issues.append(_issue("COMPONENT-PACKAGE-SLOT", "slot must be an object", path))
                continue
            if not _is_nonempty_string(slot.get("slot_id")):
                issues.append(_issue("COMPONENT-PACKAGE-SLOT", "slot_id is required", f"{path}.slot_id"))
            if str(slot.get("kind") or "text") == "text" and not isinstance(slot.get("capacity"), dict):
                issues.append(_issue("COMPONENT-PACKAGE-SLOT-CAPACITY", "text slots must declare capacity", f"{path}.capacity"))

    input_schema = package.get("input_schema")
    input_schema_issues = _schema_issues(input_schema)
    issues.extend(input_schema_issues)

    if _text_slots(package) and not _has_vertical_center_invariant(package):
        issues.append(
            _issue(
                "COMPONENT-PACKAGE-VERTICAL-CENTER",
                "text component packages must hard-code vertical center alignment as an error-level invariant",
                "qa.alignment_invariants",
            )
        )

    stories = package.get("stories")
    if not isinstance(stories, list) or not stories:
        issues.append(_issue("COMPONENT-PACKAGE-STORIES", "stories must be a non-empty list", "stories"))
    else:
        for index, story_ref in enumerate(stories):
            path = f"stories[{index}]"
            if not isinstance(story_ref, dict):
                issues.append(_issue("COMPONENT-PACKAGE-STORY", "story reference must be an object", path))
                continue
            if not _is_nonempty_string(story_ref.get("story_id")):
                issues.append(_issue("COMPONENT-PACKAGE-STORY", "story_id is required", f"{path}.story_id"))
            payload_path = story_ref.get("payload")
            if not _is_nonempty_string(payload_path):
                issues.append(_issue("COMPONENT-PACKAGE-STORY", "payload path is required", f"{path}.payload"))
                continue
            story_path = package_dir / str(payload_path)
            payload = _story_payload(story_path)
            if payload is None:
                issues.append(_issue("COMPONENT-PACKAGE-STORY", "story payload must exist and use component_story schema", str(story_path)))
                continue
            source_asset_id = str(package.get("source_asset_id") or "")
            payload_report = validate_component_story_payload(
                source_asset_id,
                payload,
                input_schema if not input_schema_issues else None,
            )
            actual_status = "pass" if payload_report["passed"] else "fail"
            expected_status = str(story_ref.get("expected_status") or "pass")
            if actual_status != expected_status:
                issues.append(
                    _issue(
                        "COMPONENT-PACKAGE-STORY-PAYLOAD",
                        f"story {story_ref.get('story_id')!r} expected {expected_status} but payload validation returned {actual_status}",
                        f"{path}.payload",
                    )
                )

    qa = package.get("qa")
    required_gates = qa.get("required_gates") if isinstance(qa, dict) else None
    if not isinstance(required_gates, list) or "component_package_contract" not in required_gates:
        issues.append(_issue("COMPONENT-PACKAGE-GATES", "qa.required_gates must include component_package_contract", "qa.required_gates"))

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "component_id": str(package.get("component_id") or package_dir.name),
        "story_count": len(stories) if isinstance(stories, list) else 0,
    }


def validate_component_packages(root: Path = PACKAGES_ROOT) -> dict[str, Any]:
    reports = [validate_component_package(path, package) for path, package in load_component_packages(root)]
    issues: list[dict[str, str]] = []
    for report in reports:
        for item in report["issues"]:
            issues.append(
                _issue(
                    item["code"],
                    item["message"],
                    f"{report['component_id']}.{item['path']}",
                )
            )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "package_count": len(reports),
        "packages": reports,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate EasySlides component package workspaces.")
    parser.add_argument("--root", type=Path, default=PACKAGES_ROOT)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_component_packages(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Component packages: {report['status']} ({report['issue_count']} issue(s), {report['package_count']} package(s))")
        for item in report["issues"]:
            print(f"- {item['code']}: {item['message']} [{item['path']}]")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
