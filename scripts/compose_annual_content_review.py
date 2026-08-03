"""Compose the canonical content header with each annual-speech body variant.

This creates review-only SVGs. It intentionally does not modify the archived
template or its body-variant assets.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
NS = {"svg": SVG_NS}

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def rewrite_asset_hrefs(node: ET.Element) -> None:
    """Make asset paths relative to the generated SVG output directory."""

    for element in node.iter():
        for attr in ("href", f"{{{XLINK_NS}}}href"):
            value = element.get(attr)
            if value and value.startswith("assets/"):
                element.set(attr, f"../{value}")


def load_children(path: Path) -> tuple[ET.Element, list[ET.Element]]:
    tree = ET.parse(path)
    root = tree.getroot()
    return root, list(root)


def compose(header_path: Path, body_path: Path, output_path: Path, variant_id: str) -> None:
    header_root, header_children = load_children(header_path)
    body_root, body_children = load_children(body_path)

    composed = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "version": "1.1",
            "width": "1280",
            "height": "720",
            "viewBox": "0 0 1280 720",
            "data-template-shell": "annual_content_review",
            "data-variant-id": variant_id,
        },
    )

    # Body first, so the header can consistently sit above the body canvas.
    for child in body_children:
        cloned = copy.deepcopy(child)
        rewrite_asset_hrefs(cloned)
        composed.append(cloned)

    # The body SVG already owns the full-page white background and top mask.
    # Append only the canonical header group to avoid a duplicate page rect.
    header_group = next(
        (
            child
            for child in header_children
            if child.get("id") == "content-header"
        ),
        None,
    )
    if header_group is None:
        raise ValueError(f"Missing content-header group in {header_path}")
    # Keep the review SVG maximally compatible with native PPTX conversion:
    # some Office/PowerPoint combinations reorder a late top-level group when
    # the body also contains full-bleed images. The group itself is only a
    # semantic wrapper, so its three fixed header elements can safely be
    # emitted as same-level siblings in the original z-order.
    for child in header_group:
        cloned = copy.deepcopy(child)
        rewrite_asset_hrefs(cloned)
        child_id = cloned.get("id") or "element"
        static_wrapper = ET.Element(
            f"{{{SVG_NS}}}g",
            {"id": f"content-header-{child_id}", "data-pptx-fixed-chrome": "true"},
        )
        static_wrapper.append(cloned)
        composed.append(static_wrapper)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(composed).write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template_root", type=Path)
    parser.add_argument("review_root", type=Path)
    args = parser.parse_args()

    template_root = args.template_root.resolve()
    review_root = args.review_root.resolve()
    body_manifest = template_root / "body_variants.json"
    header_path = template_root / "04_content.svg"
    body_dir = template_root / "body_variants"
    output_dir = review_root / "svg_output"
    assets_src = template_root / "assets"
    assets_dst = review_root / "assets"

    manifest = json.loads(body_manifest.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    if assets_src.is_dir():
        shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)

    for index, variant in enumerate(manifest["variants"], start=1):
        variant_id = variant["variant_id"]
        body_name = Path(variant["preview_svg"]).name
        body_path = body_dir / body_name
        output_path = output_dir / f"{index:02d}_{variant_id}.svg"
        compose(header_path, body_path, output_path, variant_id)

    print(f"composed={len(manifest['variants'])}")
    print(f"output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
