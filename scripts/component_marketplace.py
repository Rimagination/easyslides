#!/usr/bin/env python3
"""Discover and install declarative EasySlides component packs from a catalog."""

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
    from scripts.component_pack import PACK_ID_RE, _semver_parts, install_component_pack, validate_component_pack
except ModuleNotFoundError:  # pragma: no cover
    from component_pack import PACK_ID_RE, _semver_parts, install_component_pack, validate_component_pack


SCHEMA_VERSION = "easyslides.component_marketplace.v1"
DEFAULT_CATALOG = ROOT / "templates" / "components" / "marketplace.json"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _source_path(catalog_path: Path, source: dict[str, Any]) -> Path | None:
    if source.get("kind") != "local":
        return None
    raw = str(source.get("path") or "").replace("\\", "/")
    candidate = (ROOT / raw).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate


def validate_marketplace(catalog_path: str | Path = DEFAULT_CATALOG) -> dict[str, Any]:
    path = Path(catalog_path).resolve()
    issues: list[dict[str, str]] = []
    catalog: dict[str, Any] = {}
    try:
        catalog = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(_issue("MARKETPLACE-CATALOG", f"invalid marketplace catalog: {exc}", str(path)))

    if catalog.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("MARKETPLACE-SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version"))
    packs = catalog.get("packs")
    if not isinstance(packs, list):
        issues.append(_issue("MARKETPLACE-PACKS", "packs must be a list", "packs"))
        packs = []

    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(packs):
        item_path = f"packs[{index}]"
        if not isinstance(item, dict):
            issues.append(_issue("MARKETPLACE-PACK", "pack entry must be an object", item_path))
            continue
        pack_id = str(item.get("pack_id") or "")
        version = str(item.get("version") or "")
        if not PACK_ID_RE.fullmatch(pack_id):
            issues.append(_issue("MARKETPLACE-PACK-ID", "pack_id must be a lowercase slug", f"{item_path}.pack_id"))
        if pack_id in seen:
            issues.append(_issue("MARKETPLACE-PACK-ID", f"duplicate pack_id {pack_id!r}", f"{item_path}.pack_id"))
        seen.add(pack_id)
        if _semver_parts(version) is None:
            issues.append(_issue("MARKETPLACE-PACK-VERSION", "version must use semantic versioning", f"{item_path}.version"))
        source = item.get("source")
        if not isinstance(source, dict) or source.get("kind") not in {"local", "git"}:
            issues.append(_issue("MARKETPLACE-SOURCE", "source.kind must be local or git", f"{item_path}.source"))
            continue
        if source.get("kind") == "local":
            pack_path = _source_path(path, source)
            if pack_path is None or not pack_path.is_dir():
                issues.append(_issue("MARKETPLACE-SOURCE", "local source must resolve inside this repository", f"{item_path}.source.path"))
            else:
                report = validate_component_pack(pack_path)
                if report.get("status") != "pass":
                    issues.append(_issue("MARKETPLACE-PACK-INVALID", f"local pack {pack_id!r} fails its component-pack contract", item_path))
                elif report.get("pack_id") != pack_id or report.get("version") != version:
                    issues.append(_issue("MARKETPLACE-PACK-MISMATCH", "catalog identity must match pack.json", item_path))
        else:
            url = str(source.get("url") or "")
            if not url.startswith(("https://", "http://", "git@", "github:")):
                issues.append(_issue("MARKETPLACE-SOURCE", "git source requires a Git URL or github:owner/repo reference", f"{item_path}.source.url"))
            if not str(source.get("ref") or ""):
                issues.append(_issue("MARKETPLACE-SOURCE", "git source must pin a tag, branch, or commit in ref", f"{item_path}.source.ref"))
        tags = item.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            issues.append(_issue("MARKETPLACE-TAGS", "tags must be a list of non-empty strings", f"{item_path}.tags"))
        validated.append({"pack_id": pack_id, "version": version, "source": source, "tags": tags})
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "catalog": str(path),
        "issue_count": len(issues),
        "issues": issues,
        "pack_count": len(validated),
        "packs": validated,
    }


def search_marketplace(
    query: str = "",
    *,
    catalog_path: str | Path = DEFAULT_CATALOG,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    validation = validate_marketplace(catalog_path)
    catalog = _read_json(Path(catalog_path).resolve())
    needle = query.strip().lower()
    wanted = {tag.strip().lower() for tag in (tags or []) if tag.strip()}
    matches: list[dict[str, Any]] = []
    for item in catalog.get("packs", []):
        if not isinstance(item, dict):
            continue
        item_tags = {str(tag).lower() for tag in item.get("tags", [])}
        text = " ".join(str(item.get(key) or "") for key in ("pack_id", "display_name", "description", "license")) .lower()
        if needle and needle not in text and not any(needle in tag for tag in item_tags):
            continue
        if wanted and not wanted.issubset(item_tags):
            continue
        matches.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if validation["status"] == "pass" else "fail",
        "catalog": validation["catalog"],
        "query": {"text": query, "tags": sorted(wanted)},
        "matches": matches,
        "match_count": len(matches),
        "validation": validation,
    }


def install_marketplace_pack(
    pack_id: str,
    *,
    catalog_path: str | Path = DEFAULT_CATALOG,
    target: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    result = search_marketplace(catalog_path=catalog_path)
    if result["status"] != "pass":
        return {"schema_version": SCHEMA_VERSION, "status": "fail", "operation": "install", "issues": result["validation"]["issues"]}
    entry = next((row for row in result["matches"] if row.get("pack_id") == pack_id), None)
    if not entry:
        return {"schema_version": SCHEMA_VERSION, "status": "fail", "operation": "install", "issues": [_issue("MARKETPLACE-NOT-FOUND", f"unknown marketplace pack {pack_id!r}", "pack_id")]}
    source = entry["source"]
    if source.get("kind") == "local":
        resolved = _source_path(Path(catalog_path).resolve(), source)
        source_value: str | Path = resolved if resolved is not None else ""
    else:
        source_value = str(source.get("url") or "")
        ref = str(source.get("ref") or "")
        if source_value.startswith("github:") and ref:
            source_value = f"{source_value}@{ref}"
        elif ref:
            source_value = f"{source_value}#{ref}"
    kwargs: dict[str, Any] = {"force": force}
    if target is not None:
        kwargs["target"] = target
        kwargs["rebuild_registry"] = False
    report = install_component_pack(source_value, **kwargs)
    return {"schema_version": SCHEMA_VERSION, "operation": "install", "marketplace_entry": entry, "installation": report, "status": report.get("status", "fail")}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search and install declarative EasySlides component packs.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    search = subparsers.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--tag", action="append", default=[])
    install = subparsers.add_parser("install")
    install.add_argument("pack_id")
    install.add_argument("--target", type=Path)
    install.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        report = validate_marketplace(args.catalog)
    elif args.command == "search":
        report = search_marketplace(args.query, catalog_path=args.catalog, tags=args.tag)
    else:
        report = install_marketplace_pack(args.pack_id, catalog_path=args.catalog, target=args.target, force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
