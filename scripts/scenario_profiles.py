#!/usr/bin/env python3
"""Load and validate EasySlides academic scenario rule profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = ROOT / "references" / "scenario_profiles.json"

STRUCTURE_ORDER = {
    "weak": 1,
    "medium": 2,
    "strong": 3,
    "very_strong": 4,
}

REQUIRED_PROFILE_KEYS = {
    "display_name",
    "structure_strength",
    "typical_slide_count",
    "default_story_spine",
    "required_rules",
    "recommended_rules",
    "relaxable_rules",
    "template_policy",
}

REQUIRED_TEMPLATE_POLICY_KEYS = {
    "template_controls_visuals",
    "template_may_override",
    "template_must_not_override",
}


class ScenarioProfileError(RuntimeError):
    """Raised when scenario profile data is missing or inconsistent."""


def load_profiles(path: Path | str = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    """Return the scenario profile catalog from disk."""
    profile_path = Path(path)
    try:
        catalog = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScenarioProfileError(f"scenario profile file not found: {profile_path}") from exc
    except json.JSONDecodeError as exc:
        raise ScenarioProfileError(f"invalid scenario profile JSON: {exc}") from exc
    if not isinstance(catalog, dict):
        raise ScenarioProfileError("scenario profile catalog must be a JSON object")
    return catalog


def structure_rank(value: str) -> int:
    """Return a comparable rank for a structure strength label."""
    try:
        return STRUCTURE_ORDER[value]
    except KeyError as exc:
        raise ScenarioProfileError(f"unknown structure_strength: {value}") from exc


def get_profile(profile_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return one profile by id."""
    catalog = catalog or load_profiles()
    profiles = catalog.get("profiles")
    if not isinstance(profiles, dict):
        raise ScenarioProfileError("catalog profiles must be a JSON object")
    try:
        profile = profiles[profile_id]
    except KeyError as exc:
        raise ScenarioProfileError(f"unknown scenario profile: {profile_id}") from exc
    if not isinstance(profile, dict):
        raise ScenarioProfileError(f"profile {profile_id} must be a JSON object")
    return profile


