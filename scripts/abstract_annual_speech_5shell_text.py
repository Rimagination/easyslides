"""Replace source-deck sample text with EasySlides semantic slots.

This is intentionally coordinate-driven: the imported SVGs contain a few
malformed source-encoding text nodes, so parsing and reserializing the whole
SVG would risk changing the visual shell.  The script only rewrites the
declared text nodes and their slot metadata.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TEXT_RE = re.compile(r"<text(?P<attrs>[^>]*)>(?P<body>.*?)</text>", re.S | re.I)
TSPAN_RE = re.compile(r"<tspan(?P<attrs>[^>]*)>(?P<body>.*?)</tspan>", re.S | re.I)


def set_attr(attrs: str, key: str, value: str) -> str:
    pattern = re.compile(rf'\s{re.escape(key)}="[^"]*"')
    replacement = f' {key}="{value}"'
    if pattern.search(attrs):
        return pattern.sub(replacement, attrs, count=1)
    return attrs + replacement


def remove_attr(attrs: str, key: str) -> str:
    return re.sub(rf'\s{re.escape(key)}="[^"]*"', "", attrs)


def slot_attrs(attrs: str, slot: str) -> str:
    attrs = set_attr(attrs, "data-slot", slot)
    attrs = set_attr(attrs, "data-slot-id", slot)
    attrs = set_attr(attrs, "data-slot-kind", "text")
    attrs = set_attr(attrs, "data-slot-placeholder", "{{" + slot + "}}")
    return attrs


def pick_attrs(attrs: str, key: str, value: str) -> bool:
    return re.search(rf'\b{re.escape(key)}="{re.escape(value)}"', attrs) is not None


def replace_simple(text: str, *, key: str, value: str, slot: str) -> str:
    match = TEXT_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a text element: {text[:80]}")
    attrs = slot_attrs(match.group("attrs"), slot)
    body = match.group("body")
    tspan = TSPAN_RE.search(body)
    if tspan:
        body = (
            f"<tspan{tspan.group('attrs')}>"
            f"{value}"
            "</tspan>"
        )
    else:
        body = value
    return f"<text{attrs}>{body}</text>"


def replace_combined(text: str, *, slot: str, number: str | None = None, display: str = "章节标题") -> str:
    match = TEXT_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a text element: {text[:80]}")
    attrs = slot_attrs(match.group("attrs"), slot)
    tspans = list(TSPAN_RE.finditer(match.group("body")))
    geometry = {
        ("152.33", "339.59"): ("142.73", "303.05", "337.8", "50"),
        ("152.33", "432.92"): ("142.73", "397", "337.8", "50"),
        ("626.5", "339.59"): ("616.9", "303.05", "337.8", "50"),
        ("626.5", "432.92"): ("616.9", "397", "337.8", "50"),
    }
    x_match = re.search(r'\bx="([^"]+)"', match.group("attrs"))
    y_match = re.search(r'\by="([^"]+)"', match.group("attrs"))
    if x_match and y_match and (x_match.group(1), y_match.group(1)) in geometry:
        box_x, box_y, box_w, box_h = geometry[(x_match.group(1), y_match.group(1))]
        attrs = set_attr(attrs, "data-pptx-textbox", "true")
        attrs = set_attr(attrs, "data-pptx-box-x", box_x)
        attrs = set_attr(attrs, "data-pptx-box-y", box_y)
        attrs = set_attr(attrs, "data-pptx-box-w", box_w)
        attrs = set_attr(attrs, "data-pptx-box-h", box_h)
        attrs = set_attr(attrs, "data-pptx-valign", "middle")
    if len(tspans) < 2:
        raise ValueError(f"expected a numbered combined text box for {slot}")
    first = tspans[0]
    second = tspans[1]
    first_value = number if number is not None else first.group("body")
    first_value = first_value if first_value.endswith(" ") else first_value + " "
    first_part = f"<tspan{first.group('attrs')}>{first_value}</tspan>"
    second_attrs = slot_attrs(second.group("attrs"), slot)
    second_part = f"<tspan{second_attrs}>{display}</tspan>"
    return f"<text{attrs}>{first_part}{second_part}</text>"


def replace_meta(text: str) -> str:
    match = TEXT_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a text element: {text[:80]}")
    source_attrs = match.group("attrs")
    source_x = re.search(r'data-pptx-box-x="([^"]+)"', source_attrs)
    if source_x is None:
        raise ValueError("metadata box is missing data-pptx-box-x")
    geometry = {
        "101.6": ("111.2", "101.6", "280", "410", "400", "300"),
        "61.59": ("71.19", "61.59", "280", "370", "360", "330"),
        "99.81": ("109.41", "99.81", "280", "408", "398", "330"),
    }.get(source_x.group(1))
    if geometry is None:
        raise ValueError(f"unsupported metadata box x={source_x.group(1)}")
    first_x, first_box_x, first_w, second_x, second_box_x, second_w = geometry
    tspans = list(TSPAN_RE.finditer(match.group("body")))
    style_attrs = tspans[0].group("attrs") if tspans else ""
    for key in ("data-slot", "data-slot-id", "data-slot-kind", "data-slot-placeholder"):
        style_attrs = remove_attr(style_attrs, key)

    def make_box(x: str, box_x: str, box_w: str, label: str, display: str, slot: str) -> str:
        attrs = source_attrs
        attrs = remove_attr(attrs, "data-slot-group")
        attrs = remove_attr(attrs, "data-slot")
        attrs = remove_attr(attrs, "data-slot-id")
        attrs = remove_attr(attrs, "data-slot-kind")
        attrs = remove_attr(attrs, "data-slot-placeholder")
        attrs = set_attr(attrs, "x", x)
        attrs = set_attr(attrs, "data-pptx-box-x", box_x)
        attrs = set_attr(attrs, "data-pptx-box-w", box_w)
        value_attrs = slot_attrs(style_attrs, slot)
        body = (
            f"<tspan{style_attrs}>{label}</tspan>"
            f"<tspan{value_attrs}>{display}</tspan>"
        )
        return f"<text{attrs}>{body}</text>"

    return (
        make_box(first_x, first_box_x, first_w, "汇报人：", "姓名", "PRESENTER")
        + make_box(second_x, second_box_x, second_w, "日期：", "日期", "DATE")
    )


def rewrite_svg(path: Path, replacements: list[tuple[object, str]], optional_indices: set[int] | None = None) -> None:
    source = path.read_text(encoding="utf-8")
    counts = [0] * len(replacements)

    def repl(match: re.Match[str]) -> str:
        full = match.group(0)
        attrs = match.group("attrs")
        for index, (predicate, replacement) in enumerate(replacements):
            if predicate(attrs):
                counts[index] += 1
                return replacement(full)
        return full

    rewritten = TEXT_RE.sub(repl, source)
    optional_indices = optional_indices or set()
    missing = [
        str(i)
        for i, count in enumerate(counts)
        if count != 1 and not (i in optional_indices and count == 0)
    ]
    if missing:
        raise RuntimeError(f"{path.name}: replacement groups not matched exactly once: {missing}; counts={counts}")
    path.write_text(rewritten, encoding="utf-8")


def has_attr(key: str, value: str):
    return lambda attrs: pick_attrs(attrs, key, value)


def has_xy(x: str, y: str):
    return lambda attrs: pick_attrs(attrs, "data-pptx-box-x", x) and pick_attrs(attrs, "data-pptx-box-y", y)


def has_box(x: str, y: str, w: str):
    return lambda attrs: (
        pick_attrs(attrs, "data-pptx-box-x", x)
        and pick_attrs(attrs, "data-pptx-box-y", y)
        and pick_attrs(attrs, "data-pptx-box-w", w)
    )


def relayout_toc_descriptions(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    mapping = {
        ("200.9", "408.16", "428.83"): ("365", "385.67"),
        ("200.9", "519.64", "540.3"): ("458", "478.67"),
        ("673.5", "408.16", "428.83"): ("365", "385.67"),
        ("673.5", "519.64", "540.3"): ("458", "478.67"),
    }

    def repl(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        x_match = re.search(r'data-pptx-box-x="([^"]+)"', attrs)
        y_match = re.search(r'data-pptx-box-y="([^"]+)"', attrs)
        if not x_match or not y_match:
            return match.group(0)
        for (x, old_box_y, old_text_y), (new_box_y, new_text_y) in mapping.items():
            if x_match.group(1) == x and y_match.group(1) == old_box_y:
                attrs = set_attr(attrs, "data-pptx-box-y", new_box_y)
                attrs = set_attr(attrs, "y", new_text_y)
                return f"<text{attrs}>{match.group('body')}</text>"
        return match.group(0)

    rewritten = TEXT_RE.sub(repl, source)
    for x, old_y, new_y in [
        ("200.9", "408.16", "365"),
        ("200.9", "519.64", "458"),
        ("673.5", "408.16", "365"),
        ("673.5", "519.64", "458"),
    ]:
        rewritten = rewritten.replace(f'<rect x="{x}" y="{old_y}"', f'<rect x="{x}" y="{new_y}"')
    path.write_text(rewritten, encoding="utf-8")


def remove_stale_metadata_clones(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    stale: list[str] = []
    valid_y = {
        "01_cover.svg": "542.65",
        "04_content.svg": "608.44",
        "05_ending.svg": "541.69",
    }[path.name]

    def repl(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        body = match.group("body")
        visible = re.sub(r"<[^>]+>", "", body)
        box_y = re.search(r'data-pptx-box-y="([^"]+)"', attrs)
        if 'data-slot="DATE"' in body and (
            (box_y is not None and box_y.group(1) != valid_y)
            or "{{DATE}}" in visible
        ):
            stale.append(match.group(0))
            return ""
        return match.group(0)

    rewritten = TEXT_RE.sub(repl, source)
    if len(stale) > 3:
        raise RuntimeError(f"{path.name}: unexpectedly removed {len(stale)} stale metadata nodes")
    path.write_text(rewritten, encoding="utf-8")


def ensure_date_box(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    valid_y = {
        "01_cover.svg": "542.65",
        "04_content.svg": "608.44",
        "05_ending.svg": "541.69",
    }[path.name]
    if f'data-slot="DATE"' in source and f'data-pptx-box-y="{valid_y}"' in source:
        return
    geometry = {
        "101.6": ("410", "400", "300"),
        "61.59": ("370", "360", "330"),
        "99.81": ("408", "398", "330"),
    }

    inserted = False

    def repl(match: re.Match[str]) -> str:
        nonlocal inserted
        attrs = match.group("attrs")
        if 'data-slot="PRESENTER"' not in match.group("body"):
            return match.group(0)
        source_x = re.search(r'data-pptx-box-x="([^"]+)"', attrs)
        if source_x is None or source_x.group(1) not in geometry:
            return match.group(0)
        x, box_x, box_w = geometry[source_x.group(1)]
        tspans = list(TSPAN_RE.finditer(match.group("body")))
        style_attrs = tspans[0].group("attrs") if tspans else ""
        for key in ("data-slot", "data-slot-id", "data-slot-kind", "data-slot-placeholder"):
            style_attrs = remove_attr(style_attrs, key)
        date_attrs = attrs
        for key in ("data-slot", "data-slot-id", "data-slot-kind", "data-slot-placeholder"):
            date_attrs = remove_attr(date_attrs, key)
        date_attrs = set_attr(date_attrs, "x", x)
        date_attrs = set_attr(date_attrs, "data-pptx-box-x", box_x)
        date_attrs = set_attr(date_attrs, "data-pptx-box-w", box_w)
        value_attrs = slot_attrs(style_attrs, "DATE")
        body = f"<tspan{style_attrs}>日期：</tspan><tspan{value_attrs}>日期</tspan>"
        inserted = True
        return match.group(0) + f"<text{date_attrs}>{body}</text>"

    rewritten = TEXT_RE.sub(repl, source)
    if not inserted:
        raise RuntimeError(f"{path.name}: could not reconstruct DATE box")
    path.write_text(rewritten, encoding="utf-8")


def run(root: Path) -> None:
    if root.name != "annual_speech_2025_distilled_5shell":
        raise ValueError(f"refusing to edit unexpected template directory: {root}")
    if not root.is_dir():
        raise FileNotFoundError(root)

    rewrite_svg(
        root / "01_cover.svg",
        [
            (has_xy("101.6", "375.13"), lambda text: replace_simple(text, key="data-slot", value="副标题", slot="SUBTITLE")),
            (has_xy("97.65", "418.61"), lambda text: replace_simple(text, key="data-slot", value="汇报主题", slot="TITLE")),
            (has_box("101.6", "542.65", "705.4"), replace_meta),
        ],
        optional_indices={2},
    )

    rewrite_svg(
        root / "02_toc.svg",
        [
            (lambda attrs: pick_attrs(attrs, "x", "152.33") and pick_attrs(attrs, "y", "339.59"), lambda text: replace_combined(text, slot="TOC_ITEM_01", number="1.", display="章节标题")),
            (lambda attrs: pick_attrs(attrs, "x", "152.33") and pick_attrs(attrs, "y", "432.92"), lambda text: replace_combined(text, slot="TOC_ITEM_02", number="2.", display="章节标题")),
            (lambda attrs: pick_attrs(attrs, "x", "626.5") and pick_attrs(attrs, "y", "339.59"), lambda text: replace_combined(text, slot="TOC_ITEM_03", number="3.", display="章节标题")),
            (lambda attrs: pick_attrs(attrs, "x", "626.5") and pick_attrs(attrs, "y", "432.92"), lambda text: replace_combined(text, slot="TOC_ITEM_04", number="4.", display="章节标题")),
            (has_xy("200.9", "408.16"), lambda text: replace_simple(text, key="data-slot", value="章节说明", slot="TOC_ITEM_05")),
            (has_xy("200.9", "519.64"), lambda text: replace_simple(text, key="data-slot", value="章节说明", slot="TOC_ITEM_06")),
            (has_xy("673.5", "408.16"), lambda text: replace_simple(text, key="data-slot", value="章节说明", slot="TOC_ITEM_07")),
            (has_xy("673.5", "519.64"), lambda text: replace_simple(text, key="data-slot", value="章节说明", slot="TOC_ITEM_08")),
        ],
        optional_indices={4, 5, 6, 7},
    )
    relayout_toc_descriptions(root / "02_toc.svg")

    chapter_replacements: list[tuple[object, str]] = []
    for x, y, slot in [
        ("294.38", "206.77", "CHAPTER_TITLE_01"),
        ("294.38", "315.81", "CHAPTER_TITLE_02"),
        ("294.38", "426.96", "CHAPTER_TITLE_03"),
        ("294.38", "540.22", "CHAPTER_TITLE_04"),
        ("296.58", "257.39", "CHAPTER_DESC_01"),
        ("296.58", "366.43", "CHAPTER_DESC_02"),
        ("296.58", "477.58", "CHAPTER_DESC_03"),
        ("296.58", "590.84", "CHAPTER_DESC_04"),
    ]:
        predicate = has_xy(x, y)
        display = "章节标题" if slot.startswith("CHAPTER_TITLE_") else "章节说明"
        chapter_replacements.append((predicate, lambda text, slot=slot, display=display: replace_simple(text, key="data-slot", value=display, slot=slot)))
    chapter_replacements.append((has_xy("990.1", "458.3"), lambda text: replace_simple(text, key="data-slot", value="年度", slot="YEAR")))
    rewrite_svg(root / "03_chapter.svg", chapter_replacements)

    rewrite_svg(
        root / "04_content.svg",
        [
            (has_xy("61.59", "440.92"), lambda text: replace_simple(text, key="data-slot", value="核心观点", slot="KEY_MESSAGE")),
            (has_xy("58.7", "483.08"), lambda text: replace_simple(text, key="data-slot", value="页面标题", slot="PAGE_TITLE")),
            (has_box("61.59", "608.44", "705.4"), replace_meta),
        ],
        optional_indices={2},
    )

    rewrite_svg(
        root / "05_ending.svg",
        [
            (has_xy("99.81", "374.17"), lambda text: replace_simple(text, key="data-slot", value="结束语", slot="CLOSING_SUBTITLE")),
            (has_xy("93.72", "416.33"), lambda text: replace_simple(text, key="data-slot", value="感谢聆听", slot="CLOSING_TITLE")),
            (has_box("99.81", "541.69", "705.4"), replace_meta),
        ],
        optional_indices={2},
    )

    for name in ("01_cover.svg", "04_content.svg", "05_ending.svg"):
        path = root / name
        remove_stale_metadata_clones(path)
        ensure_date_box(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    run(args.root)


if __name__ == "__main__":
    main()
