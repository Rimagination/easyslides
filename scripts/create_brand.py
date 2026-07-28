#!/usr/bin/env python3
"""Create and inspect EasySlides brand presets."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.brand.v1"
REGISTRY_SCHEMA_VERSION = "easyslides.brand_registry.v1"
DEFAULT_BRAND_ROOT = Path(__file__).resolve().parents[1] / "templates" / "brands"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_-]+", "-", value.strip()).strip("-_").lower()
    return slug or "brand"


def _validate_color(value: str, field: str) -> str:
    if not HEX_COLOR.match(value):
        raise ValueError(f"{field} must be a #RRGGBB color")
    return value.upper()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _registry_path(root: Path) -> Path:
    return root / "registry.json"


def load_registry(root: str | Path = DEFAULT_BRAND_ROOT) -> dict[str, Any]:
    root = Path(root)
    path = _registry_path(root)
    if not path.exists():
        return {"schema_version": REGISTRY_SCHEMA_VERSION, "brands": []}
    registry = _read_json(path)
    registry.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    registry.setdefault("brands", [])
    return registry


def _save_registry(root: Path, registry: dict[str, Any]) -> None:
    registry["brands"] = sorted(registry.get("brands", []), key=lambda item: item["id"])
    _write_json(_registry_path(root), registry)


def _upsert_registry_entry(root: Path, brand_id: str, name: str, path: Path) -> None:
    registry = load_registry(root)
    rel = path.relative_to(root).as_posix()
    entry = {"id": brand_id, "name": name, "path": rel}
    brands = [item for item in registry.get("brands", []) if item.get("id") != brand_id]
    brands.append(entry)
    registry["brands"] = brands
    _save_registry(root, registry)


def create_brand(
    brand_id: str,
    *,
    name: str | None = None,
    root: str | Path = DEFAULT_BRAND_ROOT,
    primary: str = "#2454A6",
    accent: str = "#E9B44C",
    background: str = "#FFFFFF",
    surface: str = "#F6F7F9",
    text: str = "#161A1D",
    muted: str = "#68707A",
    font_heading: str = "Aptos Display",
    font_body: str = "Aptos",
    logo: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    root = Path(root)
    brand_id = slugify(brand_id)
    brand_name = name or brand_id.replace("-", " ").title()
    brand_dir = root / brand_id
    brand_path = brand_dir / "brand.json"
    if brand_path.exists() and not overwrite:
        raise FileExistsError(f"brand already exists, pass --overwrite: {brand_path}")

    logo_target = ""
    if logo:
        logo_path = Path(logo)
        if not logo_path.is_file():
            raise FileNotFoundError(f"logo not found: {logo_path}")
        assets_dir = brand_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        copied = assets_dir / logo_path.name
        shutil.copy2(logo_path, copied)
        logo_target = copied.relative_to(brand_dir).as_posix()

    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": brand_id,
        "name": brand_name,
        "palette": {
            "primary": _validate_color(primary, "primary"),
            "accent": _validate_color(accent, "accent"),
            "background": _validate_color(background, "background"),
            "surface": _validate_color(surface, "surface"),
            "text": _validate_color(text, "text"),
            "muted": _validate_color(muted, "muted"),
        },
        "typography": {
            "heading": font_heading,
            "body": font_body,
        },
        "logo": logo_target,
        "usage": {
            "preferred_layouts": [],
            "avoid": [],
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(brand_path, payload)
    _upsert_registry_entry(root, brand_id, brand_name, brand_path)
    return brand_path


def list_brands(root: str | Path = DEFAULT_BRAND_ROOT) -> list[dict[str, Any]]:
    return load_registry(root).get("brands", [])


def show_brand(brand_id: str, root: str | Path = DEFAULT_BRAND_ROOT) -> dict[str, Any]:
    root = Path(root)
    brand_id = slugify(brand_id)
    for entry in list_brands(root):
        if entry.get("id") == brand_id:
            return _read_json(root / entry["path"])
    path = root / brand_id / "brand.json"
    if path.is_file():
        return _read_json(path)
    raise FileNotFoundError(f"brand not found: {brand_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and inspect EasySlides brand presets.")
    parser.add_argument("--root", default=str(DEFAULT_BRAND_ROOT), help="Brand preset root directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a brand preset.")
    init.add_argument("brand_id")
    init.add_argument("--name")
    init.add_argument("--primary", default="#2454A6")
    init.add_argument("--accent", default="#E9B44C")
    init.add_argument("--background", default="#FFFFFF")
    init.add_argument("--surface", default="#F6F7F9")
    init.add_argument("--text", default="#161A1D")
    init.add_argument("--muted", default="#68707A")
    init.add_argument("--font-heading", default="Aptos Display")
    init.add_argument("--font-body", default="Aptos")
    init.add_argument("--logo")
    init.add_argument("--overwrite", action="store_true")

    subparsers.add_parser("list", help="List brand presets.")

    show = subparsers.add_parser("show", help="Show one brand preset.")
    show.add_argument("brand_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "init":
            path = create_brand(
                args.brand_id,
                name=args.name,
                root=root,
                primary=args.primary,
                accent=args.accent,
                background=args.background,
                surface=args.surface,
                text=args.text,
                muted=args.muted,
                font_heading=args.font_heading,
                font_body=args.font_body,
                logo=args.logo,
                overwrite=args.overwrite,
            )
            print(json.dumps({"status": "ok", "brand": str(path)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "list":
            print(json.dumps({"brands": list_brands(root)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "show":
            print(json.dumps(show_brand(args.brand_id, root), ensure_ascii=False, indent=2))
            return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
