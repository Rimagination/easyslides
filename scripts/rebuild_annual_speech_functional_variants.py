"""Rebuild the annual speech template with source-page functional variants.

The source deck is a 29-slide generic PPT template.  Its functional pages are
not single canonical layouts: slides 1-3 are cover variants, 4-6 are TOC
variants, 7-10 are transition variants, and 27-29 are ending variants.  This
script preserves those source pages and makes the choice explicit in the
template contract.  Content pages remain source-faithful body variants under
the shared content header.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

try:
    from scripts import reclassify_annual_speech_5shell as legacy
except ModuleNotFoundError:  # direct execution from the scripts directory
    import reclassify_annual_speech_5shell as legacy


TEMPLATE_ID = "thu_speech"
# Keep this development-only rebuild reproducible even when the user's
# separate F: archive is not mounted in the current Windows session. The
# source PPTX is converted to this local source-evidence directory before the
# build, and the generated package remains outside the official template set.
ROOT = Path(
    r"D:\scansci\easyslides\tmp\thu_speech"
)
SOURCE = Path(
    r"D:\scansci\easyslides\tmp\annual_source_full_pptx_to_svg"
)


FUNCTIONAL_GROUPS: dict[str, dict[str, Any]] = {
    "cover": {
        "role": "cover",
        "root_svg": "01_cover.svg",
        "variants": [
            {"variant_id": "cover_source_01", "source_slide": 1, "best_for": "wide photo cover with lower information band"},
            {"variant_id": "cover_source_02", "source_slide": 2, "best_for": "alternate wide photo cover with lower information band"},
            {"variant_id": "cover_source_03", "source_slide": 3, "best_for": "right-aligned title cover"},
        ],
    },
    "toc": {
        "role": "toc",
        "root_svg": "02_toc.svg",
        "variants": [
            {"variant_id": "toc_source_04", "source_slide": 4, "best_for": "four-item grid directory"},
            {"variant_id": "toc_source_05", "source_slide": 5, "best_for": "vertical CONTENTS rail with four chapter rows"},
            {"variant_id": "toc_source_06", "source_slide": 6, "best_for": "numbered directory with year marker"},
        ],
    },
    "transition": {
        "role": "transition",
        "root_svg": "03_transition.svg",
        "variant_model": "series_presets",
        "series_id": "transition_series",
        "shared_layout": "03_transition.svg",
        "variation_dimensions": ["TRANSITION_NUMBER", "TRANSITION_PHOTO"],
        "variants": [
            {"variant_id": "transition_source_07", "source_slide": 7, "best_for": "series preset 01; only sequence number and photo change"},
            {"variant_id": "transition_source_08", "source_slide": 8, "best_for": "series preset 02; only sequence number and photo change"},
            {"variant_id": "transition_source_09", "source_slide": 9, "best_for": "series preset 03; only sequence number and photo change"},
            {"variant_id": "transition_source_10", "source_slide": 10, "best_for": "series preset 04; only sequence number and photo change"},
        ],
    },
    "ending": {
        "role": "ending",
        "root_svg": "05_ending.svg",
        "variants": [
            {"variant_id": "ending_source_27", "source_slide": 27, "best_for": "wide photo ending with lower information band"},
            {"variant_id": "ending_source_28", "source_slide": 28, "best_for": "alternate wide photo ending"},
            {"variant_id": "ending_source_29", "source_slide": 29, "best_for": "right-aligned thank-you ending"},
        ],
    },
}


TRANSITION_MASK_PATHS = [
    [(1269.84, 0), (1109.12, 160.72), (948.4, 0)],
    [(1098.24, 171.6), (920.8, 349.12), (743.28, 171.6), (914.96, 0), (926.56, 0)],
    [(1280, 11.68), (1280, 331.6), (1120, 171.6)],
    [(1280, 353.44), (1280, 366.56), (1109.12, 537.44), (931.68, 360), (1109.12, 182.56)],
    [(1280, 388.4), (1280, 708.32), (1120, 548.4)],
    [(1269.84, 720), (948.4, 720), (1109.12, 559.28)],
    [(1098.24, 548.4), (926.56, 720), (914.96, 720), (743.28, 548.4), (743.28, 548.4), (920.8, 370.88)],
    [(893.12, 720), (571.68, 720), (732.4, 559.28)],
    [(732.39, 182.47), (910.00, 359.95), (732.39, 537.43), (554.78, 359.95)],
]


def build_transition_photo_assets(root: Path) -> None:
    """Flatten the source group-fill photos into transparent, editable image layers."""
    source_names = {7: "image15.png", 8: "image16.jpg", 9: "image17.jpg", 10: "image18.jpg"}
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    scale = 4
    canvas_w, canvas_h = 1280, 720
    photo_x, photo_w = 571.68, 708.32
    for slide, source_name in source_names.items():
        source = assets / source_name
        if not source.is_file():
            source = SOURCE / "assets" / source_name
        if not source.is_file():
            raise FileNotFoundError(f"Missing transition photo asset: {source_name}")
        photo = Image.open(source).convert("RGBA")
        hi_w, hi_h = canvas_w * scale, canvas_h * scale
        photo_hi = photo.resize((round(photo_w * scale), hi_h), Image.Resampling.LANCZOS)
        mask = Image.new("L", (hi_w, hi_h), 0)
        draw = ImageDraw.Draw(mask)
        for polygon in TRANSITION_MASK_PATHS:
            draw.polygon([(round(x * scale), round(y * scale)) for x, y in polygon], fill=255)
        layer = Image.new("RGBA", (hi_w, hi_h), (0, 0, 0, 0))
        layer.paste(photo_hi, (round(photo_x * scale), 0), mask.crop((round(photo_x * scale), 0, hi_w, hi_h)))
        layer = layer.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        layer.save(assets / f"transition_photo_{slide:02d}.png")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mark_variant(svg: str, group: str, variant_id: str, source_slide: int) -> str:
    attrs = (
        f'data-functional-page-group="{group}" '
        f'data-functional-variant-id="{variant_id}" '
        f'data-source-slide="{source_slide}"'
    )
    if group == "transition":
        attrs += (
            ' data-functional-series="transition_series"'
            ' data-functional-variation-dimensions="TRANSITION_NUMBER,TRANSITION_PHOTO"'
        )
    return svg.replace("<svg ", f"<svg {attrs} ", 1)


def replace_texts(svg: str, mapping: dict[int, tuple[str, str]]) -> str:
    replacements = {
        index: (lambda match, slot=slot, value=value: legacy.text_with_slot(match, slot, value))
        for index, (slot, value) in mapping.items()
    }
    return legacy.rewrite_by_index(svg, replacements)


def _insert_icon_into_group(svg: str, group_id: str, icon_markup: str) -> str:
    """Insert a semantic Lucide icon before the closing tag of one SVG group."""
    match = re.search(rf'<g\b(?=[^>]*\bid="{re.escape(group_id)}")[^>]*>', svg)
    if match is None:
        raise ValueError(f"Missing SVG group {group_id}")
    depth = 1
    token_re = re.compile(r'<g\b[^>]*>|</g>')
    for token in token_re.finditer(svg, match.end()):
        if token.group().startswith('</g'):
            depth -= 1
            if depth == 0:
                return svg[: token.start()] + icon_markup + svg[token.start() :]
        else:
            depth += 1
    raise ValueError(f"Unclosed SVG group {group_id}")


def _remove_group_by_id(svg: str, group_id: str) -> str:
    """Remove one complete SVG group, including nested groups, by id."""
    match = re.search(rf'<g\b(?=[^>]*\bid="{re.escape(group_id)}")[^>]*>', svg)
    if match is None:
        return svg
    depth = 1
    token_re = re.compile(r'<g\b[^>]*>|</g>')
    for token in token_re.finditer(svg, match.end()):
        if token.group().startswith('</g'):
            depth -= 1
            if depth == 0:
                return svg[: match.start()] + svg[token.end() :]
        else:
            depth += 1
    raise ValueError(f"Unclosed SVG group {group_id}")


def add_content_source_20_lucide_icons(root: Path, body_payload: dict[str, Any]) -> None:
    """Put centered Lucide icons inside the four card circles on source slide 20."""
    icon_specs = [
        ("shape-13", "graduation-cap", 214.10, 156.89, "#912C8D"),
        ("shape-17", "calendar-days", 496.73, 607.01, "#7561D6"),
        ("shape-21", "user-round", 779.80, 157.35, "#68A4C6"),
        ("shape-25", "book-open", 1059.39, 607.01, "#6A69B6"),
    ]
    # These are the source artwork's placeholder/legacy icon groups. Remove
    # them first so the four cards use one consistent Lucide treatment.
    legacy_group_ids = ["shape-97", "shape-58", "shape-68", "shape-77"]
    files = [
        root / "body_variants" / "content_source_20.svg",
        root / "page_variants" / "04_content_source_20.svg",
    ]
    for path in files:
        if not path.is_file():
            continue
        svg = path.read_text(encoding="utf-8")
        for legacy_group_id in legacy_group_ids:
            svg = _remove_group_by_id(svg, legacy_group_id)
        if 'data-icon="lucide/' not in svg:
            for group_id, icon_name, center_x, center_y, _color in icon_specs:
                size = 25.0
                icon = (
                    f'<use data-icon="lucide/{icon_name}" '
                    f'x="{center_x - size / 2:.2f}" y="{center_y - size / 2:.2f}" '
                    f'width="{size:.2f}" height="{size:.2f}" '
                    'fill="#FFFFFF" stroke-width="1.8"/>'
                )
                svg = _insert_icon_into_group(svg, group_id, icon)
        path.write_text(svg, encoding="utf-8")

    for variant in body_payload.get("variants", []):
        if variant.get("variant_id") == "content_source_20":
            variant["decorative_icons"] = [
                {
                    "library": "lucide",
                    "icon": icon_name,
                    "center": {"x": center_x, "y": center_y},
                    "color": "#FFFFFF",
                }
                for _group_id, icon_name, center_x, center_y, _color in icon_specs
            ]


def abstract_cover(source_slide: int) -> str:
    svg = legacy.normalize_root_assets(legacy.source_svg(SOURCE, source_slide))
    if source_slide in {1, 2}:
        mapping = {
            1: ("COVER_SUBTITLE", "副标题"),
            2: ("COVER_TITLE", "主标题"),
            3: ("COVER_META", "汇报人：姓名    日期：2025年1月"),
        }
    else:
        mapping = {
            1: ("PRESENTER", "汇报人：姓名"),
            2: ("DATE", "日期：2025年1月"),
            3: ("COVER_TITLE", "主标题"),
            4: ("COVER_SUBTITLE", "副标题"),
        }
    return replace_texts(svg, mapping)


def abstract_toc(source_slide: int) -> str:
    if source_slide == 4:
        # The source's numbered titles are two-tspan text nodes without the
        # source text-box metadata.  Recreate them as one editable slot with
        # the measured source box so native PPTX validation sees the real
        # title/description separation.
        svg = legacy.normalize_root_assets(legacy.source_svg(SOURCE, source_slide))
        title_boxes = {
            3: ("TOC_ITEM_01", "01 \u7ae0\u8282\u6807\u9898", (142.73, 303.05, 337.8, 50)),
            4: ("TOC_ITEM_02", "02 \u7ae0\u8282\u6807\u9898", (142.73, 397.0, 337.8, 50)),
            5: ("TOC_ITEM_03", "03 \u7ae0\u8282\u6807\u9898", (616.9, 303.05, 337.8, 50)),
            6: ("TOC_ITEM_04", "04 \u7ae0\u8282\u6807\u9898", (616.9, 397.0, 337.8, 50)),
        }
        svg = legacy.rewrite_by_index(
            svg,
            {
                index: (lambda match, slot=slot, value=value, box=box: legacy.text_with_slot(
                    match, slot, value, box=box
                ))
                for index, (slot, value, box) in title_boxes.items()
            },
        )
        return replace_texts(
            svg,
            {
                1: ("TOC_TITLE", "\u76ee\u5f55"),
                2: ("TOC_RAIL_LABEL", "CONTENTS"),
                7: ("TOC_ITEM_01_DESC", "\u7ae0\u8282\u8bf4\u660e"),
                8: ("TOC_ITEM_02_DESC", "\u7ae0\u8282\u8bf4\u660e"),
                9: ("TOC_ITEM_03_DESC", "\u7ae0\u8282\u8bf4\u660e"),
                10: ("TOC_ITEM_04_DESC", "\u7ae0\u8282\u8bf4\u660e"),
            },
        )
        mapping = {
            1: ("TOC_TITLE", "目录"),
            2: ("TOC_RAIL_LABEL", "CONTENTS"),
            3: ("TOC_ITEM_01", "01 章节标题"),
            4: ("TOC_ITEM_02", "02 章节标题"),
            5: ("TOC_ITEM_03", "03 章节标题"),
            6: ("TOC_ITEM_04", "04 章节标题"),
            7: ("TOC_ITEM_01_DESC", "章节说明"),
            8: ("TOC_ITEM_02_DESC", "章节说明"),
            9: ("TOC_ITEM_03_DESC", "章节说明"),
            10: ("TOC_ITEM_04_DESC", "章节说明"),
        }
    elif source_slide == 5:
        mapping = {
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
    else:
        mapping = {
            1: ("TOC_ITEM_01_NUMBER", "01"),
            2: ("TOC_ITEM_02_NUMBER", "02"),
            3: ("TOC_ITEM_03_NUMBER", "03"),
            4: ("TOC_ITEM_04_NUMBER", "04"),
            5: ("TOC_ITEM_01_TITLE", "章节标题"),
            6: ("TOC_ITEM_01_DESC", "章节说明"),
            7: ("TOC_ITEM_02_TITLE", "章节标题"),
            8: ("TOC_ITEM_02_DESC", "章节说明"),
            9: ("TOC_ITEM_03_TITLE", "章节标题"),
            10: ("TOC_ITEM_03_DESC", "章节说明"),
            11: ("TOC_ITEM_04_TITLE", "章节标题"),
            12: ("TOC_ITEM_04_DESC", "章节说明"),
            13: ("TOC_RAIL_LABEL", "CONTENTS"),
            14: ("TOC_TITLE", "目录"),
            15: ("TOC_YEAR", "2025"),
        }
    return replace_texts(legacy.normalize_root_assets(legacy.source_svg(SOURCE, source_slide)), mapping)


def abstract_transition(source_slide: int) -> str:
    mapping = {
        1: ("TRANSITION_TITLE", "章节标题"),
        2: ("TRANSITION_DESC", "章节说明"),
        3: ("TRANSITION_NUMBER", f"{source_slide - 6:02d}"),
    }
    # Slides 07-10 are one series, not four independent transition designs.
    # Use slide 07 as the shared visual master and vary only the sequence
    # number and the precomposed photo preset.
    svg = replace_texts(legacy.normalize_root_assets(legacy.source_svg(SOURCE, 7)), mapping)

    # The source deck applies the section photo as a group fill to nine
    # independent diamond-shaped paths. The generic SVG distiller preserves
    # those paths but cannot carry a group-level blipFill. A transparent PNG
    # generated from the same source photo and mask keeps the source geometry
    # in native PPTX while avoiding unsupported SVG clipPath semantics.
    image = (
        f'<image href="assets/transition_photo_{source_slide:02d}.png" '
        'x="0" y="0" width="1280" height="720" preserveAspectRatio="none"/>'
    )
    svg = svg.replace('<g id="shape-32"', image + '<g id="shape-32"', 1)
    return svg


def abstract_ending(source_slide: int) -> str:
    if source_slide == 27:
        mapping = {
            1: ("CLOSING_SUBTITLE", "感谢聆听"),
            2: ("CLOSING_TITLE", "谢谢，敬请批评指正！"),
            3: ("ENDING_META", "汇报人：姓名    日期：2025年1月"),
        }
    elif source_slide == 28:
        mapping = {
            1: ("ENDING_META", "汇报人：姓名    日期：2025年1月"),
            2: ("CLOSING_SUBTITLE", "感谢聆听"),
            3: ("CLOSING_TITLE", "谢谢，敬请批评指正！"),
        }
    else:
        mapping = {
            1: ("PRESENTER", "汇报人：姓名"),
            2: ("DATE", "日期：2025年1月"),
            3: ("CLOSING_TITLE", "谢谢！"),
            4: ("CLOSING_SUBTITLE", "敬请批评指正。"),
        }
    return replace_texts(legacy.normalize_root_assets(legacy.source_svg(SOURCE, source_slide)), mapping)


def functional_slots(svg: str) -> list[str]:
    return legacy.extract_slots(svg)


def build_functional_variants(root: Path) -> dict[str, Any]:
    functional_dir = root / "functional_variants"
    functional_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, Any] = {}
    for group, spec in FUNCTIONAL_GROUPS.items():
        group_dir = functional_dir / group
        group_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for item in spec["variants"]:
            slide = int(item["source_slide"])
            if group == "cover":
                svg = abstract_cover(slide)
            elif group == "toc":
                svg = abstract_toc(slide)
            elif group == "transition":
                svg = abstract_transition(slide)
            else:
                svg = abstract_ending(slide)
            variant_id = str(item["variant_id"])
            filename = f"{variant_id}.svg"
            svg = mark_variant(svg, group, variant_id, slide)
            nested_svg = svg.replace('href="assets/', 'href="../../assets/')
            target = group_dir / filename
            target.write_text(nested_svg, encoding="utf-8")
            item_payload = {
                **item,
                "role": group,
                "preview_svg": f"functional_variants/{group}/{filename}",
                "slots": functional_slots(nested_svg),
                "selection": {"mode": "explicit_variant_or_group_default", "group": group},
            }
            if group == "transition":
                item_payload.update(
                    {
                        "series_id": "transition_series",
                        "series_index": slide - 6,
                        "variation_values": {
                            "TRANSITION_NUMBER": f"{slide - 6:02d}",
                            "TRANSITION_PHOTO": f"transition_photo_{slide:02d}.png",
                        },
                        "variation_scope": ["TRANSITION_NUMBER", "TRANSITION_PHOTO"],
                    }
                )
            items.append(item_payload)
            if item is spec["variants"][0]:
                (root / spec["root_svg"]).write_text(svg, encoding="utf-8")
        groups[group] = {
            "role": group,
            "root_svg": spec["root_svg"],
            "selection_policy": "select_one_series_preset" if group == "transition" else "select_one_source_faithful_variant",
            "variant_model": spec.get("variant_model", "source_page_variants"),
            **({"series_id": spec["series_id"], "shared_layout": spec["shared_layout"], "variation_dimensions": spec["variation_dimensions"]} if group == "transition" else {}),
            "default_variant": items[0]["variant_id"],
            "variants": items,
        }
    return groups


def slot_detail(slot: str, max_lines: int = 1, max_chars: int = 24) -> dict[str, Any]:
    kind = "image" if slot.startswith("IMAGE_") or slot.endswith("_IMAGE") else "text"
    detail: dict[str, Any] = {"slot_id": slot, "role": slot.lower(), "kind": kind}
    if kind == "text":
        detail.update({"max_lines": max_lines, "max_chars_per_line": max_chars})
    return detail


def update_contracts(root: Path, groups: dict[str, Any], body_payload: dict[str, Any]) -> None:
    body_ids = list(body_payload["content_variants"])
    pages = [
        ("01_cover", "cover", "01_cover.svg", 1, "cover", list(groups["cover"]["variants"])),
        ("02_toc", "toc", "02_toc.svg", 4, "toc", list(groups["toc"]["variants"])),
        ("03_transition", "transition", "03_transition.svg", 7, "transition", list(groups["transition"]["variants"])),
        ("04_content", "content", "04_content.svg", 18, "content", []),
        ("05_ending", "ending", "05_ending.svg", 27, "ending", list(groups["ending"]["variants"])),
    ]
    functional_meta = {
        "schema_version": "easyslides.functional_page_variants.v1",
        "template_id": TEMPLATE_ID,
        "selection_policy": "select_one_variant_per_functional_role",
        "selection_rule": "Generation must choose exactly one variant from each requested functional group; no source page is silently treated as the only canonical form.",
        "series_rule": "Transition slides 07-10 share one layout; select one transition series preset whose only differences are sequence number and photo.",
        "groups": groups,
        "content_page": {"role": "content", "body_variants": body_ids, "selection_policy": "select_one_source_faithful_body_variant"},
    }
    write_json(root / "functional_page_variants.json", functional_meta)

    slot_models: dict[str, list[dict[str, Any]]] = {}
    for group, info in groups.items():
        slots: list[str] = []
        for variant in info["variants"]:
            for slot in variant["slots"]:
                if slot not in slots:
                    slots.append(slot)
        slot_models[group] = [slot_detail(slot, max_lines=2 if any(k in slot for k in ("DESC", "SUBTITLE", "META")) else 1) for slot in slots]
    content_slots: list[str] = []
    for variant in body_payload["variants"]:
        for slot in variant["slots"]:
            if slot not in content_slots:
                content_slots.append(slot)
    slot_models["content"] = [slot_detail(slot, max_lines=2 if any(k in slot for k in ("BODY", "TEXT", "EVIDENCE")) else 1) for slot in content_slots]

    layout_pages = []
    for page_id, role, svg, source_slide, slot_model, variants in pages:
        item: dict[str, Any] = {
            "id": page_id,
            "page_id": role,
            "layout_id": role,
            "svg": svg,
            "role": role,
            "page_type": role,
            "story_role": role,
            "role_fit": [role],
            "slot_model": slot_model,
            "source_slide": source_slide,
            "density_score": 3,
        }
        if role == "content":
            item["body_variants"] = body_ids
            item["selection_policy"] = "select_one_source_faithful_body_variant"
        else:
            item["functional_variant_group"] = role
            item["functional_variants"] = [v["variant_id"] for v in variants]
            item["variant_model"] = "series_presets" if role == "transition" else "source_page_variants"
            if role == "transition":
                item["series_id"] = "transition_series"
                item["variation_dimensions"] = ["TRANSITION_NUMBER", "TRANSITION_PHOTO"]
                item["shared_layout"] = svg
            item["selection_policy"] = "select_one_series_preset" if role == "transition" else "select_one_source_faithful_variant"
        layout_pages.append(item)

    layouts_payload = {
        "schema_version": "easyslides.thu_speech.layouts.v1",
        "template_id": TEMPLATE_ID,
        "replication_mode": "slot_guided_mirror",
        "global_contract": {
            "replication_mode": "slot_guided_mirror",
            "source_geometry_policy": "preserve_fixed_geometry_replace_declared_slots",
            "functional_page_policy": "four_functional_roles_with_transition_series",
            "functional_roles": ["cover", "toc", "transition", "ending"],
            "content_role": "content",
            "series_policy": {
                "transition": {
                    "series_id": "transition_series",
                    "shared_layout": "03_transition.svg",
                    "variation_dimensions": ["TRANSITION_NUMBER", "TRANSITION_PHOTO"],
                    "rule": "Slides 07-10 share one transition layout; only sequence number and photo differ.",
                }
            },
        },
        "canvas": {"width": 1280, "height": 720, "format": "ppt169"},
        "style_system": TEMPLATE_ID,
        "colors": {"primary": "#912C8D", "accent2": "#7561D6", "accent3": "#68A4C6", "accent4": "#6A69B6", "accent5": "#5199EA", "accent6": "#5B84D8"},
        "fonts": {"majorLatin": "等线 Light", "minorLatin": "等线"},
        "pages": layout_pages,
        "layouts": layout_pages,
        "shells": [{"shell_id": role, "page_id": page_id, "svg": svg, "role": role, "source_slide": source_slide, "variant_group": role if role != "content" else None} for page_id, role, svg, source_slide, _, _ in pages],
        "body_variants": body_ids,
        "functional_page_variant_groups": list(groups),
        "slot_models": slot_models,
        "text_fit_policy": {
            "schema_version": "easyslides.template_text_fit_policy.v1",
            "overflow_strategy_order": ["compress_text_to_capacity", "choose_lower_density_layout", "split_across_slides", "shrink_font_with_floor"],
            "allowed_overflow_actions": ["split", "truncate"],
            "role_defaults": {},
        },
    }
    role_defaults = legacy.fit_defaults()
    for model_slots in slot_models.values():
        for detail in model_slots:
            role = str(detail["role"])
            role_defaults.setdefault(
                role,
                {
                    "default_font_size_px": 18,
                    "min_font_size_px": 14,
                    "line_height": 1.2,
                    "max_chars_per_line_zh": detail.get("max_chars_per_line", 22),
                    "overflow_action": "split" if detail.get("max_lines", 1) > 1 else "truncate",
                    "max_lines": detail.get("max_lines", 1),
                },
            )
    layouts_payload["text_fit_policy"]["role_defaults"] = role_defaults
    write_json(root / "layouts.json", layouts_payload)

    slot_contracts = {
        "schema_version": "easyslides.template_slot_contracts.v1",
        "template_id": TEMPLATE_ID,
        "replacement_rule": "replace_declared_slots_preserve_template_geometry",
        "variant_selection": "functional_page_variants.json",
        "layouts": [
            {
                "layout_id": f"ASDV-S{index:02d}",
                "page_id": page_id,
                "svg_path": f"templates/layouts/{TEMPLATE_ID}/{svg}",
                "role_fit": [role],
                "slot_model": slot_model,
                "slots": [item["slot_id"] for item in slot_models[slot_model]],
                "text_slots": [item["slot_id"] for item in slot_models[slot_model] if item["kind"] == "text"],
                "image_slots": [item["slot_id"] for item in slot_models[slot_model] if item["kind"] == "image"],
                "functional_variants": [v["variant_id"] for v in variants],
                "body_variants": body_ids if role == "content" else [],
            }
            for index, (page_id, role, svg, _source_slide, slot_model, variants) in enumerate(pages, start=1)
        ],
    }
    write_json(root / "slot_contracts.json", slot_contracts)

    template_payload = json.loads((root / "template.json").read_text(encoding="utf-8"))
    template_payload.update(
        {
            "template_id": TEMPLATE_ID,
            "display_name": "THU Speech",
            "template_classification": "development",
            "official_template": False,
            "archive_policy": "separate_development_asset",
            "roles": ["content", "cover", "ending", "toc", "transition"],
            "layout_count": 5,
            "functional_page_variant_policy": "select_one_variant_per_functional_role",
            "functional_page_variant_groups": list(groups),
            "functional_page_series": {
                "transition": {
                    "series_id": "transition_series",
                    "shared_layout": "03_transition.svg",
                    "variation_dimensions": ["TRANSITION_NUMBER", "TRANSITION_PHOTO"],
                }
            },
            "body_variant_policy": "select_one_source_faithful_body_variant",
            "source_policy": {"raw_pptx_in_catalog": False, "raw_pptx_required_at_runtime": False, "contains_local_paths": False, "private_assets_role": "build_reference_only", "publishable_contract_sidecars": True},
        }
    )
    write_json(root / "template.json", template_payload)

    catalog_pages = []
    for page_id, role, svg, source_slide, _slot_model, variants in pages:
        catalog_pages.append(
            {
                "id": page_id,
                "source_slide": source_slide,
                "story_role": role,
                "role_fit": [role],
                "selection_policy": "select_one_source_faithful_variant" if role != "content" else "select_one_source_faithful_body_variant",
                "functional_variant_group": role if role != "content" else None,
                "functional_variants": [v["variant_id"] for v in variants],
                "variant_model": "series_presets" if role == "transition" else ("source_page_variants" if role != "content" else "body_variants"),
                "series_id": "transition_series" if role == "transition" else None,
                "body_variants": body_ids if role == "content" else [],
            }
        )
    write_json(
        root / "page_catalog.json",
        {"schema_version": "easyslides.page_catalog.v1", "template_id": TEMPLATE_ID, "selection_policy": "functional_role_variant_then_body_variant", "pages": catalog_pages, "functional_page_variants": list(groups), "body_variants": body_ids, "source_pages": list(range(1, 30))},
    )

    # The first draft was created by the generic distiller and still carried a
    # chapter shell. Reconcile its sidecar contracts with the five active
    # roles in this rebuild so no stale 03_chapter.svg declaration survives.
    page_specs = [
        {"id": page_id, "svg": svg, "source_slide": source_slide, "story_role": role}
        for page_id, role, svg, source_slide, _slot_model, _variants in pages
    ]
    geometry_path = root / "geometry_contract.json"
    if geometry_path.is_file():
        geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
        old_geometry = {item.get("id"): item for item in geometry.get("pages", [])}
        geometry_pages = []
        for spec in page_specs:
            item = dict(old_geometry.get(spec["id"], old_geometry.get("03_chapter", {})))
            item.update(spec)
            geometry_pages.append(item)
        geometry.update({"template_id": TEMPLATE_ID, "pages": geometry_pages})
        write_json(geometry_path, geometry)

    roster_path = root / "layout_roster.json"
    if roster_path.is_file():
        roster = json.loads(roster_path.read_text(encoding="utf-8"))
        old_layouts = {item.get("page_id"): item for item in roster.get("layouts", [])}
        roster_layouts = []
        for index, spec in enumerate(page_specs, start=1):
            item = dict(old_layouts.get(spec["id"], old_layouts.get("03_chapter", {})))
            item.update(
                {
                    "layout_id": f"ASDV-S{index:02d}",
                    "source_slide": spec["source_slide"],
                    "page_id": spec["id"],
                    "name": f"{index:02d} {spec['story_role']}",
                    "role_fit": [spec["story_role"]],
                    "page_archetype": spec["story_role"],
                    "svg_path": f"tmp/{TEMPLATE_ID}/{spec['svg']}",
                    "layout_contract": f"asdv_s{index:02d}_{spec['id']}_contract",
                }
            )
            roster_layouts.append(item)
        roster.update({"template_id": TEMPLATE_ID, "layouts": roster_layouts})
        write_json(roster_path, roster)

    story_path = root / "story_structure.json"
    if story_path.is_file():
        story = json.loads(story_path.read_text(encoding="utf-8"))
        roles = [spec["story_role"] for spec in page_specs]
        story.update(
            {
                "template_id": TEMPLATE_ID,
                "canonical_shells": roles,
                "shell_profile": {
                    **story.get("shell_profile", {}),
                    "active_shell_roles": roles,
                    "active_shell_count": len(roles),
                    "optional_shell_roles": ["toc", "transition"],
                    "toc_present": "toc" in roles,
                    "chapter_present": False,
                    "transition_present": "transition" in roles,
                },
                "recommended_flow": [
                    {"story_role": spec["story_role"], "page_id": spec["id"], "source_slide": spec["source_slide"]}
                    for spec in page_specs
                ],
            }
        )
        write_json(story_path, story)

    # Keep the source roster, but make the new role classification explicit.
    roster = json.loads((root / "source_page_roster.json").read_text(encoding="utf-8"))
    role_by_slide = {int(v["source_slide"]): group for group, info in groups.items() for v in info["variants"]}
    for page in roster.get("pages", []):
        slide = int(page.get("source_slide", 0))
        if slide in role_by_slide:
            page["source_role"] = role_by_slide[slide]
            page["functional_group"] = role_by_slide[slide]
            page["preserved_as"] = "functional_page_variant"
        elif 11 <= slide <= 26 and slide != 22:
            page["source_role"] = "content"
            page["preserved_as"] = "body_variant"
        elif slide == 22:
            page["excluded_from_template"] = True
            page["exclusion_reason"] = "user_removed_slide_22"
    roster.update(
        {
            "template_id": TEMPLATE_ID,
            "functional_page_variant_groups": list(groups),
            "active_shell_roles": ["cover", "toc", "transition", "content", "ending"],
            "optional_shell_roles": [],
            "required_shell_roles": ["cover", "toc", "transition", "content", "ending"],
            "shell_profile": {"policy": "functional_role_variant_selection", "active_shell_count": 5, "functional_roles": ["cover", "toc", "transition", "ending"], "content_role": "content"},
        }
    )
    write_json(root / "source_page_roster.json", roster)

    design_spec = f"""# {TEMPLATE_ID}\n\nThis is a source-faithful development template rebuilt from the 29-slide source PPTX.\n\n## Functional-page selection\n\nThe source deck has four functional page roles with variants:\n\n- cover: source slides 1-3\n- toc: source slides 4-6\n- transition: source slides 7-10\n- ending: source slides 27-29\n\nGeneration selects one explicit variant from each requested role. No source page is promoted as the only canonical form. See `functional_page_variants.json`.\n\nContent slides 11-21 and 23-26 remain source-faithful body variants under `04_content.svg`. Source slide 22 is excluded per project review.\n\n## Fidelity rules\n\nPreserve source photo crops, purple/blue palette, title treatment, rotated labels, card geometry, and page-specific cover/ending compositions. Do not redesign a functional page into a generic card layout.\n\n## Selection and overflow\n\nChoose a functional variant first, then bind declared slots. For content, choose a body variant after the shared header. If text does not fit, select another source page variant or split the material before shrinking typography.\n"""
    (root / "design_spec.md").write_text(design_spec, encoding="utf-8")
    spec_path = root / "design_spec.md"
    spec_text = spec_path.read_text(encoding="utf-8")
    spec_text = spec_text.replace(
        "- transition: source slides 7-10\n",
        "- transition: source slides 7-10, represented as one shared transition series\n",
    )
    spec_text = spec_text.replace(
        "Generation selects one explicit variant from each requested role.",
        "Slides 07-10 share one transition layout; only the sequence number and photo preset vary.\n\nGeneration selects one explicit variant from each requested role.",
    )
    spec_path.write_text(spec_text, encoding="utf-8")
    (root / "rules.md").write_text("Use functional_page_variants.json to select one source-faithful variant per functional role. Use body_variants.json for content pages. Preserve source geometry and do not silently merge variant pages.\n\nSlides 07-10 are one transition series; only the sequence number and photo preset vary.\n", encoding="utf-8")


