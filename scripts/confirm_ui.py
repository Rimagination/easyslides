#!/usr/bin/env python3
"""Build a local confirmation page for an EasySlides project."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.confirm_ui.v1"


def _pilot_previews(project: Path, output: Path, pages: list[int], pptx_path: str | Path | None = None) -> dict[str, Any]:
    try:
        from scripts.artifact_receipt import matches
        from scripts.clarification_gate import require_production_decisions
    except ModuleNotFoundError:
        from artifact_receipt import matches
        from clarification_gate import require_production_decisions
    run = _read_json(project / 'image_reconstruction_run.json')
    decisions = require_production_decisions(run.get('decisions', {}))
    if decisions['production_scheme'] not in ('image_full_rebuild', 'image_partial_rebuild'):
        raise ValueError('Pilot source/render comparison requires an image reconstruction scheme')
    render_dir = project / 'reports/rendered_png'
    receipt = _read_json(render_dir / 'render_receipt.json')
    qa = _read_json(project / 'reports/image_reconstruction_pipeline_report.json')
    pptx = Path(pptx_path) if pptx_path else Path(receipt.get('pptx_identity', {}).get('path', ''))
    if (not pptx.is_file() or not pptx.resolve().is_relative_to(project)
            or not matches(receipt.get('pptx_identity'), pptx) or receipt.get('status') != 'pass'):
        raise ValueError('Pilot preview requires a current PowerPoint/render receipt for this project')
    sources = run.get('sources', [])
    identities = run.get('source_identities', [])
    renders = receipt.get('render_identities', [])
    staged = []
    copies = []
    for n in pages:
        if type(n) is not int or not 1 <= n <= len(sources) or pages.count(n) != 1:
            raise ValueError('Pilot pages must be unique page numbers inside the source deck')
        source = (project / sources[n-1]).resolve()
        render = render_dir / f'slide_{n:03}.png'
        if (not source.is_relative_to(project) or n > len(identities) or n > len(renders)
                or Path(renders[n-1].get('path', '')).name != render.name
                or not matches(identities[n-1], source) or not matches(renders[n-1], render)):
            raise ValueError(f'Pilot page {n} has missing or stale source/render evidence')
        row = {'page': n}
        for kind, path in [('source', source), ('render', render)]:
            target = output / 'pilot' / f'{kind}_{n:03}{path.suffix.lower()}'
            copies.append((path, target))
            row[kind] = target.relative_to(output).as_posix()
        staged.append(row)
    # Validate the whole selection before replacing any previous preview asset.
    for path, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return {'pages': staged, 'decisions': decisions,
            'state': 'needs_repair' if qa.get('status') == 'fail' or qa.get('visual_status') == 'fail' or qa.get('blocking_count', 0) else 'needs_review',
            'note': '样页认可仅确认方向；最终文件仍须通过质量检查及人工渲染核对。'}


def _pilot_html(pilot: dict[str, Any]) -> str:
    if not pilot:
        return ''
    sections = []
    for row in pilot['pages']:
        sections.append(f'<h3>第 {row["page"]} 页</h3><div class="pair">'
            + ''.join(f'<figure><figcaption>{label} · 点击查看完整图片</figcaption>'
                      f'<a href="{html.escape(row[key], quote=True)}" target="_blank" rel="noopener">'
                      f'<img src="{html.escape(row[key], quote=True)}" alt="第 {row["page"]} 页{label}" loading="lazy"></a></figure>'
                      for key, label in [('source', '原始图片'), ('render', '可编辑 PPT 实际渲染')]) + '</div>')
    mode = pilot['decisions'].get('reconstruction_mode')
    scope = ('正文与简单结构可编辑；复杂原图整体可移动、替换，图内细节保留为图片。'
             if mode == 'preserve_complex_images' else '按全图矢量方案重建；实际编辑范围以逐对象检查为准。')
    if pilot['decisions'].get('production_scheme') == 'image_partial_rebuild':
        scope = '仅选定区域重建，未选区域保留原图。' + scope
    state = '待修复：整套自动检查存在未解决问题' if pilot['state'] == 'needs_repair' else '待检查：请核对实际样页'
    return ('<section class="pilot"><h2>先看样页，再继续整套</h2>'
            f'<p class="state">{state}</p><p>{scope}</p>' + ''.join(sections)
            + '<p>请核对：图文遮挡、中文与数字、表格对齐、原图标签、页码与可编辑范围。</p>'
            + f'<p>{pilot["note"]}</p><label for="feedback">给 EasySlides 的反馈（手动复制回对话）</label>'
            + '<textarea id="feedback" rows="4" placeholder="例如：认可这两页的方向，继续其余页面；或：第 5 页右侧表格需要对齐。"></textarea>'
            + '<p>本地勾选和填写不会自动提交、不会更新验收状态。</p></section>')


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
<html lang="zh-CN">
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
    .pilot {{ margin-top:32px; border-top:1px solid #deded8; padding-top:24px; }}
    .pair {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
    figure {{ margin:0; min-width:0; }} img {{ width:100%; height:auto; border:1px solid #deded8; }}
    figcaption {{ font-size:13px; color:#555f6d; margin-bottom:8px; }}
    .state {{ background:#fff0d9; padding:12px; border-left:3px solid #aa6327; }}
    textarea {{ display:block; width:100%; box-sizing:border-box; margin:12px 0; padding:12px; font:inherit; }}
    @media(max-width:680px) {{ .pair {{ grid-template-columns:1fr; }} }}
    @media (max-width: 680px) {{ .item {{ grid-template-columns: 24px 1fr; }} .item strong {{ grid-column: 2; }} }}
  </style>
</head>
<body>
  <header><h1>{title}</h1></header>
  <main>
{item_html}
{_pilot_html(manifest.get('pilot', {}))}
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
    pilot_pages: list[int] | None = None,
    pptx: str | Path | None = None,
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
    if pilot_pages:
        manifest['pilot'] = _pilot_previews(project, output, pilot_pages, pptx)
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
    parser.add_argument('--pilot-pages', help='Compare actual source/render pairs, e.g. 1,5. Requires a current render receipt.')
    parser.add_argument('--pptx', help='Explicit PPTX for pilot verification, including a renamed but unchanged artifact.')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = build_confirmation_package(
            args.project,
            args.out,
            brand=args.brand,
            title=args.title,
            pilot_pages=[int(n) for n in args.pilot_pages.split(',')] if args.pilot_pages else None,
            pptx=args.pptx,
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
