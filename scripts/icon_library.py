#!/usr/bin/env python3
"""Productized icon catalog and project-local icon synchronization.

The SVG files remain the source of truth. This module adds stable family
metadata, lightweight semantic search, validation, and the same project-local
asset preparation boundary used by PPT Master.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ICONS_ROOT = ROOT / "templates" / "icons"
MANIFEST_PATH = ICONS_ROOT / "icons_manifest.js"
SCHEMA_VERSION = "easyslides.icon_library.v1"
REPORT_SCHEMA_VERSION = "easyslides.icon_library_report.v1"

FAMILY_META: dict[str, dict[str, Any]] = {
    "chunk-filled": {
        "style": "fill",
        "role": "stylistic",
        "view_box": "0 0 16 16",
        "source": "chunk-icons / SVG Repo attribution in PPT Master",
        "display_name": "Chunk Filled",
    },
    "lucide": {
        "style": "stroke",
        "role": "stylistic",
        "view_box": "0 0 24 24",
        "source": "EasySlides curated additions; not bundled by current PPT Master main",
        "display_name": "Lucide",
    },
    "tabler-filled": {
        "style": "fill",
        "role": "stylistic",
        "view_box": "0 0 24 24",
        "source": "Tabler Icons",
        "display_name": "Tabler Filled",
    },
    "tabler-outline": {
        "style": "stroke",
        "role": "stylistic",
        "view_box": "0 0 24 24",
        "source": "Tabler Icons",
        "display_name": "Tabler Outline",
    },
    "phosphor-duotone": {
        "style": "duotone",
        "role": "stylistic",
        "view_box": "0 0 256 256",
        "source": "Phosphor Icons",
        "display_name": "Phosphor Duotone",
    },
    "simple-icons": {
        "style": "brand",
        "role": "brand",
        "view_box": "0 0 24 24",
        "source": "Simple Icons",
        "display_name": "Simple Icons",
    },
}
STYLISTIC_FAMILIES = {family for family, meta in FAMILY_META.items() if meta["role"] == "stylistic"}
BRAND_FAMILIES = {family for family, meta in FAMILY_META.items() if meta["role"] == "brand"}
FAMILY_ALIASES = {"chunk": "chunk-filled", "tabler": "tabler-outline", "phosphor": "phosphor-duotone"}

QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "environment": ("leaf", "tree", "plant", "recycle", "droplet", "water", "wind", "earth", "sun", "cloud"),
    "环境": ("leaf", "tree", "plant", "recycle", "droplet", "water", "wind", "earth", "sun", "cloud"),
    "water": ("water", "droplet", "waves", "ripple", "fish"),
    "水": ("water", "droplet", "waves", "ripple", "fish"),
    "person": ("user", "users", "person", "people", "team"),
    "人物": ("user", "users", "person", "people", "team"),
    "education": ("book", "school", "graduation", "chalkboard", "library"),
    "教育": ("book", "school", "graduation", "chalkboard", "library"),
    "data": ("chart", "database", "table", "report", "analytics", "graph"),
    "数据": ("chart", "database", "table", "report", "analytics", "graph"),
    "method": ("flask", "microscope", "test", "settings", "process", "workflow"),
    "方法": ("flask", "microscope", "test", "settings", "process", "workflow"),
}


def _family_id(raw: str) -> str:
    return FAMILY_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _icon_record(family: str, path: Path) -> dict[str, Any]:
    meta = FAMILY_META[family]
    return {
        "name": path.stem,
        "token": f"{family}/{path.stem}",
        "family": family,
        "path": _relative(path),
        "style": meta["style"],
        "role": meta["role"],
        "view_box": meta["view_box"],
        "source": meta["source"],
    }


def load_icon_library(*, icons_root: str | Path | None = None, include_icons: bool = True) -> dict[str, Any]:
    """Scan the local icon directories into a deterministic catalog."""
    root = Path(icons_root) if icons_root else ICONS_ROOT
    families: list[dict[str, Any]] = []
    for family_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        family = family_dir.name
        if family not in FAMILY_META:
            continue
        paths = sorted(family_dir.glob("*.svg"), key=lambda path: path.stem.lower())
        meta = FAMILY_META[family]
        entry: dict[str, Any] = {
            "family": family,
            "display_name": meta["display_name"],
            "style": meta["style"],
            "role": meta["role"],
            "view_box": meta["view_box"],
            "source": meta["source"],
            "count": len(paths),
            "path": _relative(family_dir),
        }
        if include_icons:
            entry["icons"] = [_icon_record(family, path) for path in paths]
        families.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "library_id": "easyslides-icons",
        "root": _relative(root),
        "manifest_path": _relative(root / "icons_manifest.js"),
        "family_count": len(families),
        "icon_count": sum(int(family["count"]) for family in families),
        "families": families,
    }


def _query_terms(query: str) -> list[str]:
    raw = str(query or "").strip().lower()
    terms = [raw]
    terms.extend(QUERY_ALIASES.get(raw, ()))
    return [term for term in dict.fromkeys(terms) if term]


def search_icons(
    query: str,
    *,
    family: str | None = None,
    style: str | None = None,
    role: str | None = None,
    limit: int = 20,
    library: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    family_id = _family_id(family) if family else None
    rows: list[tuple[int, dict[str, Any]]] = []
    for family_entry in (library or load_icon_library()).get("families", []):
        if family_id and family_entry["family"] != family_id:
            continue
        if style and family_entry["style"] != style:
            continue
        if role and family_entry["role"] != role:
            continue
        for icon in family_entry.get("icons", []):
            name = str(icon["name"]).lower()
            score = 0
            for term in terms:
                if term == name:
                    score += 8
                elif term in name:
                    score += 4
            if score:
                rows.append((score, icon))
    rows.sort(key=lambda row: (-row[0], row[1]["token"]))
    return [icon for _, icon in rows[: max(limit, 0)]]


def validate_icon_library(library: dict[str, Any] | None = None) -> dict[str, Any]:
    library = library or load_icon_library()
    issues: list[dict[str, str]] = []
    families = library.get("families")
    if library.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "ICON-LIBRARY-SCHEMA", "message": "unexpected icon library schema"})
    if not isinstance(families, list) or not families:
        issues.append({"code": "ICON-LIBRARY-EMPTY", "message": "families must be a non-empty list"})
        families = []
    seen: set[str] = set()
    for family in families:
        family_id = str(family.get("family") or "")
        if family_id not in FAMILY_META:
            issues.append({"code": "ICON-LIBRARY-FAMILY", "message": f"unknown family {family_id!r}"})
            continue
        if family_id in seen:
            issues.append({"code": "ICON-LIBRARY-DUPLICATE", "message": f"duplicate family {family_id!r}"})
        seen.add(family_id)
        if int(family.get("count") or 0) <= 0:
            issues.append({"code": "ICON-LIBRARY-COUNT", "message": f"family {family_id!r} is empty"})
        if family.get("style") != FAMILY_META[family_id]["style"]:
            issues.append({"code": "ICON-LIBRARY-STYLE", "message": f"style mismatch for {family_id!r}"})
        tokens = [str(icon.get("token") or "") for icon in family.get("icons", []) if isinstance(icon, dict)]
        if len(tokens) != len(set(tokens)):
            issues.append({"code": "ICON-LIBRARY-TOKEN", "message": f"duplicate icon token in {family_id!r}"})
    if set(seen) != set(FAMILY_META):
        missing = sorted(set(FAMILY_META) - seen)
        issues.append({"code": "ICON-LIBRARY-MISSING-FAMILY", "message": f"missing families: {', '.join(missing)}"})
    manifest_total = library.get("icon_count")
    if not isinstance(manifest_total, int) or manifest_total <= 0:
        issues.append({"code": "ICON-LIBRARY-TOTAL", "message": "icon_count must be positive"})
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "family_count": len(families),
        "icon_count": int(library.get("icon_count") or 0),
    }


def resolve_icon_token(token: str, *, icons_root: Path = ICONS_ROOT) -> tuple[str, Path] | None:
    raw = str(token or "").strip()
    if "/" not in raw:
        family, name = "chunk-filled", raw
    else:
        family, name = raw.split("/", 1)
        family = _family_id(family)
    if family not in FAMILY_META or not name or "/" in name:
        return None
    path = icons_root / family / f"{name}.svg"
    return f"{family}/{name}", path


def sync_icons(project_path: str | Path, tokens: list[str], *, icons_root: Path = ICONS_ROOT) -> dict[str, Any]:
    """Copy selected global icons into a project's local asset pool."""
    project = Path(project_path)
    if not project.is_dir():
        raise FileNotFoundError(f"project not found: {project}")
    normalized: list[tuple[str, Path]] = []
    missing: list[str] = []
    for token in tokens:
        resolved = resolve_icon_token(token, icons_root=icons_root)
        if resolved is None or not resolved[1].is_file():
            missing.append(str(token))
            continue
        normalized.append(resolved)

    stylistic = sorted(
        {
            token.split("/", 1)[0]
            for token, _ in normalized
            if token.split("/", 1)[0] in STYLISTIC_FAMILIES
        }
    )
    if len(stylistic) > 1:
        return {
            "status": "fail",
            "copied": [],
            "missing": missing,
            "violations": [{"code": "ICON-STYLE-MIX", "message": f"choose one stylistic family: {', '.join(stylistic)}"}],
        }

    copied: list[str] = []
    for token, source in normalized:
        destination = project / "icons" / f"{token}.svg"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(token)
    return {
        "status": "pass" if not missing else "fail",
        "copied": copied,
        "missing": missing,
        "violations": [] if not missing else [{"code": "ICON-MISSING", "message": f"missing icons: {', '.join(missing)}"}],
    }


