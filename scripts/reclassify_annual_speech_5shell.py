#!/usr/bin/env python3
"""Reclassify the annual speech distillation from source-faithful prototypes.

The first pass selected the wrong TOC and content source pages.  This migration
keeps the public surface at five shells, but makes the shell provenance and the
development-only page variants explicit:

* 02_toc.svg      <- source slide 5 (vertical rail TOC)
* 03_chapter.svg  <- source slide 6
* 04_content.svg  <- source slide 18 header only (body is composed separately)
* 05_ending.svg   <- source slide 29

The source page variants remain available under ``page_variants`` on F: drive,
but are never promoted to public shell files.  The old invented component
redesigns are moved to ``review_rejected`` and removed from the active catalog.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from html import unescape
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


TEMPLATE_ID = "annual_speech_2025_distilled_5shell"
CONTENT_VARIANT_SOURCE_SLIDES = {
    11: "content_cards_callout",
    12: "content_metrics",
    13: "content_source_13",
    14: "content_source_14",
    15: "content_source_15",
    16: "content_source_16",
    17: "content_source_17",
    18: "content_two_panel",
    19: "content_source_19",
    20: "content_source_20",
    21: "content_dual_panels",
    23: "content_source_23",
    24: "content_source_24",
    25: "content_source_25",
    26: "content_source_26",
}
CONTENT_VARIANT_IDS = list(CONTENT_VARIANT_SOURCE_SLIDES.values())
# The photo-led source page is retained only as development evidence.  It is
# not part of the active content-page template library.
SPECIALIZED_VARIANT_IDS: list[str] = []
EXCLUDED_VARIANT_IDS = [
    "content_photo_statement",
    "content_quote",
]
EXCLUDED_VARIANT_SOURCES = {
    "content_photo_statement": 2,
    "content_quote": 22,
}
TEXT_RE = re.compile(r"<text(?P<attrs>[^>]*)>(?P<body>.*?)</text>", re.S | re.I)
TSPAN_RE = re.compile(r"<tspan(?P<attrs>[^>]*)>(?P<body>.*?)</tspan>", re.S | re.I)

# Editable body text boxes are converted to PowerPoint paragraphs.  Their
# visible glyph centers follow the DrawingML paragraph metrics rather than the
# source SVG ``dy=28`` value, so marker placement needs a separate geometry
# model for multi-line text boxes.
BODY_TEXT_BOX_FIRST_CENTER_EM = 0.62
BODY_TEXT_BOX_LINE_STEP_EM = 1.214


def set_attr(attrs: str, key: str, value: str) -> str:
    pattern = re.compile(rf'\s{re.escape(key)}="[^"]*"')
    replacement = f' {key}="{value}"'
    if pattern.search(attrs):
        return pattern.sub(replacement, attrs, count=1)
    return attrs + replacement


def remove_attr(attrs: str, key: str) -> str:
    return re.sub(rf'\s{re.escape(key)}="[^"]*"', "", attrs)


def slot_attrs(attrs: str, slot: str, kind: str = "text") -> str:
    attrs = set_attr(attrs, "data-slot", slot)
    attrs = set_attr(attrs, "data-slot-id", slot)
    attrs = set_attr(attrs, "data-slot-kind", kind)
    attrs = set_attr(attrs, "data-slot-placeholder", "{{" + slot + "}}")
    return attrs


def box_attrs(attrs: str, x: float | str, y: float | str, w: float | str, h: float | str) -> str:
    attrs = set_attr(attrs, "data-pptx-textbox", "true")
    attrs = set_attr(attrs, "data-pptx-box-x", str(x))
    attrs = set_attr(attrs, "data-pptx-box-y", str(y))
    attrs = set_attr(attrs, "data-pptx-box-w", str(w))
    attrs = set_attr(attrs, "data-pptx-box-h", str(h))
    attrs = set_attr(attrs, "data-pptx-valign", "top")
    return attrs


def source_svg(source_root: Path, slide: int) -> str:
    return (source_root / "svg" / f"slide_{slide:02d}.svg").read_text(encoding="utf-8")


def normalize_root_assets(svg: str) -> str:
    return svg.replace('href="../assets/', 'href="assets/')


def mark_image(svg: str, href: str, slot: str) -> str:
    pattern = re.compile(rf'<image(?P<attrs>[^>]*href="{re.escape(href)}"[^>]*)/>', re.I)

    def repl(match: re.Match[str]) -> str:
        attrs = slot_attrs(match.group("attrs"), slot, "image")
        return f'<image{attrs}/>'

    return pattern.sub(repl, svg, count=1)


def text_with_slot(match: re.Match[str], slot: str, value: str, *, box: tuple[float, float, float, float] | None = None) -> str:
    attrs = match.group("attrs")
    if box is not None:
        attrs = box_attrs(attrs, *box)
    attrs = slot_attrs(attrs, slot)
    tspans = list(TSPAN_RE.finditer(match.group("body")))
    if tspans:
        tspan_attrs = slot_attrs(tspans[0].group("attrs"), slot)
        body = f'<tspan{tspan_attrs}>{escape(value)}</tspan>'
    else:
        body = escape(value)
    return f'<text{attrs}>{body}</text>'


def center_slot_text(svg: str, slot: str, center_x: float) -> str:
    """Center one source textbox inside its visual container."""
    def repl(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        if f'data-slot="{slot}"' not in attrs:
            return match.group(0)
        attrs = set_attr(attrs, "x", f"{center_x:.2f}")
        attrs = set_attr(attrs, "text-anchor", "middle")
        attrs = set_attr(attrs, "data-pptx-valign", "middle")
        return f'<text{attrs}>{match.group("body")}</text>'

    return TEXT_RE.sub(repl, svg)


def bullet_with_slot(
    match: re.Match[str],
    slot: str,
    *,
    box: tuple[float, float, float, float],
    marker_color: str,
    first_line: str = "添加正文内容，添加正文内容",
    second_line: str = "添加正文内容。",
) -> str:
    # The source page already carries the colored ring/dot marker as a separate
    # ellipse group.  Remove the source bullet glyph from the text and shift
    # the abstracted copy to the right of that existing marker instead of
    # adding a second marker on top of it.
    source_x_match = re.search(r'\sx="([\d.-]+)"', match.group("attrs"))
    source_x = float(source_x_match.group(1)) if source_x_match else box[0]
    # Keep one visible space between the marker's outer ring and the text.
    # The source marker is about 7.35 units in radius, so a 26-unit text
    # offset leaves a full visible space after the marker instead of touching it.
    text_shift = 26.0
    text_x = source_x + text_shift
    attrs = box_attrs(match.group("attrs"), text_x, box[1], max(box[2] - text_shift, 1.0), box[3])
    attrs = set_attr(attrs, "x", f"{text_x:.2f}")
    attrs = slot_attrs(attrs, slot)
    tspans = list(TSPAN_RE.finditer(match.group("body")))
    body_attrs = tspans[1].group("attrs") if len(tspans) > 1 else ""
    second_attrs = tspans[2].group("attrs") if len(tspans) > 2 else body_attrs
    body_attrs = slot_attrs(body_attrs, slot)
    second_attrs = slot_attrs(second_attrs, slot)
    if 'x="' in second_attrs:
        second_attrs = set_attr(second_attrs, "x", f"{text_x:.2f}")
    body = (
        f'<tspan{body_attrs}>{escape(first_line)}</tspan>'
        f'<tspan{second_attrs}>{escape(second_line)}</tspan>'
    )
    text_node = f'<text{attrs}>{body}</text>'
    return text_node


def rewrite_by_index(svg: str, replacements: dict[int, Any]) -> str:
    index = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal index
        index += 1
        action = replacements.get(index)
        return action(match) if action else match.group(0)

    rewritten = TEXT_RE.sub(repl, svg)
    expected = max(replacements, default=0)
    if index < expected:
        raise RuntimeError(f"expected at least {expected} text nodes, found {index}")
    return rewritten


def abstract_toc(svg: str) -> str:
    values = {
        1: ("TOC_TITLE", "目录"),
        2: ("TOC_ITEM_01_TITLE", "章节标题"),
        3: ("TOC_ITEM_01_DESC", "章节说明"),
        4: ("TOC_ITEM_01_NUMBER", "01-"),
        5: ("TOC_RAIL_LABEL", "CONTENTS"),
        6: ("TOC_ITEM_02_TITLE", "章节标题"),
        7: ("TOC_ITEM_02_DESC", "章节说明"),
        8: ("TOC_ITEM_02_NUMBER", "02-"),
        9: ("TOC_ITEM_03_TITLE", "章节标题"),
        10: ("TOC_ITEM_03_DESC", "章节说明"),
        11: ("TOC_ITEM_03_NUMBER", "03-"),
        12: ("TOC_ITEM_04_TITLE", "章节标题"),
        13: ("TOC_ITEM_04_DESC", "章节说明"),
        14: ("TOC_ITEM_04_NUMBER", "04-"),
    }
    svg = rewrite_by_index(
        svg,
        {i: (lambda match, slot=slot, value=value: text_with_slot(match, slot, value)) for i, (slot, value) in values.items()},
    )

    def relayout_rail(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        if 'data-slot="TOC_RAIL_LABEL"' not in attrs:
            return match.group(0)
        # Preserve the source-local box.  The geometry contract explicitly
        # treats this rotated structural rail as protected chrome.
        attrs = box_attrs(attrs, -324.2, 290.53, 720, 138.94)
        return f'<text{attrs}>{match.group("body")}</text>'

    return TEXT_RE.sub(relayout_rail, svg)


def abstract_content(svg: str) -> str:
    bullet_anchors = collect_bullet_anchors(svg)
    simple = {
        1: ("HIGHLIGHT_VALUE", "数据值"),
        2: ("KEYWORD_01", "关键词1"),
        3: ("PANEL_TITLE_01", "小标题"),
        4: ("PANEL_01_TAG_01", "关键词1"),
        5: ("KEYWORD_02", "关键词2"),
        6: ("PANEL_01_TAG_02", "关键词2"),
        7: ("PAGE_TITLE", "页面标题"),
        8: ("KEYWORD_03", "关键词3"),
        9: ("KEYWORD_04", "关键词4"),
        10: ("PANEL_01_TAG_03", "关键词3"),
        13: ("PANEL_TITLE_02", "小标题"),
        14: ("PANEL_02_TAG_01", "关键词1"),
        15: ("PANEL_02_TAG_02", "关键词2"),
        16: ("PANEL_02_TAG_03", "关键词3"),
    }
    replacements: dict[int, Any] = {
        i: (lambda match, slot=slot, value=value: text_with_slot(match, slot, value))
        for i, (slot, value) in simple.items()
    }
    replacements.update(
        {
            11: lambda match: bullet_with_slot(match, "PANEL_01_BODY_01", box=(148.70, 395.40, 423.55, 54.0), marker_color="#912C8D"),
            12: lambda match: bullet_with_slot(match, "PANEL_01_BODY_02", box=(148.70, 451.40, 423.55, 54.0), marker_color="#912C8D"),
            17: lambda match: bullet_with_slot(match, "PANEL_02_BODY_01", box=(693.34, 395.40, 424.45, 54.0), marker_color="#68A4C6"),
            18: lambda match: bullet_with_slot(match, "PANEL_02_BODY_02", box=(693.34, 451.40, 424.45, 54.0), marker_color="#68A4C6"),
        }
    )
    svg = rewrite_by_index(svg, replacements)
    svg = mark_image(svg, "assets/image37.jpeg", "HIGHLIGHT_IMAGE")
    return align_bullet_markers(svg, bullet_anchors)


def source_group(svg: str, group_id: str) -> str:
    """Return one source group without reinterpreting its geometry."""
    match = re.search(rf'<g id="{re.escape(group_id)}"[^>]*>.*?</g>', svg, re.S)
    if not match:
        raise RuntimeError(f"source group {group_id!r} is missing")
    return match.group(0)


def abstract_content_header(svg: str) -> str:
    """Keep only the stable source header; leave the body canvas empty."""
    title = source_group(svg, "shape-41")
    title = rewrite_by_index(
        title,
        {1: lambda match: text_with_slot(match, "PAGE_TITLE", "\u9875\u9762\u6807\u9898")},
    )
    rule = source_group(svg, "shape-42")
    brand = source_group(svg, "shape-43")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'version="1.1" width="1280" height="720" viewBox="0 0 1280 720" '
        'data-template-shell="content_header_only" data-source-slide="18">'
        '<rect x="0" y="0" width="1280" height="720" fill="#FFFFFF" data-body-canvas="true"/>'
        '<g id="content-header" data-source-groups="shape-41 shape-42 shape-43">'
        f"{title}{rule}{brand}"
        "</g></svg>"
    )


def body_composition_svg(svg: str, variant_id: str, source_slide: int) -> str:
    """Create a body-only preview by masking source header chrome in place."""
    mask = (
        '<rect x="0" y="0" width="1280" height="120" fill="#FFFFFF" '
        'data-body-header-mask="true" data-body-area-y="120"/>'
    )
    marked = svg.replace(
        "<svg ",
        f'<svg data-body-only="true" data-source-slide="{source_slide}" '
        f'data-variant-id="{variant_id}" data-coordinate-space="body_canvas" ',
        1,
    )
    closing = marked.rfind("</svg>")
    if closing < 0:
        raise RuntimeError(f"body source for {variant_id!r} has no root closing svg")
    return marked[:closing] + mask + marked[closing:]


def strip_source_header_chrome(svg: str) -> str:
    """Remove source title/logo/rule groups before composing under the shared header."""
    group_re = re.compile(r'<g id="[^"]+"[^>]*>.*?</g>', re.S)

    def keep(match: re.Match[str]) -> str:
        body = match.group(0)
        if "image20.png" in body or 'y="62.24"' in body or 'y1="89.62"' in body:
            return ""
        return body

    return group_re.sub(keep, svg)


def generic_placeholder_value(value: str) -> str:
    """Turn source placeholder copy into short, reusable material text."""
    text = unescape(re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", value)))
    if not text:
        return "正文内容"
    if "关键词" in text:
        return "关键词"
    if "图片" in text or "照片" in text:
        return "图片说明"
    if "标题" in text:
        return "小标题"
    if "时间" in text or re.fullmatch(r"\d{4}[./-]\d{1,2}([./-]\d{1,2})?", text):
        return "时间"
    if re.fullmatch(r"\d+(\.\d+)?%?", text):
        return text
    if re.fullmatch(r"\d{1,2}[.]?", text):
        return text
    return "正文内容"


def source_text_has_bullet(match: re.Match[str]) -> bool:
    return "•" in unescape(re.sub(r"<[^>]+>", "", match.group("body")))


def collect_bullet_anchors(svg: str) -> list[tuple[float, float, float]]:
    """Collect body text baselines and their intended marker centers."""
    anchors: list[tuple[float, float, float]] = []
    for match in TEXT_RE.finditer(svg):
        attrs = match.group("attrs")
        x_match = re.search(r'\sx="([\d.-]+)"', attrs)
        y_match = re.search(r'\sy="([\d.-]+)"', attrs)
        size_match = re.search(r'font-size="([\d.-]+)', attrs)
        if not x_match or not y_match:
            continue
        try:
            x = float(x_match.group(1))
            baseline = float(y_match.group(1))
            font_size = float(size_match.group(1)) if size_match else 18.67
        except ValueError:
            continue
        if not 14.0 <= font_size <= 20.0:
            continue
        marker_line_count = nearby_marker_line_count(svg, match)
        box_y_match = re.search(r'data-pptx-box-y="([\d.-]+)"', attrs)
        box_h_match = re.search(r'data-pptx-box-h="([\d.-]+)"', attrs)
        editable_text_box = box_y_match and box_h_match
        if editable_text_box:
            box_y = float(box_y_match.group(1))
            first_marker_center = box_y + font_size * BODY_TEXT_BOX_FIRST_CENTER_EM
            marker_line_step = font_size * BODY_TEXT_BOX_LINE_STEP_EM
        else:
            first_marker_center = baseline - font_size * 0.23
            marker_line_step = 28.0
        for line_index in range(marker_line_count):
            line_baseline = baseline + line_index * 28.0
            # Single-line source text uses its SVG baseline.  Multi-line
            # editable text boxes use PowerPoint paragraph metrics instead.
            marker_center = first_marker_center + line_index * marker_line_step
            anchors.append((x, line_baseline, marker_center))
    return anchors


def align_bullet_markers(svg: str, anchors: list[tuple[float, float, float]]) -> str:
    """Move source colored bullet rings to the vertical center of their text."""
    if not anchors:
        return svg

    ellipse_re = re.compile(r"<ellipse(?P<attrs>[^>]*)/>", re.I)
    claimed_anchors: set[int] = set()
    marker_groups: list[tuple[float, float, int]] = []

    def repl(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        rx_match = re.search(r'\srx="([\d.-]+)"', attrs)
        cx_match = re.search(r'\scx="([\d.-]+)"', attrs)
        cy_match = re.search(r'\scy="([\d.-]+)"', attrs)
        if not rx_match or not cx_match or not cy_match:
            return match.group(0)
        try:
            rx = float(rx_match.group(1))
            cx = float(cx_match.group(1))
            cy = float(cy_match.group(1))
        except ValueError:
            return match.group(0)
        if min(abs(rx - 7.35), abs(rx - 7.86), abs(rx - 4.2), abs(rx - 4.42)) > 0.2:
            return match.group(0)

        anchor_index: int | None = None
        for group_cx, group_cy, group_anchor in marker_groups:
            if abs(cx - group_cx) <= 0.6 and abs(cy - group_cy) <= 0.6:
                anchor_index = group_anchor
                break
        if anchor_index is not None:
            anchor = anchors[anchor_index]
            attrs = set_attr(attrs, "cy", f"{anchor[2]:.2f}")
            return f"<ellipse{attrs}/>"

        candidates = [
            (abs(cx - (anchor[0] + 4.5)) + abs(cy - anchor[1]) * 0.15, index, anchor)
            for index, anchor in enumerate(anchors)
            if index not in claimed_anchors
            and abs(cx - (anchor[0] + 4.5)) <= 40.0
            and abs(cy - anchor[1]) <= 80.0
        ]
        if not candidates:
            return match.group(0)
        _, index, anchor = min(candidates, key=lambda item: item[0])
        claimed_anchors.add(index)
        marker_groups.append((cx, cy, index))
        attrs = set_attr(attrs, "cy", f"{anchor[2]:.2f}")
        return f"<ellipse{attrs}/>"

    return ellipse_re.sub(repl, svg)


def nearby_marker_line_count(svg: str, match: re.Match[str]) -> int:
    """Count source colored marker groups belonging to one body text box."""
    attrs = match.group("attrs")
    x_match = re.search(r'\sx="([\d.-]+)"', attrs)
    y_match = re.search(r'\sy="([\d.-]+)"', attrs)
    if not x_match or not y_match:
        return 1
    try:
        text_x = float(x_match.group(1))
        text_y = float(y_match.group(1))
    except ValueError:
        return 1
    box_y_match = re.search(r'data-pptx-box-y="([\d.-]+)"', attrs)
    box_h_match = re.search(r'data-pptx-box-h="([\d.-]+)"', attrs)
    if box_y_match and box_h_match:
        try:
            y_min = float(box_y_match.group(1)) - 15.0
            y_max = float(box_y_match.group(1)) + float(box_h_match.group(1)) + 15.0
        except ValueError:
            y_min, y_max = text_y - 25.0, text_y + 25.0
    else:
        y_min, y_max = text_y - 25.0, text_y + 25.0

    ellipse_re = re.compile(r"<ellipse(?P<attrs>[^>]*)/>", re.I)
    centers: list[tuple[float, float]] = []
    for ellipse in ellipse_re.finditer(svg):
        eattrs = ellipse.group("attrs")
        rx_match = re.search(r'\srx="([\d.-]+)"', eattrs)
        cx_match = re.search(r'\scx="([\d.-]+)"', eattrs)
        cy_match = re.search(r'\scy="([\d.-]+)"', eattrs)
        if not rx_match or not cx_match or not cy_match:
            continue
        try:
            rx = float(rx_match.group(1))
            cx = float(cx_match.group(1))
            cy = float(cy_match.group(1))
        except ValueError:
            continue
        if min(abs(rx - 7.35), abs(rx - 7.86)) > 0.2:
            continue
        if abs(cx - (text_x + 4.5)) > 40.0 or not y_min <= cy <= y_max:
            continue
        if not any(abs(cx - old_x) <= 0.6 and abs(cy - old_y) <= 0.6 for old_x, old_y in centers):
            centers.append((cx, cy))
    return max(1, len(centers))


def text_with_slot_lines(
    match: re.Match[str],
    slot: str,
    value: str,
    *,
    line_count: int = 1,
    text_x: float | None = None,
) -> str:
    """Create one abstract slot while retaining source bullet row count."""
    attrs = match.group("attrs")
    if text_x is not None:
        attrs = set_attr(attrs, "x", f"{text_x:.2f}")
    attrs = slot_attrs(attrs, slot)
    tspans = list(TSPAN_RE.finditer(match.group("body")))
    tspan_attrs = slot_attrs(tspans[0].group("attrs"), slot) if tspans else slot_attrs("", slot)
    body = [f'<tspan{tspan_attrs}>{escape(value)}</tspan>']
    for _ in range(1, max(1, line_count)):
        next_attrs = set_attr(tspan_attrs, "x", f"{text_x:.2f}" if text_x is not None else re.search(r'\sx="([\d.-]+)"', attrs).group(1))
        next_attrs = set_attr(next_attrs, "dy", "28")
        body.append(f'<tspan{next_attrs}>{escape(value)}</tspan>')
    return f'<text{attrs}>{"".join(body)}</text>'


def source_marker_color(match: re.Match[str]) -> str:
    first_tspan = TSPAN_RE.search(match.group("body"))
    attrs = first_tspan.group("attrs") if first_tspan else match.group("attrs")
    fill_match = re.search(r'\sfill="([^"]+)"', attrs)
    fill = fill_match.group(1) if fill_match else ""
    if fill.lower() in {"#68a4c6", "#6a69b6", "#7561d6", "#912c8d"}:
        return fill
    return "#912C8D"


def generic_text_with_slot(
    match: re.Match[str],
    slot: str,
    value: str,
    *,
    marker_line_count: int = 1,
) -> str:
    if not source_text_has_bullet(match):
        return text_with_slot_lines(match, slot, value, line_count=marker_line_count)

    # Bullet-bearing source text boxes have a matching colored ellipse group
    # later in the SVG.  Keep that source marker, strip the glyph through the
    # abstracted value, and reserve a small left gutter for the marker.
    attrs = match.group("attrs")
    x_match = re.search(r'\sx="([\d.-]+)"', attrs)
    box_x = re.search(r'data-pptx-box-x="([^"]+)"', attrs)
    try:
        # Reserve one visible space after the source colored marker.
        shift = 26.0
        text_x = float(x_match.group(1)) + shift if x_match else None
        box_x_value = float(box_x.group(1)) + shift if box_x else None
    except (AttributeError, TypeError, ValueError):
        return text_with_slot_lines(match, slot, value, line_count=marker_line_count)
    if text_x is not None:
        attrs = set_attr(attrs, "x", f"{text_x:.2f}")
    if box_x_value is not None:
        attrs = set_attr(attrs, "data-pptx-box-x", f"{box_x_value:.2f}")
        box_w = re.search(r'data-pptx-box-w="([^"]+)"', attrs)
        if box_w:
            try:
                attrs = set_attr(attrs, "data-pptx-box-w", f"{max(float(box_w.group(1)) - shift, 1.0):.2f}")
            except ValueError:
                pass
    attrs = slot_attrs(attrs, slot)
    tspans = list(TSPAN_RE.finditer(match.group("body")))
    if tspans:
        tspan_attrs = slot_attrs(tspans[0].group("attrs"), slot)
    else:
        tspan_attrs = slot_attrs("", slot)
    body = [f'<tspan{tspan_attrs}>{escape(value)}</tspan>']
    for _ in range(1, max(1, marker_line_count)):
        next_attrs = set_attr(tspan_attrs, "x", f"{text_x:.2f}")
        next_attrs = set_attr(next_attrs, "dy", "28")
        body.append(f'<tspan{next_attrs}>{escape(value)}</tspan>')
    return f'<text{attrs}>{"".join(body)}</text>'


def abstract_generic_body_source(svg: str, source_slide: int) -> str:
    """Abstract every material text/image slot while keeping source geometry."""
    normalized = normalize_root_assets(svg)
    body = strip_source_header_chrome(normalized)
    bullet_anchors = collect_bullet_anchors(body)
    text_index = 0

    def replace_text(match: re.Match[str]) -> str:
        nonlocal text_index
        text_index += 1
        slot = f"BODY_TEXT_{text_index:02d}"
        value = generic_placeholder_value(match.group("body"))
        marker_line_count = nearby_marker_line_count(body, match)
        return generic_text_with_slot(match, slot, value, marker_line_count=marker_line_count)

    body = TEXT_RE.sub(replace_text, body)
    image_index = 0
    skip_images = {"assets/image20.png", "assets/image27.jpg"}

    def replace_image(match: re.Match[str]) -> str:
        nonlocal image_index
        attrs = match.group("attrs")
        href_match = re.search(r'href="([^"]+)"', attrs)
        href = href_match.group(1) if href_match else ""
        if href in skip_images:
            return match.group(0)
        image_index += 1
        slot = f"IMAGE_{image_index:02d}"
        return f'<image{slot_attrs(attrs, slot, "image")}/>'

    body = re.sub(r'<image(?P<attrs>[^>]*?)/>', replace_image, body, flags=re.I)
    body = align_bullet_markers(body, bullet_anchors)
    return body.replace('href="assets/', 'href="../assets/')


def extract_slots(svg: str) -> list[str]:
    slots: list[str] = []
    for match in re.finditer(r'data-slot="([^"]+)"', svg):
        slot = match.group(1)
        if slot not in slots:
            slots.append(slot)
    return slots


def abstract_body_source(svg: str, source_slide: int) -> str:
    """Abstract source body text while preserving every source geometry box."""
    normalized = normalize_root_assets(svg)
    if source_slide == 18:
        abstracted = abstract_content(normalized)
        return strip_source_header_chrome(abstracted).replace('href="assets/', 'href="../assets/')

    page_title = "\u9875\u9762\u6807\u9898"
    heading = "\u4e3b\u8981\u53d1\u73b0"
    body = "\u6b64\u5904\u586b\u5199\u4e0e\u672c\u9875\u8bba\u70b9\u76f8\u5173\u7684\u8bc1\u636e\u4e0e\u8bf4\u660e"
    label = "\u5b9a\u4e49\u6807\u7b7e"
    value = "\u5173\u952e\u6570\u503c"
    quote = "\u5728\u6b64\u586b\u5199\u9700\u8981\u5f3a\u8c03\u7684\u7ed3\u8bba\u6216\u5f15\u7528"
    source = "\u6765\u6e90\u6216\u6ce8\u91ca"
    statement = "核心结论或发现"
    mappings: dict[int, tuple[str, str]] = {}
    if source_slide == 2:
        # The source page has a large one-line statement and a separate
        # smaller evidence note. They are distinct slots; binding both boxes to
        # STATEMENT_BODY makes the long placeholder wrap into the note area.
        mappings = {1: ("STATEMENT_TITLE", heading), 2: ("STATEMENT_BODY", statement), 3: ("STATEMENT_NOTE", body)}
        normalized = mark_image(normalized, "assets/image7.jpeg", "IMAGE_01")
    elif source_slide == 11:
        mappings = {1: ("CALLOUT_TEXT", quote), 2: ("CARD_01_TITLE", heading), 3: ("CARD_01_BODY", body), 5: ("CARD_02_TITLE", heading), 6: ("CARD_02_BODY", body), 8: ("IMAGE_CAPTION", label), 9: ("PAGE_TITLE", page_title)}
        normalized = mark_image(normalized, "assets/image19.jpeg", "IMAGE_01")
    elif source_slide == 12:
        mappings = {1: ("IMAGE_CAPTION", label), 2: ("METRIC_01_VALUE", value), 3: ("METRIC_01_LABEL", label), 4: ("METRIC_02_VALUE", value), 5: ("METRIC_02_LABEL", label), 6: ("METRIC_03_VALUE", value), 7: ("METRIC_03_LABEL", label), 8: ("METRIC_04_VALUE", value), 9: ("METRIC_04_LABEL", label), 11: ("EVIDENCE_TITLE_01", heading), 12: ("EVIDENCE_TEXT_01", body), 13: ("PAGE_TITLE", page_title), 15: ("EVIDENCE_TITLE_02", heading), 16: ("EVIDENCE_TEXT_02", body)}
        # image21.jpeg is source-fixed visual chrome; only its caption is a slot.
    elif source_slide == 21:
        mappings = {1: ("PANEL_RIGHT_BODY", body), 2: ("PAGE_TITLE", page_title), 3: ("PANEL_RIGHT_BODY", body), 4: ("PANEL_LEFT_BODY", body), 5: ("PANEL_LEFT_BODY", body)}
        normalized = mark_image(normalized, "assets/image43.jpg", "PANEL_LEFT_IMAGE")
        normalized = mark_image(normalized, "assets/image44.jpg", "PANEL_RIGHT_IMAGE")
    elif source_slide == 22:
        mappings = {1: ("QUOTE_TEXT", quote), 2: ("QUOTE_SOURCE", source), 3: ("PAGE_TITLE", page_title)}
    else:
        return abstract_generic_body_source(svg, source_slide)

    replacements: dict[int, Any] = {
        index: (lambda match, slot=slot, value=value: text_with_slot(match, slot, value))
        for index, (slot, value) in mappings.items()
    }
    abstracted = rewrite_by_index(normalized, replacements)
    if source_slide == 11:
        abstracted = center_slot_text(abstracted, "IMAGE_CAPTION", 950.89)
    elif source_slide == 12:
        abstracted = center_slot_text(abstracted, "IMAGE_CAPTION", 335.64)
    abstracted = strip_source_header_chrome(abstracted)
    return abstracted.replace('href="assets/', 'href="../assets/')


def abstract_ending(svg: str) -> str:
    replacements: dict[int, Any] = {
        1: lambda match: text_with_slot(match, "PRESENTER", "汇报人：姓名"),
        2: lambda match: text_with_slot(match, "DATE", "日期：XX年XX月"),
        3: lambda match: text_with_slot(match, "CLOSING_TITLE", "谢谢！", box=(584.01, 170.54, 643.80, 78.0)),
        4: lambda match: text_with_slot(match, "CLOSING_SUBTITLE", "敬请批评指正。", box=(584.01, 260.0, 643.80, 100.0)),
    }
    return rewrite_by_index(svg, replacements)


def slot_detail(slot_id: str, role: str, kind: str = "text", max_chars: int = 18, max_lines: int = 1) -> dict[str, Any]:
    item: dict[str, Any] = {
        "slot_id": slot_id,
        "role": role,
        "kind": kind,
    }
    if kind == "text":
        item.update({"max_lines": max_lines, "max_chars_per_line": max_chars})
    else:
        item["image_fit"] = "contain"
    return item


def make_slot_models(existing: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    models = dict(existing)
    models["toc"] = [
        slot_detail("TOC_TITLE", "toc_title", max_chars=12),
        slot_detail("TOC_RAIL_LABEL", "toc_rail_label", max_chars=12),
        *[
            slot_detail(f"TOC_ITEM_{i:02d}_NUMBER", f"toc_item_{i:02d}_number", max_chars=4)
            for i in range(1, 5)
        ],
        *[
            slot_detail(f"TOC_ITEM_{i:02d}_TITLE", f"toc_item_{i:02d}_title", max_chars=12)
            for i in range(1, 5)
        ],
        *[
            slot_detail(f"TOC_ITEM_{i:02d}_DESC", f"toc_item_{i:02d}_desc", max_chars=18)
            for i in range(1, 5)
        ],
    ]
    # The public content shell owns only the stable header.  Body slots belong
    # to body_variants.json so the same PAGE_TITLE/header can host different
    # source-faithful compositions.
    models["content"] = [slot_detail("PAGE_TITLE", "page_title", max_chars=18)]
    return models


def fit_defaults() -> dict[str, dict[str, Any]]:
    defaults = {
        "title": (48, 32, 18, "split", 2),
        "subtitle": (24, 16, 28, "split", 2),
        "presenter": (20, 14, 24, "truncate", 1),
        "date": (20, 14, 16, "truncate", 1),
        "closing_title": (64, 42, 12, "split", 1),
        "closing_subtitle": (48, 32, 14, "split", 1),
        "year": (32, 24, 4, "truncate", 1),
        "page_title": (28, 20, 18, "split", 1),
        "highlight_value": (30, 22, 8, "truncate", 1),
        "toc_title": (48, 32, 12, "truncate", 1),
        "toc_rail_label": (26, 18, 12, "truncate", 1),
        "panel_title_01": (26, 18, 12, "truncate", 1),
        "panel_title_02": (26, 18, 12, "truncate", 1),
    }
    for i in range(1, 5):
        defaults[f"chapter_title_{i:02d}"] = (40, 28, 16, "split", 2)
        defaults[f"chapter_desc_{i:02d}"] = (22, 15, 30, "split", 2)
    for i in range(1, 5):
        defaults[f"keyword_{i:02d}"] = (24, 16, 8, "truncate", 1)
        defaults[f"toc_item_{i:02d}_number"] = (22, 16, 4, "truncate", 1)
        defaults[f"toc_item_{i:02d}_title"] = (26, 18, 12, "truncate", 1)
        defaults[f"toc_item_{i:02d}_desc"] = (18, 14, 18, "split", 1)
    for panel in (1, 2):
        for i in (1, 2):
            defaults[f"panel_{panel:02d}_body_{i:02d}"] = (18, 14, 22, "split", 2)
        for i in (1, 2, 3):
            defaults[f"panel_{panel:02d}_tag_{i:02d}"] = (18, 14, 8, "truncate", 1)
    return {
        role: {
            "default_font_size_px": default,
            "min_font_size_px": minimum,
            "line_height": 1.2,
            "max_chars_per_line_zh": chars,
            "overflow_action": action,
            "max_lines": lines,
        }
        for role, (default, minimum, chars, action, lines) in defaults.items()
    }


def update_layouts(root: Path, source_slide: dict[str, int], body_ids: list[str]) -> dict[str, Any]:
    path = root / "layouts.json"
    layouts = json.loads(path.read_text(encoding="utf-8"))
    layouts["slot_models"] = make_slot_models(layouts.get("slot_models") or {})
    pages = layouts.get("pages", [])
    for page in pages:
        page_id = str(page.get("id") or page.get("page_id"))
        if page_id in source_slide:
            page["source_slide"] = source_slide[page_id]
        if page_id == "02_toc":
            page["density_score"] = 4
        if page_id == "04_content":
            page["density_score"] = 4
            page["body_variants"] = body_ids
            page["specialized_variants"] = SPECIALIZED_VARIANT_IDS
        if page_id == "05_ending":
            page["density_score"] = 3
    for layout in layouts.get("layouts", []):
        page_id = str(layout.get("id") or layout.get("page_id"))
        if page_id in source_slide:
            layout["source_slide"] = source_slide[page_id]
        if page_id == "04_content":
            layout["body_variants"] = body_ids
            layout["specialized_variants"] = SPECIALIZED_VARIANT_IDS
    canonical_page_ids = {
        "01_cover": "01_cover",
        "02_toc": "05_toc_02",
        "03_chapter": "06_chapter",
        "04_content": "18_content_10",
        "05_ending": "29_ending_02",
    }
    for shell in layouts.get("shells", []):
        page_id = str(shell.get("page_id"))
        if page_id in source_slide:
            shell["source_slide"] = source_slide[page_id]
            shell["source_page_id"] = canonical_page_ids.get(page_id, shell.get("source_page_id"))
    layouts["text_fit_policy"] = {
        **(layouts.get("text_fit_policy") or {}),
        "role_defaults": fit_defaults(),
    }
    path.write_text(json.dumps(layouts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return layouts


def write_slot_contract(root: Path, layouts: dict[str, Any]) -> None:
    models = layouts["slot_models"]
    pages = []
    for index, page in enumerate(layouts.get("pages", []), start=1):
        model = str(page.get("slot_model"))
        details = models.get(model, [])
        pages.append(
            {
                "layout_id": f"ASD-S{index:02d}",
                "page_id": page["id"],
                "svg_path": f"templates/layouts/{TEMPLATE_ID}/{page['svg']}",
                "role_fit": page.get("role_fit", []),
                "slot_model": model,
                "slots": [item["slot_id"] for item in details],
                "text_slots": [item["slot_id"] for item in details if item.get("kind") == "text"],
                "image_slots": [item["slot_id"] for item in details if item.get("kind") == "image"],
                "replacement": "replace_declared_slots_preserve_template_geometry",
                "slot_details": details,
            }
        )
    payload = {
        "schema_version": "easyslides.template_slot_contracts.v1",
        "template_id": TEMPLATE_ID,
        "source": "derived_from_reclassified_layouts_json_slot_models",
        "replacement_rule": "replace_declared_slots_preserve_template_geometry",
        "private_clone_required": False,
        "text_fit_policy": layouts["text_fit_policy"],
        "layouts": pages,
    }
    (root / "slot_contracts.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def component_catalog() -> dict[str, Any]:
    prefix = f"component/{TEMPLATE_ID}/"
    return {
        "schema_version": "easyslides.semantic_component_catalog.v1",
        "template_id": TEMPLATE_ID,
        "selection_policy": "source_faithful_shell_then_inline_source_primitive",
        "components": [
            {"asset_id": prefix + "highlight_image", "component_id": "highlight_image", "asset_status": "renderable", "reuse_policy": "template_scoped_source_primitive", "category": "image_highlight", "geometry": {"x": 107.15, "y": 134.65, "width": 278.83, "height": 103.69}, "slots": ["HIGHLIGHT_IMAGE", "HIGHLIGHT_VALUE"]},
            {"asset_id": prefix + "keyword_strip", "component_id": "keyword_strip", "asset_status": "renderable", "reuse_policy": "template_scoped_source_primitive", "category": "keyword_strip", "geometry": {"x": 404.29, "y": 136.62, "width": 761.23, "height": 101.28}, "slots": ["KEYWORD_01", "KEYWORD_02", "KEYWORD_03", "KEYWORD_04"]},
            {"asset_id": prefix + "content_panel_01", "component_id": "content_panel_01", "asset_status": "renderable", "reuse_policy": "template_scoped_source_primitive", "category": "content_panel", "geometry": {"x": 108.05, "y": 276.23, "width": 512.55, "height": 358.93}, "slots": ["PANEL_TITLE_01", "PANEL_01_BODY_01", "PANEL_01_BODY_02", "PANEL_01_TAG_01", "PANEL_01_TAG_02", "PANEL_01_TAG_03"]},
            {"asset_id": prefix + "content_panel_02", "component_id": "content_panel_02", "asset_status": "renderable", "reuse_policy": "template_scoped_source_primitive", "category": "content_panel", "geometry": {"x": 653.59, "y": 276.23, "width": 512.54, "height": 358.93}, "slots": ["PANEL_TITLE_02", "PANEL_02_BODY_01", "PANEL_02_BODY_02", "PANEL_02_TAG_01", "PANEL_02_TAG_02", "PANEL_02_TAG_03"]},
        ],
        "symbols": [],
        "unknown_component_count": 0,
    }


def body_variants(root: Path, ids: list[str], preview_by_id: dict[str, str], source_by_id: dict[str, int], page_by_id: dict[str, str]) -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    content_slots = [
        "PAGE_TITLE", "HIGHLIGHT_VALUE", "KEYWORD_01", "KEYWORD_02", "KEYWORD_03", "KEYWORD_04",
        "PANEL_TITLE_01", "PANEL_TITLE_02", "PANEL_01_BODY_01", "PANEL_01_BODY_02", "PANEL_02_BODY_01", "PANEL_02_BODY_02",
        "PANEL_01_TAG_01", "PANEL_01_TAG_02", "PANEL_01_TAG_03", "PANEL_02_TAG_01", "PANEL_02_TAG_02", "PANEL_02_TAG_03", "HIGHLIGHT_IMAGE",
    ]
    prefix = f"component/{TEMPLATE_ID}/"
    variants.append(
        {
            "variant_id": "content_two_panel",
            "shell_id": "content",
            "shell": "04_content.svg",
            "preview_svg": "04_content.svg",
            "source_slides": [18],
            "source_page_ids": ["18_content_10"],
            "components": {"text_slots": 18, "image_slots": 1},
            "visual_profile": "source_faithful_two_panel",
            "best_for": "关键词摘要、双栏正文和证据并列",
            "selection": {"route": "canonical_shell_then_body_variant", "density": ["balanced", "dense"]},
            "composition_mode": "ordered_source_primitives",
            "slots": content_slots,
            "component_refs": [
                {"asset_id": prefix + "highlight_image", "instance_id": "highlight", "role": "highlight", "order": 1, "required": True, "slot_bindings": {"HIGHLIGHT_IMAGE": "HIGHLIGHT_IMAGE", "HIGHLIGHT_VALUE": "HIGHLIGHT_VALUE"}},
                {"asset_id": prefix + "keyword_strip", "instance_id": "keywords", "role": "keyword_strip", "order": 2, "required": True, "slot_bindings": {f"KEYWORD_{i:02d}": f"KEYWORD_{i:02d}" for i in range(1, 5)}},
                {"asset_id": prefix + "content_panel_01", "instance_id": "panel_01", "role": "content_panel", "order": 3, "required": True, "slot_bindings": {slot: slot for slot in content_slots if slot.startswith("PANEL_01_") or slot == "PANEL_TITLE_01"}},
                {"asset_id": prefix + "content_panel_02", "instance_id": "panel_02", "role": "content_panel", "order": 4, "required": True, "slot_bindings": {slot: slot for slot in content_slots if slot.startswith("PANEL_02_") or slot == "PANEL_TITLE_02"}},
            ],
        }
    )
    for variant_id in ids:
        variants.append(
            {
                "variant_id": variant_id,
                "shell_id": "content",
                "shell": "04_content.svg",
                "preview_svg": preview_by_id[variant_id],
                "source_slides": [source_by_id[variant_id]],
                "source_page_ids": [page_by_id[variant_id]],
                "components": {"text_slots": 0, "image_slots": 0},
                "visual_profile": "source_faithful_development_variant",
                "best_for": "仅用于源版式复核；开发中，不进入默认模板选择",
                "selection": {"route": "development_only", "density": ["balanced", "dense"]},
                "composition_mode": "source_faithful_page_variant",
                "component_refs": [],
            }
        )
    payload = {
        "schema_version": "easyslides.body_variants.v1",
        "template_id": TEMPLATE_ID,
        "source_shell": "04_content.svg",
        "selection_policy": "canonical_shell_then_source_faithful_body_variant",
        "content_area": {"x": 0, "y": 0, "width": 1280, "height": 720},
        "variants": variants,
    }
    (root / "body_variants.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def component_catalog_v2() -> dict[str, Any]:
    """Catalog source-derived body primitives used by the active body forms."""
    prefix = f"component/{TEMPLATE_ID}/"

    def item(component_id: str, category: str, geometry: dict[str, float], slots: list[str]) -> dict[str, Any]:
        return {
            "asset_id": prefix + component_id,
            "component_id": component_id,
            "asset_status": "renderable",
            "reuse_policy": "template_scoped_source_primitive",
            "category": category,
            "geometry": geometry,
            "slots": slots,
        }

    components = [
        item("highlight_image", "image_highlight", {"x": 107.15, "y": 134.65, "width": 278.83, "height": 103.69}, ["HIGHLIGHT_IMAGE", "HIGHLIGHT_VALUE"]),
        item("keyword_strip", "keyword_strip", {"x": 404.29, "y": 136.62, "width": 761.23, "height": 101.28}, ["KEYWORD_01", "KEYWORD_02", "KEYWORD_03", "KEYWORD_04"]),
        item("content_panel_01", "content_panel", {"x": 108.05, "y": 276.23, "width": 512.55, "height": 358.93}, ["PANEL_TITLE_01", "PANEL_01_BODY_01", "PANEL_01_BODY_02", "PANEL_01_TAG_01", "PANEL_01_TAG_02", "PANEL_01_TAG_03"]),
        item("content_panel_02", "content_panel", {"x": 653.59, "y": 276.23, "width": 512.54, "height": 358.93}, ["PANEL_TITLE_02", "PANEL_02_BODY_01", "PANEL_02_BODY_02", "PANEL_02_TAG_01", "PANEL_02_TAG_02", "PANEL_02_TAG_03"]),
        item("cards_group", "cards_group", {"x": 74.23, "y": 233.28, "width": 590.09, "height": 428.85}, ["CARD_01_TITLE", "CARD_01_BODY", "CARD_02_TITLE", "CARD_02_BODY"]),
        item("callout", "callout", {"x": 74.23, "y": 133.81, "width": 602.60, "height": 65.63}, ["CALLOUT_TEXT"]),
        item("side_image", "side_image", {"x": 720.80, "y": 126.72, "width": 460.17, "height": 541.37}, ["IMAGE_01", "IMAGE_CAPTION"]),
        item("metrics_strip", "metrics_strip", {"x": 482.88, "y": 142.55, "width": 722.40, "height": 127.94}, ["METRIC_01_VALUE", "METRIC_01_LABEL", "METRIC_02_VALUE", "METRIC_02_LABEL", "METRIC_03_VALUE", "METRIC_03_LABEL", "METRIC_04_VALUE", "METRIC_04_LABEL"]),
        item("metric_evidence", "metric_evidence", {"x": 746.15, "y": 301.68, "width": 414.14, "height": 340.88}, ["EVIDENCE_TITLE_01", "EVIDENCE_TEXT_01", "EVIDENCE_TITLE_02", "EVIDENCE_TEXT_02"]),
        item("image_caption", "image_caption", {"x": 87.92, "y": 583.08, "width": 495.43, "height": 83.10}, ["IMAGE_CAPTION"]),
        item("dual_panel_left", "dual_panel", {"x": 108.0, "y": 155.0, "width": 512.0, "height": 465.0}, ["PANEL_LEFT_TITLE", "PANEL_LEFT_BODY", "PANEL_LEFT_IMAGE"]),
        item("dual_panel_right", "dual_panel", {"x": 654.0, "y": 155.0, "width": 512.0, "height": 465.0}, ["PANEL_RIGHT_TITLE", "PANEL_RIGHT_BODY", "PANEL_RIGHT_IMAGE"]),
        item("photo_statement", "photo_statement", {"x": 108.0, "y": 145.0, "width": 1058.0, "height": 475.0}, ["STATEMENT_TITLE", "STATEMENT_BODY", "STATEMENT_NOTE", "IMAGE_01"]),
    ]
    return {
        "schema_version": "easyslides.semantic_component_catalog.v1",
        "template_id": TEMPLATE_ID,
        "selection_policy": "source_faithful_header_then_source_body_primitive",
        "components": components,
        "symbols": [],
        "unknown_component_count": 0,
    }


def body_slot_details_v2(slots: list[str]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for slot in slots:
        if slot.startswith("IMAGE_") or slot.endswith("_IMAGE"):
            details.append(slot_detail(slot, slot.lower(), kind="image"))
        else:
            max_lines = 2 if any(token in slot for token in ("BODY", "TEXT", "EVIDENCE")) else 1
            details.append(slot_detail(slot, slot.lower(), max_chars=22, max_lines=max_lines))
    return details


def body_variants_v2(root: Path, source_root: Path, preview_by_id: dict[str, str]) -> dict[str, Any]:
    """Write source-faithful body compositions under one stable header shell."""
    prefix = f"component/{TEMPLATE_ID}/"
    body_dir = root / "body_variants"
    body_dir.mkdir(parents=True, exist_ok=True)

    def ref(asset_id: str, instance_id: str, role: str, order: int, slots: list[str]) -> dict[str, Any]:
        placements = {
            "highlight_image": {"x": 107.15, "y": 134.65, "width": 278.83, "height": 103.69},
            "keyword_strip": {"x": 404.29, "y": 136.62, "width": 761.23, "height": 101.28},
            "content_panel_01": {"x": 108.05, "y": 276.23, "width": 512.55, "height": 358.93},
            "content_panel_02": {"x": 653.59, "y": 276.23, "width": 512.54, "height": 358.93},
            "cards_group": {"x": 74.23, "y": 233.28, "width": 590.09, "height": 428.85},
            "callout": {"x": 74.23, "y": 133.81, "width": 602.60, "height": 65.63},
            "side_image": {"x": 720.80, "y": 126.72, "width": 460.17, "height": 541.37},
            "metrics_strip": {"x": 482.88, "y": 142.55, "width": 722.40, "height": 127.94},
            "metric_evidence": {"x": 746.15, "y": 301.68, "width": 414.14, "height": 340.88},
            "image_caption": {"x": 87.92, "y": 583.08, "width": 495.43, "height": 83.10},
            "dual_panel_left": {"x": 108.0, "y": 155.0, "width": 512.0, "height": 465.0},
            "dual_panel_right": {"x": 654.0, "y": 155.0, "width": 512.0, "height": 465.0},
            "quote_block": {"x": 178.0, "y": 190.0, "width": 924.0, "height": 310.0},
            "photo_statement": {"x": 108.0, "y": 145.0, "width": 1058.0, "height": 475.0},
        }
        return {
            "asset_id": prefix + asset_id,
            "instance_id": instance_id,
            "role": role,
            "order": order,
            "required": True,
            "placement": placements[asset_id],
            "slot_bindings": {slot: slot for slot in slots},
        }

    specs = [
        {
            "variant_id": "content_two_panel", "page_role": "content", "source_slide": 18, "source_page_id": "18_content_10", "source_key": "content_source_18", "filename": "content_two_panel.svg",
            "visual_profile": "source_faithful_two_panel", "best_for": "keyword strip with paired evidence panels",
            "slots": ["HIGHLIGHT_VALUE", "HIGHLIGHT_IMAGE", "KEYWORD_01", "KEYWORD_02", "KEYWORD_03", "KEYWORD_04", "PANEL_TITLE_01", "PANEL_TITLE_02", "PANEL_01_BODY_01", "PANEL_01_BODY_02", "PANEL_02_BODY_01", "PANEL_02_BODY_02", "PANEL_01_TAG_01", "PANEL_01_TAG_02", "PANEL_01_TAG_03", "PANEL_02_TAG_01", "PANEL_02_TAG_02", "PANEL_02_TAG_03"],
            "components": [("highlight_image", "highlight", "highlight", ["HIGHLIGHT_IMAGE", "HIGHLIGHT_VALUE"]), ("keyword_strip", "keywords", "keyword_strip", ["KEYWORD_01", "KEYWORD_02", "KEYWORD_03", "KEYWORD_04"]), ("content_panel_01", "panel_01", "content_panel", ["PANEL_TITLE_01", "PANEL_01_BODY_01", "PANEL_01_BODY_02", "PANEL_01_TAG_01", "PANEL_01_TAG_02", "PANEL_01_TAG_03"]), ("content_panel_02", "panel_02", "content_panel", ["PANEL_TITLE_02", "PANEL_02_BODY_01", "PANEL_02_BODY_02", "PANEL_02_TAG_01", "PANEL_02_TAG_02", "PANEL_02_TAG_03"])],
        },
        {
            "variant_id": "content_cards_callout", "page_role": "content", "source_slide": 11, "source_page_id": "11_content_03", "source_key": "content_source_11", "filename": "content_cards_callout.svg",
            "visual_profile": "source_faithful_cards_callout", "best_for": "card-based evidence summary with a bottom callout",
            "slots": ["CARD_01_TITLE", "CARD_01_BODY", "CARD_02_TITLE", "CARD_02_BODY", "CALLOUT_TEXT", "IMAGE_01", "IMAGE_CAPTION"],
            "components": [("cards_group", "cards", "cards_group", ["CARD_01_TITLE", "CARD_01_BODY", "CARD_02_TITLE", "CARD_02_BODY"]), ("callout", "callout", "callout", ["CALLOUT_TEXT"]), ("side_image", "image", "side_image", ["IMAGE_01", "IMAGE_CAPTION"])],
        },
        {
            "variant_id": "content_metrics", "page_role": "content", "source_slide": 12, "source_page_id": "12_content_04", "source_key": "content_source_12", "filename": "content_metrics.svg",
            "visual_profile": "source_faithful_metrics_strip", "best_for": "three metric values with supporting evidence",
            "slots": ["METRIC_01_VALUE", "METRIC_01_LABEL", "METRIC_02_VALUE", "METRIC_02_LABEL", "METRIC_03_VALUE", "METRIC_03_LABEL", "METRIC_04_VALUE", "METRIC_04_LABEL", "EVIDENCE_TITLE_01", "EVIDENCE_TEXT_01", "EVIDENCE_TITLE_02", "EVIDENCE_TEXT_02", "IMAGE_CAPTION"],
            "components": [("metrics_strip", "metrics", "metrics_strip", ["METRIC_01_VALUE", "METRIC_01_LABEL", "METRIC_02_VALUE", "METRIC_02_LABEL", "METRIC_03_VALUE", "METRIC_03_LABEL", "METRIC_04_VALUE", "METRIC_04_LABEL"]), ("metric_evidence", "evidence", "metric_evidence", ["EVIDENCE_TITLE_01", "EVIDENCE_TEXT_01", "EVIDENCE_TITLE_02", "EVIDENCE_TEXT_02"]), ("image_caption", "caption", "image_caption", ["IMAGE_CAPTION"])],
        },
        {
            "variant_id": "content_dual_panels", "page_role": "content", "source_slide": 21, "source_page_id": "21_content_13", "source_key": "content_source_21", "filename": "content_dual_panels.svg",
            "visual_profile": "source_faithful_dual_panels", "best_for": "paired visual and text panels",
            "slots": ["PANEL_LEFT_TITLE", "PANEL_LEFT_BODY", "PANEL_LEFT_IMAGE", "PANEL_RIGHT_TITLE", "PANEL_RIGHT_BODY", "PANEL_RIGHT_IMAGE"],
            "components": [("dual_panel_left", "panel_left", "dual_panel", ["PANEL_LEFT_TITLE", "PANEL_LEFT_BODY", "PANEL_LEFT_IMAGE"]), ("dual_panel_right", "panel_right", "dual_panel", ["PANEL_RIGHT_TITLE", "PANEL_RIGHT_BODY", "PANEL_RIGHT_IMAGE"])],
        },
        {
            "variant_id": "content_source_13", "page_role": "content", "source_slide": 13, "source_page_id": "13_content_05", "source_key": "content_source_13", "filename": "content_source_13.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "staggered keypoint text blocks",
        },
        {
            "variant_id": "content_source_14", "page_role": "content", "source_slide": 14, "source_page_id": "14_content_06", "source_key": "content_source_14", "filename": "content_source_14.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "three-column keypoint text",
        },
        {
            "variant_id": "content_source_15", "page_role": "content", "source_slide": 15, "source_page_id": "15_content_07", "source_key": "content_source_15", "filename": "content_source_15.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "three-stage timeline with text",
        },
        {
            "variant_id": "content_source_16", "page_role": "content", "source_slide": 16, "source_page_id": "16_content_08", "source_key": "content_source_16", "filename": "content_source_16.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "four-card text matrix",
        },
        {
            "variant_id": "content_source_17", "page_role": "content", "source_slide": 17, "source_page_id": "17_content_09", "source_key": "content_source_17", "filename": "content_source_17.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "milestone line with supporting text",
        },
        {
            "variant_id": "content_source_19", "page_role": "content", "source_slide": 19, "source_page_id": "19_content_11", "source_key": "content_source_19", "filename": "content_source_19.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "statement block with two supporting points",
        },
        {
            "variant_id": "content_source_20", "page_role": "content", "source_slide": 20, "source_page_id": "20_content_12", "source_key": "content_source_20", "filename": "content_source_20.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "four-quadrant relationship page",
        },
        {
            "variant_id": "content_source_23", "page_role": "content", "source_slide": 23, "source_page_id": "23_content_15", "source_key": "content_source_23", "filename": "content_source_23.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "central relationship with four text panels",
        },
        {
            "variant_id": "content_source_24", "page_role": "content", "source_slide": 24, "source_page_id": "24_content_16", "source_key": "content_source_24", "filename": "content_source_24.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "three-period timeline with text",
        },
        {
            "variant_id": "content_source_25", "page_role": "content", "source_slide": 25, "source_page_id": "25_content_17", "source_key": "content_source_25", "filename": "content_source_25.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "hub-and-spoke four text panels",
        },
        {
            "variant_id": "content_source_26", "page_role": "content", "source_slide": 26, "source_page_id": "26_content_18", "source_key": "content_source_26", "filename": "content_source_26.svg", "generic": True,
            "visual_profile": "source_faithful_master_content", "best_for": "two-column text with side statement",
        },
    ]
    specs.sort(key=lambda spec: (0 if spec["page_role"] == "content" else 1, int(spec["source_slide"])))

    body_area = {"x": 0, "y": 120, "width": 1280, "height": 600}
    variants: list[dict[str, Any]] = []
    for spec in specs:
        source = abstract_body_source(source_svg(source_root, int(spec["source_slide"])), int(spec["source_slide"]))
        target = body_dir / str(spec["filename"])
        target.write_text(body_composition_svg(source, str(spec["variant_id"]), int(spec["source_slide"])), encoding="utf-8")
        slots = extract_slots(source) if spec.get("generic") else list(spec["slots"])
        refs = [] if spec.get("generic") else [ref(asset, instance, role, order, ref_slots) for order, (asset, instance, role, ref_slots) in enumerate(spec["components"], start=1)]
        variants.append({
            "variant_id": spec["variant_id"], "page_role": spec["page_role"], "shell_id": "content", "shell": "04_content.svg",
            "preview_svg": f"body_variants/{spec['filename']}", "source_preview_svg": preview_by_id[spec["source_key"]],
            "source_slides": [spec["source_slide"]], "source_page_ids": [spec["source_page_id"]],
            "components": {"text_slots": sum(1 for slot in slots if not (slot.startswith("IMAGE_") or slot.endswith("_IMAGE"))), "image_slots": sum(1 for slot in slots if slot.startswith("IMAGE_") or slot.endswith("_IMAGE"))},
            "visual_profile": spec["visual_profile"], "best_for": spec["best_for"],
            "selection": {"route": "canonical_header_then_source_faithful_body_variant", "density": ["balanced", "dense"]},
            "composition_mode": "source_faithful_page_variant" if spec.get("generic") else "ordered_component_refs", "coordinate_space": "body_canvas", "composition_scene": spec["variant_id"],
            "clear_region": body_area, "body_area": body_area, "slots": slots, "slot_details": body_slot_details_v2(slots), "component_refs": refs,
        })

    for variant in variants:
        refs = variant["component_refs"]
        for index, left in enumerate(refs):
            a = left["placement"]
            for right in refs[index + 1:]:
                b = right["placement"]
                dx = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
                dy = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
                if dx > 0.01 and dy > 0.01:
                    raise RuntimeError(
                        f"body variant {variant['variant_id']!r} has overlapping components "
                        f"{left['instance_id']!r} and {right['instance_id']!r}"
                    )

    payload = {
        "schema_version": "easyslides.body_variants.v1", "template_id": TEMPLATE_ID,
        "source_shell": "04_content.svg", "header_shell": "04_content.svg",
        "selection_policy": "canonical_header_then_source_faithful_body_variant",
        "coordinate_space": "body_canvas", "content_area": body_area,
        "content_variants": CONTENT_VARIANT_IDS,
        "specialized_variants": SPECIALIZED_VARIANT_IDS,
        "excluded_variants": [
            {
                "variant_id": variant_id,
                "source_slide": EXCLUDED_VARIANT_SOURCES[variant_id],
                "reason": "removed_from_active_content_page_library",
            }
            for variant_id in EXCLUDED_VARIANT_IDS
        ],
        "variants": variants,
    }
    (root / "body_variants.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def page_catalog(root: Path, layouts: dict[str, Any], roster: dict[str, Any], variants: dict[str, Any]) -> None:
    pages: list[dict[str, Any]] = []
    for page in layouts.get("pages", []):
        pages.append(
            {
                "id": page["id"],
                "source_slide": page.get("source_slide"),
                "story_role": page.get("story_role"),
                "role_fit": page.get("role_fit", []),
                "density_score": page.get("density_score"),
                "best_for": "source-faithful canonical shell",
                "avoid": "content that requires moving fixed source chrome",
                "shell_id": page.get("shell_id"),
                "body_variants": page.get("body_variants", []),
            }
        )
    payload = {
        "schema_version": "easyslides.page_catalog.v1",
        "template_id": TEMPLATE_ID,
        "selection_policy": "canonical_shell_then_source_faithful_body_variant",
        "pages": pages,
        "content_variants": variants.get("content_variants", CONTENT_VARIANT_IDS),
        "specialized_variants": variants.get("specialized_variants", SPECIALIZED_VARIANT_IDS),
        "excluded_variants": variants.get("excluded_variants", []),
        "body_variants": variants["variants"],
        "source_pages": roster["source_pages"],
    }
    (root / "page_catalog.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_rosters(root: Path, layouts: dict[str, Any], roster: dict[str, Any], variants: dict[str, Any], source_slide: dict[str, int]) -> None:
    active_body_by_slide = {
        11: "content_cards_callout",
        12: "content_metrics",
        13: "content_source_13",
        14: "content_source_14",
        15: "content_source_15",
        16: "content_source_16",
        17: "content_source_17",
        18: "content_two_panel",
        19: "content_source_19",
        20: "content_source_20",
        21: "content_dual_panels",
        23: "content_source_23",
        24: "content_source_24",
        25: "content_source_25",
        26: "content_source_26",
    }
    variant_page_roles = {variant_id: "content" for variant_id in CONTENT_VARIANT_IDS}
    source_pages = roster.get("source_pages")
    if not isinstance(source_pages, list):
        source_pages = roster.get("pages") if isinstance(roster.get("pages"), list) else []
    roster["source_pages"] = source_pages
    for row in source_pages:
        slide = int(row.get("source_slide", 0))
        row["development_only"] = False
        row["canonical_shell"] = None
        row["body_variant"] = None
        row["page_role"] = None
        row["excluded_from_template"] = False
        row["exclusion_reason"] = None
        row["preserved_as"] = "development_page_variant"
        if slide == 1:
            row["source_role"] = "cover"
            row["canonical_shell"] = "cover"
            row["preserved_as"] = "canonical_shell"
        elif slide == 5:
            row["source_role"] = "toc"
            row["canonical_shell"] = "toc"
            row["preserved_as"] = "canonical_shell"
        elif slide == 6:
            row["source_role"] = "chapter"
            row["canonical_shell"] = "chapter"
            row["preserved_as"] = "canonical_shell"
        elif slide == 18:
            row["source_role"] = "content"
            row["page_role"] = "content"
            row["canonical_shell"] = "content"
            row["preserved_as"] = "canonical_shell"
            row["body_variant"] = "content_two_panel"
        elif slide in active_body_by_slide:
            row["page_role"] = variant_page_roles.get(active_body_by_slide[slide], "content")
            row["source_role"] = row["page_role"]
            row["body_variant"] = active_body_by_slide[slide]
            row["development_only"] = True
            row["preserved_as"] = "body_variant"
        elif slide == 22:
            row["source_role"] = "excluded"
            row["page_role"] = None
            row["development_only"] = True
            row["excluded_from_template"] = True
            row["exclusion_reason"] = "removed_from_active_content_page_library"
            row["preserved_as"] = "source_evidence_only"
        elif slide == 29:
            row["source_role"] = "ending"
            row["canonical_shell"] = "ending"
            row["preserved_as"] = "canonical_shell"
        elif slide == 4:
            row["source_role"] = "toc"
            row["body_variant"] = "toc_grid"
            row["development_only"] = True
        elif slide == 28:
            row["source_role"] = "ending"
            row["body_variant"] = "ending_photo"
            row["development_only"] = True
        elif 2 <= slide <= 3 or 11 <= slide <= 17 or 19 <= slide <= 26:
            row["source_role"] = "content"
            row["body_variant"] = f"content_source_{slide:02d}"
            row["development_only"] = True
        elif 7 <= slide <= 10 or slide == 27:
            row["development_only"] = True
        if row["development_only"]:
            row["preserved_as"] = "development_page_variant"
        if row["excluded_from_template"]:
            row["preserved_as"] = "source_evidence_only"
    roster["canonical_shell_count"] = 5
    roster["body_variant_count"] = len(variants["variants"])
    roster["content_page_variant_count"] = len(variants.get("content_variants", CONTENT_VARIANT_IDS))
    roster["specialized_variant_count"] = len(variants.get("specialized_variants", SPECIALIZED_VARIANT_IDS))
    roster["excluded_source_page_count"] = 1
    roster["development_variant_policy"] = "source_page_variants_are_f_drive_only_and_never_default_selected"
    roster["canonical_sources"] = {key: value for key, value in source_slide.items()}
    roster["pages"] = source_pages
    (root / "source_page_roster.json").write_text(json.dumps(roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    layout_rows = []
    for index, page in enumerate(layouts.get("pages", []), start=1):
        layout_rows.append(
            {
                "layout_id": f"ASD-S{index:02d}",
                "source_slide": page.get("source_slide"),
                "page_id": page.get("id"),
                "name": page.get("id", "").replace("_", " "),
                "role_fit": page.get("role_fit", []),
                "page_archetype": page.get("page_type"),
                "density_score": page.get("density_score"),
                "slot_model": page.get("slot_model"),
                "svg_path": f"templates/layouts/{TEMPLATE_ID}/{page.get('svg')}",
                "layout_contract": f"asd_s{index:02d}_{page.get('id')}_contract",
                "best_for": "source-faithful canonical shell",
                "avoid": "content that requires moving fixed source chrome",
            }
        )
    (root / "layout_roster.json").write_text(json.dumps({"schema_version": "easyslides.template_layout_roster.v1", "template_id": TEMPLATE_ID, "source": "reclassified_source_faithful_five_shells", "layouts": layout_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_design_spec(root: Path, source_slide: dict[str, int], layouts: dict[str, Any]) -> None:
    placeholders = {page["id"]: [f"{{{{{slot['slot_id']}}}}}" for slot in layouts["slot_models"][page["slot_model"]]] for page in layouts["pages"]}
    content_forms = ", ".join(
        f"`{variant_id}` (slide {slide})"
        for slide, variant_id in CONTENT_VARIANT_SOURCE_SLIDES.items()
    )
    lines = [
        "---",
        f"template_id: {TEMPLATE_ID}",
        "category: imported_development_asset",
        "summary: Source-faithful five-shell pack with explicitly separated source page variants.",
        "primary_color: \"#912C8D\"",
        "canvas_format: ppt169",
        "replication_mode: slot_guided_mirror",
        "---",
        "",
        "# annual_speech_2025_distilled_5shell Design Specification",
        "",
        "This F-drive development asset is source-faithful. The public shell surface",
        "contains exactly five page shells; source pages with different geometry remain",
        "development-only variants and must not be silently merged into another shell.",
        "",
        "## Canonical shell provenance",
        "",
        "| SVG | Role | Source slide | Visual identity |",
        "|---|---|---:|---|",
        "| `01_cover.svg` | cover | 1 | cover lockup |",
        "| `02_toc.svg` | toc | 5 | vertical CONTENTS rail + four chapter rows |",
        "| `03_chapter.svg` | chapter | 6 | chapter overview with diamond numbers |",
        "| `04_content.svg` | content | 18 | title + logo + purple rule; body canvas intentionally open |",
        "| `05_ending.svg` | ending | 29 | photo-backed closing lockup |",
        "",
        "## Selection rule",
        "",
        "Select one of the five canonical shells first. Only then may a source-faithful",
        "development variant be requested explicitly. `slide_04` is the separate `toc_grid`",
        "variant; it is not an alternate rendering of `02_toc.svg`. The prior invented",
        "metric/comparison/matrix redraws are retained only under `review_rejected/`.",
        "",
        "## Content body composition",
        "",
        "`04_content.svg` is a header-only shell. Its body canvas is `x=0, y=120, width=1280, height=600`;",
        f"body variants are source-faithful compositions selected after the header shell. The {len(CONTENT_VARIANT_IDS)} content-page forms are",
        content_forms + ".",
        "The former `content_photo_statement` page (slide 2) is retained only as",
        "development evidence and is excluded from the active content-page template library.",
        "Source slide 22 is likewise retained only as evidence and is excluded from the active template library.",
        "Each form keeps its source geometry and declares body slots plus ordered source-derived components.",
        "",
        "## Placeholder inventory",
        "",
        "```json",
        json.dumps(placeholders, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    (root / "design_spec.md").write_text("\n".join(lines), encoding="utf-8")


def update_geometry_contract(root: Path, source_slide: dict[str, int]) -> None:
    path = root / "geometry_contract.json"
    if not path.is_file():
        return
    contract = json.loads(path.read_text(encoding="utf-8"))
    for page in contract.get("pages", []):
        page_id = str(page.get("id"))
        if page_id in source_slide:
            page["source_slide"] = source_slide[page_id]
        if page_id == "02_toc":
            # CONTENTS is rotated structural chrome.  Its source textbox has a
            # small intentional left bleed after rotation; the right-hand
            # content container must not claim that rail label.
            page["protected_regions"] = [
                {"id": "toc_rail", "x": 0, "y": 0, "width": 220, "height": 720, "fill": "#441351", "stroke": "none"}
            ]
            page["containers"] = [
                {"id": "toc_content", "x": 650, "y": 50, "width": 630, "height": 594.13, "fill": "#FFFFFF", "stroke": "none"}
            ]
        if page_id == "04_content":
            page["body_canvas"] = {"x": 0, "y": 120, "width": 1280, "height": 600}
            page["containers"] = [
                {"id": "content_body_canvas", "x": 0, "y": 120, "width": 1280, "height": 600, "fill": "#FFFFFF", "stroke": "none"}
            ]
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_development_variants(root: Path, source_root: Path) -> tuple[list[str], dict[str, str], dict[str, int], dict[str, str]]:
    variants_dir = root / "page_variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, tuple[int, str]] = {
        "toc_grid": (4, "02_toc_grid.svg"),
        "content_source_02": (2, "04_content_source_02.svg"),
        "content_source_03": (3, "04_content_source_03.svg"),
        "content_source_18": (18, "04_content_source_18.svg"),
        **{f"content_source_{slide:02d}": (slide, f"04_content_source_{slide:02d}.svg") for slide in list(range(11, 18)) + list(range(19, 27))},
        "ending_photo": (28, "05_ending_photo.svg"),
    }
    preview_by_id: dict[str, str] = {}
    source_by_id: dict[str, int] = {}
    page_by_id: dict[str, str] = {}

    def source_page_id(slide: int) -> str:
        if slide == 2:
            return "02_content"
        if slide == 3:
            return "03_content_02"
        if 11 <= slide <= 26:
            return f"{slide:02d}_content_{slide - 8:02d}"
        return f"{slide:02d}_source_variant"

    for variant_id, (slide, filename) in mapping.items():
        source = source_svg(source_root, slide)
        target = variants_dir / filename
        target.write_text(source, encoding="utf-8")
        content = target.read_text(encoding="utf-8")
        content = content.replace("<svg ", f'<svg data-development-only="true" data-source-slide="{slide}" data-variant-id="{variant_id}" ', 1)
        target.write_text(content, encoding="utf-8")
        preview_by_id[variant_id] = f"page_variants/{filename}"
        source_by_id[variant_id] = slide
        page_by_id[variant_id] = source_page_id(slide)
    return list(mapping), preview_by_id, source_by_id, page_by_id


def move_rejected_assets(root: Path) -> None:
    rejected = root / "review_rejected" / "previous_component_redesign"
    rejected.mkdir(parents=True, exist_ok=True)
    old_variants = root / "body_variants"
    if old_variants.exists() and not (rejected / "body_variants").exists():
        shutil.move(str(old_variants), str(rejected / "body_variants"))
    old_assets = root / "assets" / "components" / "annual_speech"
    if old_assets.exists() and not (rejected / "annual_speech_components").exists():
        shutil.move(str(old_assets), str(rejected / "annual_speech_components"))
    readme = rejected / "README.md"
    readme.write_text(
        "These files are retained for audit only. They were invented component redraws, "
        "not source-faithful annual_speech page variants, and are not selected by any active contract.\n",
        encoding="utf-8",
    )


def run(root: Path, source_root: Path) -> None:
    if root.name != TEMPLATE_ID:
        raise ValueError(f"refusing to edit unexpected template directory: {root}")
    if not root.is_dir() or not source_root.is_dir():
        raise FileNotFoundError(root if not root.is_dir() else source_root)

    move_rejected_assets(root)
    retired_variant = root / "body_variants" / "content_photo_statement.svg"
    if retired_variant.is_file():
        archive_target = root / "review_rejected" / "body_variants" / retired_variant.name
        archive_target.parent.mkdir(parents=True, exist_ok=True)
        if not archive_target.exists():
            shutil.move(str(retired_variant), str(archive_target))
    removed_variant = root / "body_variants" / "content_quote.svg"
    if removed_variant.is_file():
        archive_target = root / "review_rejected" / "body_variants" / removed_variant.name
        archive_target.parent.mkdir(parents=True, exist_ok=True)
        if not archive_target.exists():
            shutil.move(str(removed_variant), str(archive_target))

    root_targets = {
        "02_toc.svg": (5, abstract_toc),
        "04_content.svg": (18, abstract_content_header),
        "05_ending.svg": (29, abstract_ending),
    }
    for filename, (slide, transform) in root_targets.items():
        content = normalize_root_assets(source_svg(source_root, slide))
        (root / filename).write_text(transform(content), encoding="utf-8")

    dev_ids, previews, source_by_id, page_by_id = copy_development_variants(root, source_root)
    source_slide = {"01_cover": 1, "02_toc": 5, "03_chapter": 6, "04_content": 18, "05_ending": 29}
    layouts = update_layouts(root, source_slide, CONTENT_VARIANT_IDS)
    write_slot_contract(root, layouts)
    (root / "component_catalog.json").write_text(json.dumps(component_catalog_v2(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    variants = body_variants_v2(root, source_root, previews)
    roster = json.loads((root / "source_page_roster.json").read_text(encoding="utf-8"))
    update_rosters(root, layouts, roster, variants, source_slide)
    page_catalog(root, layouts, roster, variants)
    write_design_spec(root, source_slide, layouts)
    update_geometry_contract(root, source_slide)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(r"F:\Archive\projects\easyslides\nonlegacy-templates-20260802\templates\layouts\annual_speech_2025_distilled_5shell"))
    parser.add_argument("--source", type=Path, default=Path(r"F:\Archive\projects\easyslides\nonlegacy-templates-20260802\source_evidence\annual_speech_2025_distilled_5shell"))
    args = parser.parse_args()
    run(args.root, args.source)


if __name__ == "__main__":
    main()
