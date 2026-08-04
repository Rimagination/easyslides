#!/usr/bin/env python3
"""Generate a capacity stress-test deck for the five active academic templates."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from scripts.text_capacity import SlotCapacity, fit_text_to_capacity, resolve_slot_capacity
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from text_capacity import SlotCapacity, fit_text_to_capacity, resolve_slot_capacity


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"
ACTIVE_TEMPLATES = (
    "academic_general",
    "academic_scqa",
    "defense_leftnav",
    "defense_topnav",
    "literature_minimal",
)
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


STRESS_CASES = (
    ("normal", 0.8),
    ("critical", 1.0),
    ("overload", 1.5),
)
CASE_LABELS = {
    "normal": "80% 负载",
    "critical": "100% 容量",
    "overload": "150% 压力",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def text_content(elem: ET.Element) -> str:
    return "".join(elem.itertext())


def local_name(elem: ET.Element) -> str:
    return elem.tag.split("}", 1)[-1]


def first_slot(elem: ET.Element) -> str:
    slot = elem.get("data-slot")
    if slot:
        return slot
    text = text_content(elem)
    start = text.find("{{")
    end = text.find("}}", start + 2)
    if start >= 0 and end > start:
        return text[start + 2 : end]
    token = elem.get("data-slot-token") or ""
    if token.startswith("{{") and token.endswith("}}"):
        return token[2:-2]
    return ""


def content_slots(layouts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    models = layouts.get("slot_models", {})
    content = models.get("content", [])
    return {str(slot["slot_id"]): slot for slot in content if isinstance(slot, dict) and slot.get("slot_id")}


def repeat_phrase(chars: int) -> str:
    phrase = "容量约束验证展示生成内容必须先服从文本框边界再表达论点"
    repeats = chars // len(phrase) + 2
    return (phrase * repeats)[:chars]


def clear_children(elem: ET.Element) -> None:
    elem.text = None
    elem.tail = elem.tail
    for child in list(elem):
        elem.remove(child)


def set_text_lines(elem: ET.Element, lines: list[str]) -> None:
    clear_children(elem)
    if not lines:
        elem.text = ""
        return
    x = elem.get("x") or elem.get("data-pptx-box-x") or "0"
    try:
        font_size = float(elem.get("font-size") or "18")
    except ValueError:
        font_size = 18.0
    line_step = round(font_size * 1.25, 2)
    box_y = elem.get("data-pptx-box-y")
    box_h = elem.get("data-pptx-box-h")
    if box_y is not None and box_h is not None:
        try:
            top = float(box_y)
            height = float(box_h)
            total_height = font_size + line_step * (len(lines) - 1)
            valign = elem.get("data-pptx-valign")
            if valign == "middle" and len(lines) == 1:
                baseline = top + height / 2 + font_size * 0.35
            else:
                baseline = top + max(font_size, (height - total_height) / 2 + font_size * 0.85)
            elem.set("y", str(round(baseline, 2)).rstrip("0").rstrip("."))
            elem.attrib.pop("dominant-baseline", None)
        except ValueError:
            pass
    for index, line in enumerate(lines):
        tspan = ET.SubElement(elem, f"{{{SVG_NS}}}tspan")
        tspan.text = line
        tspan.set("x", x)
        if index > 0:
            tspan.set("dy", str(line_step).rstrip("0").rstrip("."))


def prepare_stress_textbox(elem: ET.Element, cap: SlotCapacity) -> None:
    elem.set("fill", "#1F2937")
    elem.attrib.pop("fill-opacity", None)
    elem.set("font-size", str(cap.font_size_px).rstrip("0").rstrip("."))
    elem.attrib.pop("data-pptx-valign", None)
    box_x = elem.get("data-pptx-box-x")
    box_w = elem.get("data-pptx-box-w")
    if box_x is None or box_w is None:
        return
    try:
        x = float(box_x)
        w = float(box_w)
    except ValueError:
        return
    pad = min(34.0, max(w / 12, 0.0))
    text_x = x + pad
    text_w = max(w - pad * 2, 1.0)
    value_x = str(round(text_x, 2)).rstrip("0").rstrip(".")
    value_w = str(round(text_w, 2)).rstrip("0").rstrip(".")
    elem.set("x", value_x)
    elem.set("text-anchor", "start")
    elem.set("data-pptx-box-x", value_x)
    elem.set("data-pptx-box-w", value_w)


def remove_unbound_content_guides(root: ET.Element) -> None:
    for parent in root.iter():
        for child in list(parent):
            if local_name(child) != "text" or first_slot(child):
                continue
            if child.get("fill") in {"#CBD5E1", "#94A3B8"}:
                parent.remove(child)


def fill_content_svg(
    template_id: str,
    layouts: dict[str, Any],
    case_id: str,
    ratio: float,
    slide_index: int,
) -> tuple[str, list[dict[str, Any]]]:
    source_svg = LAYOUTS_ROOT / template_id / "03_content.svg"
    tree = ET.parse(source_svg)
    root = tree.getroot()
    slots = content_slots(layouts)
    stress_slot_ids = {"CONTENT_BODY"}
    if "CONTENT_BODY" not in slots:
        stress_slot_ids.add("CONTENT_AREA")
    checks: list[dict[str, Any]] = []

    fallback_values = {
        "SECTION_NUM": f"{slide_index:02d}",
        "ACTIVE_SECTION": "容量验证",
        "ACTIVE_SECTION_LABEL": "容量验证",
        "CHAPTER_TITLE": template_id,
        "PAGE_TITLE": CASE_LABELS[case_id],
        "LOGO": "EasySlides",
        "KEY_MESSAGE": f"{CASE_LABELS[case_id]}：正文按槽位容量输入，输出限制在安全区内",
        "CONTENT_AREA": "内容安全区",
        "SOURCE": "capacity_stress_demo",
        "SECTION_NAME": "Text fit",
        "PAGE_NUM": str(slide_index),
    }
    has_rendered_body_probe = False

    for elem in root.iter():
        if local_name(elem) != "text":
            continue
        slot_id = first_slot(elem)
        if not slot_id:
            continue
        slot = slots.get(slot_id)
        if slot and slot.get("role") != "page_number":
            cap = resolve_slot_capacity(layouts, slot)
            if slot_id in stress_slot_ids:
                has_rendered_body_probe = True
                prepare_stress_textbox(elem, cap)
                requested_chars = max(1, round(cap.capacity_chars * ratio))
                raw = repeat_phrase(requested_chars)
            else:
                raw = fallback_values.get(slot_id, repeat_phrase(cap.capacity_chars))
                requested_chars = min(len(raw), cap.capacity_chars)
            fit = fit_text_to_capacity(raw, cap)
            set_text_lines(elem, fit.lines)
            checks.append(
                {
                    "slot_id": slot_id,
                    "role": cap.role,
                    "case": case_id,
                    "requested_chars": requested_chars,
                    "rendered_chars": fit.rendered_chars,
                    "capacity_chars": cap.capacity_chars,
                    "rendered_lines": len(fit.lines),
                    "raw_lines": fit.raw_line_count,
                    "max_lines": cap.max_lines,
                    "max_chars_per_line_zh": cap.max_chars_per_line_zh,
                    "overflow": fit.output_overflow,
                    "input_over_capacity": fit.input_over_capacity,
                    "action": fit.action,
                }
            )
        else:
            value = fallback_values.get(slot_id, slot_id)
            set_text_lines(elem, [value])

    if not has_rendered_body_probe:
        # Component-first templates deliberately keep their body canvas out of
        # the shell SVG. Preserve one comparable body-capacity check without
        # turning that invisible planning region back into visible slide copy.
        cap = resolve_slot_capacity(
            layouts,
            {"slot_id": "BODY_CAPACITY_PROBE", "role": "body"},
        )
        requested_chars = max(1, round(cap.capacity_chars * ratio))
        fit = fit_text_to_capacity(repeat_phrase(requested_chars), cap)
        checks.append(
            {
                "slot_id": cap.slot_id,
                "role": cap.role,
                "case": case_id,
                "requested_chars": requested_chars,
                "rendered_chars": fit.rendered_chars,
                "capacity_chars": cap.capacity_chars,
                "rendered_lines": len(fit.lines),
                "raw_lines": fit.raw_line_count,
                "max_lines": cap.max_lines,
                "max_chars_per_line_zh": cap.max_chars_per_line_zh,
                "overflow": fit.output_overflow,
                "input_over_capacity": fit.input_over_capacity,
                "action": fit.action,
            }
        )

    if "CONTENT_AREA" in stress_slot_ids:
        remove_unbound_content_guides(root)

    return ET.tostring(root, encoding="unicode"), checks


def matrix_rows(template_id: str, layouts: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for slot_id, slot in content_slots(layouts).items():
        if slot.get("role") == "page_number" or slot.get("fixed_geometry") is True:
            continue
        cap = resolve_slot_capacity(layouts, slot)
        rows.append(
            {
                "template": template_id,
                "slot": slot_id,
                "role": cap.role,
                "font": cap.font_size_px,
                "min_font": cap.min_font_size_px,
                "max_lines": cap.max_lines,
                "chars_per_line": cap.max_chars_per_line_zh,
                "capacity_chars": cap.capacity_chars,
                "overflow_action": cap.overflow_action,
            }
        )
    return rows


def write_capacity_matrix(project_dir: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Capacity Stress Demo Matrix",
        "",
        "| Template | Slot | Role | Font | Min font | Max lines | Chars/line | Capacity | Overflow action |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {template} | {slot} | {role} | {font} | {min_font} | {max_lines} | "
            "{chars_per_line} | {capacity_chars} | {overflow_action} |".format(**row)
        )
    (project_dir / "capacity_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_png_previews(project_dir: Path) -> dict[str, Any]:
    previews_dir = project_dir / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    try:
        import cairosvg  # type: ignore
        for svg_path in sorted((project_dir / "svg_output").glob("*.svg")):
            png_path = previews_dir / f"{svg_path.stem}.png"
            cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=1280, output_height=720)
            rendered.append(str(png_path.relative_to(project_dir)))
        return {"status": "rendered", "renderer": "cairosvg", "files": rendered}
    except Exception as cairo_exc:  # pragma: no cover - depends on environment
        return render_png_previews_with_playwright(project_dir, previews_dir, str(cairo_exc))


def render_png_previews_with_playwright(project_dir: Path, previews_dir: Path, cairo_error: str) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on environment
        return {
            "status": "skipped",
            "reason": f"cairosvg failed: {cairo_error}; playwright unavailable: {exc}",
            "files": [],
        }

    rendered = []
    html_path = project_dir / "_render_svg_preview.html"
    html_path.write_text(
        "<!doctype html><html><body style='margin:0;background:white'></body></html>",
        encoding="utf-8",
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=find_local_chromium())
            page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
            for svg_path in sorted((project_dir / "svg_output").glob("*.svg")):
                svg_text = svg_path.read_text(encoding="utf-8")
                page.set_content(
                    "<!doctype html><html><body style='margin:0;background:white'>"
                    + svg_text
                    + "</body></html>",
                    wait_until="load",
                )
                png_path = previews_dir / f"{svg_path.stem}.png"
                page.screenshot(path=str(png_path), full_page=False)
                rendered.append(str(png_path.relative_to(project_dir)))
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on local browser install
        return {
            "status": "skipped",
            "reason": f"cairosvg failed: {cairo_error}; playwright render failed: {exc}",
            "files": rendered,
        }
    finally:
        html_path.unlink(missing_ok=True)
    return {"status": "rendered", "renderer": "playwright", "cairo_error": cairo_error, "files": rendered}


def find_local_chromium() -> str | None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def generate_demo(project_dir: Path, *, render_png: bool = True) -> dict[str, Any]:
    if project_dir.exists():
        shutil.rmtree(project_dir)
    svg_dir = project_dir / "svg_output"
    svg_dir.mkdir(parents=True, exist_ok=True)

    all_checks: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    templates_report = []
    slide_index = 1
    for template_id in ACTIVE_TEMPLATES:
        layouts = read_json(LAYOUTS_ROOT / template_id / "layouts.json")
        all_rows.extend(matrix_rows(template_id, layouts))
        template_slides = []
        for case_id, ratio in STRESS_CASES:
            svg, checks = fill_content_svg(template_id, layouts, case_id, ratio, slide_index)
            name = f"{slide_index:02d}_{template_id}_{case_id}.svg"
            (svg_dir / name).write_text(svg, encoding="utf-8")
            all_checks.extend([{"slide": name, "template": template_id, **check} for check in checks])
            template_slides.append(name)
            slide_index += 1
        templates_report.append({"template_id": template_id, "slides": template_slides})

    write_capacity_matrix(project_dir, all_rows)
    preview_report = render_png_previews(project_dir) if render_png else {"status": "skipped", "files": []}
    overflow_count = sum(1 for check in all_checks if check["overflow"])
    report = {
        "schema_version": "easyslides.capacity_stress_report.v1",
        "project_dir": str(project_dir),
        "slide_count": slide_index - 1,
        "templates": templates_report,
        "stress_cases": [{"id": case_id, "ratio": ratio} for case_id, ratio in STRESS_CASES],
        "overflow_count": overflow_count,
        "preview_render": preview_report,
        "checks": all_checks,
    }
    (project_dir / "capacity_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return deepcopy(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=str(ROOT / "projects" / "capacity_stress_demo"),
        help="Output project directory.",
    )
    parser.add_argument("--no-render", action="store_true", help="Skip PNG preview rendering.")
    args = parser.parse_args()

    report = generate_demo(Path(args.project_dir), render_png=not args.no_render)
    print(json.dumps({k: report[k] for k in ("project_dir", "slide_count", "overflow_count", "preview_render")}, ensure_ascii=False, indent=2))
    return 0 if report["overflow_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
