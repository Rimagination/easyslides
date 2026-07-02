"""Whole-page PPT Master layout recipes for SVG authoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECIPES = REPO_ROOT / "templates" / "page_layouts" / "ppt_master_page_recipes.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.text_capacity import SlotCapacity, fit_text_to_capacity


def load_page_recipes(path: str | Path | None = None) -> dict[str, Any]:
    recipe_path = Path(path) if path else DEFAULT_RECIPES
    with recipe_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    recipes = registry.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise ValueError("page recipe registry must define a non-empty recipes list")
    return registry


def recipes(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return list((registry or load_page_recipes())["recipes"])


def recipe_count(registry: dict[str, Any] | None = None) -> int:
    return len(recipes(registry))


def get_page_recipe(recipe_id: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    for recipe in recipes(registry):
        if recipe.get("recipe_id") == recipe_id:
            return recipe
    raise KeyError(f"unknown recipe_id: {recipe_id}")


def select_page_recipes(
    *,
    page_role: str | None = None,
    content_shape: str | None = None,
    item_count: int | None = None,
    density: str | None = None,
    avoid: list[str] | None = None,
    registry: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    avoid_set = set(avoid or [])
    matches: list[tuple[int, str, dict[str, Any]]] = []
    for recipe in recipes(registry):
        selection = recipe.get("selection", {})
        score = 0
        if recipe.get("recipe_id") in avoid_set:
            score -= 4
        if page_role:
            roles = set(recipe.get("page_role") or [])
            if page_role in roles:
                score += 5
            else:
                score -= 1
        if content_shape:
            shapes = set(selection.get("content_shapes") or [])
            if content_shape in shapes:
                score += 7
            else:
                continue
        if item_count is not None:
            minimum = int(selection.get("item_count_min", 1))
            maximum = int(selection.get("item_count_max", minimum))
            if minimum <= item_count <= maximum:
                score += 4
                if minimum == maximum == item_count:
                    score += 1
            else:
                continue
        if density:
            score += 2 if selection.get("density") == density else -1
        matches.append((score, str(recipe["recipe_id"]), recipe))
    matches.sort(key=lambda item: (-item[0], item[1]))
    return [recipe for _, _, recipe in matches]


def _slot_capacity(slot: dict[str, Any]) -> SlotCapacity:
    max_lines = int(slot["max_lines"])
    chars = int(slot["max_chars_per_line_zh"])
    return SlotCapacity(
        slot_id=str(slot["slot_id"]),
        role=str(slot.get("role") or "body"),
        font_size_px=float(slot["font_size_px"]),
        min_font_size_px=float(slot["min_font_size_px"]),
        line_height=float(slot["line_height"]),
        max_chars_per_line_zh=chars,
        max_lines=max_lines,
        capacity_chars=max_lines * chars,
        overflow_action=str(slot["overflow_action"]),
    )


def _check_slot(slot: dict[str, Any], value: Any, location: str) -> dict[str, Any] | None:
    text = "" if value is None else str(value).strip()
    result = fit_text_to_capacity(text, _slot_capacity(slot))
    if result.input_over_capacity or result.output_overflow:
        capacity = _slot_capacity(slot)
        return {
            "location": location,
            "slot_id": slot["slot_id"],
            "input_chars": result.input_chars,
            "capacity_chars": capacity.capacity_chars,
            "max_lines": capacity.max_lines,
            "max_chars_per_line_zh": capacity.max_chars_per_line_zh,
            "overflow_action": capacity.overflow_action,
        }
    return None


def validate_page_payload(
    recipe_id: str,
    payload: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recipe = get_page_recipe(recipe_id, registry)
    items = payload.get("items")
    item_count = len(items) if isinstance(items, list) else 1
    selection = recipe.get("selection", {})
    minimum = int(selection.get("item_count_min", 1))
    maximum = int(selection.get("item_count_max", minimum))
    violations: list[dict[str, Any]] = []
    checked = 0

    if not (minimum <= item_count <= maximum):
        violations.append(
            {
                "location": "items",
                "slot_id": "item_count",
                "input_count": item_count,
                "allowed_min": minimum,
                "allowed_max": maximum,
                "overflow_action": "choose_matching_page_recipe_or_split",
            }
        )

    for slot in recipe.get("slots", []):
        slot_id = str(slot["slot_id"])
        required = bool(slot.get("required", False))
        repeated = bool(slot.get("repeated", False))
        seen = False
        if slot_id in payload:
            seen = True
            checked += 1
            violation = _check_slot(slot, payload.get(slot_id), slot_id)
            if violation:
                violations.append(violation)
        if repeated and isinstance(items, list):
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                if slot_id in item:
                    seen = True
                    checked += 1
                    violation = _check_slot(slot, item.get(slot_id), f"items[{index}].{slot_id}")
                    if violation:
                        violations.append(violation)
                elif required:
                    violations.append(
                        {
                            "location": f"items[{index}]",
                            "slot_id": slot_id,
                            "missing": True,
                            "overflow_action": "fill_required_slot",
                        }
                    )
        if required and not seen:
            violations.append(
                {
                    "location": "payload",
                    "slot_id": slot_id,
                    "missing": True,
                    "overflow_action": "fill_required_slot",
                }
            )

    return {
        "passed": not violations,
        "recipe_id": recipe_id,
        "checked_slots": checked,
        "violations": violations,
    }


def build_page_prompt(recipe_id: str, registry: dict[str, Any] | None = None) -> str:
    recipe = get_page_recipe(recipe_id, registry)
    canvas = (registry or load_page_recipes())["canvas"]
    slot_lines = []
    for slot in recipe.get("slots", []):
        repeated = " repeated" if slot.get("repeated") else ""
        slot_lines.append(
            f"- {slot['slot_id']}{repeated}: {slot['max_lines']} line(s), "
            f"{slot['max_chars_per_line_zh']} zh chars/line, "
            f"font {slot['font_size_px']}px, min {slot['min_font_size_px']}px; "
            f"overflow: {slot['overflow_action']}"
        )
    region_lines = [
        f"- {region['id']}: x={region['x']} y={region['y']} width={region['width']} height={region['height']}"
        for region in recipe.get("regions", [])
    ]
    return "\n".join(
        [
            f"You are the PPT Master-style SVG Executor for page recipe `{recipe_id}`.",
            f"Generate one whole {canvas['width']}x{canvas['height']} SVG page, not a card fragment.",
            "Use this recipe to create page-level visual diversity before choosing any nested card recipe.",
            f"Page intent: {recipe['layout_intent']}",
            "Regions:",
            *region_lines,
            "Slot capacity:",
            *slot_lines,
            "Hard text rules:",
            "- Every non-decorative text string longer than a short label must be a fixed SVG text slot.",
            "- Mark fixed slots with data-pptx-textbox=\"true\" and data-pptx-box-x/y/w/h.",
            "- Use <tspan> lines inside each fixed slot; do not rely on PowerPoint auto-fit.",
            "- Shorten, split, or choose another page recipe when text does not fit.",
            "After authoring, run:",
            "python scripts/validate_svg_text_slots.py <project>/svg_output --strict-unboxed --report <project>/reports/svg_text_slot_report.json",
            "Only output SVG markup for the full page.",
        ]
    )


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query and validate PPT Master whole-page layout recipes.")
    parser.add_argument("--recipes", default=str(DEFAULT_RECIPES), help="Path to ppt_master_page_recipes.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("count")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--json", action="store_true")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--page-role", default=None)
    query_parser.add_argument("--content-shape", default=None)
    query_parser.add_argument("--item-count", type=int, default=None)
    query_parser.add_argument("--density", default=None)
    query_parser.add_argument("--avoid", action="append", default=[])
    query_parser.add_argument("--json", action="store_true")

    prompt_parser = subparsers.add_parser("prompt")
    prompt_parser.add_argument("--recipe-id", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--recipe-id", required=True)
    payload_group = validate_parser.add_mutually_exclusive_group(required=True)
    payload_group.add_argument("--payload-json")
    payload_group.add_argument("--payload-file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = load_page_recipes(args.recipes)

    if args.command == "count":
        print(recipe_count(registry))
        return 0

    if args.command == "list":
        rows = [
            {
                "recipe_id": recipe["recipe_id"],
                "name_zh": recipe["name_zh"],
                "page_role": recipe["page_role"],
                "density": recipe["selection"]["density"],
                "best_for": recipe["selection"]["best_for"],
            }
            for recipe in recipes(registry)
        ]
        if args.json:
            _json_print(rows)
        else:
            for row in rows:
                print(f"{row['recipe_id']}\t{row['name_zh']}\t{row['density']}")
        return 0

    if args.command == "query":
        rows = [
            {
                "recipe_id": recipe["recipe_id"],
                "name_zh": recipe["name_zh"],
                "page_role": recipe["page_role"],
                "best_for": recipe["selection"]["best_for"],
            }
            for recipe in select_page_recipes(
                page_role=args.page_role,
                content_shape=args.content_shape,
                item_count=args.item_count,
                density=args.density,
                avoid=args.avoid,
                registry=registry,
            )
        ]
        if args.json:
            _json_print(rows)
        else:
            for row in rows:
                print(f"{row['recipe_id']}\t{row['name_zh']}\t{row['best_for']}")
        return 0 if rows else 1

    if args.command == "prompt":
        print(build_page_prompt(args.recipe_id, registry))
        return 0

    if args.command == "validate":
        if args.payload_file:
            with Path(args.payload_file).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            payload = json.loads(args.payload_json)
        result = validate_page_payload(args.recipe_id, payload, registry)
        _json_print(result)
        return 0 if result["passed"] else 1

    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