def main() -> None:
    if not ROOT.is_dir() or not SOURCE.is_dir():
        raise FileNotFoundError(f"Expected distill output and source workspace: {ROOT}, {SOURCE}")
    legacy.TEMPLATE_ID = TEMPLATE_ID
    build_transition_photo_assets(ROOT)
    groups = build_functional_variants(ROOT)
    # Build the stable content header from the source content page selected by
    # the existing body-variant distillation, then materialize all body forms.
    content_header = legacy.abstract_content_header(legacy.normalize_root_assets(legacy.source_svg(SOURCE, 18)))
    (ROOT / "04_content.svg").write_text(content_header, encoding="utf-8")
    _dev_ids, previews, _source_by_id, _page_by_id = legacy.copy_development_variants(ROOT, SOURCE)
    body_payload = legacy.body_variants_v2(ROOT, SOURCE, previews)
    add_content_source_20_lucide_icons(ROOT, body_payload)
    write_json(ROOT / "body_variants.json", body_payload)
    write_json(ROOT / "component_catalog.json", legacy.component_catalog_v2())
    update_contracts(ROOT, groups, body_payload)
    print(json.dumps({"template_id": TEMPLATE_ID, "functional_groups": {group: len(info["variants"]) for group, info in groups.items()}, "content_variants": len(body_payload["content_variants"]), "root": str(ROOT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
