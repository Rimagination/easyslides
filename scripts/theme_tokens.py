#!/usr/bin/env python3
"""Resolve and validate EasySlides semantic theme tokens.

Templates may expose a ``theme_palettes.json`` catalog.  Legacy packs that do
not yet have one are read from their design specification and receive a
deterministic semantic fallback.  The renderer and visual-asset planner should
consume this module instead of guessing colors from raw SVG files.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "easyslides.theme_tokens.v1"
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")

REQUIRED_ROLES = (
    "background",
    "surface",
    "primary",
    "primary_dark",
    "accent",
    "text_on_light",
    "text_on_dark",
    "muted_on_light",
    "muted_on_dark",
    "border",
    "scrim_dark",
    "scrim_light",
)

DEFAULT_TOKENS = {
    "background": "#FFFFFF",
    "surface": "#F5F7FA",
    "primary": "#003366",
    "primary_dark": "#002244",
    "accent": "#0066CC",
    "text_on_light": "#18212B",
    "text_on_dark": "#FFFFFF",
    "muted_on_light": "#5F6B76",
    "muted_on_dark": "#D9E2EC",
    "border": "#D0D7E0",
    "scrim_dark": "#000000",
    "scrim_light": "#FFFFFF",
}


class ThemeTokenError(ValueError):
    """Raised when a theme catalog cannot be resolved safely."""


def normalize_hex(value: Any, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
        raise ThemeTokenError(f"invalid six-digit hex color: {value!r}")
    return raw.upper()


def parse_theme_overrides(values: Iterable[str] | None) -> dict[str, str]:
    """Parse ``role=#RRGGBB`` overrides used by deck/build commands.

    Theme overrides are intentionally limited to semantic roles.  This keeps
    user-selected color changes inside the template contract instead of
    allowing arbitrary SVG color patches that could damage fixed chrome.
    """
    overrides: dict[str, str] = {}
    for raw_value in values or []:
        raw = str(raw_value or "").strip()
        if not raw or "=" not in raw:
            raise ThemeTokenError(
                f"theme override must use role=#RRGGBB syntax: {raw_value!r}"
            )
        key, value = raw.split("=", 1)
        role = _lower_key(key)
        if role not in REQUIRED_ROLES:
            raise ThemeTokenError(
                f"unknown semantic theme role {key!r}; expected one of {list(REQUIRED_ROLES)}"
            )
        overrides[role] = normalize_hex(value)
    return overrides


def apply_theme_overrides(
    tokens: Mapping[str, Any],
    overrides: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Return validated semantic tokens after applying user overrides."""
    merged = {
        str(key): normalize_hex(value)
        for key, value in tokens.items()
        if str(value or "").strip()
    }
    for key, value in (overrides or {}).items():
        role = _lower_key(key)
        if role not in REQUIRED_ROLES:
            raise ThemeTokenError(f"unknown semantic theme role: {key!r}")
        merged[role] = normalize_hex(value)
    report = validate_tokens(merged)
    if report["status"] != "pass":
        missing = ", ".join(row["role"] for row in report["issues"])
        raise ThemeTokenError(f"theme token set is incomplete after overrides: {missing}")
    return merged


