#!/usr/bin/env python3
"""Build a local confirmation page for an EasySlides project."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.confirm_ui.v1"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^#\s+(.+)", line.strip())
        if match:
            return match.group(1).strip()
    return ""


def _read_markdown_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False}
    text = path.read_text(encoding="utf-8")
    return {
        "exists": True,
        "path": str(path),
        "heading": _first_heading(text),
        "line_count": len(text.splitlines()),
    }


def _deck_plan_summary(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    slides = payload.get("slides") or payload.get("pages") or []
    if not isinstance(slides, list):
        slides = []
    return {
        "exists": path.is_file(),
        "path": str(path) if path.is_file() else "",
        "schema": payload.get("schema") or payload.get("schema_version") or "",
        "title": payload.get("title") or payload.get("deck_title") or "",
        "scenario_profile": payload.get("scenario_profile") or "",
        "canvas_format": payload.get("canvas_format") or payload.get("format") or "",
        "slide_count": len(slides),
    }


def _source_inventory(project: Path) -> list[str]:
    sources = project / "sources"
    if not sources.is_dir():
        return []
    return sorted(path.name for path in sources.iterdir() if path.is_file())


def _html_page(manifest: dict[str, Any]) -> str:
    title = html.escape(str(manifest["title"]))
    items = []
    for item in manifest["confirmation_items"]:
        label = html.escape(str(item["label"]))
        value = html.escape(str(item["value"]))
        items.append(
            f"""<label class="item">
  <input type="checkbox">
  <span>{label}</span>
  <strong>{value}</strong>
</label>"""
        )
    item_html = "\n".join(items)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ font-family: Inter, Segoe UI, Arial, sans-serif; color-scheme: light; }}
    body {{ margin: 0; color: #191a1c; background: #f5f6f3; }}
    header {{ padding: 28px 32px 12px; border-bottom: 1px solid #deded8; }}
    h1 {{ margin: 0; font-size: 24px; line-height: 1.2; letter-spacing: 0; }}
    main {{ max-width: 860px; margin: 0 auto; padding: 24px 28px 36px; }}
    .item {{ display: grid; grid-template-columns: 24px minmax(160px, 1fr) minmax(220px, 2fr); gap: 12px; align-items: center; padding: 13px 0; border-bottom: 1px solid #deded8; }}
    .item span {{ color: #555f6d; }}
    .item strong {{ font-weight: 650; overflow-wrap: anywhere; }}
    input {{ width: 17px; height: 17px; }}
    @media (max-width: 680px) {{ .item {{ grid-template-columns: 24px 1fr; }} .item strong {{ grid-column: 2; }} }}
  </style>
</head>
<body>
  <header><h1>{title}</h1></header>
  <main>
{item_html}
  </main>
</body>
</html>
"""


def build_confirmation_package(
    project_path: str | Path,
    output_dir: str | Path,
    *,
    brand: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    project = Path(project_path).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    deck_plan = _deck_plan_summary(project / "deck_plan.json")
    design_spec = _read_markdown_summary(project / "design_spec.md")
    spec_lock = _read_markdown_summary(project / "spec_lock.md")
    sources = _source_inventory(project)

    confirmation_items = [
        {"id": "project", "label": "Project", "value": project.name},
        {"id": "deck_title", "label": "Deck title", "value": deck_plan["title"] or design_spec.get("heading") or project.name},
        {"id": "canvas_format", "label": "Canvas", "value": deck_plan["canvas_format"] or "unconfirmed"},
        {"id": "slide_count", "label": "Slides", "value": deck_plan["slide_count"] or "unconfirmed"},
        {"id": "scenario", "label": "Scenario", "value": deck_plan["scenario_profile"] or "unconfirmed"},
        {"id": "brand", "label": "Brand", "value": brand or "default"},
        {"id": "sources", "label": "Sources", "value": ", ".join(sources) if sources else "none recorded"},
        {"id": "design_spec", "label": "Design spec", "value": "present" if design_spec["exists"] else "missing"},
        {"id": "spec_lock", "label": "Spec lock", "value": "present" if spec_lock["exists"] else "missing"},
    ]
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_confirmation",
        "title": title or f"Confirm: {project.name}",
        "project_path": str(project),
        "output_dir": str(output),
        "html": "index.html",
        "deck_plan": deck_plan,
        "design_spec": design_spec,
        "spec_lock": spec_lock,
        "sources": sources,
        "confirmation_items": confirmation_items,
    }
    (output / "confirm.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "index.html").write_text(_html_page(manifest), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local EasySlides confirmation page.")
    parser.add_argument("project", help="EasySlides project directory.")
    parser.add_argument("--out", required=True, help="Output directory for confirm.json and index.html.")
    parser.add_argument("--brand", help="Brand preset id to show in the confirmation package.")
    parser.add_argument("--title")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = build_confirmation_package(
            args.project,
            args.out,
            brand=args.brand,
            title=args.title,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(json.dumps({
            "status": manifest["status"],
            "confirm": str(Path(manifest["output_dir"]) / manifest["html"]),
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