def get_scenario_variant(
    profile_id: str,
    variant_id: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a declared scenario variant, using the profile default when omitted."""
    profile = get_profile(profile_id, catalog)
    variants = profile.get("scenario_variants")
    if not isinstance(variants, dict) or not variants:
        raise ScenarioProfileError(f"profile {profile_id} has no scenario variants")
    selected = str(variant_id or profile.get("default_scenario_variant") or "").strip()
    if selected not in variants:
        raise ScenarioProfileError(
            f"unknown scenario variant {selected!r} for profile {profile_id!r}"
        )
    variant = variants[selected]
    if not isinstance(variant, dict):
        raise ScenarioProfileError(f"scenario variant {profile_id}/{selected} must be an object")
    return variant


def duration_page_band(
    profile_id: str,
    duration_minutes: int | float,
    *,
    variant_id: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve a presentation duration to the declared page-budget band."""
    try:
        minutes = float(duration_minutes)
    except (TypeError, ValueError):
        return None
    if minutes <= 0:
        return None
    variant = get_scenario_variant(profile_id, variant_id, catalog)
    bands = variant.get("duration_page_bands")
    if not isinstance(bands, list):
        return None
    for band in bands:
        if not isinstance(band, dict):
            continue
        if float(band.get("min_minutes", 0)) <= minutes <= float(band.get("max_minutes", 0)):
            return band
    return None


def validate_profiles(catalog: dict[str, Any]) -> None:
    """Validate the catalog shape and rule-layer separation."""
    if catalog.get("schema_version") != "easyslides.scenario_profiles.v1":
        raise ScenarioProfileError("schema_version must be easyslides.scenario_profiles.v1")

    hard_rule_ids = {
        rule.get("id")
        for rule in catalog.get("hard_rules", [])
        if isinstance(rule, dict) and rule.get("id")
    }
    if not hard_rule_ids:
        raise ScenarioProfileError("hard_rules must define at least one rule id")

    global_policy = catalog.get("template_override_policy")
    if not isinstance(global_policy, dict):
        raise ScenarioProfileError("template_override_policy must be a JSON object")
    _validate_rule_lists(
        "template_override_policy",
        global_policy,
        ["template_may_override", "template_must_not_override"],
    )
    forbidden_visual_overrides = set(global_policy["template_may_override"]) & hard_rule_ids
    if forbidden_visual_overrides:
        raise ScenarioProfileError(
            "template_may_override cannot include hard rules: "
            + ", ".join(sorted(forbidden_visual_overrides))
        )

    profiles = catalog.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ScenarioProfileError("profiles must be a non-empty JSON object")

    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ScenarioProfileError(f"profile {profile_id} must be a JSON object")
        missing = REQUIRED_PROFILE_KEYS - set(profile)
        if missing:
            raise ScenarioProfileError(f"profile {profile_id} missing keys: {sorted(missing)}")
        structure_rank(str(profile["structure_strength"]))
        _validate_slide_count(profile_id, profile["typical_slide_count"])
        _validate_rule_lists(
            profile_id,
            profile,
            ["default_story_spine", "required_rules", "recommended_rules", "relaxable_rules"],
        )
        _validate_template_policy(profile_id, profile["template_policy"], hard_rule_ids)
        _validate_scenario_variants(profile_id, profile)


def _validate_slide_count(profile_id: str, value: Any) -> None:
    if not isinstance(value, dict):
        raise ScenarioProfileError(f"profile {profile_id} typical_slide_count must be an object")
    minimum = value.get("min")
    maximum = value.get("max")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise ScenarioProfileError(f"profile {profile_id} slide count min/max must be integers")
    if minimum <= 0 or maximum < minimum:
        raise ScenarioProfileError(f"profile {profile_id} has invalid slide count range")


def _validate_scenario_variants(profile_id: str, profile: dict[str, Any]) -> None:
    variants = profile.get("scenario_variants")
    if variants is None:
        return
    if not isinstance(variants, dict) or not variants:
        raise ScenarioProfileError(f"profile {profile_id} scenario_variants must be a non-empty object")
    default = profile.get("default_scenario_variant")
    if not isinstance(default, str) or default not in variants:
        raise ScenarioProfileError(
            f"profile {profile_id} default_scenario_variant must name a declared variant"
        )

    for variant_id, variant in variants.items():
        if not isinstance(variant_id, str) or not variant_id:
            raise ScenarioProfileError(f"profile {profile_id} has an invalid scenario variant id")
        if not isinstance(variant, dict):
            raise ScenarioProfileError(f"scenario variant {profile_id}/{variant_id} must be an object")
        workflow = variant.get("workflow_stages")
        if not isinstance(workflow, list) or not workflow or not all(
            isinstance(item, str) and item for item in workflow
        ):
            raise ScenarioProfileError(
                f"scenario variant {profile_id}/{variant_id} workflow_stages must be a non-empty list"
            )
        bands = variant.get("duration_page_bands")
        if not isinstance(bands, list) or not bands:
            raise ScenarioProfileError(
                f"scenario variant {profile_id}/{variant_id} duration_page_bands must be a non-empty list"
            )
        previous_max = 0
        for index, band in enumerate(bands):
            path = f"{profile_id}/{variant_id}.duration_page_bands[{index}]"
            if not isinstance(band, dict):
                raise ScenarioProfileError(f"{path} must be an object")
            required = ("min_minutes", "max_minutes", "min_pages", "max_pages")
            if not all(isinstance(band.get(key), int) for key in required):
                raise ScenarioProfileError(f"{path} min/max minutes and pages must be integers")
            if (
                band["min_minutes"] <= 0
                or band["max_minutes"] < band["min_minutes"]
                or band["min_pages"] <= 0
                or band["max_pages"] < band["min_pages"]
                or band["min_minutes"] <= previous_max
            ):
                raise ScenarioProfileError(f"{path} has invalid or overlapping bounds")
            previous_max = band["max_minutes"]


def _validate_rule_lists(owner: str, data: dict[str, Any], keys: list[str]) -> None:
    for key in keys:
        value = data.get(key)
        if not isinstance(value, list) or not value:
            raise ScenarioProfileError(f"{owner} {key} must be a non-empty list")
        if not all(isinstance(item, str) and item for item in value):
            raise ScenarioProfileError(f"{owner} {key} must contain non-empty strings")


def _validate_template_policy(
    profile_id: str,
    policy: Any,
    hard_rule_ids: set[str],
) -> None:
    if not isinstance(policy, dict):
        raise ScenarioProfileError(f"profile {profile_id} template_policy must be an object")
    missing = REQUIRED_TEMPLATE_POLICY_KEYS - set(policy)
    if missing:
        raise ScenarioProfileError(
            f"profile {profile_id} template_policy missing keys: {sorted(missing)}"
        )
    if policy["template_controls_visuals"] is not True:
        raise ScenarioProfileError(
            f"profile {profile_id} must set template_controls_visuals to true"
        )
    _validate_rule_lists(
        f"profile {profile_id} template_policy",
        policy,
        ["template_may_override", "template_must_not_override"],
    )
    overlap = set(policy["template_may_override"]) & set(policy["template_must_not_override"])
    if overlap:
        raise ScenarioProfileError(
            f"profile {profile_id} template policy has contradictory overrides: "
            + ", ".join(sorted(overlap))
        )
    hard_override = set(policy["template_may_override"]) & hard_rule_ids
    if hard_override:
        raise ScenarioProfileError(
            f"profile {profile_id} template_may_override includes hard rules: "
            + ", ".join(sorted(hard_override))
        )


def _list_payload(catalog: dict[str, Any]) -> dict[str, Any]:
    profiles = catalog["profiles"]
    return {
        "schema_version": catalog["schema_version"],
        "profiles": sorted(profiles),
    }


def main(argv: list[str] | None = None) -> str:
    """CLI entry point. Returns output text for tests and prints in __main__."""
    parser = argparse.ArgumentParser(description="Inspect EasySlides scenario profiles.")
    parser.add_argument("--profile", help="Show one scenario profile by id.")
    parser.add_argument("--list", action="store_true", help="List available profile ids.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--path",
        default=str(DEFAULT_PROFILE_PATH),
        help="Path to scenario_profiles.json.",
    )
    args = parser.parse_args(argv)

    catalog = load_profiles(args.path)
    validate_profiles(catalog)

    if args.profile:
        payload: Any = get_profile(args.profile, catalog)
    else:
        payload = _list_payload(catalog)

    if args.json:
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.profile:
        profile = payload
        lines = [
            f"{args.profile}: {profile['display_name']}",
            f"structure_strength: {profile['structure_strength']}",
            "required_rules:",
            *[f"- {rule}" for rule in profile["required_rules"]],
            "recommended_rules:",
            *[f"- {rule}" for rule in profile["recommended_rules"]],
        ]
        return "\n".join(lines) + "\n"

    return "\n".join(_list_payload(catalog)["profiles"]) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.write(main())
    except ScenarioProfileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
