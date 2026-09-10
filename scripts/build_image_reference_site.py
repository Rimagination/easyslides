"""Package the canonical image-reference library for the static gallery."""
import argparse
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "templates" / "image_references"


def build(output, source=LIBRARY):
    entries = json.loads((source / "registry.json").read_text(encoding="utf-8"))["templates"]
    public = []
    seen = set()
    assets = []
    for entry in entries:
        template_id = entry["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", template_id) or template_id in seen:
            raise ValueError(f"Invalid or duplicate template ID: {template_id}")
        seen.add(template_id)
        item = {key: entry[key] for key in ("id", "name", "style_summary", "slide_count", "version", "image", "preview")}
        for key in ("image", "preview"):
            name = item[key]
            if not re.fullmatch(r"[a-z0-9_]+\.(png|jpg)", name):
                raise ValueError(f"Invalid asset name: {name}")
            asset = source / name
            if not asset.is_file():
                raise FileNotFoundError(asset)
            assets.append(asset)
        public.append(item)
    output.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        shutil.copyfile(asset, output / asset.name)
    payload = json.dumps(public, ensure_ascii=True, indent=2)
    (output / "catalog.js").write_text("window.imageReferenceTemplates = " + payload + ";\n", encoding="utf-8")
    return public


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site" / "assets" / "image-references")
    args = parser.parse_args()
    print(f"Packaged {len(build(args.output))} image-reference templates into {args.output}")
