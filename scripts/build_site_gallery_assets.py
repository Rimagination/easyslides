"""Build small gallery thumbnails; full-size slides and reference sheets stay intact."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "site" / "assets"


def thumbnail(source: Path, target: Path, width: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        image.thumbnail((width, round(width * image.height / image.width)), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=87, method=6)


def build() -> list[Path]:
    outputs = []
    templates = json.loads((ROOT / "templates/template_policy.json").read_text(encoding="utf-8"))
    directory = ASSETS / "native-templates"
    directory.mkdir(parents=True, exist_ok=True)
    for template_id in templates["official_template_ids"]:
        filename = f"template-{template_id.replace('_', '-')}.webp"
        target = directory / filename
        shutil.copyfile(ROOT / "assets/readme/previews" / filename, target)
        outputs.append(target)
    for name in ("academic-classic", "academic-scqa"):
        target = directory / f"template-{name}.png"
        shutil.copyfile(ROOT / "assets/readme" / target.name, target)
        outputs.append(target)
    for index in range(1, 10):
        target = ASSETS / "case-previews" / f"work-{index:02d}.webp"
        thumbnail(ASSETS / "slides" / f"work-{index:02d}" / "slide-01.jpg", target, 900)
        outputs.append(target)
    references = ROOT / "templates/image_references"
    registry = json.loads((references / "registry.json").read_text(encoding="utf-8"))
    for entry in registry["templates"]:
        target = ASSETS / "style-previews" / f"{entry['id']}.webp"
        thumbnail(references / entry["preview"], target, 640)
        outputs.append(target)
    return outputs


if __name__ == "__main__":
    outputs = build()
    print(json.dumps({"files": len(outputs), "bytes": sum(path.stat().st_size for path in outputs)}, indent=2))
