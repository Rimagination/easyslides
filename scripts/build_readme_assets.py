"""Build lightweight README previews from existing, unchanged project assets.

Run from any directory with Python, Pillow and CairoSVG. Full-size sources stay
behind image links; only the WebP derivatives are embedded in the README.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "readme"
PREVIEWS = ASSETS / "previews"


def preview(source: Path, name: str, width: int, quality: int = 84) -> Path:
    target = PREVIEWS / f"{name}.webp"
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        if image.width > width:
            height = round(image.height * width / image.width)
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)
    return target


def template_cover(template_id: str, subtitle: str) -> Path:
    import cairosvg

    source = ROOT / "templates" / "layouts" / template_id / "01_cover.svg"
    svg = ET.parse(source).getroot()
    values = {
        "TITLE": "学术论文汇报",
        "SUBTITLE": subtitle,
        "LOGO": "EasySlides",
        "AUTHOR": "汇报人：示例",
        "PRESENTER": "汇报人：示例",
        "ADVISOR": "",
        "INSTITUTION": "汇报单位：示例",
        "AFFILIATION": "汇报单位：示例",
        "DATE": "日期：示例",
        "FOOTER": "",
    }
    for node in svg.iter():
        if node.tag.rsplit("}", 1)[-1] != "text":
            continue
        slot = node.get("data-slot") or (node.text or "").strip("{}")
        if slot in values:
            node.text = values[slot]
    target = ASSETS / f"template-{template_id.replace('_', '-')}.png"
    cairosvg.svg2png(
        bytestring=ET.tostring(svg), write_to=str(target),
        output_width=1600, output_height=900,
    )
    return target


def discipline_collage() -> Path:
    directory = ROOT / "templates" / "layouts" / "academic_general" / "cover_banners"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["assets"]
    assert len(entries) == manifest["asset_count"] == 14
    assert [item["discipline_code"] for item in entries] == [f"{i:02d}" for i in range(1, 15)]
    width, height, gap = 1536, 512, 12
    board = Image.new("RGB", (width * 2 + gap, height * 7 + gap * 6), "white")
    for index, entry in enumerate(entries):
        source = directory / entry["file"]
        with Image.open(source) as image:
            tile = ImageOps.fit(image.convert("RGB"), (width, height), Image.Resampling.LANCZOS)
            board.paste(tile, ((index % 2) * (width + gap), (index // 2) * (height + gap)))
    target = ASSETS / "discipline-themes.jpg"
    board.save(target, "JPEG", quality=91, optimize=True, progressive=True)
    preview(target, "discipline-themes", 960, quality=82)
    return target


def build() -> list[Path]:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    outputs = [discipline_collage()]
    sources = [
        (ASSETS / "native-editable.png", "native-editable", 960, 88),
        (ROOT / "site/assets/slides/work-06/slide-06.jpg", "image-rebuild", 960, 88),
        (ASSETS / "native-method.png", "native-method", 1280, 88),
    ]
    for name in ("academic-blue", "academic-purple", "academic-green", "technology-blue"):
        sources.append((ASSETS / f"theme-{name}.jpg", f"theme-{name}", 720, 84))
    template_sources = {
        "academic_general": ROOT / "site/assets/slides/work-09/slide-09.jpg",
        "academic_classic": template_cover("academic_classic", "研究背景 · 方法 · 结果 · 讨论"),
        "academic_scqa": template_cover("academic_scqa", "情境 · 冲突 · 问题 · 回答"),
        "defense_leftnav": ROOT / "site/assets/slides/work-02/slide-08.jpg",
        "defense_topnav": ROOT / "site/assets/slides/work-03/slide-08.jpg",
        "literature_minimal": ROOT / "site/assets/slides/work-01/slide-08.jpg",
        "nsfc_defense": ROOT / "site/assets/slides/work-04/slide-05.jpg",
        "thu_speech": ROOT / "site/assets/slides/work-05/slide-08.jpg",
    }
    policy = json.loads((ROOT / "templates/template_policy.json").read_text(encoding="utf-8"))
    assert list(template_sources) == policy["official_template_ids"]
    for name, source in template_sources.items():
        sources.append((source, f"template-{name.replace('_', '-')}", 480, 88))
    references = ROOT / "templates" / "image_references"
    for name, source_name in (
        ("nsfc-green", "nsfc_green_preview.jpg"),
        ("nsfc-purple", "nsfc_purple_preview.jpg"),
        ("zdyf-blue", "rdp_blue_technology_preview.jpg"),
    ):
        sources.append((references / source_name, f"reference-{name}", 600, 86))
    for source, name, width, quality in sources:
        outputs.append(preview(source, name, width, quality))
    return outputs


if __name__ == "__main__":
    generated = build()
    previews = sorted(PREVIEWS.glob("*.webp"))
    print(json.dumps({
        "preview_count": len(previews),
        "preview_bytes": sum(path.stat().st_size for path in previews),
        "collage": "assets/readme/discipline-themes.jpg",
        "collage_bytes": (ASSETS / "discipline-themes.jpg").stat().st_size,
        "originals_preserved": True,
    }, indent=2))
