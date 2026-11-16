#!/usr/bin/env python3
"""Package the shared EasySlides runtime for Qoder's Plugin ZIP importer."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

try:
    from scripts.build_plugin_bundle import ROOT, build_bundle
except ModuleNotFoundError:  # direct CLI invocation
    from build_plugin_bundle import ROOT, build_bundle


def build_qoder_plugin(output_dir: Path, archive_path: Path) -> dict[str, object]:
    output_dir = output_dir.resolve()
    archive_path = archive_path.resolve()
    if output_dir.name != "easyslides":
        raise ValueError("Qoder plugin directory must be named easyslides")
    if archive_path.suffix.lower() != ".zip":
        raise ValueError("Qoder archive must use the .zip extension")
    if archive_path.is_relative_to(output_dir):
        raise ValueError("ZIP must be outside the plugin directory")
    if archive_path.exists():
        raise FileExistsError(f"Archive already exists; choose a new path: {archive_path}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_bundle(output_dir, host="qoder")
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir).as_posix())
    return {
        **manifest,
        "plugin_dir": str(output_dir),
        "archive": str(archive_path),
        "archive_size_bytes": archive_path.stat().st_size,
    }


def main() -> int:
    version = json.loads((ROOT / ".qoder-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build/qoder-plugin/easyslides")
    parser.add_argument("--zip", type=Path, default=ROOT / f"build/easyslides-qoder-{version}.zip")
    args = parser.parse_args()
    try:
        result = build_qoder_plugin(args.out, args.zip)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
