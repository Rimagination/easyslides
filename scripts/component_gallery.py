#!/usr/bin/env python3
"""Build a static review gallery for EasySlides component packages."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import sys
import textwrap
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.component_package import (
        INSTALLED_PACKAGES_ROOT,
        PACKAGES_ROOT,
        STORY_SCHEMA_VERSION,
        is_public_component_package,
        load_component_packages_from_roots,
        validate_component_package,
        validate_component_story_payload,
    )
    from scripts.component_preview_gate import validate_component_preview_dir
    from scripts.component_renderer_registry import register_renderer_handler, render_registered
except ModuleNotFoundError:  # pragma: no cover
    from component_package import (
        INSTALLED_PACKAGES_ROOT,
        PACKAGES_ROOT,
        STORY_SCHEMA_VERSION,
        is_public_component_package,
        load_component_packages_from_roots,
        validate_component_package,
        validate_component_story_payload,
    )
    from component_preview_gate import validate_component_preview_dir
    from component_renderer_registry import register_renderer_handler, render_registered


DEFAULT_OUTPUT = ROOT / "templates" / "components" / "gallery"
SCHEMA_VERSION = "easyslides.component_gallery.v1"
CANVAS_W = 1280
CANVAS_H = 720


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _story_payload(package_dir: Path, story_ref: dict[str, Any]) -> dict[str, Any]:
    story_path = package_dir / str(story_ref["payload"])
    story = _read_json(story_path)
    if story.get("schema_version") != STORY_SCHEMA_VERSION:
        raise ValueError(f"{story_path} must use {STORY_SCHEMA_VERSION}")
    payload = story.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{story_path} payload must be an object")
    return payload


def _wrap(text: Any, width: int = 22, max_lines: int = 4) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return [""]
    lines = textwrap.wrap(value, width=width, break_long_words=False, replace_whitespace=False)
    if not lines:
        lines = [value]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(". ") + "..."
    return lines


def _text_block(
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    text: Any,
    size: int,
    fill: str,
    weight: str = "500",
    anchor: str = "middle",
    wrap_width: int = 22,
    max_lines: int = 4,
    slot_id: str = "text",
) -> str:
    lines = _wrap(text, width=wrap_width, max_lines=max_lines)
    line_height = size * 1.25
    start_y = y + h / 2 - ((len(lines) - 1) * line_height) / 2
    tspans = []
    for index, line in enumerate(lines):
        tspans.append(
            f'<tspan x="{x + w / 2:.1f}" y="{start_y + index * line_height:.1f}">{_escape(line)}</tspan>'
        )
    return (
        f'<text data-pptx-textbox="true" data-pptx-box-x="{x:.1f}" data-pptx-box-y="{y:.1f}" '
        f'data-pptx-box-w="{w:.1f}" data-pptx-box-h="{h:.1f}" data-pptx-valign="middle" '
        f'data-center-lock="true" data-slot-id="{_escape(slot_id)}" '
        f'x="{x + w / 2:.1f}" y="{y + h / 2:.1f}" text-anchor="{anchor}" '
        f'font-family="Aptos, Segoe UI, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">'
        f'{"".join(tspans)}</text>'
    )


def _status_badge(status: str, x: int = 1040, y: int = 54) -> str:
    fill = "#0F7B55" if status == "pass" else "#B42318"
    label = "PASS" if status == "pass" else "FAIL"
    return (
        f'<rect x="{x}" y="{y}" width="128" height="34" rx="17" fill="{fill}"/>'
        f'<text x="{x + 64}" y="{y + 23}" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" '
        f'font-size="15" font-weight="800" fill="#FFFFFF">{label}</text>'
    )


def _svg_shell(component_id: str, story_id: str, status: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W} {CANVAS_H}" width="{CANVAS_W}" height="{CANVAS_H}">
  <rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#F7F8FA"/>
  <rect x="38" y="30" width="1204" height="660" rx="18" fill="#FFFFFF" stroke="#D7DDE5"/>
  <rect x="38" y="30" width="1204" height="86" rx="18" fill="#172033"/>
  <rect x="38" y="98" width="1204" height="18" fill="#172033"/>
  <text x="70" y="68" font-family="Aptos, Segoe UI, sans-serif" font-size="24" font-weight="800" fill="#FFFFFF">{_escape(component_id)}</text>
  <text x="70" y="94" font-family="Aptos, Segoe UI, sans-serif" font-size="14" font-weight="600" fill="#B7C3D3">story: {_escape(story_id)} | center-locked text slots</text>
  {_status_badge(status)}
  {body}
</svg>
'''


def _render_three_card(component_id: str, story_id: str, payload: dict[str, Any], status: str) -> str:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    boxes = [(74, 166, 348, 430), (466, 166, 348, 430), (858, 166, 348, 430)]
    body = []
    for index, (x, y, w, h) in enumerate(boxes, start=1):
        item = items[index - 1] if index - 1 < len(items) and isinstance(items[index - 1], dict) else {}
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#FDFEFE" stroke="#CDD6E0"/>')
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="10" rx="5" fill="#1C75BC"/>')
        body.append(f'<circle cx="{x + 42}" cy="{y + 52}" r="22" fill="#EAF3FA" stroke="#C9DFF0"/>')
        body.append(
            f'<text x="{x + 42}" y="{y + 58}" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" '
            f'font-size="16" font-weight="800" fill="#1C75BC">{index:02d}</text>'
        )
        body.append(
            _text_block(
                x=x + 34,
                y=y + 104,
                w=w - 68,
                h=70,
                text=item.get("title", ""),
                size=24,
                fill="#172033",
                weight="800",
                wrap_width=14,
                max_lines=2,
                slot_id="title",
            )
        )
        body.append(f'<line x1="{x + 34}" y1="{y + 196}" x2="{x + w - 34}" y2="{y + 196}" stroke="#D7DDE5"/>')
        body.append(
            _text_block(
                x=x + 34,
                y=y + 220,
                w=w - 68,
                h=138,
                text=item.get("body", ""),
                size=18,
                fill="#4B5B6D",
                weight="500",
                wrap_width=25,
                max_lines=5,
                slot_id="body",
            )
        )
    return _svg_shell(component_id, story_id, status, "\n  ".join(body))


def _render_process(component_id: str, story_id: str, payload: dict[str, Any], status: str) -> str:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    count = max(3, min(5, len(items) or 4))
    gap = 24
    w = (1088 - gap * (count - 1)) / count
    y = 238
    body = ['<line x1="104" y1="318" x2="1176" y2="318" stroke="#9CB6C9" stroke-width="4" stroke-dasharray="8 12"/>']
    for index in range(count):
        x = 96 + index * (w + gap)
        item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
        body.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="250" rx="12" fill="#FFFFFF" stroke="#CDD6E0"/>')
        body.append(f'<rect x="{x + 18:.1f}" y="{y - 30}" width="58" height="58" rx="29" fill="#145F8F"/>')
        body.append(
            f'<text x="{x + 47:.1f}" y="{y + 7}" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" '
            f'font-size="20" font-weight="800" fill="#FFFFFF">{index + 1}</text>'
        )
        body.append(
            _text_block(
                x=x + 20,
                y=y + 54,
                w=w - 40,
                h=56,
                text=item.get("title", ""),
                size=20,
                fill="#172033",
                weight="800",
                wrap_width=12,
                max_lines=2,
                slot_id="title",
            )
        )
        body.append(
            _text_block(
                x=x + 20,
                y=y + 134,
                w=w - 40,
                h=84,
                text=item.get("body", ""),
                size=16,
                fill="#4B5B6D",
                weight="500",
                wrap_width=18,
                max_lines=4,
                slot_id="body",
            )
        )
    return _svg_shell(component_id, story_id, status, "\n  ".join(body))


def _render_figure(component_id: str, story_id: str, payload: dict[str, Any], status: str) -> str:
    body = [
        '<rect x="82" y="156" width="690" height="452" rx="14" fill="#E9EEF3" stroke="#C4CDD8"/>',
        '<rect x="122" y="198" width="610" height="322" rx="8" fill="#F8FAFC" stroke="#D7DDE5" stroke-dasharray="12 10"/>',
        '<text x="427" y="366" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" font-size="28" font-weight="800" fill="#8290A2">FIGURE</text>',
        '<text x="427" y="402" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" font-size="15" font-weight="600" fill="#8290A2">preserve aspect ratio | source-linked</text>',
        '<rect x="824" y="156" width="374" height="452" rx="14" fill="#FFFFFF" stroke="#CDD6E0"/>',
        '<rect x="824" y="156" width="374" height="10" rx="5" fill="#1C75BC"/>',
        _text_block(
            x=858,
            y=206,
            w=306,
            h=84,
            text=payload.get("takeaway", ""),
            size=24,
            fill="#172033",
            weight="800",
            wrap_width=16,
            max_lines=2,
            slot_id="takeaway",
        ),
        '<line x1="858" y1="318" x2="1164" y2="318" stroke="#D7DDE5"/>',
        _text_block(
            x=858,
            y=350,
            w=306,
            h=148,
            text=payload.get("bullets", ""),
            size=17,
            fill="#4B5B6D",
            weight="500",
            wrap_width=26,
            max_lines=5,
            slot_id="bullets",
        ),
    ]
    caption = payload.get("caption") or payload.get("source") or payload.get("image") or ""
    body.append(
        f'<text x="858" y="560" font-family="Aptos, Segoe UI, sans-serif" font-size="13" font-weight="600" fill="#69788A">{_escape(caption)}</text>'
    )
    return _svg_shell(component_id, story_id, status, "\n  ".join(body))


def _render_kpi_row(component_id: str, story_id: str, payload: dict[str, Any], status: str) -> str:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    boxes = [(94, 246, 340, 190), (470, 246, 340, 190), (846, 246, 340, 190)]
    body = []
    for index, (x, y, w, h) in enumerate(boxes):
        item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="#FFFFFF" stroke="#CDD6E0"/>')
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="9" rx="4.5" fill="#0F766E"/>')
        body.append(
            _text_block(
                x=x + 34,
                y=y + 28,
                w=w - 68,
                h=58,
                text=item.get("metric", ""),
                size=34,
                fill="#0F766E",
                weight="850",
                wrap_width=8,
                max_lines=1,
                slot_id="metric",
            )
        )
        body.append(
            _text_block(
                x=x + 34,
                y=y + 92,
                w=w - 68,
                h=34,
                text=item.get("label", ""),
                size=18,
                fill="#172033",
                weight="800",
                wrap_width=14,
                max_lines=1,
                slot_id="label",
            )
        )
        body.append(
            _text_block(
                x=x + 34,
                y=y + 134,
                w=w - 68,
                h=42,
                text=item.get("note", ""),
                size=14,
                fill="#617083",
                weight="500",
                wrap_width=24,
                max_lines=2,
                slot_id="note",
            )
        )
    return _svg_shell(component_id, story_id, status, "\n  ".join(body))


def _render_comparison(component_id: str, story_id: str, payload: dict[str, Any], status: str) -> str:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    boxes = [(82, 184, 520, 372), (678, 184, 520, 372)]
    accents = ["#1C75BC", "#0F766E"]
    body = []
    for index, (x, y, w, h) in enumerate(boxes):
        item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#FFFFFF" stroke="#CDD6E0"/>')
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="11" rx="5.5" fill="{accents[index]}"/>')
        body.append(
            _text_block(
                x=x + 38,
                y=y + 58,
                w=w - 76,
                h=52,
                text=item.get("title", ""),
                size=24,
                fill="#172033",
                weight="850",
                wrap_width=18,
                max_lines=1,
                slot_id="title",
            )
        )
        body.append(f'<line x1="{x + 38}" y1="{y + 136}" x2="{x + w - 38}" y2="{y + 136}" stroke="#D7DDE5"/>')
        body.append(
            _text_block(
                x=x + 38,
                y=y + 170,
                w=w - 76,
                h=128,
                text=item.get("body", ""),
                size=17,
                fill="#4B5B6D",
                weight="500",
                wrap_width=34,
                max_lines=5,
                slot_id="body",
            )
        )
    body.append('<rect x="202" y="584" width="876" height="54" rx="27" fill="#EFF6FB" stroke="#C9DFF0"/>')
    body.append(
        _text_block(
            x=242,
            y=592,
            w=796,
            h=38,
            text=payload.get("synthesis", ""),
            size=15,
            fill="#145F8F",
            weight="700",
            wrap_width=70,
            max_lines=2,
            slot_id="synthesis",
        )
    )
    return _svg_shell(component_id, story_id, status, "\n  ".join(body))


def _render_evidence_stack(component_id: str, story_id: str, payload: dict[str, Any], status: str) -> str:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    count = max(3, min(5, len(items) or 3))
    row_gap = 14
    row_h = (306 - row_gap * (count - 1)) / count
    body = [
        '<rect x="116" y="162" width="1048" height="86" rx="14" fill="#172033" stroke="#172033"/>',
        _text_block(
            x=156,
            y=176,
            w=968,
            h=58,
            text=payload.get("claim", ""),
            size=24,
            fill="#FFFFFF",
            weight="850",
            wrap_width=42,
            max_lines=2,
            slot_id="claim",
        ),
    ]
    for index in range(count):
        y = 286 + index * (row_h + row_gap)
        item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
        body.append(f'<rect x="116" y="{y:.1f}" width="1048" height="{row_h:.1f}" rx="12" fill="#FFFFFF" stroke="#CDD6E0"/>')
        body.append(f'<rect x="138" y="{y + row_h / 2 - 18:.1f}" width="36" height="36" rx="18" fill="#EAF3FA" stroke="#C9DFF0"/>')
        body.append(
            f'<text x="156" y="{y + row_h / 2 + 6:.1f}" text-anchor="middle" font-family="Aptos, Segoe UI, sans-serif" '
            f'font-size="16" font-weight="800" fill="#1C75BC">{index + 1}</text>'
        )
        body.append(
            _text_block(
                x=198,
                y=y + 8,
                w=924,
                h=row_h - 16,
                text=item.get("evidence", ""),
                size=16,
                fill="#4B5B6D",
                weight="600",
                wrap_width=58,
                max_lines=2,
                slot_id="evidence",
            )
        )
    return _svg_shell(component_id, story_id, status, "\n  ".join(body))


register_renderer_handler("three_card_summary", "svg", _render_three_card)
register_renderer_handler("process_timeline", "svg", _render_process)
register_renderer_handler("figure_with_notes", "svg", _render_figure)
register_renderer_handler("kpi_row_3", "svg", _render_kpi_row)
register_renderer_handler("comparison_pair", "svg", _render_comparison)
register_renderer_handler("evidence_stack", "svg", _render_evidence_stack)


def render_story_svg(
    component_id: str,
    story_id: str,
    payload: dict[str, Any],
    status: str,
    renderer_id: str | None = None,
) -> str:
    renderer = renderer_id or component_id
    try:
        return render_registered("svg", renderer, component_id, story_id, payload, status)
    except (KeyError, ValueError):
        return _svg_shell(component_id, story_id, status, '<text x="640" y="360" text-anchor="middle">No renderer yet</text>')


def _render_html(manifest: dict[str, Any]) -> str:
    package_cards = []
    for package in manifest["packages"]:
        story_cards = []
        for story in package["stories"]:
            status_class = "pass" if story["status"] == "pass" else "fail"
            issues = "".join(
                f"<li>{_escape(item.get('slot_id', item.get('code', 'issue')))}: {_escape(item.get('overflow_action', item.get('message', '')))}</li>"
                for item in story.get("violations", [])
            )
            story_cards.append(
                f'''
                <article class="story {status_class}">
                  <div class="story-head">
                    <span>{_escape(story["story_id"])}</span>
                    <strong>{_escape(story["status"].upper())}</strong>
                  </div>
                  <img src="{_escape(story["svg"])}" alt="{_escape(package["component_id"])} {_escape(story["story_id"])} preview">
                  <ul>{issues or "<li>payload fits source asset capacity</li>"}</ul>
                </article>
                '''
            )
        gates = "".join(f"<span>{_escape(gate)}</span>" for gate in package.get("required_gates", []))
        package_cards.append(
            f'''
            <section class="package" id="{_escape(package["component_id"])}">
              <div class="package-title">
                <div>
                  <p>component package</p>
                  <h2>{_escape(package["component_id"])}</h2>
                  <small>source: {_escape(package["source_asset_id"])}</small>
                </div>
                <b>{_escape(package["status"].upper())}</b>
              </div>
              <div class="gates">{gates}</div>
              <div class="stories">
                {"".join(story_cards)}
              </div>
            </section>
            '''
        )

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EasySlides Component Gallery</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #657386;
      --line: #D8DEE7;
      --paper: #F4F5F7;
      --accent: #1C75BC;
      --pass: #0F7B55;
      --fail: #B42318;
      --amber: #B7791F;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Aptos", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(23,32,51,.045) 1px, transparent 1px),
        linear-gradient(0deg, rgba(23,32,51,.045) 1px, transparent 1px),
        var(--paper);
      background-size: 24px 24px;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 24px;
      align-items: end;
      padding: 28px 34px 22px;
      background: rgba(244,245,247,.92);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    h1 {{ margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 34px; letter-spacing: 0; }}
    header p {{ margin: 8px 0 0; color: var(--muted); max-width: 820px; }}
    .metrics {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }}
    .metric {{ min-width: 112px; padding: 10px 12px; background: #fff; border: 1px solid var(--line); }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    main {{ padding: 28px 34px 54px; display: grid; gap: 24px; }}
    .package {{ background: rgba(255,255,255,.94); border: 1px solid var(--line); box-shadow: 0 18px 40px rgba(23,32,51,.08); }}
    .package-title {{ display: flex; justify-content: space-between; gap: 18px; padding: 20px 22px; border-bottom: 1px solid var(--line); }}
    .package-title p {{ margin: 0 0 4px; color: var(--accent); font-size: 12px; font-weight: 800; text-transform: uppercase; }}
    .package-title h2 {{ margin: 0; font-size: 25px; letter-spacing: 0; }}
    .package-title small {{ color: var(--muted); }}
    .package-title b {{ align-self: start; padding: 8px 13px; background: var(--pass); color: white; font-size: 13px; }}
    .gates {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 14px 22px; border-bottom: 1px solid var(--line); }}
    .gates span {{ border: 1px solid #C9D6E3; color: #344255; padding: 5px 8px; font-size: 12px; background: #F8FAFC; }}
    .stories {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; padding: 18px; }}
    .story {{ border: 1px solid var(--line); background: #fff; min-width: 0; }}
    .story-head {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-bottom: 1px solid var(--line); }}
    .story-head span {{ font-weight: 800; }}
    .story.pass .story-head strong {{ color: var(--pass); }}
    .story.fail .story-head strong {{ color: var(--fail); }}
    .story img {{ width: 100%; display: block; aspect-ratio: 16 / 9; background: #E8EDF3; }}
    .story ul {{ margin: 0; padding: 11px 14px 14px 28px; color: var(--muted); min-height: 62px; font-size: 13px; }}
    footer {{ color: var(--muted); padding: 0 34px 30px; font-size: 13px; }}
    @media (max-width: 980px) {{
      header {{ grid-template-columns: 1fr; }}
      .metrics {{ justify-content: flex-start; }}
      .stories {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>EasySlides Component Gallery</h1>
      <p>Generated review surface for component packages. Every story is rendered from package payloads and checked against the source asset capacity contract.</p>
    </div>
    <div class="metrics">
      <div class="metric"><strong>{manifest["package_count"]}</strong><span>packages</span></div>
      <div class="metric"><strong>{manifest["story_count"]}</strong><span>stories</span></div>
      <div class="metric"><strong>{manifest["fail_story_count"]}</strong><span>expected fails</span></div>
    </div>
  </header>
  <main>
    {"".join(package_cards)}
  </main>
  <footer>Schema {SCHEMA_VERSION}. Output generated by scripts/component_gallery.py.</footer>
</body>
</html>
'''


def build_component_gallery(
    *,
    packages_root: Path = PACKAGES_ROOT,
    installed_root: Path | None = INSTALLED_PACKAGES_ROOT,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_dir = output_dir / "previews"
    svg_dir.mkdir(parents=True, exist_ok=True)

    package_rows: list[dict[str, Any]] = []
    package_roots = [packages_root]
    if installed_root and Path(installed_root).resolve() != Path(packages_root).resolve():
        package_roots.append(Path(installed_root))
    for package_dir, package in load_component_packages_from_roots(package_roots):
        if not is_public_component_package(package_dir):
            continue
        package_report = validate_component_package(package_dir, package)
        component_id = str(package.get("component_id") or package_dir.name)
        stories = []
        for story_ref in package.get("stories", []):
            if not isinstance(story_ref, dict):
                continue
            story_id = str(story_ref.get("story_id") or "story")
            payload = _story_payload(package_dir, story_ref)
            payload_report = validate_component_story_payload(str(package.get("source_asset_id") or ""), payload)
            status = "pass" if payload_report["passed"] else "fail"
            svg = render_story_svg(
                component_id,
                story_id,
                payload,
                status,
                renderer_id=str(package.get("renderer_id") or component_id),
            )
            svg_path = svg_dir / f"{component_id}__{story_id}.svg"
            svg_path.write_text(svg, encoding="utf-8")
            stories.append(
                {
                    "story_id": story_id,
                    "expected_status": str(story_ref.get("expected_status") or "pass"),
                    "status": status,
                    "svg": _rel(svg_path, output_dir),
                    "checked_slots": payload_report.get("checked_slots", 0),
                    "violations": payload_report.get("violations", []),
                }
            )
        qa = package.get("qa") if isinstance(package.get("qa"), dict) else {}
        package_rows.append(
            {
                "component_id": component_id,
                "source_asset_id": str(package.get("source_asset_id") or ""),
                "status": package_report["status"],
                "required_gates": list(qa.get("required_gates", [])) if isinstance(qa.get("required_gates"), list) else [],
                "stories": stories,
            }
        )

    if package_rows:
        preview_gate_report = validate_component_preview_dir(svg_dir)
    else:
        preview_gate_report = {
            "schema_version": "easyslides.component_preview_gate_report.v1",
            "status": "not_applicable",
            "issue_count": 0,
            "issues": [],
            "preview_root": str(svg_dir),
            "svg_count": 0,
            "checked_text_count": 0,
            "tolerance_px": 2.0,
            "svgs": [],
            "reason": "no_public_component_packages",
        }
    package_status = "pass" if all(row["status"] == "pass" for row in package_rows) else "fail"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if package_status == "pass" and preview_gate_report["status"] in {"pass", "not_applicable"} else "fail",
        "output_dir": str(output_dir),
        "html": "component_gallery.html",
        "preview_gate_status": preview_gate_report["status"],
        "preview_gate_report": preview_gate_report,
        "package_count": len(package_rows),
        "story_count": sum(len(row["stories"]) for row in package_rows),
        "fail_story_count": sum(
            1
            for row in package_rows
            for story in row["stories"]
            if story["status"] == "fail"
        ),
        "packages": package_rows,
    }
    (output_dir / "component_gallery_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    html = "\n".join(line.rstrip() for line in _render_html(manifest).splitlines()) + "\n"
    (output_dir / "component_gallery.html").write_text(html, encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a static EasySlides component package review gallery.")
    parser.add_argument("--packages-root", type=Path, default=PACKAGES_ROOT)
    parser.add_argument("--installed-root", type=Path, default=INSTALLED_PACKAGES_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = build_component_gallery(
        packages_root=args.packages_root,
        installed_root=args.installed_root,
        output_dir=args.out,
    )
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"Component gallery: {manifest['status']} ({manifest['package_count']} package(s), {manifest['story_count']} story(s))")
        print(args.out / "component_gallery.html")
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