def validate_icon_payload(family: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an icon-family payload without constraining color choices."""
    family_id = _family_id(family)
    violations: list[dict[str, str]] = []
    raw_token = payload.get("icon_name") or payload.get("token") or payload.get("icon")
    if not isinstance(raw_token, str) or not raw_token.strip():
        violations.append({"code": "ICON-PAYLOAD-NAME", "message": "icon payload needs icon_name, token, or icon"})
    else:
        resolved = resolve_icon_token(raw_token)
        if resolved is None or not resolved[1].is_file():
            violations.append({"code": "ICON-PAYLOAD-MISSING", "message": f"icon does not exist: {raw_token}"})
        elif resolved[0].split("/", 1)[0] != family_id:
            violations.append({"code": "ICON-PAYLOAD-FAMILY", "message": f"icon {raw_token!r} does not belong to {family_id!r}"})
    return {
        "passed": not violations,
        "checked_slots": 1 if payload else 0,
        "violations": violations,
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect, search, validate, and sync EasySlides icon assets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--json", action="store_true")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--family")
    list_parser.add_argument("--json", action="store_true")

    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--family")
    search.add_argument("--style")
    search.add_argument("--role")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--json", action="store_true")

    sync = subparsers.add_parser("sync")
    sync.add_argument("project_path")
    sync.add_argument("tokens", nargs="+")
    sync.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    library = load_icon_library()
    if args.command == "validate":
        report = validate_icon_library(library)
        if args.json:
            _print_json(report)
        else:
            print(f"Icon library: {report['status']} ({report['issue_count']} issue(s), {report['icon_count']} icons)")
        return 0 if report["status"] == "pass" else 1
    if args.command == "list":
        rows = library["families"]
        if args.family:
            family_id = _family_id(args.family)
            rows = [row for row in rows if row["family"] == family_id]
        if args.json:
            _print_json(rows)
        else:
            for row in rows:
                print(f"{row['family']}\t{row['count']}\t{row['style']}\t{row['role']}\t{row['source']}")
        return 0 if rows else 1
    if args.command == "search":
        rows = search_icons(args.query, family=args.family, style=args.style, role=args.role, limit=args.limit, library=library)
        if args.json:
            _print_json({"schema_version": SCHEMA_VERSION, "matches": rows, "match_count": len(rows)})
        else:
            for row in rows:
                print(f"{row['token']}\t{row['style']}\t{row['source']}")
        return 0 if rows else 1
    if args.command == "sync":
        result = sync_icons(args.project_path, args.tokens)
        if args.json:
            _print_json(result)
        else:
            for token in result["copied"]:
                print(f"[OK] {token}")
            for token in result["missing"]:
                print(f"[MISSING] {token}")
            for violation in result["violations"]:
                print(f"[ERROR] {violation['message']}")
        return 0 if result["status"] == "pass" else 1
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