def theme_replacements_for_overrides(
    base_tokens: Mapping[str, Any],
    overrides: Mapping[str, Any] | None,
    existing: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Extend palette replacements so custom semantic colors reach SVG chrome."""
    replacements = {
        str(old).upper(): str(new).upper()
        for old, new in (existing or {}).items()
        if str(old).strip() and str(new).strip()
    }
    for key, value in (overrides or {}).items():
        role = _lower_key(key)
        if role not in REQUIRED_ROLES:
            raise ThemeTokenError(f"unknown semantic theme role: {key!r}")
        old = normalize_hex(base_tokens.get(role), fallback="")
        new = normalize_hex(value)
        if old and new and old != new:
            replacements[old] = new
    return replacements


def _lower_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ThemeTokenError(f"invalid theme catalog JSON: {path}: {exc}") from exc
    return value if isinstance(value, dict) else None


def _colors_from_catalog(catalog: Mapping[str, Any], palette_id: str | None) -> tuple[str, dict[str, str]]:
    palettes = catalog.get("palettes")
    if not isinstance(palettes, Mapping) or not palettes:
        raise ThemeTokenError("theme_palettes.json must contain a non-empty palettes object")
    selected = palette_id or str(catalog.get("default_palette") or "")
    if selected not in palettes:
        if palette_id:
            available = ", ".join(sorted(str(key) for key in palettes))
            raise ThemeTokenError(f"unknown palette {palette_id!r}; available: {available}")
        selected = next(iter(palettes))
    row = palettes.get(selected)
    if not isinstance(row, Mapping):
        raise ThemeTokenError(f"palette {selected!r} must be an object")
    colors = row.get("colors")
    if not isinstance(colors, Mapping):
        colors = {key: value for key, value in row.items() if isinstance(value, str)}
    normalized = {
        _lower_key(key): normalize_hex(value)
        for key, value in colors.items()
        if isinstance(value, str) and HEX_RE.fullmatch(value.strip().upper())
    }
    # Keep explicit role aliases from the catalog as well.
    for key in ("primary_hex", "primary", "primary_dark", "accent", "background", "surface", "border"):
        if key in row and isinstance(row[key], str) and HEX_RE.fullmatch(row[key].strip().upper()):
            normalized.setdefault(_lower_key(key), normalize_hex(row[key]))
    return selected, normalized


def _palette_colors(catalog: Mapping[str, Any], palette_id: str) -> Mapping[str, Any]:
    palettes = catalog.get("palettes")
    if not isinstance(palettes, Mapping):
        raise ThemeTokenError("theme_palettes.json must contain a palettes object")
    row = palettes.get(palette_id)
    if not isinstance(row, Mapping):
        raise ThemeTokenError(f"palette {palette_id!r} must be an object")
    colors = row.get("colors")
    if isinstance(colors, Mapping):
        return colors
    return {key: value for key, value in row.items() if isinstance(value, str)}


def palette_replacements(catalog: Mapping[str, Any], palette_id: str) -> dict[str, str]:
    """Return exact SVG/style color replacements from the catalog default."""
    palettes = catalog.get("palettes")
    if not isinstance(palettes, Mapping) or not palettes:
        raise ThemeTokenError("theme_palettes.json must contain a non-empty palettes object")
    default_id = str(catalog.get("default_palette") or "")
    if default_id not in palettes:
        raise ThemeTokenError("theme_palettes.json default_palette is missing or unknown")
    if palette_id not in palettes:
        raise ThemeTokenError(f"palette {palette_id!r} is not declared in theme_palettes.json")
    roles = catalog.get("replace_roles")
    if not isinstance(roles, list) or not roles:
        raise ThemeTokenError("theme_palettes.json replace_roles must be a non-empty list")
    default_colors = _palette_colors(catalog, default_id)
    target_colors = _palette_colors(catalog, palette_id)
    replacements: dict[str, str] = {}
    for role in roles:
        role_name = str(role)
        if role_name not in default_colors or role_name not in target_colors:
            raise ThemeTokenError(f"palette role {role_name!r} is missing from the default or selected palette")
        old = normalize_hex(default_colors[role_name])
        new = normalize_hex(target_colors[role_name])
        replacements[old] = new
    return replacements


def _colors_from_design_spec(template_dir: Path) -> dict[str, str]:
    path = template_dir / "design_spec.md"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    colors: dict[str, str] = {}
    for line in text.splitlines():
        matches = HEX_RE.findall(line)
        if not matches:
            continue
        label = line.split("|", 2)[1] if "|" in line else line
        key = _lower_key(label)
        if key:
            colors.setdefault(key, normalize_hex(matches[0]))
    primary = re.search(r"primary_color:\s*['\"]?(#[0-9A-Fa-f]{6})", text, re.I)
    if primary:
        colors.setdefault("primary", normalize_hex(primary.group(1)))
    return colors


def _pick(colors: Mapping[str, str], *keys: str, fallback: str) -> str:
    for key in keys:
        normalized_key = _lower_key(key)
        if normalized_key in colors:
            return colors[normalized_key]
    return fallback


def semantic_tokens(colors: Mapping[str, str] | None = None) -> dict[str, str]:
    """Map a loose palette into the fixed semantic token contract."""
    colors = { _lower_key(key): normalize_hex(value) for key, value in (colors or {}).items() }
    primary = _pick(colors, "primary", "primary_color", "primary_dark_blue", "academic_blue", fallback=DEFAULT_TOKENS["primary"])
    primary_dark = _pick(colors, "primary_dark", "deep_blue", "navigation_accent", fallback=primary)
    accent = _pick(colors, "accent", "accent_blue", "sky_cyan", "primary_mid", fallback=DEFAULT_TOKENS["accent"])
    background = _pick(colors, "background", "background_white", "ice_background", "main_background", fallback=DEFAULT_TOKENS["background"])
    surface = _pick(colors, "surface", "subtle_surface", "soft_surface", "card_gray", "light_blue_gray", fallback=DEFAULT_TOKENS["surface"])
    border = _pick(colors, "border", "border_gray", "light_border", fallback=DEFAULT_TOKENS["border"])
    light_text = _pick(colors, "text_on_light", "primary_text", "body_text", "deep_text", "emphasis_text", "ink", fallback=DEFAULT_TOKENS["text_on_light"])
    muted = _pick(colors, "muted_on_light", "secondary_text", "muted_gray", "muted_text", fallback=DEFAULT_TOKENS["muted_on_light"])
    dark_text = _pick(colors, "text_on_dark", fallback=DEFAULT_TOKENS["text_on_dark"])
    muted_dark = _pick(colors, "muted_on_dark", fallback=DEFAULT_TOKENS["muted_on_dark"])
    scrim_dark = _pick(colors, "scrim_dark", fallback=DEFAULT_TOKENS["scrim_dark"])
    scrim_light = _pick(colors, "scrim_light", fallback=DEFAULT_TOKENS["scrim_light"])
    return {
        "background": background,
        "surface": surface,
        "primary": primary,
        "primary_dark": primary_dark,
        "accent": accent,
        "text_on_light": light_text,
        "text_on_dark": dark_text,
        "muted_on_light": muted,
        "muted_on_dark": muted_dark,
        "border": border,
        "scrim_dark": scrim_dark,
        "scrim_light": scrim_light,
    }


def resolve_template_tokens(template_dir: str | Path, palette_id: str | None = None) -> dict[str, Any]:
    """Resolve a template's selected palette into semantic tokens."""
    path = Path(template_dir)
    if not path.is_absolute():
        direct = (ROOT / path).resolve()
        layouts = (ROOT / "templates" / "layouts" / path).resolve()
        path = direct if direct.is_dir() else layouts
    catalog = _read_json(path / "theme_palettes.json")
    selected = palette_id or "default"
    colors: dict[str, str]
    replacements: dict[str, str] = {}
    if catalog:
        selected, colors = _colors_from_catalog(catalog, palette_id)
        replacements = palette_replacements(catalog, selected)
    else:
        colors = _colors_from_design_spec(path)
        selected = palette_id or "design_spec_default"
    tokens = semantic_tokens(colors)
    return {
        "schema_version": SCHEMA_VERSION,
        "template_id": path.name,
        "palette_id": selected,
        "source": "theme_palettes.json" if catalog else "design_spec.md",
        "tokens": tokens,
        "replacements": replacements,
        "required_roles": list(REQUIRED_ROLES),
        "status": "pass",
    }


def validate_tokens(tokens: Mapping[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for role in REQUIRED_ROLES:
        value = tokens.get(role)
        try:
            normalize_hex(value)
        except ThemeTokenError:
            issues.append({"code": "THEME-TOKEN-MISSING", "role": role, "value": str(value or "")})
    return {
        "schema_version": "easyslides.theme_tokens_report.v1",
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve and validate EasySlides semantic theme tokens.")
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("template_dir")
    resolve.add_argument("--palette", default=None)
    validate = sub.add_parser("validate")
    validate.add_argument("template_dir")
    validate.add_argument("--palette", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        resolved = resolve_template_tokens(args.template_dir, args.palette)
        if args.command == "validate":
            report = validate_tokens(resolved["tokens"])
            resolved["validation"] = report
            print(json.dumps(resolved, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "pass" else 1
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ThemeTokenError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
